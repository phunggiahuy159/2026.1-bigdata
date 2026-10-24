# contracts/redis

Redis phục vụ số liệu live cho dashboard. Dữ liệu tạm, có thể dựng lại từ `ct.raw`; không phải nguồn sự thật.
Ghi: P3 (`jobs/stream_detect`, qua `foreachBatch`). Đọc: P5 (Streamlit). Không ai khác ghi vào các key này.

| Key | Kiểu | TTL | Ghi | Đọc |
| --- | --- | --- | --- | --- |
| `cnt:{brand}:{minute}` | string (số nguyên thập phân) | 48 giờ | P3 | P5 |
| `top:suspicious:1h` | sorted set | 2 giờ, làm mới mỗi lần ghi | P3 | P5 |
| `top:suspicious:1h:ts` | hash | 2 giờ, làm mới mỗi lần ghi | P3 | không (nội bộ P3) |

## Quy ước chung

- Thời gian là UTC. Domain là eTLD+1 ASCII punycode viết thường, như `contracts/mongodb`. `brand` là `brand_id` trong `data/reference/brands.yaml`
  (chỉ gồm `[a-z0-9_]`, nên không đụng dấu `:` làm phân cách).
- Mọi lệnh ghi phải **idempotent** vì `foreachBatch` có thể chạy lại sau khi khôi phục: dùng `SET` giá trị tuyệt đối, `ZADD ... GT`, `HSET`; không dùng `INCR` / `INCRBY`.
- Người đọc không dùng `KEYS` hay `SCAN` trên cụm dùng chung; tự dựng danh sách khoá từ `brand_id` và các phút cần xem rồi `MGET`.

## `cnt:{brand}:{minute}`

- Khoá: `cnt:momo:202610241137`. `minute` là `YYYYMMDDHHMM` theo UTC của `seen_ts` (event time, không phải giờ xử lý).
- Giá trị: số nguyên không âm dạng chuỗi thập phân, là số chứng chỉ (đã khử trùng theo `sha256`) có khớp thương hiệu `brand` trong phút đó.
  Chứng chỉ không khớp thương hiệu nào không được đếm.
- Ghi: stream đầu ra theo output mode `update`; mỗi lần chỉ phát các cặp (brand, phút) có thay đổi, kèm tổng hiện tại, nên ghi `SET key value EX 172800` (ghi lại cùng giá trị là vô hại).
  Phút còn trong khoảng watermark có thể được ghi lại với giá trị lớn hơn; sau khi qua watermark thì giá trị cố định.
- TTL 48 giờ (172800 giây), đặt lại mỗi lần `SET`.
- Đọc: `MGET` các phút cần xem; khoá không tồn tại nghĩa là 0.

## `top:suspicious:1h`

- Kiểu sorted set: member là domain gốc, score là điểm nghi vấn 0-100 (cùng `score` ở `alerts.v1`).
- Ghi: với mỗi cảnh báo, `ZADD top:suspicious:1h GT {score} {domain}` (`GT` cần Redis 6.2+; chạy lại cảnh báo cũ không hạ điểm) và `HSET top:suspicious:1h:ts {domain} {alert_ts}`.
- Cửa sổ 1 giờ: sau mỗi batch P3 duyệt `top:suspicious:1h:ts`, domain có `alert_ts` cũ hơn 1 giờ so với `alert_ts` lớn nhất vừa ghi thì `ZREM` khỏi tập và `HDEL` khỏi hash.
  Hash `:ts` chỉ phục vụ việc này; người đọc bỏ qua.
- TTL 2 giờ trên cả hai key, đặt lại mỗi lần ghi, để luồng ngừng thì dữ liệu tự biến mất.
- Đọc: `ZREVRANGE top:suspicious:1h 0 {n-1} WITHSCORES` lấy n domain điểm cao nhất. Domain hiển thị phải vô hiệu hoá (`hxxps://abc[.]com`).
  Sorted set chỉ là xếp hạng gần đúng trong 1 giờ; điểm hiệu lực (có batch) lấy từ MongoDB `domains`.

## Ngoài phạm vi

Bảng tổng nhỏ theo thương hiệu cho dashboard live (output mode `complete`) chưa chốt nơi lưu; khi chốt sẽ thêm key vào file này.
Đổi không tương thích (kiểu giá trị, định dạng khoá) thì đổi tên key có phiên bản (`cnt2:...`) và báo P5.
