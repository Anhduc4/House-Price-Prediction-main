#!/usr/bin/env python
# coding: utf-8

# # 🧹 Data Preprocessing — House Price Prediction
# Notebook này thực hiện làm sạch dữ liệu và tách thành 2 tập: Chung cư & Nhà đất.
# 
# **Input:** `data/raw/raw_data.csv`  
# **Output:** `data/processed/cleaned_chung_cu.csv`, `cleaned_nha_dat.csv`, `cleaned_full_web.csv`

# In[9]:


import pandas as pd
import numpy as np
import re
import os

os.makedirs('../data/processed', exist_ok=True)
df = pd.read_csv('../data/raw/raw_data.csv', low_memory=False)
print(f"Ban đầu: {len(df)} dòng × {len(df.columns)} cột")


# ## Bước 1: Xóa rác, Dedup & Sửa lỗi Scraper & Parse giá

# In[10]:


# 1. Bỏ cột rỗng 100%
df = df.drop(columns=['toilets'])

# 2. Xóa dòng trùng lặp
df = df.drop_duplicates(subset='listing_id')
print(f"Sau dedup: {len(df)} dòng")

# 3. Sửa lỗi Scraper: Swap cột price <-> price_per_m2 nếu bị đảo
mask = df['price'].str.contains('triệu/m', na=False)
df.loc[mask, ['price', 'price_per_m2']] = df.loc[mask, ['price_per_m2', 'price']].values
print(f"Đã sửa {mask.sum()} dòng bị lỗi đảo cột price")

# 4. Parse diện tích TRƯỚC (parse_price cần dùng)
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

before = len(df)
df = df.dropna(subset=['price_billion'])
print(f"Sau khi xóa dòng không có giá: {len(df)} dòng (mất {before - len(df)})")


# ## Bước 2: Phân loại BĐS và Tách Nhánh

# In[11]:


is_chung_cu = df['property_type'].str.contains('chung cư|Chung cư', na=False)
is_nha_rieng = df['property_type'].str.contains('nhà riêng|Nhà riêng|biệt thự|Biệt thự', na=False)

unclassified = df[~is_chung_cu & ~is_nha_rieng]
print(f"Không phân loại được: {len(unclassified)} dòng")

df_chung_cu = df[is_chung_cu].copy()
df_nha_dat = df[is_nha_rieng].copy()
print(f"Chung cư: {len(df_chung_cu)} | Nhà đất: {len(df_nha_dat)}")


# ## Bước 3: Làm sạch chung cho cả 2 nhánh

# In[12]:


def clean_common_features(data):
    data = data.copy()

    # 1. Quận / Huyện
    data['district'] = data['address'].str.split(' - ').str[1].str.strip()
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

    # 3. Hướng nhà & Ban công
    data['direction'] = data['direction'].fillna('Không rõ')
    data['balcony_direction'] = data['balcony_direction'].fillna('Không rõ')

    # 4. Nội thất
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


# ## Bước 4: Lọc Outlier cho Chung Cư

# In[13]:


df_chung_cu = df_chung_cu.drop(columns=['floors', 'frontage', 'road_width'])
df_chung_cu['project_name'] = df_chung_cu['project_name'].fillna('Không rõ')

before = len(df_chung_cu)
df_chung_cu = df_chung_cu[
    (df_chung_cu['area_m2'] >= 20) & (df_chung_cu['area_m2'] <= 300) &
    (df_chung_cu['price_billion'] >= 0.3) & (df_chung_cu['price_billion'] <= 50) &
    (df_chung_cu['bedrooms_num'] >= 1) & (df_chung_cu['bedrooms_num'] <= 6)
]
print(f"Chung cư sau outlier: {len(df_chung_cu)} (loại {before - len(df_chung_cu)})")


# ## Bước 5: Fill NA & Lọc Outlier cho Nhà Đất

# In[14]:


df_nha_dat['floors_num'] = df_nha_dat['floors'].str.extract(r'(\d+)')[0].astype(float)
df_nha_dat['frontage_m'] = df_nha_dat['frontage'].str.extract(r'([\d,.]+)')[0].str.replace(',', '.').astype(float)
df_nha_dat['road_width_m'] = df_nha_dat['road_width'].str.extract(r'([\d,.]+)')[0].str.replace(',', '.').astype(float)

for col in ['floors_num', 'frontage_m', 'road_width_m']:
    df_nha_dat[col] = df_nha_dat.groupby('district')[col].transform(lambda x: x.fillna(x.median()))
    df_nha_dat[col] = df_nha_dat[col].fillna(df_nha_dat[col].median())

before = len(df_nha_dat)
df_nha_dat = df_nha_dat[
    (df_nha_dat['area_m2'] >= 15) & (df_nha_dat['area_m2'] <= 1000) &
    (df_nha_dat['price_billion'] >= 0.5) & (df_nha_dat['price_billion'] <= 200) &
    (df_nha_dat['bedrooms_num'] >= 1) & (df_nha_dat['bedrooms_num'] <= 25) &
    (df_nha_dat['road_width_m'] <= 50)
]
print(f"Nhà đất sau outlier: {len(df_nha_dat)} (loại {before - len(df_nha_dat)})")


# ## Bước 6: Xuất file

# In[15]:


features_cc = ['price_billion', 'area_m2', 'bedrooms_num', 'district', 'direction', 'balcony_direction', 'furniture_std', 'legal_std', 'title', 'description', 'image_urls']
df_chung_cu[features_cc].to_csv('../data/processed/cleaned_chung_cu.csv', index=False)

features_nd = ['price_billion', 'area_m2', 'bedrooms_num', 'district', 'direction', 'furniture_std', 'legal_std', 'floors_num', 'frontage_m', 'road_width_m', 'title', 'description', 'image_urls']
df_nha_dat[features_nd].to_csv('../data/processed/cleaned_nha_dat.csv', index=False)

df_full = pd.concat([df_chung_cu, df_nha_dat])
df_full.to_csv('../data/processed/cleaned_full_web.csv', index=False)

print(f"✅ Chung cư: {len(df_chung_cu)} dòng × {len(features_cc)} features")
print(f"✅ Nhà đất: {len(df_nha_dat)} dòng × {len(features_nd)} features")
print(f"✅ Full web: {len(df_full)} dòng")


# ## Kiểm tra nhanh sau xuất

# In[16]:


# Verify: không còn NaN trong features
cc = pd.read_csv('../data/processed/cleaned_chung_cu.csv')
nd = pd.read_csv('../data/processed/cleaned_nha_dat.csv')
print('=== NaN check Chung cư ===')
print(cc.isnull().sum())
print(f'\n=== NaN check Nhà đất ===')
print(nd.isnull().sum())
print(f'\n=== Describe Chung cư ===')
print(cc.describe())
print(f'\n=== Describe Nhà đất ===')
print(nd.describe())

