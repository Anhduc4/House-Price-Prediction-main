"""
CRAWLER BĐS v3 — batdongsan.com.vn
- FIX: Chống trùng bằng Set lưu listing_id đã cào
- FIX: Cào từ NHIỀU danh mục (chung cư, nhà riêng, biệt thự) để đủ 3000
- SPEED: Giảm sleep xuống 1.5-3s (vẫn an toàn)
- RESUME: Đọc file cũ để biết đã cào những ID nào rồi
"""

from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import json
import os
import csv
import logging
import traceback

# ============================================================
# CẤU HÌNH
# ============================================================
# Cào từ NHIỀU danh mục khác nhau để tránh hết link
CATEGORY_URLS = [
    "https://batdongsan.com.vn/ban-can-ho-chung-cu-ha-noi/p{}",          # Chung cư HN
    "https://batdongsan.com.vn/ban-nha-rieng-ha-noi/p{}",               # Nhà riêng HN
    "https://batdongsan.com.vn/ban-nha-biet-thu-lien-ke-ha-noi/p{}",    # Biệt thự HN
    "https://batdongsan.com.vn/ban-can-ho-chung-cu-tp-hcm/p{}",         # Chung cư HCM
    "https://batdongsan.com.vn/ban-nha-rieng-tp-hcm/p{}",               # Nhà riêng HCM
    "https://batdongsan.com.vn/ban-can-ho-chung-cu-da-nang/p{}",        # Chung cư Đà Nẵng
]

TARGET_TOTAL = 3000   # Mục tiêu tổng cộng (bao gồm cả dữ liệu cũ)
MIN_SLEEP = 1.5       # Giảm sleep: 1.5s
MAX_SLEEP = 3.0       # Giảm sleep: 3.0s
MAX_PAGES_PER_CATEGORY = 80

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'raw')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'raw_data.csv')
LOG_FILE = os.path.join(BASE_DIR, 'crawler.log')

ALL_COLUMNS = [
    'stt', 'listing_id', 'title', 'price', 'price_per_m2', 'area',
    'bedrooms', 'toilets', 'direction', 'balcony_direction',
    'floors', 'frontage', 'road_width', 'furniture', 'legal',
    'property_type', 'project_name', 'address',
    'post_date', 'expiry_date', 'listing_type',
    'description', 'image_urls', 'image_count', 'url',
]

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)

# ============================================================
# SESSION + ANTI-BAN
# ============================================================
session = cf_requests.Session(impersonate="chrome")

def refresh_session():
    global session
    logging.info("♻️ Đổi Session mới...")
    time.sleep(random.uniform(8, 12))
    session = cf_requests.Session(impersonate="chrome")

def safe_get(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp
            elif resp.status_code in [403, 429, 503]:
                logging.warning(f"⚠️ HTTP {resp.status_code} → Chờ 20s + đổi session")
                time.sleep(20)
                refresh_session()
            else:
                time.sleep(3)
        except Exception as e:
            logging.error(f"❌ Lỗi mạng: {str(e)[:80]}")
            time.sleep(8)
            refresh_session()
    return None

# ============================================================
# LẤY DANH SÁCH LINK (có dedup ngay tại đây)
# ============================================================
def get_listing_urls(base_url, page_num):
    url = base_url.format(page_num)
    logging.info(f"📄 Quét trang: {url}")
    resp = safe_get(url)
    if not resp: return []
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    urls = []
    for selector in ['a.js__product-link-for-product-id',
                     'div.js__card a[href*="/ban-"]',
                     'a[href*="pr4"]',
                     'div.re__card-info a']:
        cards = soup.select(selector)
        if cards:
            for card in cards:
                href = card.get('href')
                if href and '/ban-' in href:
                    full_url = 'https://batdongsan.com.vn' + href if href.startswith('/') else href
                    if full_url not in urls:
                        urls.append(full_url)
            break
    logging.info(f"   → {len(urls)} link")
    return urls

# ============================================================
# CÀO CHI TIẾT
# ============================================================
def scrape_detail(url):
    resp = safe_get(url)
    if not resp: return None
    soup = BeautifulSoup(resp.text, 'html.parser')
    data = {col: '' for col in ALL_COLUMNS}
    data['url'] = url

    # Tiêu đề
    for sel in ['h1.re__pr-title', 'h1.pr-title', 'h1']:
        el = soup.select_one(sel)
        if el and len(el.text.strip()) > 5:
            data['title'] = el.text.strip()
            break
    if not data['title']: return None

    # Giá, Diện tích, Phòng ngủ
    for item in soup.select('div.re__pr-short-info-item'):
        title_el = item.select_one('span.title')
        if not title_el: continue
        t = title_el.text.strip().lower()
        val = item.select_one('span.value')
        ext = item.select_one('span.ext') or item.select_one('span.summary')
        if 'giá' in t:
            if val: data['price'] = val.text.strip()
            if ext: data['price_per_m2'] = ext.text.strip()
        elif 'diện tích' in t:
            if val: data['area'] = val.text.strip()
        elif 'phòng ngủ' in t:
            if val: data['bedrooms'] = val.text.strip()

    # Địa chỉ (breadcrumb)
    bread = soup.select('div.re__breadcrumb a')
    if bread:
        data['address'] = ' - '.join([x.text.strip() for x in bread[1:]])
    else:
        el = soup.select_one('span.re__address-line-2')
        if el: data['address'] = el.text.strip()

    # Bảng thông số
    label_map = {
        'Diện tích': 'area', 'Mức giá': 'price',
        'Hướng nhà': 'direction', 'Hướng ban công': 'balcony_direction',
        'Số phòng ngủ': 'bedrooms', 'Số toilet': 'toilets',
        'Pháp lý': 'legal', 'Nội thất': 'furniture',
        'Số tầng': 'floors', 'Mặt tiền': 'frontage', 'Đường vào': 'road_width',
    }
    for item in soup.select('div.re__pr-specs-content-item'):
        for sel_pair in [('span.re__pr-specs-content-item-title', 'span.re__pr-specs-content-item-value'),
                         ('span[class*="title"]', 'span[class*="value"]')]:
            lbl = item.select_one(sel_pair[0])
            val = item.select_one(sel_pair[1])
            if lbl and val:
                key = label_map.get(lbl.text.strip())
                if key and not data[key]:
                    data[key] = val.text.strip()

    # Tên dự án
    for sel in ['div.re__project-title', 'a.re__project-title']:
        el = soup.select_one(sel)
        if el:
            data['project_name'] = el.text.strip()
            break

    # Mô tả
    for sel in ['div.re__section-body.re__section-description', 'div.re__detail-content', 'div.re__section-body']:
        el = soup.select_one(sel)
        if el:
            data['description'] = el.get_text('\n', strip=True)
            break

    # Mã tin, ngày đăng, loại tin
    for item in soup.select('div.re__pr-short-info-item'):
        text = item.get_text(' ', strip=True)
        val_el = item.select_one('span.value')
        if not val_el: continue
        v = val_el.text.strip()
        if 'Ngày đăng' in text: data['post_date'] = v
        elif 'hết hạn' in text: data['expiry_date'] = v
        elif 'Mã tin' in text: data['listing_id'] = v
        elif 'Loại tin' in text: data['listing_type'] = v

    # Loại BĐS
    if bread and len(bread) >= 2:
        data['property_type'] = bread[-1].text.strip()

    # Ảnh
    img_urls = []
    for img in soup.select('img[data-src*="file4"], img[src*="file4"], img[data-src*="cdn"], img[src*="cdn"]'):
        src = img.get('data-src') or img.get('src') or ''
        if src and 'http' in src and src not in img_urls:
            img_urls.append(src)
    data['image_urls'] = json.dumps(img_urls, ensure_ascii=False)
    data['image_count'] = str(len(img_urls))
    return data

# ============================================================
# LƯU
# ============================================================
def save_one_row(data, file_path, write_header=False):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    mode = 'w' if write_header else 'a'
    with open(file_path, mode, newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=ALL_COLUMNS)
        if write_header: writer.writeheader()
        writer.writerow(data)

# ============================================================
# MAIN — RESUME MODE
# ============================================================
def main():
    # ĐỌC FILE CŨ để biết đã cào những listing_id nào rồi
    seen_ids = set()
    seen_urls = set()
    existing_count = 0
    
    if os.path.exists(OUTPUT_FILE):
        try:
            df_old = pd.read_csv(OUTPUT_FILE)
            existing_count = len(df_old)
            seen_ids = set(df_old['listing_id'].dropna().astype(str).tolist())
            seen_urls = set(df_old['url'].dropna().tolist())
            logging.info(f"📂 Đã đọc file cũ: {existing_count} dòng, {len(seen_ids)} ID đã biết")
        except:
            logging.warning("⚠️ File cũ bị lỗi, bỏ qua")
    
    need = TARGET_TOTAL - existing_count
    if need <= 0:
        logging.info(f"✅ Đã đủ {existing_count}/{TARGET_TOTAL}. Không cần cào thêm!")
        return

    logging.info("=" * 60)
    logging.info(f"🚀 CÀO TIẾP: Đã có {existing_count}, cần thêm {need} → Mục tiêu {TARGET_TOTAL}")
    logging.info(f"📂 File: {OUTPUT_FILE}")
    logging.info(f"🔄 Có {len(CATEGORY_URLS)} danh mục để cào")
    logging.info("=" * 60)

    count = existing_count
    new_count = 0

    try:
        for cat_idx, cat_url in enumerate(CATEGORY_URLS):
            if new_count >= need: break
            logging.info(f"\n{'='*60}")
            logging.info(f"📁 DANH MỤC {cat_idx+1}/{len(CATEGORY_URLS)}: {cat_url.format('X')}")
            logging.info(f"{'='*60}")
            
            empty_pages = 0  # Đếm số trang liên tiếp không có link mới
            
            for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
                if new_count >= need: break
                
                urls = get_listing_urls(cat_url, page)
                if not urls:
                    empty_pages += 1
                    if empty_pages >= 3:
                        logging.info("⏭️ 3 trang liên tiếp trống → Chuyển danh mục")
                        break
                    continue
                
                # LỌC BỎ URL ĐÃ CÀO
                new_urls = [u for u in urls if u not in seen_urls]
                if not new_urls:
                    empty_pages += 1
                    logging.info(f"   ⏭️ Tất cả {len(urls)} link đều đã cào rồi, bỏ qua")
                    if empty_pages >= 3:
                        logging.info("⏭️ 3 trang liên tiếp toàn trùng → Chuyển danh mục")
                        break
                    continue
                
                empty_pages = 0  # Reset bộ đếm
                logging.info(f"   🆕 {len(new_urls)} link MỚI (bỏ {len(urls)-len(new_urls)} trùng)")
                
                for url in new_urls:
                    if new_count >= need: break
                    
                    data = scrape_detail(url)
                    if data and data.get('title'):
                        lid = str(data.get('listing_id', ''))
                        
                        # KIỂM TRA TRÙNG LẦN 2 (theo listing_id)
                        if lid and lid in seen_ids:
                            logging.info(f"   ⏭️ ID {lid} đã tồn tại, bỏ qua")
                            seen_urls.add(url)
                            continue
                        
                        count += 1
                        new_count += 1
                        data['stt'] = str(count)
                        save_one_row(data, OUTPUT_FILE, write_header=False)
                        
                        if lid: seen_ids.add(lid)
                        seen_urls.add(url)
                        
                        logging.info(f"✅ [{count}/{TARGET_TOTAL}] +{new_count} mới | {data.get('title','')[:50]}... | {data.get('price','')}")
                    else:
                        seen_urls.add(url)
                    
                    time.sleep(random.uniform(MIN_SLEEP, MAX_SLEEP))
                
    except KeyboardInterrupt:
        logging.warning(f"\n⚠️ DỪNG. Đã thêm {new_count} mới. Tổng: {count}")
    except Exception as e:
        logging.critical(f"🔥 LỖI: {str(e)}")
        logging.error(traceback.format_exc())

    logging.info(f"\n{'='*60}")
    logging.info(f"🎉 KẾT THÚC! Thêm {new_count} mới. Tổng: {count}/{TARGET_TOTAL}")
    logging.info(f"{'='*60}")

if __name__ == "__main__":
    main()
