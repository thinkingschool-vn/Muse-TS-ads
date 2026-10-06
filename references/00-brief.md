# Giai đoạn 0 — BRIEF

Mục tiêu: một file `BRIEF.md` chứa **mọi sự thật** sẽ xuất hiện trong quảng cáo, mỗi dòng có nguồn.
Không có trong BRIEF = không được nói, không được hiện trong quảng cáo.

## 1. Thu thập
1. Hỏi user: link + tỷ lệ + độ dài master + nền tảng (SKILL.md, Giai đoạn 0).
2. Đọc trang khoá học (đọc URL hoặc mở trình duyệt). Cần thông tin thương hiệu (số khoá học, số học viên, mô hình học 5 phút/bài) thì đọc trang chủ `app.thinkingschool.vn` — **đọc lại mỗi lần**, số liệu trên web thay đổi.
3. Điền `templates/BRIEF.md`. Mỗi trường ghi nguồn: `(nguồn: <url>)` hoặc `(user xác nhận <ngày>)`.
4. Trường không tìm thấy → `⚠ cần xác nhận`. Gom **tất cả** trường ⚠ vào **một** tin nhắn, đánh số, kèm gợi ý mặc định nếu hợp lý.

## 2. Phân loại sản phẩm (quyết định chiến lược ở Giai đoạn 1)
| Loại | Dấu hiệu | Ví dụ |
|---|---|---|
| A. Khoá lẻ | 1 khoá, 1 giá | khoá kỹ năng microlearning |
| B. Master Series | lộ trình theo cấp bậc Staff / Senior / Manager / Leader | Master Series |
| C. Chương trình chuyên sâu | nhiều tuần/tháng, mentor, cohort | Mini MBA, Master Mindset, King Of Skills |
| D. Seminar / sự kiện | ngày giờ cụ thể, số chỗ | seminar cùng mentor |
| E. Miễn phí / phi lợi nhuận | học bổng, 0đ | Thinking Uni |
| F. Membership / ưu đãi có hạn | gói thành viên, mã giảm, flash sale | Membership |

## 3. Trường bắt buộc theo loại
| Trường | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| Tên chính xác | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Persona (tuổi, nghề, cấp bậc, nỗi đau) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| 3 lợi ích | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Giá gốc / giá bán | ✔ | ✔ | nếu công khai | giá vé | ghi "miễn phí" | ✔ |
| Hạn ưu đãi | nếu giảm giá | nếu giảm giá | nếu giảm giá | ✔ | — | ✔ |
| Ngày (khai giảng / sự kiện / ra mắt / hết hạn) | nếu có | — | ✔ | ✔ | ✔ | ✔ |
| Link CTA | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Bằng chứng (số học viên, đánh giá, mentor) | tuỳ chọn, phải có nguồn | | | | | |

## 4. must_say
Cuối BRIEF liệt kê `must_say`: cụm bắt buộc phải **nghe được** trong VO, viết dạng đọc theo `brand/LEXICON.md`
(vd "mười một tháng mười", "một triệu hai trăm nghìn đồng"). Giai đoạn 9 truyền từng cụm vào `qc.py final --must-say`.

## 5. Duyệt
Gửi user BRIEF (bảng) + danh sách câu hỏi ⚠. Chỉ sang Giai đoạn 1 khi user duyệt.
Thông tin thay đổi về sau → sửa BRIEF trước, rồi mới sửa kịch bản/thẻ.
