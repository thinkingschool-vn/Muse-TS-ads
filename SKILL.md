---
name: "thinking_school_ads"
description: "Skill làm video quảng cáo hoạt hình cho khoá học, chương trình, seminar, ưu đãi của Thinking School trên Muse AI: đọc link khoá học → BRIEF có nguồn, chiến lược theo loại sản phẩm, kịch bản theo BLOCK, nhân vật mới theo chân dung học viên, audio-first, keyframes, mega prompt chỉ SFX, generate + QC clip, thẻ thương hiệu render bằng ffmpeg (logo, giá, QR Zalo, end card), dựng bản master rồi tự cắt 30s/15s, QC quảng cáo có số đo, caption đăng bài. Dùng khi user muốn làm video quảng cáo/giới thiệu sản phẩm giáo dục của Thinking School."
---

# Thinking School Ads (Muse AI)

Từ **link khoá học** → **3 video quảng cáo** cùng tỷ lệ (master + 30s + 15s) + caption đăng bài, tất cả đã qua QC có số đo.
Dựa trên pipeline "Muse animated short film v2" (audio-first, 1 nhạc nền, không chữ do AI vẽ, QC đo đạc), chuyên biệt cho thương hiệu Thinking School.

## 4 luật nền (vi phạm = làm lại)
1. **Sự thật trước:** mọi tên, giá, ngày, con số trong quảng cáo phải có trong `BRIEF.md` kèm nguồn. Thiếu → ghi `⚠ cần xác nhận` và hỏi user. Không tự bịa, không dùng số cũ.
2. **Âm thanh 3 lớp:** clip video chỉ mang SFX; 1 bài nhạc cho mọi bản; 1 track VO. Prompt video không chứa MUSIC / VO / lời thoại.
3. **Không chữ do AI vẽ:** logo, giá, QR, link, mọi chữ là thẻ `scripts/brand_cards.py` hoặc overlay của `scripts/assemble.py`. Prompt hình/video không chứa tên riêng, tên hãng, con số.
4. **Đo, không tự khai:** báo "đạt" phải kèm `qc_report.md` từ `scripts/qc.py`.

## Giai đoạn 0 — Đầu vào (bắt buộc, hỏi trước mọi thứ)
1. **Link** khoá học / chương trình / sự kiện.
2. **Tỷ lệ:** 9:16 (Reels/TikTok/Shorts) · 16:9 (YouTube/web) · 1:1 (Facebook feed).
3. **Độ dài master:** 60s (mặc định) hoặc 30s. Bản 30s/15s **tự cắt** từ master, cùng tỷ lệ.
   Muốn tỷ lệ khác → chạy lại từ Giai đoạn 4 với ref đúng tỷ lệ mới (AI video không đổi tỷ lệ sau khi sinh được); tái dùng BRIEF, kịch bản, VO, nhạc.
4. **Nền tảng** chạy quảng cáo (ảnh hưởng vùng an toàn và caption).

Sau đó đọc trang, lập BRIEF theo `references/00-brief.md` (mẫu `templates/BRIEF.md`), hỏi các trường ⚠, chờ user duyệt.

**STRICT ASPECT RATIO LOCK** — dán nguyên văn vào mọi prompt ảnh/video:
> The final output video MUST be **[9:16 vertical | 16:9 landscape | 1:1 square — chọn 1]**. All reference images — character sheets, keyframes, first-frame and last-frame images — MUST share this exact aspect ratio. Any reference image with a mismatched aspect ratio MUST be regenerated or cropped before use. NEVER mix aspect ratios within a single project.

CLI `media-generation`: 9:16 → `--orientation vertical`; 16:9 → `--orientation landscape`; 1:1 → nếu không có tuỳ chọn vuông, sinh 16:9 với chủ thể ở giữa (xem `references/04-keyframes.md`).

## Workflow
Làm đúng thứ tự; kết thúc mỗi giai đoạn đưa user duyệt kèm bằng chứng.

| # | Giai đoạn | Hướng dẫn | Đầu ra |
|---|---|---|---|
| 0 | Brief | `references/00-brief.md` | `BRIEF.md` đã duyệt (có nguồn, must_say) |
| 1 | Chiến lược + kịch bản BLOCK | `references/01-ad-strategy.md` | `SCRIPT.md` + ước tính thời lượng 60/30/15 |
| 2 | Nhân vật mới theo persona | `references/02-characters.md` | character sheets đúng tỷ lệ, không chữ |
| 3 | Âm thanh trước | `references/03-audio-first.md` | VO từng block, 1 bài nhạc, bảng CUES |
| 4 | Keyframes | `references/04-keyframes.md` | keyframe theo CUES, kiểu nối từng mối |
| 5 | Mega prompt | `references/05-mega-prompts.md` | `MEGA_PROMPTS.md` chỉ SFX, TEXT BAN |
| 6 | Generate + QC clip | `references/06-video-generation.md` | clip đạt `qc.py clips` |
| 7 | Thẻ thương hiệu | `references/07-brand-cards.md` | `cards/logo.mp4`, `cards/price.mp4`, `cards/end.mp4` |
| 8 | Dựng master + cắt 30/15 | `references/08-assembly-and-cutdown.md` | 3 file MP4 |
| 9 | QC + giao | `references/09-qc.md` | 3 `qc_report.md` + `AD_COPY.md` |

Đọc trước khi bắt đầu: `references/10-lessons.md`, `brand/BRAND_GUIDE.md`, `brand/LEXICON.md`.

## Brand kit
`brand/brand.json` (màu, font, logo, QR, hotline), `brand/logo-on-dark.png`, `brand/logo-on-light.png`, `brand/zalo-qr.png`, `brand/fonts/BeVietnamPro-Bold.ttf`. Mặc định lấy từ website — có file gốc mới thì thay file, giữ tên.

## Scripts (Python 3.8+, ffmpeg ≥ 6.1 có libass; `faster-whisper` tuỳ chọn)
```bash
python scripts/brand_cards.py end_card --aspect 9:16 --cta "Đăng ký ngay" --link "..." --out cards/end.mp4
python scripts/assemble.py edit.json --plan
python scripts/assemble.py edit.json
python scripts/cutdown.py edit.json --render
python scripts/qc.py clips videos/c1.mp4 videos/c2.mp4 --aspect 9:16
python scripts/qc.py final out/ts-<slug>-9x16-60s.mp4 --aspect 9:16 --ad --duration 60 --end-card cards/end.mp4 --script out/ts-<slug>-9x16-60s.vo.txt --must-say "..."
```
Script chi tiết: `scripts/brand_cards.py`, `scripts/assemble.py`, `scripts/cutdown.py`, `scripts/qc.py` (dùng chung `scripts/adslib.py`, `scripts/vi_numbers.py`). Mẫu: `templates/edit.example.json`, `templates/BRIEF.md`, `templates/AD_COPY.md`.

## Output contract
- `BRIEF.md` (có nguồn từng dòng), `SCRIPT.md` (block, VO hiển thị + TTS input, overlay, bản)
- `character_sheets/`, `keyframes/`, `MEGA_PROMPTS.md`, `videos/` (đã qua `qc.py clips`)
- `audio/` (VO từng block + 1 bài nhạc), `cards/` (3 thẻ)
- `edit.json`, `edit_30.json`, `edit_15.json`
- `out/ts-<slug>-<9x16|16x9|1x1>-{60,30,15}s.mp4` + `.timeline.json` + `.vo.txt`
- `qc_60/`, `qc_30/`, `qc_15/` (`qc_report.md`, `boundaries.jpg`)
- `AD_COPY.md`

## Operating rules
1. Giai đoạn 0 bắt buộc; BRIEF chưa duyệt thì chưa viết kịch bản.
2. Kịch bản viết theo BLOCK ngay từ đầu; VO mỗi block đứng độc lập.
3. Mỗi quảng cáo tạo nhân vật mới theo persona; không vẽ logo/chữ lên nhân vật hay đồ vật.
4. Âm thanh 3 lớp; prompt video kết thúc bằng AUDIO RULES (SFX only).
5. Mọi cảnh trong `edit.json` có `id` + `block`; VO/overlay gắn `scene` + `offset`.
6. Logo, giá, QR, link chỉ qua `brand_cards.py`; giá ưu đãi luôn kèm hạn.
7. Dựng bằng `assemble.py`, cắt bằng `cutdown.py` — không viết tay lệnh ffmpeg nối/mix.
8. QC từng bản với `--ad`; bản nào FAIL thì chưa giao; còn WARN thì nói rõ.
9. Không "nhất / số 1 / duy nhất" nếu không có bằng chứng trong BRIEF.
10. Mọi con số báo user (thời lượng, LUFS, độ phân giải) lấy từ output tool, không đoán.
