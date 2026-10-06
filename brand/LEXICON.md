# Từ điển phát âm thương hiệu (Hiển thị ↔ TTS input)

Dùng khi viết VO_SCRIPT: cột **TTS input** là chữ đưa vào máy đọc; cột **Hiển thị** là chữ trên màn hình.
Sau khi thu VO, chạy round-trip (`qc.py final --must-say ...`): whisper phải nghe ra đúng tên và số.

> ⚠ Cách đọc tên tiếng Anh dưới đây là đề xuất — cần Thinking School xác nhận cách đọc chuẩn.
> Nếu giọng TTS đọc tiếng Anh tốt, giữ nguyên tiếng Anh; nếu round-trip sai, dùng phiên âm.

| Hiển thị | TTS input (ưu tiên) | Phiên âm dự phòng | Ghi chú |
|---|---|---|---|
| Thinking School | Thinking School | thinh-kinh xờ-cun | Tên thương hiệu, luôn đọc đủ 2 từ |
| Thinking Uni | Thinking Uni | thinh-kinh diu-ni | Dự án phi lợi nhuận |
| Thinking University | Thinking University | thinh-kinh diu-ni-vơ-xi-ti | |
| Master Series | Master Series | mát-tơ xi-ri | 24 chương trình theo cấp bậc |
| Mini MBA | Mini em-bi-ây | mi-ni em-bi-ây | |
| Master Mindset | Master Mindset | mát-tơ mai-sét | |
| King Of Skills | King of Skills | kinh ọp xkin | |
| AI | ây-ai | trí tuệ nhân tạo | Ưu tiên "trí tuệ nhân tạo" nếu câu cho phép |
| Zalo | Da-lô | Da-lô | |
| 1.200.000đ | một triệu hai trăm nghìn đồng | | Viết số bằng chữ trong TTS input |
| 1.600.000đ | một triệu sáu trăm nghìn đồng | | |
| 11/10 | mười một tháng mười | | Ngày luôn có "tháng" |
| 100% | một trăm phần trăm | | |
| 300+ khoá học | hơn ba trăm khoá học | | Chỉ dùng khi trang hiện tại vẫn ghi số này |
| 60.000+ học viên | hơn sáu mươi nghìn học viên | | Chỉ dùng khi trang hiện tại vẫn ghi số này |
| 5 phút | năm phút | | Microlearning 5 phút/bài |

**Không đọc trong VO:** URL, hotline, email — chỉ hiển thị trên end card. VO nói "link bên dưới" hoặc "quét mã Zalo trên màn hình".
