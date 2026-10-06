# Giai đoạn 7 — Dựng phim bằng `scripts/assemble.py`

## Mục đích
Nối cảnh, chuyển cảnh, chèn chữ, mix 3 lớp âm thanh và chuẩn hóa loudness **bằng 1 lệnh lặp lại được** — không viết tay lệnh ffmpeg mỗi lần (dễ sai timecode, quên ducking, quên loudness).

## Bước 1 — Viết `edit.json`
Copy `templates/edit.example.json` vào thư mục dự án rồi sửa. Các khối chính:

| Khối | Nội dung |
|---|---|
| `aspect`, `fps` | `"9:16"` → 720×1280, `"16:9"` → 1280×720; 24fps |
| `scenes[]` | `file`, `in`, `out` (cắt bỏ đầu/đuôi lỗi, flash), `transition` sang cảnh kế (`"cut"` hoặc `{type, duration}`) |
| `sfx` | Tiếng gốc clip: `keep`, `gain_db` (mặc định −14). Clip còn lời lạ → `keep: false` |
| `music` | 1 file nhạc cho cả phim: `gain_db`, `fade_in`, `fade_out`, `start_offset` |
| `vo[]` | Mỗi câu: `file` + (`scene` + `offset`) hoặc `at` tuyệt đối. **Script dừng nếu 2 câu chồng nhau** |
| `duck` | Mức hạ nhạc khi có lời (mặc định đã ổn) |
| `font` | File .ttf có dấu tiếng Việt (gợi ý Be Vietnam Pro — Google Fonts) |
| `overlays[]` | `text`, (`scene`+`offset` hoặc `at`), `duration`, `style`, tùy chọn `y` (0..1), `anim` |
| `loudness` | Mặc định −14 LUFS, TP −1,5 dBTP |

Chuyển cảnh xfade hay dùng: `fade`, `dissolve`, `fadeblack`, `smoothup`, `slideleft`, `circleopen`. Tránh `fadewhite` cạnh đoạn đã sáng.

Một clip 10s có thể dùng **2 lần** với in/out khác nhau → nhịp nhanh hơn mà không cần generate thêm.

## Bước 2 — Xem timeline trước khi render
```bash
python scripts/assemble.py edit.json --plan
```
In mốc bắt đầu/kết thúc từng cảnh sau khi trừ chuyển cảnh. Dùng để chỉnh `offset` VO/overlay.

## Bước 3 — Render
```bash
python scripts/assemble.py edit.json
```
Script làm 5 việc:
1. Chuẩn hóa từng cảnh (cắt, scale+crop, fps) — clip không có audio được thêm khoảng lặng.
2. Sinh overlay ASS: font tiếng Việt, viền, fade/pop, **tự kẹp trong vùng an toàn** (9:16: tránh 14% trên, 24% dưới, 14% phải — chỗ UI TikTok/Reels).
3. Nối cảnh + xfade; tiếng gốc crossfade theo.
4. Mix: SFX (nhỏ) + nhạc → **tự hạ khi có lời** (sidechain) → + VO.
5. Loudnorm 2 lượt → MP4 `+faststart`; ghi `<output>.timeline.json` + in cảnh báo (overlay quá ngắn để đọc, nhạc ngắn hơn phim…).

Yêu cầu: Python 3.8+, ffmpeg có `libass` (bản build "full" thường có sẵn).

## Bước 4 — QC bắt buộc
```bash
python scripts/qc.py final final/phim.mp4 --aspect 9:16 --duration 60 --script vo_lines.txt
```
`vo_lines.txt` = mỗi dòng 1 câu VO (bản **Hiển thị**). Xem chi tiết ngưỡng ở `08-qc.md`. Chưa PASS thì chưa giao.

## Lỗi thường gặp
| Thông báo | Sửa |
|---|---|
| `VO CHỒNG NHAU` | Dời `offset`, rút gọn câu, hoặc kéo dài cảnh |
| `out vượt độ dài clip` | Kiểm tra lại thời lượng clip bằng ffprobe |
| Chữ thiếu dấu / sai font | Khai báo `font.file` + `font.name` đúng tên family |
| `No such filter: 'ass'` | ffmpeg thiếu libass → cài bản full |

---

## Bổ sung: quảng cáo Thinking School — master + bản cắt

### Trường edit.json mới
| Trường | Ý nghĩa |
|---|---|
| `"brand": "<skill>/brand/brand.json"` | font + màu style overlay từ brand kit |
| `"version": "60"` | bản đang dựng; lọc item theo `versions`, áp `trim`; QC dùng làm thời lượng đích |
| scene `"id"` + `"block"` | bắt buộc với MỌI cảnh |
| scene `"trim": {"30": {"out": 6}}` | rút ngắn cảnh riêng cho bản 30s/15s |
| item `"versions": ["15"]` | scene/VO/overlay chỉ có ở các bản liệt kê |
| `"cutdowns": {"15": ["HOOK", "ƯU ĐÃI", "CTA"]}` | ghi đè kế hoạch cắt mặc định |
| `"logo_bug": {"logo": "on_dark", "corner": "tr"}` | logo góc; ẩn ở THƯƠNG HIỆU/ƯU ĐÃI/CTA (đổi bằng `skip_blocks`) |
| vo `"text"` | chữ đã đọc → `<output>.vo.txt` cho `qc.py --script` |
| `"aspect": "1:1"` | 720×720 (ngoài 9:16 và 16:9) |

VO/overlay **phải** gắn `scene` + `offset` (không dùng `at`), nếu không cutdown.py báo lỗi. Mẫu: `templates/edit.example.json`.

### Quy trình
```powershell
python scripts/assemble.py edit.json --plan     # timeline + block từng cảnh
python scripts/assemble.py edit.json            # master
python scripts/cutdown.py edit.json             # edit_30.json + edit_15.json + ước tính thời lượng
python scripts/cutdown.py edit.json --render    # tạo + dựng luôn 2 bản cắt
```
Mặc định: 30s = HOOK → THƯƠNG HIỆU → LỢI ÍCH-1 → ƯU ĐÃI → CTA; 15s = HOOK → THƯƠNG HIỆU → CTA.
Lệch > ±1,5s → chỉnh `trim` (cắt cảnh AI, không cắt thẻ) rồi chạy lại. VO chồng nhau sau trim → assemble.py dừng; rút `out` ít hơn hoặc dùng câu VO riêng cho bản ngắn.

### Đặt tên file
`out/ts-<slug>-<9x16|16x9|1x1>-<60|30|15>s.mp4` — cutdown.py tự đổi đuôi `-60s`.
