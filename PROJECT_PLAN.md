# 🏠 DỰ ÁN: Hệ Thống Web Dự Đoán Giá Bất Động Sản Việt Nam

**Môn học:** Phát triển Hệ thống Thông minh — Học viện Bưu chính Viễn thông (PTIT)  
**Đề số:** 2 — Dự đoán Giá (Regression)  
**Deadline:** Chiều thứ 5, ngày 07/05/2026

---

## 1. TỔNG QUAN ĐỀ TÀI

### Mục tiêu
Xây dựng một hệ thống web cho phép người dùng nhập thông số căn nhà (diện tích, số phòng ngủ, quận/huyện, hướng nhà...) và nhận về **giá dự đoán bằng VNĐ** từ mô hình Machine Learning.

### Điểm nổi bật (so với các nhóm khác)
- **Tự crawl dữ liệu thực** từ batdongsan.com.vn (không dùng dataset có sẵn)
- **Kiến trúc Multi-Model:** Tách riêng model Chung cư và Nhà đất (thay vì 1 model chung) — cải thiện độ chính xác đáng kể
- So sánh **4 thuật toán ML** và chọn ra mô hình tốt nhất cho từng loại BĐS
- Giao diện web **hiển thị chi tiết từng căn nhà** như trang BĐS thật

### Quy trình tổng thể (End-to-End Pipeline)

```
[1. CRAWL] → [2. CLEAN & EDA] → [3. TRAIN AI] → [4. TESTING/VALIDATION] → [5. WEB APP]
   (Tài)        (Tài)           (Thái)            (Đức)              (Tài+Đông)
```

---

## 2. NHÓM THỰC HIỆN

| Thành viên | Vai trò | Phụ trách chính |
|---|---|---|
| **Tài** | Leader / Full-stack | Crawl, Clean, EDA, Flask API, Tích hợp hệ thống |
| **Thái** | ML Engineer | Huấn luyện mô hình (×2), Tuning tham số, Export .pkl |
| **Đức** | Validation & Analyst| Kiểm thử mô hình, Phân tích sai số, Viết nội dung báo cáo |
| **Đông** | Frontend Dev | Giao diện Web (HTML/CSS/JS), UI/UX |
| **Mai Anh** | Documentation | Tổng hợp báo cáo, Nghiên cứu lý thuyết, QA |

---

## 3. GIẢI THÍCH CHI TIẾT TỪNG BƯỚC

### BƯỚC 1: CRAWL DỮ LIỆU ✅ (Tài — Hoàn thành)

**Mục đích:** Thu thập dữ liệu thực về giá BĐS tại Hà Nội từ batdongsan.com.vn.

**Cách hoạt động:**
- Dùng thư viện `curl_cffi` (Python) giả lập trình duyệt Chrome để truy cập trang web
- Tự động lật qua từng trang danh sách, vào từng tin đăng, rút thông tin ra
- Mỗi căn nhà cào xong → ghi ngay 1 dòng vào file CSV

**Dữ liệu cào được (25 cột):**

| Nhóm | Các trường | Dùng cho |
|---|---|---|
| **Cốt lõi** | Giá, Diện tích, Số PN | Train AI |
| **Vị trí** | Địa chỉ, Quận/Huyện | Train AI |
| **Kỹ thuật** | Hướng nhà, Hướng BC, Nội thất, Pháp lý, Số tầng, Mặt tiền, Đường vào | Train AI |
| **Hiển thị** | Tiêu đề, Mô tả, Ảnh, Tên dự án, Loại BĐS, Mã tin | Hiện trên Web |

**Kết quả:** 3000 bản ghi (Chung cư 44.3%, Nhà riêng 49.5%, Biệt thự 6.2%)  
**File đầu ra:** `data/raw/raw_data.csv`

---

### BƯỚC 2: LÀM SẠCH & PHÂN TÍCH DỮ LIỆU ✅ (Tài + Đức — Hoàn thành)

> Chi tiết kỹ thuật xem file `DATA_CLEANING_GUIDE.md`

**Phát hiện quan trọng:** Dữ liệu là **Mixed Property Types** — Chung cư và Nhà đất có đặc điểm định giá hoàn toàn khác nhau.

**Quyết định thiết kế:** Tách thành 2 pipeline riêng biệt:
- **Chung cư:** 8 features (area, bedrooms, district, direction, balcony, furniture, legal)
- **Nhà đất:** 10 features (thêm floors, frontage, road_width — không có balcony)

**Các xử lý đã thực hiện:**
1. Dedup bằng `listing_id`
2. Swap 107 dòng lỗi scraper (price ↔ price_per_m2 bị đảo)
3. Parse giá: tỷ, triệu, triệu/m², nghìn (lỗi scraper)
4. Fill bedrooms NaN bằng median theo quận
5. Gom quận hiếm (<30 tin) thành "Khác"
6. Chuẩn hóa nội thất (4 nhóm) và pháp lý (4 nhóm)
7. Fill frontage/road_width/floors bằng median theo quận (chỉ Nhà đất)
8. Lọc outlier: road_width ≤ 50m, bedrooms ≤ 25 (Nhà đất), ≤ 6 (Chung cư)

**File đầu ra:**
- `data/processed/cleaned_chung_cu.csv` — ~1031 dòng × 8 features
- `data/processed/cleaned_nha_dat.csv` — ~1551 dòng × 10 features
- `data/processed/cleaned_full_web.csv` — Tất cả cột, cho web hiển thị
- `notebooks/02_preprocessing.ipynb` — Code tiền xử lý
- `notebooks/01_eda.ipynb` — 5 biểu đồ EDA

---

### BƯỚC 3: HUẤN LUYỆN MÔ HÌNH AI (Thái phụ trách)

**Mục đích:** Train 2 model riêng biệt cho Chung cư và Nhà đất.

**Quy trình:**
1. Đọc file CSV sạch tương ứng (`cleaned_chung_cu.csv` hoặc `cleaned_nha_dat.csv`)
2. Chia dữ liệu: 80% train, 20% test
3. One-Hot Encode các cột categorical: `district`, `direction`, `balcony_direction`, `furniture_std`, `legal_std`
4. Train 4 thuật toán cho **MỖI** loại BĐS:

| # | Thuật toán | Đặc điểm |
|---|---|---|
| 1 | **Linear Regression** | Baseline đơn giản nhất |
| 2 | **Decision Tree** | Chia dữ liệu theo cây quyết định |
| 3 | **Random Forest** | Tập hợp nhiều cây → chính xác hơn |
| 4 | **XGBoost** | Thuật toán mạnh nhất cho bài toán bảng |

5. So sánh bằng: **RMSE**, **MAE**, **R² Score**
6. Chọn model tốt nhất → xuất `.pkl`

> **Lưu ý:** Kiểm tra skewness từ EDA. Nếu skew > 1 → nên dùng `log(price)` khi train.

**File đầu ra:**
- `models/model_chung_cu.pkl` + `models/scaler_chung_cu.pkl`
- `models/model_nha_dat.pkl` + `models/scaler_nha_dat.pkl`
- `notebooks/03_training.ipynb`

---

### BƯỚC 4: XÂY DỰNG WEB (Tài + Đông phụ trách)

**Kiến trúc:**
```
Người dùng (Chrome)
    ↓ Chọn loại BĐS + Nhập thông số
    ↓
[Frontend - HTML/CSS/JS]  ←→  [Backend - Flask API]
                                    ↓
                          Loại = Chung cư? → Load model_chung_cu.pkl
                          Loại = Nhà đất?  → Load model_nha_dat.pkl
                                    ↓
                          Trả về: Giá dự đoán (tỷ VNĐ)
```

**Phân công:**

| Người | Làm gì |
|---|---|
| **Đông** | Code HTML/CSS giao diện (form nhập, trang kết quả, biểu đồ Chart.js) |
| **Tài** | Code Flask API (`/predict`), load model, điều hướng đúng model theo loại BĐS |

**Các trang web:**
- Trang chủ: Form nhập thông số + hiển thị kết quả dự đoán
- Dashboard: Biểu đồ phân tích dữ liệu (giá theo quận, phân phối giá...)
- About: Giới thiệu nhóm và đề tài

---

### BƯỚC 5: BÁO CÁO (Mai Anh phụ trách chính, Tài review)

**Cấu trúc báo cáo 7 chương:**

| Chương | Nội dung | Ai viết |
|---|---|---|
| 1 | Tổng quan: Đặt vấn đề, mục tiêu, phân công | Mai Anh |
| 2 | Cơ sở lý thuyết: ML, Regression, 4 thuật toán | Mai Anh |
| 3 | Thu thập & Tiền xử lý dữ liệu (kèm biểu đồ EDA) | Đức → Mai Anh tổng hợp |
| 4 | Xây dựng & Đánh giá mô hình (bảng so sánh) | Thái → Mai Anh tổng hợp |
| 5 | Phát triển hệ thống Web | Đông + Tài → Mai Anh tổng hợp |
| 6 | Kết quả & Demo (screenshot) | Mai Anh |
| 7 | Kết luận & Hướng phát triển | Tài + Mai Anh |

---

## 4. CẤU TRÚC THƯ MỤC DỰ ÁN

```
house-price-prediction/
├── PROJECT_PLAN.md             # File này — Kế hoạch tổng thể
├── DATA_CLEANING_GUIDE.md      # Hướng dẫn kỹ thuật tiền xử lý
├── requirements.txt            # Thư viện Python cần cài
├── data/
│   ├── crawl/crawler.py        # Code cào dữ liệu (Tài)
│   ├── raw/raw_data.csv        # Dữ liệu thô (3000 dòng)
│   └── processed/              # Dữ liệu đã làm sạch
│       ├── cleaned_chung_cu.csv
│       ├── cleaned_nha_dat.csv
│       └── cleaned_full_web.csv
├── notebooks/
│   ├── 01_eda.ipynb            # Phân tích EDA (5 biểu đồ)
│   ├── 02_preprocessing.ipynb  # Code tiền xử lý (chạy để tạo CSV)
│   └── 03_training.ipynb       # Train model (Thái)
├── models/                     # Model AI đã train
│   ├── model_chung_cu.pkl
│   ├── model_nha_dat.pkl
│   ├── scaler_chung_cu.pkl
│   └── scaler_nha_dat.pkl
├── app/app.py                  # Flask Backend (Tài)
├── templates/                  # HTML (Đông)
├── static/css/ js/ images/     # CSS/JS (Đông)
└── docs/report.pdf             # Báo cáo (Mai Anh)
```

---

## 5. TIMELINE CHI TIẾT (14 NGÀY)

### TUẦN 1: DATA + ML (23/4 → 29/4)

| Ngày | Tài (Leader) | Thái (ML) | Đức (Data) | Đông (FE) | Mai Anh (Docs) |
|---|---|---|---|---|---|
| **T5 23/4** | ✅ Setup GitHub, crawl | Setup môi trường Python | Clone repo | Phác thảo wireframe UI | Tạo Google Docs, viết mục lục |
| **T6 24/4** | ✅ Crawl 3000 tin, Clean, EDA | Review data | Tìm hiểu cách test model | Code layout HTML/CSS | Viết Chương 1 |
| **T7 25/4** | Review & hỗ trợ | Bắt đầu train model CC | Chuẩn bị kịch bản test | Code form nhập liệu | Viết Chương 2 (2.1, 2.2) |
| **CN 26/4** | Setup Flask API cơ bản | Train model NĐ | Nghiên cứu Error Analysis | Code JS gọi API | Viết Chương 2 (thuật toán) |
| **T2 27/4** | Review code team | ✅ Train xong 4 algo × 2 model | **Bắt đầu Test Model** | Thêm Chart.js | Viết Chương 3 |
| **T3 28/4** | ✅ Tích hợp 2 model vào web | ✅ Export .pkl | **Báo cáo kết quả Test** | Polish UI | Viết Chương 4 |
| **T4 29/4** | ✅ Web chạy E2E, demo | Fix bugs model | Viết phân tích cho báo cáo | Responsive design | Tổng hợp feedback |

### TUẦN 2: TÍCH HỢP + BÁO CÁO (30/4 → 6/5)

| Ngày | Tài | Thái | Đức | Đông | Mai Anh |
|---|---|---|---|---|---|
| **T5 30/4** | Fix bugs web | Thêm comments notebook | Export biểu đồ PNG | Dashboard page | Viết Chương 5 |
| **T6 1/5** | Chụp screenshot gửi MA | Viết nội dung ML cho báo cáo | Viết nội dung data cho báo cáo | Polish cuối | ✅ Bản nháp 7 chương |
| **T7 2/5** | Sửa báo cáo + format | Viết README.md | Kiểm tra biểu đồ | — | Format báo cáo đẹp |
| **CN 3/5** | Testing toàn diện | Test 10 trường hợp | Test 10 trường hợp | Test 10 trường hợp | Ghi kết quả test |
| **T2 4/5** | ✅ Báo cáo final PDF | Clean code | — | — | ✅ Export PDF |
| **T3 5/5** | Chuẩn bị Q&A | Ôn phần ML | Ôn phần Data | Ôn phần Web | Ôn phần lý thuyết |
| **T4 6/5** | ✅ Tổng duyệt cả nhóm | Tổng duyệt | Tổng duyệt | Tổng duyệt | Tổng duyệt |

### 🎯 THỨ 5, 7/5: BÁO CÁO
- **Sáng:** Cả nhóm review lần cuối
- **Chiều:** Báo cáo trước giảng viên

---

## 6. TECH STACK

| Layer | Công nghệ |
|---|---|
| Crawl Data | Python, curl_cffi, BeautifulSoup |
| ML / AI | scikit-learn, XGBoost, pandas, numpy |
| Visualization | matplotlib, seaborn, Chart.js |
| Backend | Flask (Python) |
| Frontend | HTML, CSS, JavaScript |
| Notebook | Jupyter |
| Version Control | Git + GitHub |

---

## 7. CÂU HỎI GIẢNG VIÊN CÓ THỂ HỎI

| Câu hỏi | Ai trả lời |
|---|---|
| Tại sao chọn đề tài giá nhà? | Tài |
| Dữ liệu lấy từ đâu, crawl thế nào? | Tài |
| Tại sao phải tách 2 model riêng biệt? | Tài / Đức (dùng biểu đồ EDA chứng minh) |
| Tiền xử lý dữ liệu ra sao? Missing values? | Đức |
| Tại sao XGBoost tốt hơn Linear Regression? | Thái |
| R² Score, RMSE nghĩa là gì? | Mai Anh |
| Feature nào quan trọng nhất? | Thái hoặc Đức |
| Hạn chế của hệ thống? Hướng phát triển? | Tài |
| Web dùng công nghệ gì? | Đông |

---

## 8. QUY TẮC LÀM VIỆC NHÓM

1. **Commit code lên GitHub mỗi ngày** — Tài check hàng ngày
2. **Ai bị stuck phải báo group chat NGAY** — không tự ôm
3. **Họp nhanh 15 phút mỗi tối** — check tiến độ
4. **Deadline nội bộ sớm hơn 2 ngày** — có buffer sửa lỗi
5. **Mỗi người phải hiểu phần mình** — sẵn sàng trả lời GV
