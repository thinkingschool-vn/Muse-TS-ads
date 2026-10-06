# Giai đoạn 7 — Thẻ thương hiệu (`scripts/brand_cards.py`)

Logo, giá, QR, link, hotline **không bao giờ** để AI vẽ. Thẻ render bằng ffmpeg từ `brand/` → đúng chữ, đúng màu, đủ dấu tiếng Việt, đúng vùng an toàn của từng tỷ lệ.

| Thẻ | Block trong edit.json | Mặc định | Nội dung |
|---|---|---|---|
| `logo_sting` | THƯƠNG HIỆU | 1,4s | logo chữ trắng + tagline |
| `price_card` | ƯU ĐÃI | 3,0s | nhãn, giá gốc gạch ngang, giá bán (vàng), hạn ưu đãi |
| `end_card` | CTA | 4,5s | logo, CTA (vàng), dòng phụ, link, QR Zalo, hotline |

## Lệnh
```powershell
python scripts/brand_cards.py logo_sting --aspect 9:16 --out cards/logo.mp4
python scripts/brand_cards.py price_card --aspect 9:16 --original "1.600.000đ" --price "1.200.000đ" --deadline "Ưu đãi đến hết 15/10" --out cards/price.mp4
python scripts/brand_cards.py price_card --aspect 9:16 --label "Học bổng" --price "100% MIỄN PHÍ" --out cards/price.mp4
python scripts/brand_cards.py end_card --aspect 9:16 --cta "Đăng ký ngay" --sub "Ra mắt 11/10" --link "app.thinkingschool.vn/thinking-uni" --out cards/end.mp4
```
Tuỳ chọn: `--duration`, `--tagline`, `--no-tagline`, `--label`, `--hotline`, `--no-qr`, `--brand`.

## Luật
- Chữ trên thẻ lấy nguyên văn từ BRIEF (giá giữ định dạng "1.200.000đ").
- Có giá gốc → bắt buộc `--deadline` (script từ chối nếu thiếu).
- CTA ≤ 4 từ; ngày/ưu đãi để ở `--sub`. Chữ dài tự thu nhỏ; dài quá mức → lỗi "tràn vùng an toàn" → rút gọn.
- Link hiển thị bỏ "https://". VO không đọc link.
- Thẻ có track âm thanh câm; nhạc + VO phủ lên ở khâu dựng.
- Render xong phải **nhìn** frame cuối (dấu tiếng Việt, gạch ngang giá, QR rõ):
  `ffmpeg -sseof -0.3 -i cards/end.mp4 -update 1 cards/end.png`
- Đổi tỷ lệ = render lại thẻ với `--aspect` mới.
