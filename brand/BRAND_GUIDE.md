# Brand Guide — quảng cáo Thinking School

## Giọng điệu
- Thông thái nhưng gần gũi; truyền cảm hứng học tập; tôn trọng người học. Xưng "bạn".
- Câu ngắn, động từ mạnh, một ý mỗi câu. Không giáo điều, không hù doạ.
- Gọi đúng tên: **Thinking School**, **Thinking Uni**, **Master Series**, **Mini MBA** (giữ hoa/thường như trên).

## Luật nội dung (bắt buộc)
1. **Không** dùng "nhất", "số 1", "duy nhất", "tốt nhất", "đảm bảo" nếu BRIEF không có bằng chứng kèm nguồn.
2. Mọi con số (số khoá học, số học viên, giá, % giảm, ngày) phải có trong `BRIEF.md` kèm nguồn (link trang hoặc "user xác nhận ngày …").
3. Giá ưu đãi (có giá gốc gạch ngang) **bắt buộc** kèm hạn ưu đãi rõ ràng. `brand_cards.py` từ chối render nếu thiếu.
4. Không hứa kết quả thu nhập/thăng tiến cụ thể ("tăng lương 50%") và không tạo khan hiếm giả ("chỉ còn 2 suất") nếu không đúng sự thật.
5. Thinking Uni là dự án **phi lợi nhuận**: dùng "học bổng", "miễn phí 100%" đúng như trang; không gắn giá.

## Hình ảnh
- Logo, giá, QR, link **luôn** là thẻ `brand_cards.py` hoặc overlay — không bao giờ để model AI vẽ.
- Trên nền tối dùng `logo-on-dark.png` (chữ trắng, "g" xanh); trên nền sáng dùng `logo-on-light.png`. Không đặt logo lên nền xanh #0064FF (chữ "g" bị chìm).
- Màu: xanh chủ đạo #0064FF, tím #8B5CF6, chàm #4F46E5, nhấn vàng #F59E0B (giá, CTA). Nền thẻ: gradient #0B1020 → #1E1B4B.
- Font chữ overlay/thẻ: Be Vietnam Pro Bold (đủ dấu tiếng Việt).
- Logo góc (logo bug) chỉ hiện trên cảnh câu chuyện, ẩn ở thẻ THƯƠNG HIỆU / ƯU ĐÃI / CTA.

## CTA mẫu
- "Đăng ký ngay" · "Học thử miễn phí" · "Nhận tư vấn qua Zalo" · "Đăng ký trước <ngày>" · "Giữ chỗ seminar".
- CTA trên end card ≤ 4 từ; ngày/ưu đãi đặt ở dòng phụ.
