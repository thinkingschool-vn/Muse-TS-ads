# Thiết kế: Muse-TS-ads v2 — Phong cách video + Hook 3 giây

## 1. Mục tiêu
Nâng cấp skill `Muse-TS-ads` theo ba hướng:
- Cho phép **chọn phong cách video** (drama, góc máy điện ảnh, hoạt hình, motion graphics).
- Có **hệ thống hook 3 giây đầu** dựa trên bằng chứng (Meta/Nielsen, Google ABCD).
- Có **QC tự động** để chặn lỗi hook, lỗi thoại và chồng tiếng.

Nghiên cứu nền: artifact `research_hook_styles.md` (hội thoại 2026-10-06). Phần cốt lõi được chép vào `references/11-styles-and-hooks.md`.

## 2. Các quyết định đã chốt
| Hạng mục | Quyết định |
|---|---|
| Thoại drama | Model video tự tạo thoại khớp khẩu hình. Câu thoại viết sẵn nguyên văn trong prompt, mỗi clip 1 người nói, tối đa 15 từ. Có QC thoại |
| Phong cách v1 | `cinematic-drama`, `micro-drama`, `warm-3d` (mặc định, giữ look hiện tại), `motion-graphics`. Phóng sự / trailer / tối giản để sau |
| Hook A/B | Mặc định 3 bản hook / quảng cáo, chỉnh được 1–5 |
| Nhãn AI | Không gắn trong video. Checklist đăng bài nhắc bật nhãn AI trên nền tảng; mẫu nhãn theo Luật 134/2025/QH15 ⚠ cần pháp chế xác nhận |
| Người | Luôn vẽ cách điệu (stylized 3D chất lượng điện ảnh); bối cảnh, ánh sáng và vật thể có thể photoreal |
| Kiến trúc | Hướng 2: phong cách là cấu hình JSON, kèm công cụ, QC và tài liệu. Đã loại hai hướng: (1) chỉ viết tài liệu — không kiểm tra được; (3) mỗi phong cách một skill — trùng lặp nhiều |

## 3. Phong cách (`styles/*.json`)
Mỗi file có các trường bắt buộc:
- `id`, `name`, `use_when`
- `look`: khối tiếng Anh chèn vào đầu prompt clip
- `camera_allowed[]`, `camera_forbidden[]`
- `shot_len`: [min, max] giây
- `hook_min_shots`: số shot tối thiểu trong 0–5s, ≥1
- `hook_types[]`: id trong thư viện hook
- `transitions[]`: tập con của các chuyển cảnh `assemble.py` hỗ trợ
- `grade_arc`, `music_brief`, `vo_brief`
- `dialogue`: bool
- `humans`: luôn là `"stylized"`

Giá trị dự kiến:

| id | hook_min_shots | dialogue | transitions |
|---|---|---|---|
| cinematic-drama | 2 | true | cut, fade, whip, flash, zoompunch |
| micro-drama | 2 | true | cut, whip, zoompunch, flash |
| warm-3d | 1 | false | cut, fade, fadewhite, dissolve, slideup |
| motion-graphics | 3 | false | cut, whip, zoompunch, flash, slideup |

**`adslib.py`**
- `load_style(id_or_none)`: `None` → `warm-3d`. Thiếu trường, sai kiểu hoặc `humans` khác `stylized` → `AdsError` báo bằng tiếng Việt.
- `list_styles()`
- `style_prompt_block(style)`: trả về text gồm `STYLE:` (look), `CAMERA ALLOWED:`, `CAMERA FORBIDDEN:` và `HUMANS: stylized 3D characters, never photoreal humans`.

**`scripts/styles.py`** (CLI)
- `list`
- `show <id>`: in luật dễ đọc
- `prompt <id>`: in đúng `style_prompt_block`

**edit.json:** thêm `"style": "<id>"` (tuỳ chọn, mặc định `warm-3d`). `assemble.py` kiểm tra:
- chuyển cảnh của từng cảnh phải nằm trong `transitions` của phong cách, sai thì báo lỗi;
- cảnh có `dialogue` mà phong cách có `dialogue: false` thì báo lỗi.

**Tuỳ chọn cảnh `"punch": 1.0–1.5`:** sau khi scale/crop về khung, phóng to thêm hệ số này rồi crop giữa, để tạo shot cận hơn từ cùng clip. Ngoài khoảng 1.0–1.5 thì báo lỗi.

## 4. Hook 3 giây
**Luật** (ghi trong `11-styles-and-hooks.md` và được QC kiểm tra):
1. Khung hình 0 có chuyển động và có chủ thể. Không fade-in hay logo ở đầu.
2. Cắt cảnh đầu ≤ 2,5s. Số shot trong 0–5s ≥ `hook_min_shots`.
3. Trong 0–3s có overlay chữ hook (5–8 từ) và âm thanh bắt đầu trong ≤ 0,5s.
4. Thương hiệu trong 5s đầu: logo góc hoặc tên thương hiệu trong lời. Logo sting vẫn ở khoảng giây 10.

**Thư viện 12 loại hook.** Mỗi loại ghi: khung hình đầu, mẫu câu mở, mẫu chữ, rủi ro, có hợp với hoạt hình không. Các id:
- `in-medias-res`, `cold-open`, `pattern-interrupt`, `why-question`, `bold-claim`, `stop-doing`
- `pov-pain`, `curiosity-gap`, `before-after`, `direct-address`, `callout`, `stat-shock`

Tài liệu cũng có khung micro-drama theo nhịp 15/30/60s và cách đọc hook rate.

**`hook_variants` trong edit.json** (tuỳ chọn): danh sách 1–5 phần tử, mỗi phần tử có:
- `id`: chữ/số, duy nhất
- `type`: thuộc thư viện hook
- `scenes[]`: mọi cảnh có `block: "HOOK"`
- `vo[]`, `overlays[]`: chỉ được gắn `scene` vào cảnh của chính bản đó

Xử lý (`adslib.apply_hook_variant(edit, variant)`, hàm thuần):
- Bỏ mọi cảnh HOOK của master cùng VO/overlay gắn vào chúng.
- Chèn cảnh của bản hook vào đầu, nối thêm VO/overlay của bản hook.
- Tên output thêm hậu tố `_hook<id>`.
- Master không có cảnh HOOK, có VO/overlay dùng `at` trỏ vào vùng HOOK, hoặc dữ liệu bản hook sai luật → báo lỗi tiếng Việt.

`assemble.py edit.json`:
- Nếu có `hook_variants` thì dựng lần lượt từng bản, mỗi bản có timeline riêng.
- `--hook <id>` chỉ dựng một bản.

`cutdown.py`:
- Giữ `hook_variants`. `trim` theo bản trong cảnh hook vẫn được áp dụng.

## 5. Thoại drama
**`05-mega-prompts.md`** thêm khối dùng cho clip có thoại:
```
DIALOGUE: <Tên> (<mô tả ngắn>, <cảm xúc>) says in Vietnamese: "<câu nguyên văn>"
AUDIO RULES: only <Tên> speaks; no other voices; no music; room tone + SFX only.
```
Luật kèm theo:
- Mỗi clip 1 người nói, tối đa 15 từ.
- Trung cảnh hoặc cận vừa, máy đứng yên hoặc dolly chậm.

**Cảnh có thoại trong edit.json:** `"dialogue": {"speaker": "…", "text": "…"}`, nhập tay. Khi dựng (`assemble.py`):
- `text` quá 15 từ → lỗi.
- Có VO nào trùng thời gian (từ lúc bắt đầu đến lúc kết thúc file VO) với cảnh thoại → lỗi.
- Tiếng gốc của cảnh thoại dùng `dialogue_gain_db` (mặc định 0 dB) thay cho `sfx.gain_db`.
- Nhạc được duck theo cả VO lẫn tiếng cảnh thoại.
- Thoại được ghi vào `<output>.vo.txt` theo đúng thứ tự thời gian.
- Timeline ghi thêm `dialogue` cho cảnh.

**QC thoại (`qc.py final --ad`):** với mỗi cảnh có `dialogue` trong timeline:
- Whisper nghe đoạn `[start, end]` của cảnh đó.
- So với `text` bằng bộ so khớp có hiểu số (đã có sẵn).
- Độ phủ dưới 0,8 → FAIL "thoại sai/thiếu".
- Số từ nghe được lớn hơn 1,5 × số từ kịch bản → FAIL "thừa lời / giọng lạ".
- `QC_NO_WHISPER=1` → SKIP.

## 6. Chuyển cảnh mới + QC hook
**Chuyển cảnh mới** trong `assemble.py`, viết tên trong `transition` như các loại sẵn có:

| Tên | Thực hiện | Mặc định |
|---|---|---|
| `whip` | xfade `hblur` (đã kiểm tra có trong ffmpeg 8.1) | 0,2s |
| `zoompunch` | xfade `zoomin` | 0,15s |
| `flash` | xfade `fadewhite` | 0,12s |

Tiếng gốc được crossfade như các chuyển cảnh hiện có.

**Timeline** ghi thêm: `style`, `hook_variant` (id hoặc null), `overlays` (start/end/text), `vo` (start/end), `logo_bug` (khoảng thời gian hiện).

**QC hook** (`qc.py final --ad`, áp dụng cho mọi file quảng cáo):

| Kiểm tra | Cách đo | Mức |
|---|---|---|
| Cắt cảnh đầu ≤ 2,5s | `detect_cuts`, kết hợp ranh giới cảnh trong timeline | FAIL |
| Số shot 0–5s ≥ `hook_min_shots` | số cut < 5s + 1 | FAIL |
| Khung 0 không đen/tĩnh | độ sáng trung bình khung 0 > ngưỡng VÀ khác biệt khung 0 với khung 0,5s > ngưỡng | FAIL |
| Overlay trong 0–3s | timeline `overlays` | FAIL |
| Âm thanh bắt đầu ≤ 0,5s | `silencedetect` (−40 dB) trên audio cuối | FAIL |
| Thương hiệu trong 5s | logo_bug hiện trước 5s, HOẶC tên thương hiệu (brand.json) có trong lời VO/thoại bắt đầu trước 5s | WARN |

Báo cáo QC có thêm mục "Hook 3s".

## 7. Tài liệu
- `SKILL.md`:
  - Thêm bước chọn phong cách trong BRIEF.
  - Bước chiến lược viết 3 bản hook.
  - Bước prompt chèn `styles.py prompt`.
- Cập nhật `00-brief`, `01-ad-strategy`, `05-mega-prompts`, `08-assembly-and-cutdown`, `09-qc`.
- Thêm mới `11-styles-and-hooks.md`.
- `templates/BRIEF.md`: thêm trường phong cách.
- `templates/edit.example.json`: thêm ví dụ `style`, `hook_variants`, `dialogue`, `punch`.
- `templates/AD_COPY.md`: thêm checklist nhãn AI.

## 8. Kiểm thử
pytest, chỉ dùng stdlib và ffmpeg. Phạm vi:
- nạp/kiểm phong cách (đúng và sai);
- `style_prompt_block`;
- `styles.py` CLI;
- `apply_hook_variant` (thay đúng cảnh, VO và overlay; các lỗi);
- chặn VO trùng thoại, chặn thoại quá 15 từ;
- kiểm chuyển cảnh theo phong cách;
- `punch` (render thật);
- 3 chuyển cảnh mới (render thật bằng clip giả);
- assemble xuất ra N file hook;
- từng mục QC hook (FAIL/PASS);
- QC thoại với `QC_NO_WHISPER` và với bộ so khớp chữ.

Kiểm tra tài liệu: mọi cờ CLI được nhắc trong tài liệu phải có thật.

82 test hiện có phải tiếp tục xanh.

## 9. Ngoài phạm vi
- Ba phong cách còn lại (phóng sự, trailer, tối giản).
- Gắn nhãn AI trong video.
- Người photoreal.
- Tự động gọi model video.
- Tự đo hook rate từ nền tảng.
