# Giai đoạn 4 — Keyframes (Khung hình chốt)

## Mục đích
Vẽ trước các "cột mốc" hình ảnh: first frame và last frame của từng cảnh. Có keyframes rồi thì video chỉ việc "đi từ A đến B".

## Quy trình
1. Từ STORY.md + bảng CUES, liệt kê keyframe cho từng cảnh và **kiểu nối** của từng mối (MATCH / CUT / TRANSITION — xem `06-video-generation.md`).
   - Mối **MATCH**: last frame cảnh N = first frame cảnh N+1 (cùng 1 file). Khi generate, first frame của N+1 sẽ được thay bằng frame cuối *thật* của clip N.
   - Mối **CUT/TRANSITION**: mỗi cảnh có keyframe đầu/cuối riêng; cỡ cảnh hai bên nên khác hẳn nhau (wide ↔ close-up) để tránh jump cut.
2. Generate từng keyframe, **nạp character sheet trước**:
   ```bash
   /opt/hatch/bin/media-generation --media-subagent-output-type image \
     --orientation <vertical | landscape> \
     --image-file <path/character-sheet.webp> \
     --output-dir <project>/keyframes \
     "<style lock + TEXT BAN + character lock (ngoại hình) + mô tả keyframe>"
   ```
3. Cảnh sẽ có overlay chữ (ads) → yêu cầu luôn trong prompt: *"leave clean empty space in the upper third for later titles"*.
4. Kiểm tra từng keyframe:
   - Đúng tỷ lệ đã khóa (ffprobe).
   - Nhân vật chính **và phụ** khớp sheet (kính, râu, tóc, trang phục).
   - **Không có chữ** — kể cả chữ "nhìn cũng hợp". Có chữ = vẽ lại.
5. Đặt tên rõ: `k1-walls.webp`, `k2-light-crack.webp`...

## Checklist
- [ ] Đủ keyframe cho mọi cảnh; mỗi mối nối đã gán MATCH / CUT / TRANSITION
- [ ] Mối MATCH: last N và first N+1 là CÙNG MỘT FILE
- [ ] Nhân vật khớp sheet; không có chữ/logo/nhãn lạ
- [ ] Tất cả đúng tỷ lệ đã khóa ở Giai đoạn 0
- [ ] (Ads) Shot có overlay đã chừa khoảng trống cho chữ

---

## Bổ sung cho quảng cáo Thinking School
- Keyframe chỉ cho cảnh câu chuyện. Logo sting, thẻ giá, end card **không** vẽ bằng AI (Giai đoạn 7).
- Cảnh có overlay: yêu cầu "leave clean empty space in the upper third" (9:16) hoặc "in the left third" (16:9).
- 1:1: nếu công cụ không sinh khung vuông, vẽ 16:9 với chủ thể ở chính giữa, chừa ~22% mỗi bên (assemble.py crop giữa về 1:1).
- Cảnh ngay trước end card kết thúc tĩnh/nhẹ để cắt sang thẻ không giật.
