# Giai đoạn 1 — Chiến lược & kịch bản theo BLOCK

## 1. Chiến lược theo loại sản phẩm
| Loại | Góc tiếp cận | Block nhấn | CTA gợi ý |
|---|---|---|---|
| A Khoá lẻ | 1 kỹ năng cụ thể, học nhanh 5 phút/bài | LỢI ÍCH-1, ƯU ĐÃI | Học ngay |
| B Master Series | đúng bài cho đúng vai (cấp bậc) | VẤN ĐỀ theo cấp bậc, BẰNG CHỨNG | Chọn lộ trình |
| C Chuyên sâu | chuyển hoá dài hạn, mentor đồng hành | LỢI ÍCH ×3, BẰNG CHỨNG | Đăng ký tư vấn |
| D Seminar | chủ đề nóng + ngày cụ thể | ƯU ĐÃI (ngày, chỗ), CTA | Giữ chỗ |
| E Miễn phí | sứ mệnh "tri thức không rào cản" | THƯƠNG HIỆU, ƯU ĐÃI "100% miễn phí" | Đăng ký |
| F Membership / ưu đãi | giá trị so với giá, hạn chót | ƯU ĐÃI có hạn | Nhận ưu đãi |

## 2. Thư viện hook (nỗi đau Thinking School dùng trên website)
- "Học trước quên sau?" → microlearning 5 phút + quiz ôn tập.
- "Bơi giữa biển thông tin, không biết bắt đầu từ đâu?" → lộ trình hệ thống.
- "Lịch kín mít, lấy đâu thời gian học?" → 5 phút/bài, học trên điện thoại / Zalo Mini App.
- "Lên quản lý rồi, ai dạy bạn cách quản lý?" → Master Series theo cấp bậc.
- "Muốn học kiến thức đại học chuẩn quốc tế nhưng vướng học phí?" → Thinking Uni.

Luật hook: theo 8 luật ở `references/11-styles-and-hooks.md` (khung 0 có chuyển động, cắt cảnh đầu ≤ 2,5s, chữ + tiếng trong 3s, thương hiệu trong 5s).
**Viết 3 bản HOOK (A/B/C)** khác loại — lấy từ `hook_types` của phong cách (`python scripts/styles.py show <id>`). Ghi trong SCRIPT.md là các dòng `1A`, `1B`, `1C`; phần thân dùng chung. Phong cách drama: dựng theo khung micro-drama (mục 4 của reference 11).
Chỉ dùng tính năng có trong BRIEF.

## 3. Kịch bản theo BLOCK
Mỗi dòng kịch bản thuộc đúng 1 block: `HOOK · VẤN ĐỀ · THƯƠNG HIỆU · LỢI ÍCH-1 · LỢI ÍCH-2 · LỢI ÍCH-3 · BẰNG CHỨNG · ƯU ĐÃI · CTA`.

**Luật vàng:** VO của mỗi block phải **đứng độc lập** — không "nó", "điều đó", "ngoài ra", "thêm nữa" trỏ sang block khác, vì bản 30s/15s bỏ bớt block.

### Ngân sách thời gian (giây)
| Block | 60s | 30s | 15s |
|---|---|---|---|
| HOOK | 0–5 | 0–4/5 | 0–4 |
| VẤN ĐỀ | 5–10 | — | — |
| THƯƠNG HIỆU (logo sting 1,4s + cảnh) | 10–19 | ~5–11 | 4–10 |
| LỢI ÍCH-1 | 19–29 | 11–21 | — |
| LỢI ÍCH-2 | 29–39 | — | — |
| LỢI ÍCH-3 | 39–47 | — | — |
| BẰNG CHỨNG | 47–52 | — | — |
| ƯU ĐÃI (thẻ giá 3s) | 52–55 | 21–25 | — |
| CTA (end card 4,5–5s) | 55–60 | 25–30 | 10–15 |

- Bản 30s/15s dùng lại clip master; rút ngắn bằng `trim` (Giai đoạn 8).
- Bản 15s không có thẻ giá → câu CTA bản 15s phải tự nói ngày/ưu đãi. Viết thêm câu VO riêng (`"versions": ["15"]`) nếu câu CTA master không đủ.

### SCRIPT.md (mẫu dòng)
| # | Block | Giây | Hình (tiếng Anh, KHÔNG chữ, KHÔNG tên riêng) | VO hiển thị | VO TTS input | Overlay | Bản |
|---|---|---|---|---|---|---|---|
| 1 | HOOK | 5 | Close-up of a tired young office worker at night, laptop glow, sticky notes everywhere | Học trước quên sau? | Học trước quên sau? | Học trước quên sau? | 60·30·15 |
| 9 | CTA | 5 | (end card) | Đăng ký ngay, ra mắt 11/10. | Đăng ký ngay, ra mắt mười một tháng mười. | (thẻ) | 60·30 |
| 9b | CTA | 5 | (end card) | Thinking Uni ra mắt 11/10 — đăng ký ngay. | Thinking Uni ra mắt mười một tháng mười, đăng ký ngay. | (thẻ) | 15 |

## 4. Nhịp, âm thanh, chữ
- Độ dài shot theo `shot_len` của phong cách (drama 1–4s, motion 0,8–2,5s, 3D ấm 3–10s); mỗi 3–5s có thay đổi thị giác (cut, cỡ cảnh, overlay mới, chuyển động máy).
- VO phủ 70–85% thời lượng; khoảng lặng dài nhất ≤ 3s. CTA là 1 câu riêng, ~3,5 âm tiết/giây, `gain_db` +1 đến +2.
- Overlay ≤ 6–7 chữ/thẻ, hiện ≥ 0,8s + 0,3s × số chữ, không đè mặt, không đặt trên đoạn flash.
- Tên thương hiệu nghe + thấy trước giây 12 (60s) hoặc giây 6 (30s/15s).
- Tối đa 3 thông điệp. Tuân thủ `brand/BRAND_GUIDE.md`.

## 5. Duyệt
Gửi user `SCRIPT.md` + bảng ước tính thời lượng 3 bản kèm phương án đề xuất tối ưu. Thông báo mốc chờ 5 phút: *"Trong 5 phút nếu anh không có phản hồi hoặc chỉnh sửa, em sẽ tự động duyệt kịch bản này để sang Giai đoạn 2 (thiết kế nhân vật) nhé ạ!"* Hết 5 phút tự động tiến hành.
