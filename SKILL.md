---
name: "thinking_school_ads"
description: "Skill làm video quảng cáo hoạt hình cho khoá học, chương trình, seminar, ưu đãi của Thinking School trên Muse AI: đọc link khoá học → BRIEF có nguồn, chiến lược theo loại sản phẩm, kịch bản theo BLOCK, nhân vật mới theo chân dung học viên, audio-first, keyframes, mega prompt chỉ SFX, generate + QC clip, thẻ thương hiệu render bằng ffmpeg (logo, giá, QR Zalo, end card), dựng bản master rồi tự cắt 30s/15s, QC quảng cáo có số đo, caption đăng bài. Có nhiều phong cách (drama điện ảnh, micro-drama, hoạt hình 3D ấm, motion-graphics), hook 3 giây đo được với 3 bản hook A/B, thoại nhân vật cho phong cách drama. Dùng khi user muốn làm video quảng cáo/giới thiệu sản phẩm giáo dục của Thinking School."
---

# Thinking School Ads (Muse AI)

Từ **link khoá học** → **3 video quảng cáo** cùng tỷ lệ (master + 30s + 15s) + caption đăng bài, tất cả đã qua QC có số đo.
Dựa trên pipeline "Muse animated short film v2" (audio-first, 1 nhạc nền, không chữ do AI vẽ, QC đo đạc), chuyên biệt cho thương hiệu Thinking School.

## 4 luật nền (vi phạm = làm lại)
1. **Sự thật trước:** mọi tên, giá, ngày, con số trong quảng cáo phải có trong `BRIEF.md` kèm nguồn. Thiếu → ghi `⚠ cần xác nhận` và hỏi user. Không tự bịa, không dùng số cũ.
2. **Âm thanh 3 lớp:** clip video chỉ mang SFX; 1 bài nhạc cho mọi bản; 1 track VO. Prompt video không chứa MUSIC / VO / lời thoại. **Ngoại lệ duy nhất:** phong cách có thoại (`cinematic-drama`, `micro-drama`) — clip thoại theo khối DIALOGUE ở `references/05-mega-prompts.md` (≤ 15 từ, 1 người nói, không VO đè).
3. **Không chữ do AI vẽ:** logo, giá, QR, link, mọi chữ là thẻ `scripts/brand_cards.py` hoặc overlay của `scripts/assemble.py`. Prompt hình/video không chứa tên riêng, tên hãng, con số.
4. **Đo, không tự khai:** báo "đạt" phải kèm `qc_report.md` từ `scripts/qc.py`.

## Giai đoạn 0 — Đầu vào (bắt buộc, hỏi trước mọi thứ)
1. **Link** khoá học / chương trình / sự kiện.
2. **Tỷ lệ:** 9:16 (Reels/TikTok/Shorts) · 16:9 (YouTube/web) · 1:1 (Facebook feed).
3. **Độ dài master:** 60s (mặc định) hoặc 30s. Bản 30s/15s **tự cắt** từ master, cùng tỷ lệ.
   Muốn tỷ lệ khác → chạy lại từ Giai đoạn 4 với ref đúng tỷ lệ mới (AI video không đổi tỷ lệ sau khi sinh được); tái dùng BRIEF, kịch bản, VO, nhạc.
4. **Nền tảng** chạy quảng cáo (ảnh hưởng vùng an toàn và caption).
5. **Phong cách:** chạy `python scripts/styles.py list`, gợi ý 1 phong cách theo loại sản phẩm (`references/11-styles-and-hooks.md`), user chọn. Mặc định `warm-3d`.

Sau đó đọc trang, lập BRIEF theo `references/00-brief.md` (mẫu `templates/BRIEF.md`), hỏi các trường ⚠ kèm gợi ý tốt nhất, áp dụng cơ chế tự động duyệt sau 5 phút.

**STRICT ASPECT RATIO LOCK** — dán nguyên văn vào mọi prompt ảnh/video:
> The final output video MUST be **[9:16 vertical | 16:9 landscape | 1:1 square — chọn 1]**. All reference images — character sheets, keyframes, first-frame and last-frame images — MUST share this exact aspect ratio. Any reference image with a mismatched aspect ratio MUST be regenerated or cropped before use. NEVER mix aspect ratios within a single project.

CLI `media-generation`: 9:16 → `--orientation vertical`; 16:9 → `--orientation landscape`; 1:1 → nếu không có tuỳ chọn vuông, sinh 16:9 với chủ thể ở giữa (xem `references/04-keyframes.md`).

## Workflow
Làm đúng thứ tự; kết thúc mỗi giai đoạn đưa user duyệt kèm bằng chứng và áp dụng **Cơ chế Chốt duyệt Tự động 5 Phút**.

### Cơ chế Chốt duyệt Tự động 5 Phút (Auto-Approval Protocol)
Để tiến độ sản xuất diễn ra liên tục, không bị đình trệ khi user bận:
1. **Gửi kết quả kèm đề xuất tối ưu:** Kết thúc mỗi giai đoạn (Giai đoạn 0–8), Agent gửi sản phẩm/bằng chứng (bảng BRIEF, kịch bản, ảnh character sheet, audio/CUES, keyframes, mega prompts, video clip, file dựng, báo cáo QC...) và nêu rõ phương án tối ưu được chọn.
2. **Thông báo đếm ngược 5 phút:** Luôn kết thúc tin nhắn bằng câu chốt:
   > *"Em gửi anh [kết quả Giai đoạn X]. Em đề xuất [phương án tối ưu nhất]. Trong vòng 5 phút nếu anh bận hoặc chưa kịp phản hồi, em sẽ tự động duyệt phương án này và tiến hành tiếp Giai đoạn [X+1] nhé ạ!"*
3. **Cơ chế kỹ thuật thực hiện:**
   - **Môi trường có công cụ hẹn giờ (schedule/timer):** Agent lập tức gọi `schedule(DurationSeconds=300, TimerCondition="any", Prompt="Hết 5 phút chờ duyệt Giai đoạn X: Người dùng không phản hồi, tự động duyệt phương án tối ưu và bắt đầu Giai đoạn X+1.")` rồi kết thúc lượt.
     * Nếu trong 5 phút user gửi tin nhắn (bất kỳ nội dung nào), timer tự động hủy, Agent thức dậy và ưu tiên xử lý ý kiến của user.
     * Nếu sau 5 phút không có tin nhắn từ user, timer kích hoạt notification, Agent tự động thức dậy, ghi nhận đã auto-approve sau 5 phút và tự động triển khai tiếp giai đoạn sau.
   - **Môi trường chat thông thường (không có background timer):** Agent không được dừng chờ bị động (không được halt chờ user gõ duyệt mới chạy tiếp). Sau khi gửi thông báo 5 phút, Agent chủ động tiếp tục thực thi giai đoạn tiếp theo theo phương án tốt nhất đã đề xuất.
4. **Quyền can thiệp của User (Human Override):** Bất cứ lúc nào user phản hồi (trong hoặc sau 5 phút), Agent ngay lập tức dừng tiến trình tự động và ưu tiên làm theo yêu cầu chỉnh sửa của user.
5. **Ngoại lệ an toàn:** Duy nhất Giai đoạn 0: chỉ dừng hẳn chờ user khi thiếu thông tin thực tế cốt lõi (link khoá học, giá tiền/ngày tổ chức) mà không thể tra cứu trên web. Khi Agent đã tự tìm thấy và điền đủ thông tin vào BRIEF, vẫn áp dụng nguyên tắc 5 phút tự động chốt để lên kịch bản.

| # | Giai đoạn | Hướng dẫn | Đầu ra |
|---|---|---|---|
| 0 | Brief | `references/00-brief.md` | `BRIEF.md` đã duyệt hoặc tự động chốt sau 5 phút (có nguồn, must_say) |
| 1 | Chiến lược + kịch bản BLOCK | `references/01-ad-strategy.md` | `SCRIPT.md` + 3 bản HOOK A/B/C + ước tính thời lượng 60/30/15 |
| 2 | Nhân vật mới theo persona | `references/02-characters.md` | character sheets đúng tỷ lệ, không chữ |
| 3 | Âm thanh trước | `references/03-audio-first.md` | VO từng block, 1 bài nhạc, bảng CUES |
| 4 | Keyframes | `references/04-keyframes.md` | keyframe theo CUES, kiểu nối từng mối |
| 5 | Mega prompt | `references/05-mega-prompts.md` | `MEGA_PROMPTS.md`: khối `styles.py prompt` ở đầu, chỉ SFX (trừ clip thoại), TEXT BAN |
| 6 | Generate + QC clip | `references/06-video-generation.md` | clip đạt `qc.py clips` |
| 7 | Thẻ thương hiệu | `references/07-brand-cards.md` | `cards/logo.mp4`, `cards/price.mp4`, `cards/end.mp4` |
| 8 | Dựng master + cắt 30/15 | `references/08-assembly-and-cutdown.md` | 3 file MP4 |
| 9 | QC + giao | `references/09-qc.md` | 3 `qc_report.md` + `AD_COPY.md` |

Đọc trước khi bắt đầu: `references/10-lessons.md`, `references/11-styles-and-hooks.md`, `brand/BRAND_GUIDE.md`, `brand/LEXICON.md`.

## Brand kit
`brand/brand.json` (màu, font, logo, QR, hotline), `brand/logo-on-dark.png`, `brand/logo-on-light.png`, `brand/zalo-qr.png`, `brand/fonts/BeVietnamPro-Bold.ttf`. Mặc định lấy từ website — có file gốc mới thì thay file, giữ tên.

## Scripts (Python 3.8+, ffmpeg ≥ 6.1 có libass; `faster-whisper` tuỳ chọn)
```bash
python scripts/styles.py list
python scripts/styles.py prompt cinematic-drama
python scripts/brand_cards.py end_card --aspect 9:16 --cta "Đăng ký ngay" --link "..." --out cards/end.mp4
python scripts/assemble.py edit.json --plan
python scripts/assemble.py edit.json
python scripts/assemble.py edit.json --hook B
python scripts/cutdown.py edit.json --render
python scripts/qc.py clips videos/c1.mp4 videos/c2.mp4 --aspect 9:16
python scripts/qc.py final out/ts-<slug>-9x16-60s.mp4 --aspect 9:16 --ad --duration 60 --end-card cards/end.mp4 --script out/ts-<slug>-9x16-60s.vo.txt --must-say "..."
```
Script chi tiết: `scripts/styles.py`, `scripts/brand_cards.py`, `scripts/assemble.py`, `scripts/cutdown.py`, `scripts/qc.py` (dùng chung `scripts/adslib.py`, `scripts/vi_numbers.py`). Mẫu: `templates/edit.example.json`, `templates/BRIEF.md`, `templates/AD_COPY.md`.

## Output contract
- `BRIEF.md` (có nguồn từng dòng), `SCRIPT.md` (block, VO hiển thị + TTS input, overlay, bản)
- `character_sheets/`, `keyframes/`, `MEGA_PROMPTS.md`, `videos/` (đã qua `qc.py clips`)
- `audio/` (VO từng block + 1 bài nhạc), `cards/` (3 thẻ)
- `edit.json`, `edit_30.json`, `edit_15.json`
- `out/ts-<slug>-<9x16|16x9|1x1>-{60,30,15}s_hook{A,B,C}.mp4` (mỗi bản hook 1 file) + `.timeline.json` + `.vo.txt`
- `qc_60_A/`, `qc_60_B/`… (`qc_report.md`, `boundaries.jpg`)
- `AD_COPY.md`

## Operating rules
1. Giai đoạn 0 bắt buộc; BRIEF được duyệt hoặc tự động chốt sau 5 phút (kèm đề xuất) mới viết kịch bản.
2. Kịch bản viết theo BLOCK ngay từ đầu; VO mỗi block đứng độc lập.
3. Mỗi quảng cáo tạo nhân vật mới theo persona; không vẽ logo/chữ lên nhân vật hay đồ vật.
4. Âm thanh 3 lớp; prompt video kết thúc bằng AUDIO RULES (SFX only).
5. Mọi cảnh trong `edit.json` có `id` + `block`; VO/overlay gắn `scene` + `offset`.
6. Logo, giá, QR, link chỉ qua `brand_cards.py`; giá ưu đãi luôn kèm hạn.
7. Dựng bằng `assemble.py`, cắt bằng `cutdown.py` — không viết tay lệnh ffmpeg nối/mix.
8. QC từng bản với `--ad`; bản nào FAIL thì chưa giao; còn WARN thì nói rõ.
9. Không "nhất / số 1 / duy nhất" nếu không có bằng chứng trong BRIEF.
10. Mọi con số báo user (thời lượng, LUFS, độ phân giải) lấy từ output tool, không đoán.
11. Hook 3 giây theo `references/11-styles-and-hooks.md`; mặc định 3 bản hook trong `hook_variants`; mục "Hook:" trong QC phải PASS.
12. Người luôn vẽ cách điệu; không học viên/giảng viên/lời chứng thực giả; nhắc user bật nhãn AI trên nền tảng khi đăng.
13. Tự động duyệt sau 5 phút: Tại mọi điểm chốt duyệt giai đoạn, nếu sau 5 phút user không có phản hồi thì tự động duyệt phương án tối ưu đã đề xuất và làm tiếp (không dừng chờ bị động).
