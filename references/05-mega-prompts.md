# Giai đoạn 5 — Mega Prompt từng cảnh

## Mục đích
Viết 1 prompt "copy-paste là chạy" cho mỗi cảnh. Prompt video chỉ lo **hình + tiếng động**. Nhạc và lời KHÔNG nằm trong prompt video — chúng đã được làm riêng ở Giai đoạn 3.

## Cấu trúc mega prompt (tiếng Anh)
```
<GLOBAL LOCKS>
SHOT: <cỡ cảnh + góc máy: wide / medium / close-up, eye-level / low angle>
FIRST FRAME: <mô tả = keyframe đầu (hoặc frame cuối thật của clip trước)>
MOTION: <hành động theo trình tự thời gian, từng bước, đúng vật lý>
CAMERA: <1 chuyển động máy duy nhất: slow push-in / gentle orbit / static>
LAST FRAME: <mô tả = keyframe cuối>. Hold this final composition steady for the last second.
SOUND (SFX only): <tiếng động môi trường: gió, bước chân, giấy lật...>
AUDIO RULES: No music. No dialogue. No narration. No singing. Characters do not speak; mouths stay closed or smile silently.
```
- **"Hold … for the last second"** giúp frame cuối ổn định → dễ match-cut, dễ trim.
- Mỗi cảnh **1 chuyển động máy**. Nhiều chuyển động = model dễ lạc khỏi last frame.

## Global locks (dán đầu mọi prompt)
```
Stylized 3D feature-animation look, soft rounded shapes, gentle subsurface skin,
warm cinematic lighting, rich painterly backgrounds, [9:16 vertical 720x1280 | 16:9 landscape 1280x720].
STRICT ASPECT RATIO LOCK: the output MUST be exactly [9:16 | 16:9]. All attached
references share this ratio.
TEXT BAN: no text, no letters, no numbers, no logos, no captions, no UI labels,
no watermark anywhere in frame. Posters, screens, books and signs are blank or abstract.
<Character lock: mô tả NGOẠI HÌNH chép từ STORY.md — không tên, không tuổi bằng số>
Keep every character exactly on-model with the attached sheets in all frames.
```
> Viết style bằng **tính từ** khớp với cái Muse thực sự tạo ra (dự án Thinking Uni: lock ghi "2D" nhưng ra 3D). Chọn mô tả theo character sheet đã duyệt.

## ⛔ Vệ sinh prompt — chống chữ lạ (bài học Thinking Uni)
Model video/ảnh **in ra màn hình những chữ nó đọc được trong prompt**.

| Không viết | Vì đã xảy ra | Viết thay bằng |
|---|---|---|
| "Disney/Pixar style" | Model vẽ chữ "Disney/PIXAR" lên 3 clip → render lại | "stylized 3D feature-animation look" |
| "Linh, 24 years old" | Hologram lộ nhãn "Linh 24" | "a young woman in her mid-twenties, high black ponytail, light-blue cardigan…" |
| Tên thương hiệu, slogan, ngày, % | Model cố vẽ thành chữ (thường sai) | Bỏ hẳn — mọi chữ đưa vào ở khâu dựng (overlay) |
| "walls labeled 'học phí'" | Mời model viết chữ | "tall grey stone walls" — ý nghĩa do VO/overlay truyền tải |
| poster/màn hình/sách "có nội dung" | Model tự chế chữ ("HỌC TẬP SÁNG TẠO") | "blank poster", "abstract glowing shapes on the screen" |

Trong video chỉ được có chữ mà user **chủ động yêu cầu** và đã duyệt. Phát hiện chữ lạ ở keyframe/clip = làm lại, không "giữ vì nhìn cũng hợp".

## Thứ tự nạp ref (bắt buộc)
1. Character sheet của nhân vật trong cảnh
2. First frame (keyframe, hoặc **frame cuối thật** của clip trước nếu cảnh nối MATCH — xem Giai đoạn 6)
3. Last frame (keyframe)
→ Rồi mới đến prompt text.

## ⚠️ Luật realism (đọc kỹ trước khi viết MOTION)
Mọi hành động vật lý nhỏ phải đúng cơ chế thực tế:
- Thắp đèn có khung kính: **mở cửa kính → đưa bấc vào → đóng cửa lại**. Không "châm lửa xuyên qua kính".
- Gió dập lửa: gió **xé rách đèn giấy**, lửa **chập chờn trong housing rung rồi tắt**.
- Cầm điện thoại: màn hình hướng về phía người xem thì người cầm không thể đọc được.
Kiểm tra từng động từ: "ngoài đời nó xảy ra như vậy không?" — không → viết lại.

## Checklist
- [ ] Mỗi cảnh đủ: SHOT / FIRST FRAME / MOTION / CAMERA / LAST FRAME (+hold) / SOUND / AUDIO RULES
- [ ] **Không có** MUSIC, VO, dialogue, tên riêng, tên thương hiệu, con số, chữ cần hiển thị
- [ ] TEXT BAN + character lock (chỉ ngoại hình) + style lock có mặt
- [ ] Thứ tự ref: sheet → first frame → last frame
- [ ] MOTION đã rà realism; mỗi cảnh 1 chuyển động máy
- [ ] Độ dài cảnh khớp bảng CUES (Giai đoạn 3)

---

## Bổ sung cho quảng cáo Thinking School
- TEXT BAN mở rộng: không "Thinking School", "Thinking Uni", "MBA", giá, ngày, URL, QR, logo trong prompt. Màn hình/hologram: "abstract glowing shapes, no text, no letters, no numbers, no UI labels".
- Không tả nhân vật bằng tên hay tuổi dạng số ("Linh 24" từng bị vẽ thành chữ trong hình).
- Kết prompt bằng AUDIO RULES (SFX only) như trên.
