# deploy/: dịch vụ nền tảng trên cụm kind `bigd`

Đề xuất triển khai, **chưa cài gì lên cụm**. Phiên bản và tài nguyên nằm trong
[`services.yaml`](services.yaml); `tests/deploy/` kiểm tra ghim phiên bản, requests/limits và
tổng tài nguyên. Secret không nằm trong repo: `make secrets` tạo từ `.env` (mẫu ở `.env.example`).

## Dịch vụ cả kỳ

CPU và RAM là requests (limits ở `services.yaml`); `values` = đã viết và render thử bằng
`helm template`, `ước lượng` = chốt khi tới tuần cài. Mọi image dưới đây đã kiểm manifest còn kéo được.

| Dịch vụ | Tuần | Chart (ghim) | Image (ghim) | CPU | RAM | Disk | Nguồn số |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Strimzi operator | 1 | `strimzi-kafka-operator` 1.3.0 | `strimzi/operator:1.3.0` | 0.2 | 384 MiB | 0 | values |
| Kafka KRaft, 1 node controller+broker, topic operator | 1 | CR `Kafka` + `KafkaNodePool` | `strimzi/kafka:1.3.0-kafka-4.2.2` | 1.1 | 3.25 GiB | 60 GiB | values |
| MinIO standalone | 1 | `minio` 5.4.0 | `pgsty/minio:RELEASE.2026-08-04T00-00-00Z`, `pgsty/mc:RELEASE.2026-10-18T00-00-00Z` | 0.25 | 1 GiB | 150 GiB | values |
| Iceberg REST catalog (Lakekeeper) + PostgreSQL | 1 | `lakekeeper` 0.12.0 (kèm `groundhog2k/postgres`) | `lakekeeper/catalog:v0.13.3`, `postgres:18.6` | 0.2 | 512 MiB | 5 GiB | values |
| MongoDB | 2 | `groundhog2k/mongodb` 0.8.4 | `mongo:8.3.13` | 0.25 | 1 GiB | 20 GiB | ước lượng |
| Redis (8.10 ≥ 6.2) | 2 | `groundhog2k/redis` 2.4.8 | `redis:8.10.2` | 0.1 | 256 MiB | 2 GiB | ước lượng |
| Spark Operator | 2 | `spark-operator` 2.5.2 | `kubeflow/spark-operator/controller:2.5.2` | 0.2 | 512 MiB | 0 | ước lượng |
| Airflow | 3 | `airflow` 1.22.0 | `apache/airflow:3.2.2`, `postgres:18.6` | 1.1 | 4 GiB | 5 GiB | ước lượng |
| Trino | 3 | `trino` 1.45.0 | `trinodb/trino:484` | 1.0 | 4 GiB | 0 | ước lượng |
| kube-prometheus-stack | 3 | `kube-prometheus-stack` 92.13.1 | Prometheus v3.15.0, Alertmanager v0.34.1, Operator v0.94.1, Grafana 13.2.4, node-exporter v1.12.1, kube-state-metrics v2.20.0 | 0.85 | 2 GiB | 10 GiB | ước lượng |
| **Tổng nền tảng** | | | | **5.25 / 12 luồng** | **16.9 GiB** | **252 GiB** | |

Tuần 1 (Kafka, MinIO, catalog): **1.75 CPU, 5.1 GiB RAM requests** (limits 5.5 CPU, 6.6 GiB), 215 GiB disk danh nghĩa.

### So với máy 12 luồng, 30 GB RAM

Dành 4 GiB cho OS và kind, còn khoảng 26 GiB cho workload. Spark chưa tính vào bảng trên;
ước lượng cho Spark: 2 job streaming (bronze, detect) khoảng 6.6 GiB, một lần batch 7 GiB
(driver 1 + 2 executor × 3), thí nghiệm scaling 14 GiB (driver 2 + 3 executor × 4). Collector và
Streamlit khoảng 1 GiB.

| Tình huống | RAM requests | Vừa 26 GiB? |
| --- | --- | --- |
| Tuần 1 (3 dịch vụ + operator) | 5.1 GiB | có |
| MVP tuần 2 (+ Mongo, Redis, Spark Operator, collector, 2 job streaming) | 14.5 GiB | có |
| Toàn bộ nền tảng + collector + 2 job streaming | 24.5 GiB | sát giới hạn |
| Như trên + một lần batch 7 GiB | 31.5 GiB | **không**: phải tắt Trino và 1 job streaming khi chạy batch |
| Thí nghiệm scaling 14 GiB | 23.9 GiB | có, nếu tắt Trino, Airflow và job streaming |

Vì vậy Trino (4 GiB) nên scale về 0 ngoài lúc truy vấn, và lịch chạy batch/scaling phải
báo trước cho cả nhóm. Đây là ước lượng từ giá trị chart và giả định executor, cần đo lại khi cài.

## Tuần 1: lệnh cài dự kiến (chờ duyệt)

Không lệnh nào dưới đây đã được chạy.

```bash
make helm-repos        # thêm repo chart vào cấu hình helm cục bộ
make render-core       # kiểm tra render, không đụng cụm
cp .env.example .env   # điền giá trị thật (không commit)
make deploy-core       # = deploy-storage, secrets, deploy-kafka, deploy-minio, deploy-catalog
```

Từng bước (đều có target riêng):

1. `deploy-storage`: tạo `~/bigd/data/{kafka,minio,catalog-postgres}` (0777) trên máy chủ rồi
   `kubectl apply` namespace `kafka`, `minio`, `iceberg`, StorageClass `bigd-data` và 3 PV hostPath
   trỏ `/bigd-data/...` (node kind mount `~/bigd/data` thành `/bigd-data`).
2. `secrets`: tạo `minio-credentials`, `catalog-postgres`, `catalog-encryption` từ `.env`.
3. `deploy-kafka`: `helm upgrade --install strimzi` (1.3.0) rồi `kubectl apply` CR Kafka và đợi Ready.
4. `deploy-minio`: `helm upgrade --install minio` (5.4.0); job sau cài tạo bucket
   `warehouse`, `checkpoints`, `models`.
5. `deploy-catalog`: `helm upgrade --install iceberg-catalog` (Lakekeeper 0.12.0 + PostgreSQL).

Địa chỉ trong cụm: Kafka `bigd-kafka-kafka-bootstrap.kafka.svc:9092` (plain, chưa xác thực),
MinIO `minio.minio.svc:9000`, catalog `iceberg-catalog-lakekeeper.iceberg.svc:8181`.

Sau khi cài còn hai việc thủ công, chưa nằm trong `make`: bootstrap Lakekeeper và tạo warehouse
trỏ bucket `warehouse` bằng API (cần khoá S3 của MinIO), sau đó cấu hình catalog `rest` trong image Spark.

## Điểm cần Minh quyết định

1. **MinIO**: `quay.io/minio/minio` và `quay.io/minio/mc` (mặc định của chart 5.4.0) không còn
   manifest, `docker.io/minio/minio` cũng không kéo được. Phương án đề xuất: chart chính thức của
   MinIO với image fork cộng đồng `pgsty/minio` (ghim tag; API S3 giống hệt; bên thứ ba duy trì,
   cần chấp nhận độ tin cậy). Khác: `bitnamilegacy/minio:2025.7.23` (đóng băng, không vá lỗi) hoặc đổi
   sang SeaweedFS (thay tên "MinIO" trong tài liệu và policy).
2. **Bitnami**: chart `bitnami/*` chỉ có tag `latest` (không ghim được); `bitnamilegacy/*` đóng băng.
   Đề xuất bỏ hẳn: PostgreSQL, MongoDB, Redis dùng chart `groundhog2k` với image chính thức; Airflow
   tắt PostgreSQL đi kèm (Bitnami) và dùng PostgreSQL chính thức.
3. **Catalog**: Lakekeeper (REST catalog thật, PostgreSQL backend, helm chart) thay cho
   `apache/iceberg-rest-fixture`, vì jar của fixture chỉ có driver SQLite, không có PostgreSQL, và
   dự án ghi rõ đó là bản test. Chưa bật xác thực; NetworkPolicy ở tuần 5.
4. **Volume**: StorageClass mặc định `standard` ghi vào `/var/local-path-provisioner` trong node,
   không phải `/bigd-data`, nên dùng StorageClass `bigd-data` với PV tĩnh. File do container ghi sẽ
   thuộc UID của container trên máy chủ; dọn dẹp bằng `docker exec bigd-control-plane` (cần ghi vào `teardown.sh`).
5. **Dung lượng Kafka**: 60 GiB cho `ct.raw` 48 giờ chỉ đủ nếu zstd nén được khoảng 2×-4× so với
   49 GB/ngày thô. Cần đo tốc độ ghi thật sau vài giờ có collector rồi chỉnh. MinIO 150 GiB cũng là
   ước đoán, chưa có số đo bronze.
6. **Kafka 4.2.2**: Strimzi 1.3.0 hỗ trợ Kafka 4.2.x và 4.3.x; chọn 4.2.2. Cần xác nhận connector
   Kafka trong image Spark chung nói chuyện được với broker 4.2 (client 3.x/4.x đều tương thích về giao thức).
7. Chưa đo dung lượng kéo image qua Wi-Fi; image Kafka, Airflow, Trino là các gói lớn nhất.
