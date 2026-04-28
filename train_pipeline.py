import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
import pickle
import os

print("Bat dau qua trinh huan luyen mo hinh voi Pipeline...")
os.makedirs('models', exist_ok=True)

def train_model(data_path, model_name, num_features, cat_features):
    print(f"\n--- Dang huan luyen cho: {model_name} ---")
    try:
        df = pd.read_csv(data_path)
        print(f"Da load du lieu: {len(df)} dong.")
    except Exception as e:
        print(f"Loi doc file {data_path}: {e}")
        return

    # Kiểm tra thiếu cột
    missing_cols = [col for col in num_features + cat_features if col not in df.columns]
    if missing_cols:
        print(f"Loi: Thieu cac cot trong du lieu {missing_cols}")
        return

    # Pipeline xử lý
    num_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    cat_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='constant', fill_value='Không rõ')),
        ('onehot', OneHotEncoder(handle_unknown='ignore'))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', num_transformer, num_features),
            ('cat', cat_transformer, cat_features)
        ])

    pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('model', RandomForestRegressor(n_estimators=100, random_state=42))
    ])

    X = df[num_features + cat_features]
    y = df['price_billion']

    print("Dang train (Training)...")
    pipeline.fit(X, y)

    model_path = f'models/{model_name}.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(pipeline, f)
    
    print(f"Hoan thanh! Da luu mo hinh tai: {model_path}")

# 1. Huấn luyện cho Chung Cư
train_model(
    data_path='data/processed/cleaned_chung_cu.csv',
    model_name='model_chung_cu_pipeline',
    num_features=['area_m2', 'bedrooms_num'],
    cat_features=['district', 'direction', 'balcony_direction', 'furniture_std', 'legal_std']
)

# 2. Huấn luyện cho Nhà Đất
train_model(
    data_path='data/processed/cleaned_nha_dat.csv',
    model_name='model_nha_dat_pipeline',
    num_features=['area_m2', 'bedrooms_num', 'floors_num', 'frontage_m', 'road_width_m'],
    cat_features=['district', 'direction', 'furniture_std', 'legal_std']
)

print("\nDa huan luyen xong toan bo!")
