# Muse-TS-ads — Skill làm video quảng cáo Thinking School trên Muse AI

Từ **link khoá học** → 3 video quảng cáo hoạt hình cùng tỷ lệ (**60s + 30s + 15s**), thẻ thương hiệu chính xác (logo, giá, QR Zalo, end card) và caption đăng bài — mọi bản đều qua QC có số đo.

- Tỷ lệ: 9:16 · 16:9 · 1:1 (mỗi lần chạy 1 tỷ lệ)
- Loại sản phẩm: khoá lẻ, Master Series, chương trình chuyên sâu (Mini MBA…), seminar, miễn phí (Thinking Uni), membership/ưu đãi
- Dựa trên pipeline Muse animated short film v2 (audio-first, 1 nhạc nền, không chữ do AI vẽ, −14 LUFS)

## Cài đặt
- Python 3.8+ (không cần thư viện ngoài cho scripts)
- ffmpeg ≥ 6.1 có libass trong PATH (Windows: `winget install Gyan.FFmpeg`)
- Tuỳ chọn: `pip install faster-whisper` (kiểm tra lời VO), `pip install pytest` (chạy test)

## Dùng trên Muse AI
Nạp thư mục này làm skill; mở đầu bằng: *"Làm video quảng cáo cho khoá <link>, tỷ lệ 9:16"*. Muse đi theo `SKILL.md`: BRIEF → kịch bản block → nhân vật → âm thanh → keyframe → video → thẻ thương hiệu → dựng + cắt → QC.

## Phong cách + hook 3 giây (v2)
- `python scripts/styles.py list` — 4 phong cách: `warm-3d` (mặc định), `cinematic-drama`, `micro-drama`, `motion-graphics`.
- `edit.json`: `"style"`, `"hook_variants"` (3 bản A/B/C → 3 file `_hookA/B/C`), cảnh `"punch"`, `"dialogue"`, chuyển cảnh `whip` / `zoompunch` / `flash`.
- `qc.py final --ad` có thêm mục **Hook:** (cắt cảnh đầu, số shot, khung hình 0, chữ, âm thanh, thương hiệu) và kiểm tra thoại.
- Chi tiết: `references/11-styles-and-hooks.md`.

## Cấu trúc
```
SKILL.md        quy trình điều phối
brand/          brand.json, logo, QR Zalo, font, LEXICON (cách đọc), BRAND_GUIDE (luật nội dung)
references/     00-brief … 11-styles-and-hooks
scripts/        styles.py · brand_cards.py · assemble.py · cutdown.py · qc.py · adslib.py · vi_numbers.py
templates/      BRIEF.md · AD_COPY.md · edit.example.json
examples/       thinking-uni-launch (chạy thử end-to-end)
tests/          pytest
```

## Cập nhật brand kit
Thay file trong `brand/` (giữ nguyên tên) hoặc sửa `brand/brand.json` (màu, hotline, tagline). Logo mặc định lấy từ website — nên thay bằng file gốc độ phân giải cao.

## Kiểm thử
```powershell
$env:PYTHONIOENCODING="utf-8"; python -m pytest
```

## Tác giả & giấy phép
Pipeline gốc: Đặng Hữu Sơn (Muse animated short film). Bản chuyên biệt Thinking School: Thinking School. MIT — xem `LICENSE`. Font Be Vietnam Pro: SIL OFL (`brand/fonts/OFL.txt`).
