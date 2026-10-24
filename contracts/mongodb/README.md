# contracts/mongodb

MongoDB, database `scamradar`, ba collection. Schema là JSON Schema (`*.schema.json`), index ở `indexes.json`.
Tên trường, kiểu và quy ước bám `contracts/kafka` và `contracts/iceberg`.

| Collection | `_id` | Ghi | Đọc | Nguồn |
| --- | --- | --- | --- | --- |
| `domains` | domain gốc (eTLD+1) | P3 (`speed`, `brand_id`), P5 (`batch`) | P5 (Streamlit) | `alerts.v1`, `gold.domain_scores`, `silver.enrichment`, `gold.campaigns` |
| `alerts` | `{domain}\|{alert_ts}` | P3 | P5 | `alerts.v1` |
| `campaigns` | `campaign_id` | P5 | P5 | `gold.campaigns` (P4) |

## Quy ước chung

- Domain (`_id` của `domains`, `alerts.domain`, `campaigns.domains[]`) là eTLD+1 **ASCII punycode** (`xn--...`), viết thường, giống `registered_domain` ở Iceberg. Unicode chỉ dùng khi hiển thị.
- Thời gian là UTC mili giây, số nguyên (Spark `TIMESTAMP` ghi sang Mongo thì đổi về mili giây epoch). Ngày (`score_date`, `run_date`) là chuỗi `YYYY-MM-DD` theo UTC.
- `score` là số nguyên 0-100 kèm `reasons[]`.
- `batch.enrichment.asn`, `asn_org`, `country` là **mảng**, một phần tử cho mỗi IP của `concat(a_records, aaaa_records)` theo cùng thứ tự, phần tử `null` nếu IP không tra được (như `silver.enrichment`).
- Tên trường lấy theo cột Iceberg tương ứng: `gold.domain_scores` (`score_date`, `score`, `reasons`, `model_version`, `scored_ts`), `gold.campaigns` (`run_date`, `domain_count`, `domains`, `brands`, `shared_ips`, `shared_nameservers`, `asns`, `hub_node`, `hub_rank`, `first_seen_ts`, `last_seen_ts`).
- Domain lừa đảo trong ví dụ và tài liệu viết dạng vô hiệu hoá (`hxxps://abc[.]com`); dữ liệu trong collection là domain thật, mọi nơi hiển thị phải vô hiệu hoá.

## Quy tắc hợp nhất speed + batch (`domains`)

1. **Mỗi bên chỉ ghi vùng của mình.** P3 chỉ `$set` `speed.*` và `brand_id`; P5 chỉ `$set` `batch.*`. Không ai `replaceOne` cả document, nên hai bên không ghi đè lẫn nhau. Dùng `upsert: true` vì document có thể do bên nào đến trước tạo ra.
2. **Điểm batch ghi đè.** Điểm hiệu lực (`effective_score`) tính khi đọc, không lưu: `batch.score` nếu có `batch`, ngược lại `speed.score`. `reasons` đi theo điểm được chọn.
3. **Ghi chạy lại được, bản cũ không đè bản mới.** Điều kiện "mới hơn" **không** đặt trong filter của `updateOne` có `upsert: true`: nếu document đã tồn tại nhưng không khớp filter, MongoDB thử chèn document mới và lỗi trùng `_id` (E11000). Filter chỉ là `{_id: domain}`; điều kiện nằm trong **update bằng aggregation pipeline** (MongoDB 4.2+), chọn giữa khối `batch` mới và khối cũ:

   ```python
   # new = toàn bộ khối batch mới (xem quy tắc 4)
   newer = {
       "$or": [
           {"$not": ["$batch"]},
           {"$gt": [new["score_date"], "$batch.score_date"]},
           {
               "$and": [
                   {"$eq": [new["score_date"], "$batch.score_date"]},
                   {"$gte": [new["scored_ts"], "$batch.scored_ts"]},
               ]
           },
       ]
   }
   coll.update_one(
       {"_id": domain}, [{"$set": {"batch": {"$cond": [newer, new, "$batch"]}}}], upsert=True
   )
   ```

   Chấm lại cùng `score_date` ghi lại cùng giá trị (idempotent); `score_date` cũ hơn không đổi gì; cùng `score_date` thì `scored_ts` lớn hơn thắng. Không cần bắt E11000. Hợp đồng này áp dụng cho mọi bên ghi vào `domains`, kể cả `speed` của P3 nếu P3 cần chống ghi lùi (so `speed.updated_ts` tương tự).
4. Domain chưa có `batch` (mới xuất hiện sau lần chấm cuối) chỉ có `speed`; ứng dụng hiển thị điểm speed và đánh dấu "chưa chấm batch".

## Ghi chú

- `alerts` có TTL 30 ngày trên `created_at` (bản xem nhanh; bản đầy đủ nằm ở Kafka/Iceberg). `created_at` **bắt buộc là BSON Date**: TTL index bỏ qua document có trường là chuỗi hay số nên sẽ không bao giờ xoá. Người ghi (P3) chuyển `alert_ts` (mili giây) sang Date, ví dụ `datetime.fromtimestamp(alert_ts / 1000, tz=UTC)`.
- `alerts` bám `alerts.v1`; hiện chưa có `contracts/kafka/alerts.v1.schema.json`, P3 chốt xong thì đối chiếu lại tên trường.
- Thay đổi tương thích ngược (thêm trường tuỳ chọn) chỉ cần báo; đổi không tương thích thì đổi tên collection có phiên bản (`domains_v2`) và báo người đọc, người ghi.
