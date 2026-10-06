# Phong cách video + Hook 3 giây

Đọc ở Giai đoạn 0 (chọn phong cách) và Giai đoạn 1 (viết 3 bản hook). Nguồn: Meta/Nielsen (47% giá trị quảng cáo video nằm ở 3s đầu), Google ABCD (Attention · Branding · Connection · Direction), TikTok Creative Center.

## 1. Chọn phong cách
```powershell
python scripts/styles.py list
python scripts/styles.py show cinematic-drama
```
| Phong cách | Khi dùng | Hook ≥ shot (0–5s) | Thoại |
|---|---|---|---|
| `warm-3d` (mặc định) | Thinking Uni, cộng đồng, người mới | 1 | không |
| `cinematic-drama` | Mini MBA, chuyên sâu, hội thảo, câu chuyện chuyển mình | 2 | có |
| `micro-drama` | Microlearning, kỹ năng văn phòng, giao tiếp | 2 | có |
| `motion-graphics` | Ưu đãi, flash sale, seminar, nhiều lợi ích | 3 | không |

Ghi `"style": "<id>"` vào `edit.json`. `assemble.py` chặn chuyển cảnh không thuộc phong cách và chặn thoại ở phong cách không cho thoại.
Người **luôn** vẽ cách điệu (stylized 3D); bối cảnh/ánh sáng có thể như thật. Không dựng học viên/giảng viên giả, không lời chứng thực giả.

## 2. Tám luật hook 3 giây
1. **Khung hình 0** có chủ thể + chuyển động. Không fade-in, không logo mở đầu, không màn đen.
2. **Cắt cảnh đầu ≤ 2,5s**; số shot trong 0–5s ≥ `hook_min_shots` của phong cách (dùng `in/out` + `"punch": 1.2–1.4` để có shot cận từ cùng clip).
3. **Ba lớp trong 0–3s:** hình mạnh + chữ hook 5–8 từ + âm thanh mở trong 0,5s (SFX hit / thoại / VO vào lúc 0,3–0,5s).
4. **Thương hiệu trong 5s:** logo góc (`logo_bug`) hoặc nhắc tên trong lời. Logo sting vẫn ở ~giây 10.
5. **Mặt người** (nhân vật) càng sớm càng tốt; nhìn vào máy hoặc phản ứng mạnh.
6. **Chữ khớp lời:** chữ hook là phiên bản ngắn của câu VO/thoại đầu.
7. **CTA vừa nói vừa hiện** (end card + câu VO CTA).
8. **Hook là module:** mặc định viết **3 bản hook** (`hook_variants`) khác loại, cùng thân quảng cáo → chạy A/B.

Đo trên nền tảng: **hook rate = lượt xem 3s ÷ lượt hiển thị** — < 20% yếu · 25–35% ổn · > 35% mạnh. Giữ bản thắng, thay bản thua bằng loại hook khác.

## 3. Thư viện 12 loại hook
| id | Khung hình đầu | Câu mở mẫu | Chữ mẫu | Rủi ro | Hợp hoạt hình |
|---|---|---|---|---|---|
| `in-medias-res` | Giữa xung đột: sếp đập tập hồ sơ xuống bàn | "Lại sai số liệu nữa à?" | LẠI SAI NỮA À? | Cần giải quyết nhanh ở block sau | ✔ |
| `cold-open` | Khoảnh khắc cao trào cuối phim (lên chức, vỗ tay) rồi cắt ngược | "Ba tháng trước, tôi suýt bỏ việc." | 3 THÁNG TRƯỚC… | Lộ kết, phải giữ tò mò "bằng cách nào" | ✔ |
| `pattern-interrupt` | Hình bất ngờ: chồng sách đổ sập, đèn vỡ thành pháo hoa | (SFX mạnh, VO 0,4s) "Khoan đã!" | KHOAN ĐÃ! | Lạc đề nếu không nối về nỗi đau | ✔ (tốt nhất cho AI) |
| `why-question` | Nhân vật nhíu mày trước vấn đề | "Vì sao học mãi vẫn quên?" | VÌ SAO HỌC MÃI VẪN QUÊN? | Tránh câu hỏi có/không | ✔ |
| `bold-claim` | Nhân vật tự tin, ánh sáng hero | "5 phút mỗi ngày là đủ." | 5 PHÚT/NGÀY | Phải có bằng chứng trong BRIEF | ✔ |
| `stop-doing` | Tay gạt bỏ thói quen sai (giấy note bay đi) | "Đừng học kiểu nhồi nhét nữa." | ĐỪNG NHỒI NHÉT | Giọng chê bai → giữ tích cực | ✔ |
| `pov-pain` | Góc nhìn thứ nhất: hộp thư 99+ email, đồng hồ 23h | "POV: 11 giờ đêm vẫn chưa xong việc." | POV: 23H VẪN CHƯA XONG | Màn hình không được có chữ đọc được | ✔ |
| `curiosity-gap` | Vật bí ẩn phát sáng trong tay nhân vật | "Thứ này thay đổi cách tôi học." | THỨ NÀY LÀ GÌ? | Phải trả lời trong block THƯƠNG HIỆU | ✔ |
| `before-after` | Chia đôi/chuyển nhanh: rối → gọn | "Trước và sau 30 ngày." | TRƯỚC → SAU | Không hứa kết quả không có nguồn | ✔ |
| `direct-address` | Người nói thẳng vào máy | "Nếu bạn là quản lý mới, nghe này." | QUẢN LÝ MỚI? | Cần người thật; AI dễ "creepy" | ✘ (chỉ quay thật) |
| `callout` | Nhân vật đúng persona trong bối cảnh nhận diện | "Dành cho ai vừa lên trưởng nhóm." | VỪA LÊN TRƯỞNG NHÓM? | Thu hẹp tệp — chỉ dùng khi target rõ | ✔ |
| `stat-shock` | Con số lớn bằng overlay (KHÔNG do AI vẽ) | "70% kiến thức quên sau 24 giờ." | 70% QUÊN SAU 24H | Bắt buộc nguồn trong BRIEF | ✔ |

## 4. Khung micro-drama (1 beat ≈ 1 clip)
| Beat | 60s | 30s | 15s |
|---|---|---|---|
| Xung đột (hook, < 3s đã thấy mâu thuẫn) | 0–5 | 0–4 | 0–4 |
| Leo thang / đáy | 5–15 | 4–9 | — |
| Phát hiện (bài học hiện tự nhiên trên điện thoại/laptop — màn hình không chữ) | 15–25 | 9–14 | 4–8 |
| Lật ngược / thắng | 25–45 | 14–22 | 8–10 |
| Ưu đãi + CTA | 45–60 | 22–30 | 10–15 |
Lật kèo phải đến từ **kỹ năng học được**, không từ may mắn. Tránh cringe: thoại đời thường, không thuyết giảng, không bôi nhọ người khác.

## 5. Ngôn ngữ máy cho AI video
- Công thức prompt: **[máy quay] + [chủ thể] + [hành động] + [bối cảnh] + [phong cách & không khí]**, đặt khối `styles.py prompt <id>` lên đầu.
- Ổn định: máy tĩnh + chủ thể chuyển động, dolly-in/out chậm, pan chậm, orbit chậm, handheld nhẹ, low-angle hero.
- Hay hỏng: whip pan / crash zoom trong clip, nhiều chuyển động chồng nhau, cận tay gõ phím, màn hình đọc được, đám đông.
- Whip / zoom giật / chớp trắng làm **lúc dựng**: `"transition": "whip" | "zoompunch" | "flash"`.
- Màu kể chuyện: trước lạnh → sau ấm (`grade_arc` của phong cách).

## 6. Nhãn AI
Video không gắn nhãn AI. Khi đăng: bật nhãn "nội dung AI" trên TikTok/Meta. Luật Trí tuệ nhân tạo 134/2025/QH15 (hiệu lực 1/3/2026) yêu cầu gắn nhãn — mẫu nhãn ⚠ cần pháp chế xác nhận.
