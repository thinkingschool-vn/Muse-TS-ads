# Giai đoạn 6 — Generate video từng cảnh

## Mục đích
Biến mỗi mega prompt thành 1 clip, rồi **đo** (không tự khai) chất lượng trước khi dựng.

## Bước 0 — Quyết định kiểu nối cho từng mối nối
Ghi vào STORY.md/CUES cho mỗi ranh giới cảnh N → N+1:

| Kiểu | Khi nào | Cách làm | Ngưỡng QC (SSIM) |
|---|---|---|---|
| **MATCH** | Hành động liên tục (cùng không gian, cùng nhân vật) | **Chain**: dùng frame cuối THẬT của clip N làm first frame clip N+1 | ≥ 0,75 |
| **CUT** | Đổi cảnh/không gian/cỡ cảnh rõ rệt | Generate song song; cỡ cảnh khác nhau ≥ 2 bậc (wide ↔ close-up) | < 0,25 |
| **TRANSITION** | Đổi thời gian/không gian, cần mềm | Generate song song; dựng bằng xfade (fade, dissolve…) | — |

> ⚠️ Vùng **0,25–0,75 = jump cut**: hai khung "gần giống nhưng lệch" — tệ hơn cả cắt hẳn. Phim Thinking Uni dính lỗi này: định match-cut nhưng model trôi khỏi last-frame.

## Câu lệnh
```bash
/opt/hatch/bin/media-generation --media-subagent-output-type video \
  --orientation <landscape | vertical> \
  --image-file <character-sheet-1.webp> \
  --image-file <first-frame.png> \
  --last-frame-image <K-last-frame.webp> \
  --output-dir <project>/videos \
  --timeout-secs 600 \
  "<mega prompt của cảnh>"
```
- `--orientation`: **vertical** nếu khóa 9:16, **landscape** nếu 16:9. Không để mặc định.
- Character sheet LUÔN đứng trước frame.
- Đổi tên file ngay: `videos/c3-think.mp4`.

### Chain cho mối nối MATCH (tuần tự, không song song)
```bash
python scripts/qc.py lastframe videos/c2-door.mp4 keyframes/c3-first-real.png
# rồi dùng keyframes/c3-first-real.png làm --image-file first frame của c3
```
Các cảnh nối CUT/TRANSITION vẫn chạy song song để tiết kiệm thời gian.

## Verify (bắt buộc, có số đo)
```bash
python scripts/qc.py clips videos/c1.mp4 videos/c2.mp4 ... --aspect 9:16 --out qc_clips
```
Script kiểm tra:
1. Tỷ lệ khung hình, thời lượng từng clip.
2. **Lời nói lạ trong tiếng gốc** (cần `pip install faster-whisper`) — có lời = FAIL.
3. Cháy sáng / flash.
4. SSIM từng mối nối + ảnh ghép `qc_clips/boundaries.jpg`.

Rồi tự xem thêm (script không làm được):
5. **On-model:** nhân vật chính *và phụ* (kính, râu, tóc, trang phục) khớp sheet ở frame đầu/giữa/cuối.
6. **Chữ lạ:** soi poster, màn hình, sách, hologram — có chữ không được duyệt = render lại.

Gửi user: **ảnh boundaries.jpg + bảng kết quả qc_report.md**, không chỉ câu "đã kiểm tra kỹ".

## Xử lý khi FAIL
| Lỗi | Cách sửa |
|---|---|
| Có lời nói lạ | Render lại với AUDIO RULES rõ hơn; nếu vẫn còn → khi dựng `sfx.keep=false` |
| Jump cut ở mối MATCH | Chain lại clip N+1 từ frame cuối thật; hoặc đổi thành CUT/TRANSITION |
| Chữ lạ | Tìm từ gây rò trong prompt (tên, brand, số) → xóa → render lại |
| Lệch nhân vật | Siết character lock (thêm chi tiết dễ trôi: kính, râu…), sheet đứng đầu ref |
| Flash/cháy sáng | Trim bỏ đoạn đó bằng in/out khi dựng; không đặt chữ lên |

Đừng sửa 1 clip quá 2–3 lần — nếu vẫn lệch, quay lại sửa mega prompt.

---

## Bổ sung cho quảng cáo Thinking School
- Chỉ sinh clip cho bản master. Bản 30s/15s tái dùng clip master qua `trim` — không sinh thêm.
- Thêm tỷ lệ khác: chạy lại từ Giai đoạn 4 với ref đúng tỷ lệ mới; tái dùng BRIEF, SCRIPT, VO, nhạc.
- `qc.py clips … --aspect 1:1` được hỗ trợ.
