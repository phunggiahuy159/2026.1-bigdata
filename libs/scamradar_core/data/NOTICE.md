# Dữ liệu đi kèm scamradar_core

## public_suffix_list.dat

- Nguồn: https://publicsuffix.org/list/public_suffix_list.dat (bản `VERSION: 2026-10-22_08-36-41_UTC`,
  `COMMIT: 8437e5262f13305f94087abe699b4fe2be1d1de8`, ghi ở đầu file).
- License: Mozilla Public License 2.0 (https://mozilla.org/MPL/2.0/); file giữ nguyên, không sửa.
- Mục đích: thư viện tách eTLD+1 không cần mạng, nên test và CI chạy được offline.
- Cập nhật: tải lại bản mới từ URL trên, ghi lại VERSION/COMMIT ở đây rồi chạy test. Script
  `data/reference/download.sh` tải bản mới nhất cho mục đích khác (không commit); thư viện chỉ đọc
  file này, hoặc file trỏ bởi biến môi trường `SCAMRADAR_PSL`.

## Bảng ký tự dễ nhầm

Bảng trong `confusables.py` là bảng tự soạn, nhỏ (chữ Cyrillic/Greek giống Latin, số giả chữ, chữ ghép
như `rn`→`m`), tham khảo ý tưởng của Unicode UTS #39 nhưng không sao chép dữ liệu của Unicode, nên
không kèm file ngoài.
