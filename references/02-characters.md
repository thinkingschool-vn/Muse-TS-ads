# Giai đoạn 1 — Character Sheets (Khóa nhân vật)

## Mục đích
Tạo "chứng minh thư" hình ảnh cho từng nhân vật. Từ đây về sau, mọi ảnh/video đều phải nạp sheet này để nhân vật không bị lệch (on-model).

## ⚠️ Tỷ lệ khung hình (từ Giai đoạn 0)
Character sheet PHẢI vẽ đúng tỷ lệ đã khóa — 16:9 hay 9:16. Sheet không chỉ là tham chiếu style/nhân vật, nó còn định hình trực tiếp output video. Dán STRICT ASPECT RATIO LOCK vào prompt. CLI: 16:9 → `--orientation landscape`; 9:16 → `--orientation vertical`.

## Prompt mẫu (dùng cho từng nhân vật, prompt tiếng Anh)
```
Character reference sheet, [16:9 landscape | 9:16 vertical] orientation,
stylized 3D feature-animation look (or: soft hand-drawn 2D look — chọn 1 và giữ nguyên cả dự án),
clean rounded shapes, warm cinematic lighting.
STRICT ASPECT RATIO LOCK: the sheet MUST be exactly [16:9 | 9:16]. This sheet
will directly condition video output framing — no other ratio is acceptable.
Character: [NGOẠI HÌNH CHI TIẾT: độ tuổi bằng chữ ("in her mid-twenties"), giới tính,
tóc, mắt, trang phục từng món, màu sắc chính xác, phụ kiện, đặc điểm nhận dạng]
Show: front view, side view, back view, 3/4 view, plus 3 expression close-ups
(happy, sad, determined). Same outfit and colors in every view, consistent
proportions. Plain soft neutral background.
TEXT BAN: no text, no names, no labels, no numbers, no logos, no watermark.
```

> ⛔ **Không** đưa vào prompt hình: tên nhân vật, tuổi bằng số, tên hãng/studio ("Disney", "Pixar"). Dự án Thinking Uni: model vẽ chữ "Disney/PIXAR" lên clip và nhãn "Linh 24" lên hologram. Tên nhân vật chỉ dùng trong tài liệu (STORY.md), không dùng trong prompt.

## Quy trình
1. Viết mô tả nhân vật thật cụ thể (màu áo, kiểu tóc, phụ kiện). Với nhân vật **phụ** cũng phải khóa các chi tiết dễ trôi: kính (kiểu gọng), râu (có/không, độ dài), kiểu tóc. Hỏi user chốt mô tả trước khi vẽ.
2. Generate bằng CLI (orientation theo tỷ lệ đã khóa):
   ```
   /opt/hatch/bin/media-generation --media-subagent-output-type image \
     --orientation <vertical | landscape> --output-dir <project>/character_sheets \
     "<prompt trên>"
   ```
3. Kiểm tra: đúng tỷ lệ (ffprobe), các góc đồng nhất trang phục/màu sắc, **không có chữ**. Chưa đạt → sửa prompt, vẽ lại.
4. Ghi lại phong cách thực tế của sheet (2D hay 3D) — style lock ở các giai đoạn sau phải mô tả đúng phong cách này.
5. Lưu sheet với tên rõ ràng: `linh-sheet-9x16.webp`, `thay-an-sheet-9x16.webp`...

## Checklist trước khi sang giai đoạn 2
- [ ] Mỗi nhân vật (chính + phụ có thoại/xuất hiện nhiều) có sheet riêng đúng tỷ lệ đã khóa
- [ ] Mô tả nhân vật đã được user chốt (không đổi giữa chừng)
- [ ] Sheet đủ các góc nhìn + biểu cảm, nền trơn, không chữ
- [ ] Đã ghi phong cách thực tế (2D/3D) để dùng cho style lock

---

## Bổ sung cho quảng cáo Thinking School
- **Không có dàn nhân vật cố định.** Mỗi quảng cáo tạo nhân vật mới theo **persona trong BRIEF**: độ tuổi, nghề, cấp bậc (Staff/Senior/Manager/Leader), bối cảnh Việt Nam (văn phòng, nhà, quán cà phê, thư viện).
- Tối đa 2 nhân vật chính (người học + mentor nếu cần). Bản 15–30s ưu tiên 1 nhân vật.
- Trang phục/đạo cụ phản ánh persona; có 1 **đạo cụ nhận dạng** dễ thấy ở khung nhỏ.
- **Không** đưa vào prompt: tên nhân vật, tuổi dạng số, tên thương hiệu, chữ trên áo/đồ vật. Tả tuổi bằng chữ: "a woman in her mid-twenties".
- Không vẽ logo Thinking School lên áo/đồ vật — logo chỉ qua thẻ `brand_cards.py` và logo góc.
- Đa dạng, tôn trọng; nhân vật trông như người Việt Nam ngoài đời.
