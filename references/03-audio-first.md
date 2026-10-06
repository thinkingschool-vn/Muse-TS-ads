# Giai đoạn 3 — Âm thanh trước (VO + nhạc) → CUES

> **Vì sao làm âm thanh TRƯỚC hình?** Ở phim Thinking Uni, mỗi clip tự sinh nhạc + lời riêng, VO TTS đặt cứng "+1s mỗi cảnh" → 6 bài nhạc nối nhau, nhân vật tự nói câu ngoài kịch bản đè lên VO, câu CTA ngày ra mắt gần như không nghe ra. Làm VO + nhạc trước, đo thời lượng thật, rồi mới chia cảnh → hình đi theo tiếng, không còn chồng chéo.

## Kiến trúc âm thanh 3 lớp (BẮT BUỘC)

| Lớp | Nguồn | Quy tắc |
|---|---|---|
| ① SFX | Tiếng gốc của clip video | Prompt video **chỉ** mô tả tiếng động; cấm nhạc, cấm lời. Khi dựng để nhỏ (≈ −14 dB). Clip có lời lạ → render lại hoặc `sfx.keep=false` |
| ② Nhạc | **1 bài duy nhất** cho cả phim | Không lời, dài ≥ phim + 3s, fade in/out. Không bao giờ dùng nhạc riêng của từng clip |
| ③ VO | TTS (hoặc user thu) | Mỗi câu 1 file, đặt theo CUES; không câu nào chồng câu nào |

`scripts/assemble.py` tự hạ nhạc + SFX khi có lời (sidechain ducking) và chuẩn hóa về −14 LUFS.

## Bước 1 — Viết VO_SCRIPT.md với "ngân sách âm tiết"

Tốc độ đọc tiếng Việt tự nhiên ≈ **4–4,5 âm tiết/giây** (quảng cáo năng động tối đa ~5).

| Loại phim | VO phủ bao nhiêu thời lượng | Ví dụ 10s/cảnh |
|---|---|---|
| Phim kể chuyện | 50–60% | ≤ 25 âm tiết/cảnh |
| Quảng cáo | 70–85% | ≤ 35 âm tiết/cảnh |

- Đếm âm tiết từng câu (tiếng Việt: 1 chữ = 1 âm tiết). Vượt ngân sách → rút gọn câu, **không** đọc nhanh hơn.
- Câu quan trọng nhất (CTA, ngày, giá) đọc **chậm hơn** (~3,5 âm tiết/s) và để riêng 1 câu.

Template mỗi câu:
```markdown
## VO-03 — cảnh c3 "THINK"
**Hiển thị:** Học liệu mở quốc tế, được chắt lọc và bản địa hóa.
**TTS input:** Học liệu mở quốc tế, được chắt lọc và bản địa hóa.
**Âm tiết:** 13 · **Dự kiến:** ~3,2s · **Direction:** hào hứng, nhấn "quốc tế"
```

## Bước 2 — Từ điển phát âm (lexicon)

TTS tiếng Việt thường đọc sai tên tiếng Anh, số, ký hiệu. **TTS input** khác **Hiển thị**:

| Hiển thị (chữ trên màn hình) | TTS input (gợi ý — phải nghe thử) |
|---|---|
| 11/10 | mười một tháng mười |
| 100% | một trăm phần trăm |
| AI | ây ai |
| app.thinkingschool.vn | *(đừng đọc URL — nói "đường link bên dưới")* |
| Thinking University | thử 2–3 phương án: giữ nguyên tiếng Anh / "Thin-kinh Diu-ni-vơ-si-ti" / thu riêng bằng giọng tiếng Anh rồi ghép |

**Kiểm tra vòng ngược (round-trip):** sau khi TTS, chạy nhận dạng giọng nói trên file VO (VD `faster-whisper`). Nếu máy nghe ra sai tên thương hiệu → người xem cũng dễ nghe sai → đổi TTS input.

## Bước 3 — Thu VO

**Option A: TTS**
```bash
/opt/hatch/bin/tts speak --voice <voice-id> --language vi \
  --output <project>/audio/vo_03.wav --text-stdin <<< "<TTS input>"
```
- Chọn voice trong `/opt/hatch/skills/voice-selector/voice_source.json`; dùng voice bản xứ tiếng Việt.
- Cùng 1 voice cho mọi câu. Truyền text qua `--text-stdin`.
- Đo thời lượng: `ffprobe -v error -show_entries format=duration -of csv=p=0 audio/vo_03.wav`

**Option B: User thu** — đưa VO_SCRIPT.md (cột TTS input) + spec WAV 48kHz, không nhạc nền, 2–3 take/câu.

## Bước 4 — Nhạc nền (1 bài cho cả phim)

1. **Kiểm tra Muse có tạo nhạc không:** chạy `/opt/hatch/bin/media-generation --help` (hoặc xem danh sách tool/skill khả dụng) tìm loại output audio/music.
   - Có → tạo 1 bài: *"instrumental only, no vocals, <mood>, <BPM>, builds at <mốc reveal>, warm resolve at the end, length ≥ <phim + 3>s"*.
   - Không → **xin user tải lên** file nhạc (có quyền sử dụng). Không tự lấy nhạc có bản quyền.
2. Nhạc ≥ thời lượng phim; nếu ngắn hơn assemble.py sẽ lặp (cảnh báo) — tránh.
3. Ghi BPM/mốc nhấn (nếu biết) để đặt chuyển cảnh trùng phách.

## Bước 5 — CUES: chia cảnh theo VO

Cho mỗi cảnh: `độ dài cảnh ≥ offset vào (0,3–0,6s) + độ dài VO + 0,8s đuôi`, tối đa ~10s (giới hạn 1 clip). VO dài hơn → tách 2 cảnh hoặc rút câu.

Ghi vào bảng (nằm trong STORY.md hoặc CUES.md):

| Cảnh | VO | VO dài | Cảnh dài (cần generate) | Overlay |
|---|---|---|---|---|
| c1 | VO-01 | 4,2s | 6s | — |
| c2 | VO-02 | 5,1s | 7s | "Thinking University" |

Bảng này là nguồn sự thật cho keyframes, mega prompt và `edit.json` (VO ghi `"scene": "c2", "offset": 0.4`). Dùng `python scripts/assemble.py edit.json --plan` để xem timeline thực tế sau khi trừ chuyển cảnh.

## Checklist
- [ ] VO_SCRIPT.md: mỗi câu có Hiển thị / TTS input / số âm tiết / direction
- [ ] Mọi tên riêng, số, ngày đã qua lexicon + round-trip nghe ra đúng
- [ ] Đã có 1 file nhạc không lời ≥ thời lượng phim
- [ ] Bảng CUES: mọi cảnh đủ dài cho VO của nó, không câu nào chồng câu nào
- [ ] Đưa user nghe VO + nhạc **trước** khi vẽ keyframe (sửa lời lúc này rẻ nhất)

---

## Bổ sung cho quảng cáo Thinking School
- **VO theo block:** mỗi block 1 file `audio/vo_<block>.wav` (vd `vo_hook.wav`, `vo_brand.wav`, `vo_b1.wav`, `vo_offer.wav`, `vo_cta.wav`). Câu riêng cho bản ngắn: `vo_cta_15.wav` + `"versions": ["15"]`.
- TTS input theo `brand/LEXICON.md`; không đọc URL/hotline.
- Ghi đúng chữ đã đọc vào `"text"` của từng VO trong edit.json → assemble.py xuất `<output>.vo.txt` cho qc.py.
- Đo thời lượng thật từng file VO → bảng CUES theo block; tổng từng bản (60/30/15) phải khớp ngân sách ở `01-ad-strategy.md` trước khi vẽ keyframe.
- Nhạc: 1 bài dài ≥ master + 2s, có điểm nhấn ở logo sting và end card. Bản cắt dùng chung bài nhạc (assemble.py tự fade-out theo độ dài từng bản).
