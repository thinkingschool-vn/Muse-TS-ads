# Bài học xương máu (từ dự án "The Last Lantern")

Đọc trước khi bắt đầu pipeline mới. Mỗi bài học dưới đây đều đã "trả giá" bằng giờ generate lại.

## 1. Chốt kịch bản trước, vẽ sau
Đổi 1 chi tiết kịch bản sau khi đã generate = làm lại keyframes + video của mọi cảnh liên quan. STORY.md phải được user duyệt cứng (giai đoạn 2) rồi mới vẽ. Không có "sửa nhỏ thôi".

## 2. Mô tả nhân vật càng chi tiết, càng ít lệch
"Chàng trai mặc áo xanh" sẽ cho ra 8 phiên bản áo xanh khác nhau. "Blue double-breasted keeper's jacket with gold buttons and gold trim, brown trousers, brown boots" mới khóa được. Màu sắc + từng món đồ phải có tên gọi cụ thể trong character lock.

## 3. Character sheet luôn đứng đầu danh sách ref
Thứ tự nạp ref ảnh hưởng trực tiếp đến độ on-model. Sheet nhân vật trước, keyframe sau. Đảo thứ tự là nhân vật bắt đầu "trôi".

## 4. Realism: kiểm tra từng động từ trong MOTION
Bài học lớn nhất dự án: user phát hiện prompt viết "thắp đèn" trong khi đèn còn khung kính đóng kín — phi thực tế. Từ đó mọi prompt đều phải trả lời: "ngoài đời nó diễn ra đúng như vậy không?" Mở cửa kính → châm bấc → đóng cửa. Gió dập lửa → xé đèn giấy / lửa chập chờn trong housing rung. Viết prompt như một đạo diễn hiểu vật lý, không phải nhà thơ.

## 5. Match-cut miễn phí nhưng phải thiết kế từ đầu
Last frame N = first frame N+1 nghe đơn giản, nhưng chỉ hoạt động khi keyframes được vẽ đúng luật từ giai đoạn 3. Không thể "fix ở khâu dựng" — dựng chỉ nối, không tạo được continuity.

## 6. Đừng generate lại 1 clip quá 3 lần
Nếu clip vẫn lệch sau 2–3 lần thử, vấn đề nằm ở mega prompt (MOTION mơ hồ, thiếu character lock, hoặc yêu cầu phi thực tế), không phải ở may rủi. Quay lại sửa prompt.

## 7. Kiểm tra audio gốc trước khi mix
Đừng giả định clip generate ra là im lặng. Có clip mang sẵn tiếng gió/nhạc nền — xóa đi thì phí, giữ lại thì phải duck dưới VO. Quyết định này cần dữ kiện từ ffprobe, không phải từ suy đoán.

## 8. Normalize trước khi nối, không bao giờ nối trước normalize
Trộn clip 1248×704 với 1280×720 trong 1 lệnh concat = lỗi hoặc méo hình. Chuẩn hóa tất cả về cùng độ phân giải/fps/codec trước.

## 9. VO là gia vị, không phải món chính
Phim 80 giây chỉ cần ~45 giây VO. Khoảng lặng cho hình ảnh và nhạc thở mới là thứ khiến VO đắt giá. Cảnh đỉnh cảm xúc: cho moment tự lên tiếng, VO rút lui. *(Quảng cáo khác: VO phủ 70–85% — xem `09-ads-mode.md`.)*

## 10. Đặt tên file có ý nghĩa từ ngày đầu
`scene1-fading-light.mp4` chứ không phải `media-generation-...-uuid.mp4`. Đến lúc có 30+ file trong folder, bạn sẽ cảm ơn chính mình.

## 11. Khóa tỷ lệ khung hình từ câu hỏi đầu tiên
16:9 hay 9:16 không phải chuyện "để sau tính" — nó quyết định toàn bộ ref đầu vào. Một character sheet vẽ 16:9 đem đi generate video 9:16 sẽ cho ra bố cục vỡ. Hỏi và khóa ngay ở Giai đoạn 0, dán STRICT ASPECT RATIO LOCK vào mọi prompt.

---

# Bài học từ quảng cáo "Thinking Uni" (60s, 9:16) — xem `examples/thinking-uni/POSTMORTEM.md`

## 12. Có chữ "VO"/lời thoại trong prompt video = nhân vật tự nói
Prompt video có `VO: "..."` và `MUSIC:` → model sinh lời + nhạc riêng cho từng clip. Kết quả: nhân vật nói câu ngoài kịch bản (*"Chúng ta cùng nhau, học hỏi và chia sẻ kiến thức nhé!"*, *"We did it together."*) đè lên VO TTS. Prompt video chỉ có SFX + "No music. No dialogue. No narration."

## 13. Mỗi clip một bài nhạc = phim có 6 bài nhạc
Nhạc đổi đột ngột mỗi 10 giây, hụt tiếng 1,3s ở mối nối. Cả phim dùng **1 bài nhạc** đặt ở khâu dựng.

## 14. Làm âm thanh trước, hình sau
VO đặt cứng "+1s mỗi cảnh" cho ra nhịp đọc kiểu máy và chỗ chết 3 giây. Thu VO trước → đo → chia cảnh theo VO (bảng CUES).

## 15. "Gần giống" ở mối nối tệ hơn "khác hẳn"
Định match-cut nhưng model trôi khỏi last-frame → jump cut (SSIM 0,33). Mối nối nào cũng phải chọn rõ: MATCH thật (chain từ frame cuối thật) hoặc CUT hẳn (đổi cỡ cảnh) hoặc chuyển cảnh mềm.

## 16. Model in ra chữ nó đọc được trong prompt
"Disney/Pixar" → chữ "Disney/PIXAR" trên 3 clip; "Linh, 24" → nhãn "Linh 24" trên hologram; tường "ghi chữ học phí" → chữ lạ. Prompt hình không chứa tên riêng, tên hãng, con số; mọi chữ là overlay khi dựng.

## 17. Đừng tự khai QC
Agent báo "match-cut liền mạch, on-model" mà không đo; thực tế 5/5 mối nối lệch, flash cháy sáng đúng lúc hiện "100% MIỄN PHÍ". Mỗi báo cáo phải kèm số đo + ảnh từ `scripts/qc.py`.

## 18. Câu quan trọng nhất phải nghe rõ nhất
Câu CTA "ra mắt ngày 11 tháng 10" bị nhạc + tiếng gốc nuốt mất (nhận dạng ra *"…mắc kệ mũi thằng Mùi"*). CTA: câu riêng, đọc chậm, số viết bằng chữ, nhạc hạ sâu, kiểm tra round-trip.

## 19. Chuẩn loudness của nền tảng
Phim ra −26,3 LUFS — nghe lí nhí trên điện thoại so với video khác (≈ −14). Luôn loudnorm về −14 LUFS (assemble.py làm sẵn).

---

## Bài học riêng cho quảng cáo Thinking School
20. **Sự thật trước, sáng tạo sau:** mọi giá/ngày/con số có nguồn trong BRIEF; số liệu website thay đổi → đọc lại trang mỗi lần.
21. **Logo/giá/QR không bao giờ do AI vẽ** — sai một ký tự là hỏng quảng cáo. Dùng brand_cards.py.
22. **Viết kịch bản theo block từ đầu** — nếu không, bản 30s/15s phải viết và thu VO lại.
23. **VO mỗi block đứng độc lập** — không từ nối trỏ sang block khác.
24. **Bản 15s cần câu CTA tự nói ngày/ưu đãi** vì thẻ giá thường bị bỏ.
25. **Tỷ lệ khác = chạy lại từ keyframe** — không crop 9:16 thành 16:9.
26. **Chữ "g" xanh của logo chìm trên nền xanh** — thẻ dùng nền tối #0B1020 → #1E1B4B.
27. **Whisper ghi số bằng chữ số** — qc.py tự quy đổi; vẫn nghe lại câu CTA trên loa điện thoại.
