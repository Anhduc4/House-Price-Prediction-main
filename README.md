# House Price Prediction

Flask web app du doan gia bat dong san, tim kiem BDS, xem phan tich du lieu va dang nhap bang email/Google OAuth.

## 1. Chay local lan dau

```powershell
cd "C:\Users\vuanh\Documents\Kì 2 N4\Phát triển các hệ thống thông minh\House-Price-Prediction-main"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Neu `.venv` bi loi do duong dan co dau tieng Viet, co the chay bang Python he thong:

```powershell
python -m pip install -r requirements.txt
python app/app.py
```

## 2. Cau hinh Google OAuth de dang nhap Google

Khong hard-code Client ID/Secret vao `app/app.py` va khong commit secret len GitHub.

### Cach A: dung file local

Copy file mau:

```powershell
copy app\oauth_config.example.py app\oauth_config.py
```

Sua `app/oauth_config.py`:

```python
GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"
```

File `app/oauth_config.py` da nam trong `.gitignore`, nen se khong bi commit.

### Cach B: dung bien moi truong

```powershell
$env:GOOGLE_CLIENT_ID="YOUR_GOOGLE_CLIENT_ID"
$env:GOOGLE_CLIENT_SECRET="YOUR_GOOGLE_CLIENT_SECRET"
python app/app.py
```

### Google Cloud Console

Trong OAuth Client, them **Authorized redirect URIs**:

```text
http://127.0.0.1:5000/auth/google/callback
http://localhost:5000/auth/google/callback
```

Neu deploy len domain public, them URI production, vi du:

```text
https://your-domain.com/auth/google/callback
```

Sau khi cau hinh xong, restart Flask. Kiem tra:

```powershell
python -c "from app.app import app; print(app.test_client().get('/api/auth/status').json)"
```

Ket qua dung:

```text
{'google_configured': True}
```

## 3. Chay ung dung

```powershell
python app/app.py
```

Mo:

```text
http://127.0.0.1:5000
```

Tai khoan email demo:

```text
admin@prophet.vn
123456
```

## 4. Kiem tra truoc khi public/push

Chay cac lenh:

```powershell
python -m compileall app train_pipeline.py
python -c "from app.app import app; c=app.test_client(); print(c.get('/').status_code); print(c.get('/about').status_code); print(c.get('/api/auth/status').json)"
rg -n "GOCSPX-|apps\\.googleusercontent\\.com|AIza|ya29\\." -S . --glob "!README.md"
git status --short
```

Lenh `rg` khong duoc in ra secret that. Neu co, xoa truoc khi commit.

## 5. Commit va push len GitHub

```powershell
git add .
git status --short
git commit -m "Finalize house price prediction app"
git pull origin main --rebase
git push origin main
```

Neu GitHub bao push protection do secret:

1. Xoa secret khoi file.
2. Kiem tra lai bang `rg`.
3. Neu secret da nam trong commit, can rewrite commit local roi push lai.
4. Khong bam unblock secret tru khi chac chan secret da rotate.

## 6. Checklist public lan cuoi

- `app/oauth_config.py` ton tai local neu muon Google login local.
- `app/oauth_config.py` khong bi commit.
- Google Cloud da co redirect URI dung.
- `python -m compileall app train_pipeline.py` pass.
- Trang `/`, `/about`, `/search`, `/analytics` mo duoc.
- Google login button khong bi disabled khi `/api/auth/status` tra `google_configured: True`.
- Khong con secret trong repo.
