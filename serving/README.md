# serving/

Ứng dụng Streamlit của ScamRadar VN. Đây là **khung** chạy trên dữ liệu mẫu tự soạn
(`app/sample_data/`, theo schema trong `contracts/mongodb/`); cụm chưa có MongoDB.

## Chạy cục bộ

```bash
uv sync --all-packages
uv run streamlit run serving/app/main.py
```

## Trang

- **Feed cảnh báo**: cảnh báo mới nhất trước, lọc theo điểm và thương hiệu.
- **Chi tiết domain**: điểm hiệu lực (batch ghi đè speed khi có), lý do, enrichment, chiến dịch.
- **Domain .vn**: domain `.vn` nghi vấn theo điểm.

## Quy ước hiển thị

Mọi domain đi qua `app/defang.py` trước khi hiển thị: `hxxps://abc[.]com`. Trang chỉ nhận dữ liệu từ
`app/views.py` (đã vô hiệu hoá) và hiển thị bằng bảng/văn bản thuần, không render link bấm được tới domain nghi vấn.

## Cấu trúc

| File | Vai trò |
| --- | --- |
| `app/defang.py` | vô hiệu hoá domain và URL |
| `app/data.py` | `Repository` (hiện là `SampleRepository`), điểm hiệu lực, hàm tiện ích |
| `app/views.py` | dựng dữ liệu hiển thị cho từng trang |
| `app/pages.py`, `app/main.py` | các trang Streamlit và điểm vào |

Nối MongoDB sau này: viết lớp `Repository` mới đọc `domains` và `alerts`, các trang không đổi.
Test ở `tests/serving/` (dữ liệu mẫu được kiểm theo schema contract).
