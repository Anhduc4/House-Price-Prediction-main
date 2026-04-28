# Phân Tích & Đánh Giá Dự Án: House Price Prediction (Dự Đoán Giá Bất Động Sản)

Chào bạn, với góc nhìn của một kỹ sư phần mềm chuyên nghiệp, mình đã xem qua tài liệu (`PROJECT_PLAN.md`, `DATA_CLEANING_GUIDE.md`) và mã nguồn backend (`app/app.py`) của nhóm. 

**Nhận xét tổng quan:** 
Dự án của các bạn có một cấu trúc rất mạch lạc, quy trình thực hiện rõ ràng (từ Crawl -> Clean -> Train -> Web E2E). Việc nhóm phát hiện ra vấn đề "Mixed Property Types" và quyết định tách thành 2 luồng xử lý riêng biệt cho Chung cư và Nhà đất là một điểm sáng cực kỳ chuyên nghiệp (nhiều sinh viên hay mắc lỗi gộp chung để train).

Tuy nhiên, để dự án hoàn thiện hơn, chuẩn "industry-level" hơn và đạt điểm tuyệt đối trước hội đồng, mình có một số câu hỏi gợi ý để nhóm suy nghĩ và cải thiện:

---

### 1. Kiến trúc & Tích hợp Model (Training-Serving Skew)
Trong file `app.py`, bạn Tài có để lại comment: 
`TODO: Cần transform data này giống y hệt cách Đức làm trong file Tiền xử lý`

Đây là một "cái bẫy" rất phổ biến khi đưa AI lên Web, được gọi là **Training-Serving Skew** (sự sai lệch giữa lúc train và lúc chạy thực tế). Nếu backend tự code tay lại các bước chuẩn hóa (ví dụ: chuyển tên quận thành One-Hot Encoding, fillna), rất dễ xảy ra sai sót.

❓ **Câu hỏi cho bạn:** 
1. Thay vì export scaler và model riêng rẽ rồi để Backend code lại logic transform, Thái (ML) có thể sử dụng `sklearn.pipeline.Pipeline` kết hợp `ColumnTransformer` để đóng gói toàn bộ quy trình (từ Imputer, Scaler, OneHotEncoder đến XGBoost/RandomForest) vào chung **1 file .pkl duy nhất** được không? Việc này giúp Tài (Backend) chỉ cần gọi đúng 1 lệnh `pipeline.predict(raw_data)` là xong, không lo sai lệch logic.
2. File model (đặc biệt là Random Forest) có thể khá nặng. Nhóm đã có cơ chế load model 1 lần duy nhất lúc khởi động app (Singleton) thay vì load mỗi khi có người gọi API `/predict` chưa?

### 2. Xử lý Edge Cases & Data Validation
Việc crawl data đã làm sạch được outlier, nhưng trên Web, người dùng có thể nhập những thông tin vô lý.

❓ **Câu hỏi cho bạn:**
1. Trong file xử lý data, nhóm gom các quận ít tin đăng thành nhóm `"Khác"`. Trên giao diện Frontend, nếu người dùng chọn một quận không có trong danh sách train, backend sẽ báo lỗi hay tự động map nó thành `"Khác"` để model vẫn chạy được?
2. Backend (app.py) đã có cơ chế Validate đầu vào chưa? Ví dụ: người dùng cố tình nhập diện tích là số âm (`-50`), hoặc nhập số phòng ngủ lên tới `1000`, API có chặn lại và trả về lỗi `400 Bad Request` với message thân thiện không?

### 3. Khía cạnh Giao diện (Frontend)
❓ **Câu hỏi cho bạn:**
1. Các danh sách chọn lựa (Dropdown) như: Quận/Huyện, Hướng nhà, Loại nội thất... trên Web sẽ được fix cứng (hardcode) trong HTML hay sẽ được gọi qua một API từ Backend để đảm bảo đồng bộ 100% với dữ liệu lúc Train model?
2. Sau khi có kết quả dự đoán (ví dụ: 3.5 Tỷ), trang web có hiển thị thêm các thông tin phân tích để thuyết phục người dùng không? (Ví dụ: "Giá trung bình tại quận này là X", hoặc một biểu đồ Chart.js nhỏ cho thấy mức giá này cao hay thấp hơn mặt bằng chung).

### 4. Triển khai & Demo (Deployment)
Báo cáo sẽ ấn tượng hơn rất nhiều nếu giảng viên có thể dùng điện thoại truy cập thẳng vào trang web thay vì chỉ xem demo trên localhost.

❓ **Câu hỏi cho bạn:**
1. Nhóm đã có kế hoạch deploy ứng dụng này lên Cloud chưa? (Gợi ý: Dùng **Render** hoặc **Railway** cho backend Flask, và **Vercel** hoặc **GitHub Pages** cho giao diện Frontend tĩnh).
2. Nếu deploy, môi trường server miễn phí thường có RAM giới hạn (512MB). Việc load file Pickle lớn có thể gây tràn RAM, nhóm đã kiểm tra kích thước file `.pkl` sinh ra chưa? (Lưu ý: XGBoost thường sinh ra file model nhẹ hơn Random Forest rất nhiều).

---
**💡 Gợi ý bước tiếp theo:** 
Bạn hãy chia sẻ các câu hỏi này vào group chat của nhóm để Tài, Thái, Đức và Đông cùng thảo luận nhé. Nếu bạn cần mình code mẫu phần `sklearn Pipeline` để đồng bộ ML và Backend, hoặc viết logic Validate cho file `app.py`, cứ thoải mái yêu cầu mình!
