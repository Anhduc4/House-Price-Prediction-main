import os
import base64
import json
import time
import urllib.parse
import urllib.request
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import pickle
import pandas as pd
from secrets import token_hex
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or token_hex(32)

cors_origins = [origin.strip() for origin in os.environ.get('CORS_ORIGINS', '').split(',') if origin.strip()]
if cors_origins:
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# Google OAuth: set env vars, or create app/oauth_config.py from oauth_config.example.py.
try:
    from oauth_config import GOOGLE_CLIENT_ID as GOOGLE_CLIENT_ID_LOCAL
    from oauth_config import GOOGLE_CLIENT_SECRET as GOOGLE_CLIENT_SECRET_LOCAL
except ModuleNotFoundError:
    try:
        from app.oauth_config import GOOGLE_CLIENT_ID as GOOGLE_CLIENT_ID_LOCAL
        from app.oauth_config import GOOGLE_CLIENT_SECRET as GOOGLE_CLIENT_SECRET_LOCAL
    except ModuleNotFoundError:
        GOOGLE_CLIENT_ID_LOCAL = ''
        GOOGLE_CLIENT_SECRET_LOCAL = ''

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '').strip() or GOOGLE_CLIENT_ID_LOCAL.strip()
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip() or GOOGLE_CLIENT_SECRET_LOCAL.strip()

GOOGLE_CONFIGURED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

# Simple in-memory user store (demo)
USERS = {
    'admin@prophet.vn': {'password_hash': generate_password_hash('123456'), 'name': 'Admin'},
}

def password_matches(user, password):
    password_hash = user.get('password_hash')
    if password_hash:
        return check_password_hash(password_hash, password)

    legacy_password = user.get('password')
    return legacy_password is not None and legacy_password == password

def _decode_jwt_payload(token):
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
    except Exception:
        return None

def verify_google_credential(credential):
    if not GOOGLE_CLIENT_ID:
        raise ValueError('Google Client ID chưa được cấu hình.')

    if google_id_token is not None and google_requests is not None:
        try:
            return google_id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                GOOGLE_CLIENT_ID
            )
        except Exception:
            pass

    payload = _decode_jwt_payload(credential)
    if not payload:
        raise ValueError('Google credential không hợp lệ.')
    if payload.get('aud') != GOOGLE_CLIENT_ID:
        raise ValueError('Google Client ID không khớp.')
    if int(payload.get('exp', 0)) < int(time.time()):
        raise ValueError('Google credential đã hết hạn.')
    return payload

def exchange_google_code(code, redirect_uri):
    data = urllib.parse.urlencode({
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))

def user_from_google_id_token(id_token_value):
    payload = _decode_jwt_payload(id_token_value)
    if not payload:
        raise ValueError('Google token invalid.')
    if payload.get('aud') != GOOGLE_CLIENT_ID:
        raise ValueError('Google Client ID mismatch.')
    if int(payload.get('exp', 0)) < int(time.time()):
        raise ValueError('Google token expired.')
    return payload


# ==========================================
# Khởi động app: Load model 1 lần duy nhất (Singleton Pattern)
# ==========================================
models = {}

def load_model(name):
    # Lấy đường dẫn an toàn cho dù chạy từ root hay thư mục app/
    model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', f'{name}.pkl')
    if not os.path.exists(model_path): # Fallback
        model_path = f'models/{name}.pkl'
    try:
        with open(model_path, 'rb') as f:
            models[name] = pickle.load(f)
        print(f"[OK] Da load thanh cong {name}")
    except FileNotFoundError:
        print(f"[ERROR] Chua tim thay model {name}. Vui long chay file train_pipeline.py truoc!")
        models[name] = None

# Load cả 2 model cho Chung cư và Nhà đất
load_model('model_chung_cu_pipeline')
load_model('model_nha_dat_pipeline')

# Load data cho gợi ý căn nhà tương tự
dataframes = {}
try:
    csv_chung_cu = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'processed', 'cleaned_chung_cu.csv')
    csv_nha_dat = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'processed', 'cleaned_nha_dat.csv')
    if not os.path.exists(csv_chung_cu): csv_chung_cu = 'data/processed/cleaned_chung_cu.csv'
    if not os.path.exists(csv_nha_dat): csv_nha_dat = 'data/processed/cleaned_nha_dat.csv'
    
    dataframes['chung_cu'] = pd.read_csv(csv_chung_cu)
    dataframes['nha_dat'] = pd.read_csv(csv_nha_dat)
    print("[OK] Da load du lieu CSV de lam goi y")
except Exception as e:
    print("[ERROR] Khong load duoc du lieu CSV:", e)

@app.route('/')
def home():
    """Route mặc định render giao diện trang chủ"""
    return render_template('index.html', user=session.get('user'))

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    user = USERS.get(email)
    if user and password_matches(user, password):
        session['user'] = {'email': email, 'name': user['name']}
        return jsonify({'success': True, 'name': user['name']})
    return jsonify({'success': False, 'error': 'Email hoặc mật khẩu không đúng.'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    name = data.get('name', 'Người dùng')
    if not email or not password:
        return jsonify({'success': False, 'error': 'Vui lòng nhập đầy đủ thông tin.'}), 400
    if email in USERS:
        return jsonify({'success': False, 'error': 'Email này đã được đăng ký.'}), 400
    USERS[email] = {'password_hash': generate_password_hash(password), 'name': name}
    session['user'] = {'email': email, 'name': name}
    return jsonify({'success': True, 'name': name})

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

# ── Google OAuth Routes ────────────────────────────────────────────
@app.route('/auth/google')
def google_login():
    if not GOOGLE_CONFIGURED:
        return jsonify({'error': 'Google OAuth is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.'}), 503
    state = token_hex(16)
    session['google_oauth_state'] = state
    redirect_uri = url_for('google_callback', _external=True)
    params = urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    })
    return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{params}')

@app.route('/auth/google/callback')
def google_callback():
    if not GOOGLE_CONFIGURED:
        return redirect('/?auth_error=google_unavailable')
    if request.args.get('state') != session.pop('google_oauth_state', None):
        return redirect('/?auth_error=google_state')
    code = request.args.get('code')
    if not code:
        return redirect('/?auth_error=google_no_code')
    try:
        token = exchange_google_code(code, url_for('google_callback', _external=True))
        user_info = user_from_google_id_token(token.get('id_token', ''))
        email = user_info.get('email', '').strip().lower()
        name = user_info.get('name') or email.split('@')[0]
        picture = user_info.get('picture', '')
        if email not in USERS:
            USERS[email] = {'password_hash': None, 'name': name, 'picture': picture, 'provider': 'google'}
        session['user'] = {'email': email, 'name': name, 'picture': picture, 'provider': 'google'}
        return redirect('/')
    except Exception:
        return redirect('/?auth_error=google_failed')

@app.route('/auth/google/token', methods=['POST'])
def google_token_login():
    return jsonify({'success': False, 'error': 'Google token login is disabled. Use /auth/google.'}), 410
    data = request.get_json(silent=True) or {}
    credential = data.get('credential', '')
    try:
        user_info = verify_google_credential(credential)
        email = user_info.get('email', '').strip().lower()
        if not email:
            return jsonify({'success': False, 'error': 'Google không trả về email.'}), 400

        name = user_info.get('name') or email.split('@')[0]
        picture = user_info.get('picture', '')
        if email not in USERS:
            USERS[email] = {'password_hash': None, 'name': name, 'picture': picture, 'provider': 'google'}
        session['user'] = {'email': email, 'name': name, 'picture': picture, 'provider': 'google'}
        return jsonify({'success': True, 'name': name})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/me')
def me():
    user = session.get('user')
    if user:
        return jsonify({'logged_in': True, 'name': user['name']})
    return jsonify({'logged_in': False})

@app.route('/api/auth/status')
def auth_status():
    return jsonify({
        'google_configured': bool(GOOGLE_CONFIGURED)
    })

@app.route('/analytics')
def analytics():
    """Trang phân tích dữ liệu bất động sản từ dữ liệu processed"""
    import json as _json

    cc = dataframes.get('chung_cu', pd.DataFrame())
    nd = dataframes.get('nha_dat', pd.DataFrame())

    def safe_dict(series):
        return {str(k): round(float(v), 2) for k, v in series.items() if pd.notna(k) and str(k) != 'nan'}

    stats = {
        'total_cc': len(cc),
        'total_nd': len(nd),
        'total': len(cc) + len(nd),
        # Price stats
        'cc_price_mean': round(float(cc['price_billion'].mean()), 2) if len(cc) else 0,
        'cc_price_median': round(float(cc['price_billion'].median()), 2) if len(cc) else 0,
        'cc_price_min': round(float(cc['price_billion'].min()), 2) if len(cc) else 0,
        'cc_price_max': round(float(cc['price_billion'].max()), 2) if len(cc) else 0,
        'nd_price_mean': round(float(nd['price_billion'].mean()), 2) if len(nd) else 0,
        'nd_price_median': round(float(nd['price_billion'].median()), 2) if len(nd) else 0,
        # District counts
        'cc_dist_count': safe_dict(cc['district'].value_counts().head(10)),
        'nd_dist_count': safe_dict(nd['district'].value_counts().head(10)),
        # Avg price by district
        'cc_price_by_dist': safe_dict(cc.groupby('district')['price_billion'].mean().sort_values(ascending=False).head(10)),
        'nd_price_by_dist': safe_dict(nd.groupby('district')['price_billion'].mean().sort_values(ascending=False).head(10)),
        # Legal breakdown
        'cc_legal': safe_dict(cc['legal_std'].value_counts()),
        # Furniture
        'cc_furniture': safe_dict(cc['furniture_std'].value_counts()),
        # Bedroom dist
        'cc_bedroom': safe_dict(cc['bedrooms_num'].value_counts().sort_index()),
        # Area ranges
        'cc_area_mean': round(float(cc['area_m2'].mean()), 1) if len(cc) else 0,
        'nd_area_mean': round(float(nd['area_m2'].mean()), 1) if len(nd) else 0,
    }

    return render_template('analytics.html',
                           stats=stats,
                           stats_json=_json.dumps(stats, ensure_ascii=False),
                           user=session.get('user'))

@app.route('/about')
def about():
    return render_template('about.html', user=session.get('user'))

@app.route('/news')
def news():
    return render_template('news.html', user=session.get('user'))

@app.route('/search')
def search():
    return render_template('search.html', user=session.get('user'))

@app.route('/api/search')
def api_search():
    """Search properties from CSV data with filters"""
    import math
    q        = request.args.get('q', '').strip().lower()
    ptype    = request.args.get('type', 'all')       # all / chung_cu / nha_dat
    sort     = request.args.get('sort', 'default')
    district  = request.args.get('district', '').strip()
    per_page  = 12

    if ptype not in {'all', 'chung_cu', 'nha_dat'}:
        return jsonify({'success': False, 'error': 'Loại bất động sản không hợp lệ.'}), 400

    if sort not in {'default', 'price_asc', 'price_desc'}:
        return jsonify({'success': False, 'error': 'Kiểu sắp xếp không hợp lệ.'}), 400

    try:
        price_min = float(request.args.get('price_min', 0))
        price_max = float(request.args.get('price_max', 9999))
        page      = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Tham số tìm kiếm không hợp lệ.'}), 400

    if price_min < 0 or price_max < 0 or price_min > price_max:
        return jsonify({'success': False, 'error': 'Khoảng giá không hợp lệ.'}), 400

    results = []
    for dtype in (['chung_cu', 'nha_dat'] if ptype == 'all' else [ptype]):
        df = dataframes.get(dtype, pd.DataFrame())
        if df.empty:
            continue
        mask = pd.Series([True] * len(df), index=df.index)
        if q:
            text_mask = df['district'].astype(str).str.lower().str.contains(q, na=False)
            if 'title' in df.columns:
                text_mask |= df['title'].astype(str).str.lower().str.contains(q, na=False)
            mask &= text_mask
        if district:
            mask &= df['district'].astype(str).str.lower() == district.lower()
        mask &= (df['price_billion'] >= price_min) & (df['price_billion'] <= price_max)
        sub = df[mask].copy()
        sub['_type'] = dtype
        sub['_id'] = sub.index
        results.append(sub)

    if results:
        combined = pd.concat(results, ignore_index=True)
    else:
        combined = pd.DataFrame()

    if not combined.empty and sort in {'price_asc', 'price_desc'}:
        combined = combined.sort_values('price_billion', ascending=(sort == 'price_asc'))

    total = len(combined)
    start = (page - 1) * per_page
    page_df = combined.iloc[start:start + per_page]

    def row_to_dict(row):
        import json as _json
        imgs = []
        if 'image_urls' in row.index and pd.notna(row.get('image_urls')):
            raw = str(row['image_urls']).strip()
            try:
                parsed = _json.loads(raw)
                imgs = [u for u in parsed if isinstance(u, str) and u.startswith('http')]
            except Exception:
                # fallback: try comma split
                imgs = [u.strip().strip('"') for u in raw.split(',') if 'http' in u]
        thumb = imgs[0] if imgs else ''
        return {
            'id': int(row.get('_id', 0)),
            'type': row.get('_type', ''),
            'title': str(row.get('title', f"BĐS tại {row.get('district','')}")),
            'district': str(row.get('district', '')),
            'price': round(float(row.get('price_billion', 0)), 2),
            'area': float(row.get('area_m2', 0)),
            'bedrooms': int(row.get('bedrooms_num', 0)) if pd.notna(row.get('bedrooms_num')) else 0,
            'image': thumb,
            'legal': str(row.get('legal_std', '')),
            'furniture': str(row.get('furniture_std', '')),
        }

    items = [row_to_dict(row) for _, row in page_df.iterrows()]
    return jsonify({
        'total': total,
        'page': page,
        'pages': math.ceil(total / per_page) if total else 0,
        'items': items
    })

@app.route('/predict', methods=['POST'])
def predict():
    """API nhận data từ Frontend và trả về giá dự đoán"""
    try:
        # Lấy dữ liệu user nhập từ giao diện (JSON)
        data = request.get_json(silent=True) or {}
        
        # Nhận diện loại bất động sản cần dự đoán (mặc định chung_cu nếu Frontend không gửi)
        property_type = data.get('property_type', 'chung_cu')
        
        # --- VALIDATION ĐẦU VÀO (CHẶN DỮ LIỆU VÔ LÝ) ---
        area = float(data.get('area', 0))
        if area <= 0 or area > 50000:
            return jsonify({'success': False, 'error': f'Diện tích {area}m2 không hợp lệ! Vui lòng nhập số > 0.'}), 400
            
        bedrooms = int(data.get('bedrooms', 0))
        if bedrooms < 0 or bedrooms > 100:
            return jsonify({'success': False, 'error': f'Số phòng ngủ {bedrooms} không hợp lệ! Vui lòng nhập số từ 0 đến 100.'}), 400

        if property_type == 'nha_dat':
            floors = int(data.get('floors', 1))
            if floors <= 0 or floors > 200:
                return jsonify({'success': False, 'error': f'Số tầng {floors} không hợp lệ! Vui lòng nhập số > 0.'}), 400
            
            frontage = float(data.get('frontage', 0))
            if frontage < 0 or frontage > 1000:
                return jsonify({'success': False, 'error': f'Mặt tiền {frontage}m không hợp lệ!'}), 400
                
            road_width = float(data.get('road_width', 0))
            if road_width < 0 or road_width > 1000:
                return jsonify({'success': False, 'error': f'Đường vào {road_width}m không hợp lệ!'}), 400
        # ------------------------------------------------
        
        # 1. Chỉ cần tạo thẳng 1 DataFrame 1 dòng từ input của Frontend
        # Chú ý: Các key của dictionary phải khớp Y HỆT tên cột lúc Thái train
        if property_type == 'chung_cu':
            input_dict = {
                'area_m2': area,
                'bedrooms_num': bedrooms,
                'district': data.get('district', 'Khác'),
                'direction': data.get('direction', 'Không rõ'),
                'balcony_direction': data.get('balcony_direction', 'Không rõ'),
                'furniture_std': data.get('furniture', 'Không rõ'),
                'legal_std': data.get('legal', 'Không rõ')
            }
            model_key = 'model_chung_cu_pipeline'
            
        elif property_type == 'nha_dat':
            input_dict = {
                'area_m2': area,
                'bedrooms_num': bedrooms,
                'district': data.get('district', 'Khác'),
                'direction': data.get('direction', 'Không rõ'),
                'furniture_std': data.get('furniture', 'Không rõ'),
                'legal_std': data.get('legal', 'Không rõ'),
                'floors_num': int(data.get('floors', 1)),
                'frontage_m': float(data.get('frontage', 0)),
                'road_width_m': float(data.get('road_width', 0))
            }
            model_key = 'model_nha_dat_pipeline'
            
        else:
            return jsonify({'success': False, 'error': 'Loại bất động sản không hợp lệ (chỉ nhận chung_cu hoặc nha_dat)'}), 400

        # Chuyển Dictionary thành DataFrame (chỉ có 1 dòng dữ liệu)
        input_data = pd.DataFrame([input_dict])
        
        # 2. Đưa thẳng DataFrame vào model dự đoán
        model = models.get(model_key)
        prediction_billion = 0
        if model:
            prediction_billion = model.predict(input_data)[0]
            prediction_vnd = prediction_billion * 1_000_000_000
        else:
            prediction_billion = float(data.get('area', 0)) * 0.1
            prediction_vnd = prediction_billion * 1_000_000_000
            
        # 3. Tìm các căn nhà tương tự
        similar_properties = []
        df_target = dataframes.get(property_type)
        if df_target is not None and not df_target.empty and prediction_billion > 0:
            # Lọc +- 15% giá
            min_price = prediction_billion * 0.85
            max_price = prediction_billion * 1.15
            
            # Ưu tiên cùng quận
            user_district = data.get('district', '')
            filtered = df_target[(df_target['price_billion'] >= min_price) & (df_target['price_billion'] <= max_price)]
            
            if not filtered.empty:
                # Ưu tiên cùng quận trước, nếu ko có thì lấy ngẫu nhiên trong tầm giá
                same_district = filtered[filtered['district'] == user_district]
                if len(same_district) >= 3:
                    sampled = same_district.sample(3)
                elif len(same_district) > 0:
                    needed = 3 - len(same_district)
                    others = filtered[filtered['district'] != user_district]
                    sampled = pd.concat([same_district, others.sample(min(needed, len(others)))])
                else:
                    sampled = filtered.sample(min(3, len(filtered)))
                
                # Format kết quả
                for idx, row in sampled.iterrows():
                    prop = {
                        "id": int(idx),
                        "property_type": property_type,
                        "price_billion": round(row['price_billion'], 2),
                        "area_m2": row['area_m2'],
                        "district": row['district']
                    }
                    if property_type == 'chung_cu':
                        prop["desc"] = f"{int(row['bedrooms_num'])} PN · Hướng {row['direction']}"
                    else:
                        prop["desc"] = f"{int(row.get('floors_num', 1))} tầng · Mặt tiền {row.get('frontage_m', 0)}m"

                    # Lấy ảnh đầu tiên nếu có
                    import json as _json
                    raw_imgs = row.get('image_urls', '[]')
                    try:
                        imgs = _json.loads(str(raw_imgs).replace("'", '"'))
                        # Ưu tiên ảnh 1275x717 (to, nét)
                        big_imgs = [u for u in imgs if '1275x717' in u or ('resize' not in u and '200x200' not in u and 'crop' not in u)]
                        prop["image"] = big_imgs[0] if big_imgs else (imgs[0] if imgs else "")
                    except Exception:
                        prop["image"] = ""

                    # Tiêu đề
                    prop["title"] = str(row.get('title', f"Bất động sản tại {row['district']}"))[:80]
                    similar_properties.append(prop)

        return jsonify({
            'success': True,
            'predicted_price_vnd': prediction_vnd,
            'similar_properties': similar_properties,
            'message': f'Dự đoán thành công ({property_type})' + (' (Dùng Model AI Pipeline)' if model else ' (Đang dùng số liệu ảo)')
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/property/<property_type>/<int:prop_id>')
def property_detail(property_type, prop_id):
    """Trang chi tiết của một bất động sản"""
    try:
        df = dataframes.get(property_type)
        if df is None or prop_id not in df.index:
            return "Không tìm thấy bất động sản!", 404
            
        prop_data = df.loc[prop_id].to_dict()
        prop_data['id'] = prop_id
        prop_data['type'] = property_type
        
        # Parse image_urls
        fallback_image = url_for('static', filename='hero-bg.png')
        try:
            import json
            images = json.loads(prop_data.get('image_urls', '[]'))
            images = [img for img in images if isinstance(img, str) and img.startswith(('http://', 'https://'))]
            if isinstance(images, list) and len(images) > 0:
                prop_data['image'] = images[0]
                prop_data['all_images'] = images
            else:
                prop_data['image'] = fallback_image
                prop_data['all_images'] = [prop_data['image']]
        except:
            prop_data['image'] = fallback_image
            prop_data['all_images'] = [prop_data['image']]
            
        # Add title and description safe fallback
        if 'title' not in prop_data or pd.isna(prop_data['title']):
            prop_data['title'] = f"Bất động sản tại {prop_data.get('district', 'Hà Nội')}"
            
        if 'description' not in prop_data or pd.isna(prop_data['description']):
            prop_data['description'] = "Đang cập nhật mô tả cho bất động sản này."
        
        # Generate fake phone per property id
        import random as _rand
        _rand.seed(prop_id * 37 + 7)
        phone_full = f"0{_rand.choice([9,8,7])}{_rand.randint(10,99)} {_rand.randint(100,999)} {_rand.randint(100,999)}"
        phone_masked = phone_full[:-3] + '***'
        prop_data['phone_full'] = phone_full
        prop_data['phone_masked'] = phone_masked

        # Filter to only high-res images (1275x717)
        all_imgs = prop_data.get('all_images', [])
        hires = [u for u in all_imgs if '1275x717' in u]
        prop_data['all_images'] = hires if hires else all_imgs[:8]

        logged_in = 'user' in session
        return render_template('property_detail.html', prop=prop_data, logged_in=logged_in, user=session.get('user'))
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    # Chạy server ở port 5000
    debug = os.environ.get('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes'}
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=debug, host=host, port=port)
