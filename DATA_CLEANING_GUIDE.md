# 🧹 Hướng Dẫn Làm Sạch & Phân Tích Dữ Liệu BĐS (Data Cleaning Guide)

> **Vai trò:** Data Analyst  
> **Input:** `data/raw/raw_data.csv` — 3000 dòng × 25 cột  
> **Output:** 
> - `data/processed/cleaned_chung_cu.csv` — Data cho Model Chung cư
> - `data/processed/cleaned_nha_dat.csv` — Data cho Model Nhà đất
> - `data/processed/cleaned_full_web.csv` — Data đầy đủ cho Web hiển thị

---

## 📊 1. Kết Quả "Khám Sức Khỏe" Dữ Liệu Thô (3000 dòng)

| Cột | Tỷ lệ có dữ liệu | Trạng thái | Ghi chú |
|---|---|---|---|
| `price` | 100% | ⚠️ Cần xử lý | Có lỗi đảo cột ở 107 dòng. Có 360 dòng `"Thỏa thuận"`. Có 2 dòng lỗi `"nghìn"`. |
| `price_per_m2` | 87% | ❌ **KHÔNG DÙNG** | Gây **Data Leakage** nếu dùng để train model. |
| `area` | 100% | ⚠️ Cần xử lý | Dạng chữ: `"75 m²"`. 1 dòng NaN (rác). |
| `bedrooms` | 80% | ⚠️ Thiếu 591 dòng | Dạng chữ: `"2 PN"`. Fill NaN bằng median theo quận. |
| `direction` | 33% | ⚠️ Thiếu nhiều | 8 hướng. Thiếu 67% -> Fill "Không rõ". |
| `balcony_direction` | 32% | ⚠️ Thiếu nhiều | Thêm vào features của Chung cư. |
| `furniture` | 70% | ⚠️ Cần chuẩn hóa | Quá nhiều biến thể. |
| `legal` | 86% | ⚠️ Cần chuẩn hóa | Quá nhiều biến thể. |
| `address` | 100% | ✅ Rất tốt | Cấu trúc chuẩn: `"Hà Nội - Quận - Loại BĐS tại Dự án"`. |
| `property_type` | 100% | ✅ Rất tốt | Có Chung cư (44.3%), Nhà riêng (49.5%), Biệt thự (6.2%). |
| `floors` | 45.2% | ⚠️ Quan trọng | Chỉ có ý nghĩa với Nhà đất. |
| `frontage` | 32.2% | ⚠️ Quan trọng | Chỉ có ý nghĩa với Nhà đất. |
| `road_width` | 27.1% | ⚠️ Quan trọng | Chỉ có ý nghĩa với Nhà đất. |
| `toilets` | 0% | ❌ Trống 100% | Bỏ cột này hoàn toàn. |
| `post_date` | ~100% | ℹ️ Không dùng | Data chỉ span vài ngày → vô nghĩa cho dự đoán giá. Giữ cho web hiển thị. |

> [!CAUTION]
> **QUAN TRỌNG:** Tập dữ liệu là **Mixed Property Types** (Hỗn hợp Chung cư và Nhà riêng/Biệt thự). Việc định giá 2 loại này khác nhau hoàn toàn (Chung cư không quan tâm mặt tiền/đường vào, Nhà riêng thì cực kỳ quan trọng). 
> **=> Giải pháp:** Tách luồng làm sạch thành 2 nhánh: **Chung Cư** và **Nhà Đất (Nhà riêng + Biệt thự)**.

---

## 🔧 2. QUY TRÌNH LÀM SẠCH VÀ CHIA NHÁNH (6 BƯỚC)

### BƯỚC 1: Xóa rác, Dedup & Sửa lỗi Scraper

```python
import pandas as pd
import re

print(f"Ban đầu: {len(df)} dòng")

# 1. Bỏ cột rỗng 100%
df = df.drop(columns=['toilets'])

# 2. Xóa dòng trùng lặp (Dedup)
df = df.drop_duplicates(subset='listing_id')
print(f"Sau khi dedup: {len(df)} dòng")

# 3. Sửa lỗi Scraper: Swap cột price và price_per_m2 nếu bị đảo ngược
mask = df['price'].str.contains('triệu/m', na=False)
df.loc[mask, ['price', 'price_per_m2']] = df.loc[mask, ['price_per_m2', 'price']].values
print(f"Đã sửa {mask.sum()} dòng bị lỗi đảo cột price")

# 4. Parse diện tích TRƯỚC (vì hàm parse_price cần dùng)
df['area_m2'] = df['area'].str.extract(r'([\d,.]+)')[0].str.replace(',', '.').astype(float)

# 5. Parse Giá
def parse_price(price_str, area_m2=None):
    if pd.isna(price_str): return None
    p = str(price_str).lower().strip()
    if 'thỏa thuận' in p or 'thỏa' in p: return None
    
    # Lỗi scraper: "4 nghìn" thực ra là "4 tỷ"
    if 'nghìn' in p:
        num = re.findall(r'[\d,.]+', p)
        if num: return float(num[0].replace(',', '.'))
    
    if 'triệu/m' in p and area_m2:
        num = re.findall(r'[\d,.]+', p)
        if num:
            unit_price = float(num[0].replace(',', '.'))
            return round(unit_price * area_m2 / 1000, 2)
    elif 'tỷ' in p:
        num = re.findall(r'[\d,.]+', p)
        if num: return float(num[0].replace(',', '.'))
    elif 'triệu' in p:
        num = re.findall(r'[\d,.]+', p)
        if num: return round(float(num[0].replace(',', '.')) / 1000, 3)
    return None

df['price_billion'] = df.apply(lambda row: parse_price(row['price'], row.get('area_m2')), axis=1)

# Xóa các dòng không có giá hợp lệ
before = len(df)
df = df.dropna(subset=['price_billion'])
print(f"Sau khi xóa dòng không có giá hợp lệ: {len(df)} dòng (mất {before - len(df)})")
```

### BƯỚC 2: Phân loại BĐS và Tách Nhánh (Branching)

```python
# Phân loại BĐS
is_chung_cu = df['property_type'].str.contains('chung cư|Chung cư', na=False)
is_nha_rieng = df['property_type'].str.contains('nhà riêng|Nhà riêng|biệt thự|Biệt thự', na=False)

# Log các dòng không thuộc 2 nhóm trên (nếu có)
unclassified = df[~is_chung_cu & ~is_nha_rieng]
print(f"Số dòng không phân loại được: {len(unclassified)}")

# Tách thành 2 DataFrame
df_chung_cu = df[is_chung_cu].copy()
df_nha_dat = df[is_nha_rieng].copy()
print(f"Tập Chung cư: {len(df_chung_cu)} dòng. Tập Nhà đất: {len(df_nha_dat)} dòng.")
```

---

### BƯỚC 3: Làm sạch chung cho cả 2 nhánh

Áp dụng cho cả `df_chung_cu` và `df_nha_dat`:

```python
def clean_common_features(data):
    data = data.copy()
    
    # 1. Quận / Huyện
    data['district'] = data['address'].str.split(' - ').str[1].str.strip()
    
    # Gom nhóm các quận có quá ít dữ liệu (< 30) thành "Khác" để tránh Class Imbalance
    district_counts = data['district'].value_counts()
    rare_districts = district_counts[district_counts < 30].index
    print(f"Quận bị gom vào 'Khác': {list(rare_districts)}")
    data['district'] = data['district'].replace(rare_districts, 'Khác')
    
    # 2. Phòng ngủ (Fill NaN bằng median theo quận TRƯỚC khi lọc outlier)
    data['bedrooms_num'] = data['bedrooms'].str.extract(r'(\d+)')[0].astype(float)
    data['bedrooms_num'] = data.groupby('district')['bedrooms_num'].transform(
        lambda x: x.fillna(x.median())
    )
    data['bedrooms_num'] = data['bedrooms_num'].fillna(data['bedrooms_num'].median())
    
    # 3. Hướng nhà & Hướng ban công
    data['direction'] = data['direction'].fillna('Không rõ')
    data['balcony_direction'] = data['balcony_direction'].fillna('Không rõ')
    
    # 4. Nội thất (Lưu ý: Default là "Không rõ")
    def standardize_furniture(val):
        if pd.isna(val): return 'Không rõ'
        val = str(val).lower()
        if any(x in val for x in ['full', 'đầy đủ', 'cao cấp']): return 'Đầy đủ'
        if any(x in val for x in ['cơ bản', 'nguyên bản', 'cđt']): return 'Cơ bản'
        if any(x in val for x in ['không', 'trống']): return 'Không nội thất'
        return 'Không rõ'
    data['furniture_std'] = data['furniture'].apply(standardize_furniture)
    
    # 5. Pháp lý
    def standardize_legal(val):
        if pd.isna(val): return 'Không rõ'
        val = str(val).lower()
        if any(x in val for x in ['sổ đỏ', 'sổ hồng', 'sẵn sổ', 'có sổ']): return 'Sổ đỏ/Sổ hồng'
        if any(x in val for x in ['hợp đồng', 'hđmb']): return 'HĐMB'
        if 'chờ' in val: return 'Đang chờ sổ'
        return 'Khác'
    data['legal_std'] = data['legal'].apply(standardize_legal)
    
    return data

df_chung_cu = clean_common_features(df_chung_cu)
df_nha_dat = clean_common_features(df_nha_dat)
```

---

### BƯỚC 4: Lọc Outlier & Đặc thù riêng cho CHUNG CƯ

```python
# CHUNG CƯ: Không dùng mặt tiền, đường vào, số tầng
cols_to_drop_cc = ['floors', 'frontage', 'road_width']
df_chung_cu = df_chung_cu.drop(columns=cols_to_drop_cc)

df_chung_cu['project_name'] = df_chung_cu['project_name'].fillna('Không rõ')

# Lọc Outliers cho Chung Cư
before = len(df_chung_cu)
df_chung_cu = df_chung_cu[
    (df_chung_cu['area_m2'] >= 20) & (df_chung_cu['area_m2'] <= 300) &
    (df_chung_cu['price_billion'] >= 0.3) & (df_chung_cu['price_billion'] <= 50) &
    (df_chung_cu['bedrooms_num'] >= 1) & (df_chung_cu['bedrooms_num'] <= 6)
]
print(f"Chung cư sau khi lọc outlier: {len(df_chung_cu)} dòng (loại {before - len(df_chung_cu)})")
```

---

### BƯỚC 5: Xử lý kỹ thuật & Outlier cho NHÀ ĐẤT

```python
# NHÀ ĐẤT: Chuyển đổi floors, frontage, road_width sang số
df_nha_dat['floors_num'] = df_nha_dat['floors'].str.extract(r'(\d+)')[0].astype(float)
df_nha_dat['frontage_m'] = df_nha_dat['frontage'].str.extract(r'([\d,.]+)')[0].str.replace(',', '.').astype(float)
df_nha_dat['road_width_m'] = df_nha_dat['road_width'].str.extract(r'([\d,.]+)')[0].str.replace(',', '.').astype(float)

# Fill Missing Values cho Nhà Đất (Bằng Median theo Quận)
for col in ['floors_num', 'frontage_m', 'road_width_m']:
    df_nha_dat[col] = df_nha_dat.groupby('district')[col].transform(lambda x: x.fillna(x.median()))
    # Fallback: Fill bằng median toàn tập nếu quận đó hoàn toàn NaN
    df_nha_dat[col] = df_nha_dat[col].fillna(df_nha_dat[col].median())

# Lọc Outliers cho Nhà Đất (Giới hạn thực tế: <= 25 PN, đường <= 50m)
before = len(df_nha_dat)
df_nha_dat = df_nha_dat[
    (df_nha_dat['area_m2'] >= 15) & (df_nha_dat['area_m2'] <= 1000) &
    (df_nha_dat['price_billion'] >= 0.5) & (df_nha_dat['price_billion'] <= 200) &
    (df_nha_dat['bedrooms_num'] >= 1) & (df_nha_dat['bedrooms_num'] <= 25) &
    (df_nha_dat['road_width_m'] <= 50)
]
print(f"Nhà đất sau khi lọc outlier: {len(df_nha_dat)} dòng (loại {before - len(df_nha_dat)})")
```

---

### BƯỚC 6: Xuất file sạch (Export)

```python
# Features cho Chung Cư (KHÔNG lấy project_name và post_date để train model)
features_cc = ['price_billion', 'area_m2', 'bedrooms_num', 'district', 'direction', 'balcony_direction', 'furniture_std', 'legal_std']
df_chung_cu[features_cc].to_csv('data/processed/cleaned_chung_cu.csv', index=False)

# Features cho Nhà Đất 
features_nd = ['price_billion', 'area_m2', 'bedrooms_num', 'district', 'direction', 'furniture_std', 'legal_std', 'floors_num', 'frontage_m', 'road_width_m']
df_nha_dat[features_nd].to_csv('data/processed/cleaned_nha_dat.csv', index=False)

# File cho Frontend hiển thị (giữ tất cả cột bao gồm post_date, project_name, images...)
df_full = pd.concat([df_chung_cu, df_nha_dat])
df_full.to_csv('data/processed/cleaned_full_web.csv', index=False)

print(f"✅ Chung cư: {len(df_chung_cu)} dòng × {len(features_cc)} features")
print(f"✅ Nhà đất: {len(df_nha_dat)} dòng × {len(features_nd)} features")
print(f"✅ Full web: {len(df_full)} dòng")
```

---

## 📈 3. PHÂN TÍCH DỮ LIỆU (EDA) NÂNG CAO

Khi vẽ biểu đồ, bạn Đức cần so sánh giữa Chung cư và Nhà đất:

1. **Boxplot phân bố giá theo Loại BĐS** (Rất quan trọng để thuyết phục GV tại sao phải tách 2 model).
2. **Scatter Plot (Diện tích vs Giá)** với màu sắc (hue) khác nhau cho Chung cư và Nhà đất.
3. **Heatmap Tương quan riêng biệt**: 1 Heatmap cho Chung cư, 1 Heatmap cho Nhà đất.
4. **Biểu đồ cột Stacked**: Phân bố Chung cư / Nhà đất theo từng Quận.
5. **Histogram phân phối giá**: So sánh phân phối giá giữa 2 loại BĐS.

---

## ✅ 4. CHECKLIST KIỂM TRA

- [ ] KHÔNG sử dụng `price_per_m2` trong tập features train model.
- [ ] KHÔNG sử dụng `post_date` trong features (data chỉ span vài ngày, vô nghĩa cho prediction).
- [ ] Số lượng model train = 2 (`model_chung_cu.pkl` và `model_nha_dat.pkl`).
- [ ] Trong model Nhà Đất không có giá trị NaN ở các cột `frontage`, `road_width`, `floors`.
- [ ] `bedrooms_num` NaN đã được fill bằng median theo quận TRƯỚC khi lọc outlier.
- [ ] Các quận quá ít dữ liệu (<30) đã được tự động gom vào nhóm "Khác".
- [ ] 107 dòng lỗi scraper (price ↔ price_per_m2 bị đảo) đã được swap đúng.
- [ ] 2 dòng giá "nghìn" (lỗi scraper) đã được parse đúng thành tỷ.
