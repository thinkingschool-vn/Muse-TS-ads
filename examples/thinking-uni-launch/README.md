# Ví dụ: Thinking Uni — ra mắt 11/10 (9:16, 60/30/15s)

Chạy thử toàn bộ khâu dựng của skill bằng 6 clip và 6 câu VO lấy từ bản quảng cáo v1.
Media không đưa lên git — tự đặt clip vào `media/` (c1–c6.mp4, vo_01–06.wav, music.wav) rồi chạy:

```powershell
python ..\..\scripts\brand_cards.py logo_sting --aspect 9:16 --out cards/logo.mp4
python ..\..\scripts\brand_cards.py price_card --aspect 9:16 --label "Học bổng" --price "100% MIỄN PHÍ" --out cards/price.mp4
python ..\..\scripts\brand_cards.py end_card --aspect 9:16 --cta "Đăng ký ngay" --sub "Ra mắt 11/10" --link "app.thinkingschool.vn/thinking-uni" --duration 5 --out cards/end.mp4
python ..\..\scripts\assemble.py edit.json
python ..\..\scripts\cutdown.py edit.json --render
python ..\..\scripts\qc.py final out/ts-thinking-uni-9x16-60s.mp4 --aspect 9:16 --ad --duration 60 --end-card cards/end.mp4 --out qc_60
```

## Kết quả đo (lần chạy 2026-10-06)
| Bản | Thời lượng | LUFS | True peak | Kết luận QC |
|---|---|---|---|---|
| 60s | 60.02s | −14.5 | −1.4 dBFS | ⚠️ WARN (0 FAIL) |
| 30s | 30.02s | −14.7 | −1.4 dBFS | ✅ PASS |
| 15s | 15.02s | −15.4 | −1.3 dBFS | ✅ PASS |

Khối block: 60s = HOOK → VẤN ĐỀ → THƯƠNG HIỆU → LỢI ÍCH-1/2/3 → BẰNG CHỨNG → ƯU ĐÃI → CTA; 30s = HOOK → THƯƠNG HIỆU → LỢI ÍCH-1 → ƯU ĐÃI → CTA; 15s = HOOK → THƯƠNG HIỆU → CTA. End card khớp file thẻ: SSIM 1.00 cả 3 bản.

**WARN còn lại (bản 60s):**
- *Cháy sáng/flash trắng* 40.2–41.4s — nằm sẵn trong clip c5 của v1. Overlay "CONTRIBUTE" đã dời sang sau đoạn flash (`offset` 2.6). Làm quảng cáo thật: sinh lại cảnh hoặc cắt bỏ đoạn flash.

**Lưu ý về media mẫu:** clip c5/c6 là đoạn cắt từ phim v1 nên có sẵn chữ cũ ("100% MIỄN PHÍ", "RA MẮT 11/10") — đó là chữ của v1, không phải do skill vẽ. Clip AI thật của skill không được chứa chữ (luật nền số 3).
Câu VO của v1 không có file chữ nên ví dụ không chạy `--script` / `--must-say`; quảng cáo thật phải ghi `"text"` cho từng VO và truyền must_say trong `BRIEF.md`.
