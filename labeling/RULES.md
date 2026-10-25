# Quy tắc gán nhãn domain

Mục tiêu: gán cho mỗi domain gốc (eTLD+1) một trong ba nhãn `phishing`, `suspicious`, `clean`
để huấn luyện và đánh giá mô hình. Mọi domain dưới đây viết ở dạng vô hiệu hoá
(`hxxps://abc[.]com`); **không mở, fetch hay ping** domain lấy từ luồng chứng chỉ.
Chỉ dùng thông tin có sẵn: chuỗi domain, thông tin chứng chỉ, enrichment (DNS, ASN),
kết quả Safe Browsing và `data/reference/brands.yaml`.

## Định nghĩa

### `phishing` (lừa đảo)
Gán khi có **ít nhất một** bằng chứng mạnh:
- Safe Browsing đánh dấu `SOCIAL_ENGINEERING` hoặc `MALWARE`.
- Domain chứa tên thương hiệu trong `brands.yaml` hoặc biến thể gần giống (typosquat, homoglyph,
  thay ký tự) **và** không thuộc danh sách domain chính thức của thương hiệu đó
  **và** có thêm một tín hiệu phụ: TLD rủi ro, chứng chỉ vừa cấp, hạ tầng khác hẳn hạ tầng thương hiệu.

Ví dụ:
- `hxxps://vietcombank-xacthuc[.]top` (thương hiệu + từ khoá xác thực + TLD `.top`)
- `hxxps://vietc0mbank[.]com` (thay `o` bằng `0`, không phải domain chính thức)
- `hxxps://momo-nhanqua[.]xyz`

### `suspicious` (nghi vấn)
Có dấu hiệu nhưng **chưa đủ** để kết luận:
- Chứa tên thương hiệu hoặc biến thể nhưng chỉ có một tín hiệu yếu, không có tín hiệu phụ.
- Cấu trúc bất thường (nhiều dấu gạch ngang, chuỗi ngẫu nhiên dài) mà không nhắc thương hiệu nào.
- Safe Browsing không đánh dấu nhưng nhiều đặc trưng giống domain `phishing` đã gán.

Ví dụ:
- `hxxps://shopee-sale-2026[.]com` (từ khoá thương hiệu, chưa rõ mạo danh)
- `hxxps://tpb-support-vn[.]net` (viết tắt, có thể là đại lý hợp pháp)

`suspicious` **không** dùng làm nhãn dương khi huấn luyện; chỉ dùng để phân tích và đánh giá bổ sung.

### `clean` (sạch)
- Domain chính thức của thương hiệu trong `brands.yaml`.
- Domain trong Tranco top-1M và không có bất kỳ tín hiệu mạo danh nào.
- Domain nhắc thương hiệu nhưng là bên hợp pháp đã xác minh (báo chí, trang so sánh, đại lý uỷ quyền),
  ghi rõ lý do trong cột `note`.

Ví dụ:
- `hxxps://vietcombank[.]com[.]vn` (chính thức)
- `hxxps://example-news[.]vn` (nhắc thương hiệu trong tin tức, đã xác minh)

### Không gán (`skip`)
Không đủ thông tin để phân biệt `suspicious` với `clean`. Bỏ qua, không ép nhãn.

## Quy trình

1. Lấy mẫu để gán: nghi vấn từ cảnh báo của speed layer (stratified theo thương hiệu) cộng mẫu âm
   từ Tranco top-1M và domain chính thức. Mục tiêu ≥ 500 domain.
2. Người gán 1 gán toàn bộ mẫu vào `data/labels/manual_labels.csv`.
3. **Gán chéo 10%**: chọn ngẫu nhiên (seed cố định, ghi trong CSV hoặc commit message) 10% số dòng,
   người gán 2 gán độc lập, không xem nhãn của người 1.
4. Đo độ đồng thuận bằng Cohen's kappa và tỉ lệ trùng khớp thô trên phần gán chéo. Báo cáo cả hai
   cùng kích thước tập. Kappa < 0.6: họp lại sửa quy tắc rồi gán lại phần bất đồng.
5. Bất đồng còn lại: hai người thống nhất; nếu không được thì nhãn là `skip`.
6. Safe Browsing (`labeling/safebrowsing.py`) dùng làm bằng chứng bổ sung và để dán nhãn tự động
   (nhãn yếu), luôn lưu cột `source` để phân biệt nhãn tay với nhãn tự động.

## Định dạng `data/labels/manual_labels.csv`

| Cột | Ý nghĩa |
| --- | --- |
| `domain` | domain gốc (eTLD+1), ASCII punycode, chữ thường, dạng thật để join với bảng khác (không bao giờ mở) |
| `label` | `phishing` / `suspicious` / `clean` |
| `brand_id` | thương hiệu bị nhắm tới, rỗng nếu `clean` không liên quan |
| `annotator` | mã người gán (`a1`, `a2`) |
| `source` | `manual` / `safe_browsing` / `tranco` / `official` |
| `double_labeled` | `1` nếu thuộc phần gán chéo 10% |
| `note` | lý do ngắn gọn |

## Quy ước nhãn khi ghi `silver.labels`

Nhãn tay trong CSV giữ ba giá trị để phân tích; bảng `silver.labels` (hợp đồng Iceberg) chỉ có hai lớp
`phishing | benign` vì mô hình huấn luyện là phân loại nhị phân. Phép ánh xạ do job nhãn thực hiện
(`labeling/labels.py`):

| CSV `label` | `silver.labels.label` |
| --- | --- |
| `phishing` | `phishing` |
| `clean` | `benign` |
| `suspicious` | không ghi vào bảng |
| `skip` | không ghi vào bảng |

`label_source` của `silver.labels` lấy từ cột `source` của CSV (`manual`, `safe_browsing`, `tranco`, `official`).
Khi cả nhãn tay và Safe Browsing cùng có cho một domain, hai dòng được ghi với `label_source` khác nhau
(hạt của bảng là `(registered_domain, label_source)`); job huấn luyện chọn thứ tự ưu tiên: `manual` hơn
`official` hơn `safe_browsing` hơn `tranco`.

## An toàn và quản trị

- API key Safe Browsing chỉ đọc từ biến môi trường `SAFE_BROWSING_API_KEY` (file `.env` cục bộ hoặc K8s Secret).
- Tôn trọng giới hạn tốc độ; client mặc định cách nhau ≥ 1 giây giữa các lời gọi và lùi theo cấp số nhân khi gặp 429/5xx.
- Không commit phản hồi thô của Safe Browsing, chỉ commit nhãn đã rút gọn.
- Khi dán domain vào docs, báo cáo, issue: luôn dạng vô hiệu hoá.
