# labeling/

Công cụ tạo nhãn domain cho `silver.labels`: quy tắc gán tay (`RULES.md`), ánh xạ nhãn (`labels.py`)
và client Google Safe Browsing Lookup API (`safebrowsing.py`).

## Tạo API key Safe Browsing

Mỗi người tự tạo key riêng; **không commit key**.

1. Vào Google Cloud Console, tạo (hoặc chọn) một project.
2. Mục APIs & Services > Library, tìm "Safe Browsing API" và bật (Enable).
3. APIs & Services > Credentials > Create credentials > API key.
4. Nên giới hạn key ở "API restrictions: Safe Browsing API" (và giới hạn IP nếu có IP cố định).
5. Đặt vào `.env` cục bộ (đã gitignore), mẫu ở `.env.example`:

   ```bash
   SAFE_BROWSING_API_KEY=<key của bạn>
   ```

   Trên cụm, key đi qua K8s Secret, không nằm trong image hay values.

## Quota và giới hạn tốc độ

- Safe Browsing API miễn phí nhưng chỉ cho mục đích **phi thương mại**. Hạn mức mặc định được cấp khi bật API
  và xem được ở Cloud Console (APIs & Services > Safe Browsing API > Quotas); muốn tăng thì gửi yêu cầu ở đó.
  Hạn mức cụ thể phụ thuộc project nên không ghi cứng ở đây: xem con số thật ở Console trước khi gán nhãn hàng loạt.
- Client (`SafeBrowsingClient`) tự giới hạn: tối đa 500 URL mỗi request (giới hạn của API), mặc định cách nhau
  ít nhất 1 giây giữa hai request (`min_interval`), và lùi theo cấp số nhân khi gặp 429/5xx (`max_retries`).
  Dùng `min_interval` lớn hơn nếu quota của project thấp.
- Thông báo lỗi không chứa key. Phản hồi thô không được lưu; chỉ giữ kết quả rút gọn `Verdict`.

## Dùng

```python
from labeling.safebrowsing import SafeBrowsingClient

client = SafeBrowsingClient()  # đọc SAFE_BROWSING_API_KEY
for v in client.check(["xn--example.com"]):
    print(v.domain, v.flagged, v.threats)
```

Chỉ gửi domain tới Safe Browsing; không bao giờ mở, fetch hay ping domain lấy từ luồng chứng chỉ.

## Test

Test mock tầng HTTP (`transport` được tiêm vào), không gọi API thật và không cần key:

```bash
uv run pytest tests/labeling
```
