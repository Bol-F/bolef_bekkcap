from pathlib import Path
import json
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


# =========================
# 1. Find the dataset path
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "datasets" / "crop_yield_dataset.csv"


# =========================
# 2. Read the CSV file
# =========================
df = pd.read_csv(DATASET_PATH)

print("Dataset loaded successfully.")
print("Shape:", df.shape)
print(df.head())


# =========================
# 3. Rename columns to simple names
# =========================
df = df.rename(
    columns={
        "Farm_ID": "farm_id",
        "Crop_Type": "crop_type",
        "Farm_Area(acres)": "farm_area_acres",
        "Irrigation_Type": "irrigation_type",
        "Fertilizer_Used(tons)": "fertilizer_used_tons",
        "Pesticide_Used(kg)": "pesticide_used_kg",
        "Yield(tons)": "yield_tons",
        "Soil_Type": "soil_type",
        "Season": "season",
        "Water_Usage(cubic meters)": "water_usage_cubic_meters",
    }
)

print("\nRenamed columns:")
print(df.columns.tolist())


# =========================
# 4. Check missing values
# =========================
print("\nMissing values in each column:")
print(df.isnull().sum())

print("\nDuplicated rows:", df.duplicated().sum())


# =========================
# 5. Normalize text values
#    so they match your app logic better
# =========================
df["crop_type"] = df["crop_type"].astype(str).str.strip()

df["irrigation_type"] = (
    df["irrigation_type"]
    .astype(str)
    .str.strip()
    .str.lower()
    .replace(
        {
            "rain-fed": "rainfed",
            "rain fed": "rainfed",
        }
    )
)

df["soil_type"] = df["soil_type"].astype(str).str.strip().str.lower()
df["season"] = df["season"].astype(str).str.strip().str.lower()


# =========================
# 6. Convert numeric columns
# =========================
numeric_columns = [
    "farm_area_acres",
    "fertilizer_used_tons",
    "pesticide_used_kg",
    "yield_tons",
    "water_usage_cubic_meters",
]

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# =========================
# 7. Remove rows with missing important values
# =========================
required_columns = [
    "crop_type",
    "farm_area_acres",
    "irrigation_type",
    "fertilizer_used_tons",
    "pesticide_used_kg",
    "soil_type",
    "season",
    "water_usage_cubic_meters",
    "yield_tons",
]

df = df.dropna(subset=required_columns).copy()

print("\nShape after cleaning:", df.shape)


# =========================
# 8. Define X and y
#    X = input features
#    y = target
# =========================
feature_columns = [
    "crop_type",
    "farm_area_acres",
    "irrigation_type",
    "fertilizer_used_tons",
    "pesticide_used_kg",
    "soil_type",
    "season",
    "water_usage_cubic_meters",
]

target_column = "yield_tons"

X = df[feature_columns]
y = df[target_column]


# =========================
# 9. Split into train and test
# =========================
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
)

print("\nTrain shape:", X_train.shape)
print("Test shape:", X_test.shape)


# =========================
# 10. Train CatBoost model
# =========================
categorical_features = [
    "crop_type",
    "irrigation_type",
    "soil_type",
    "season",
]

model = CatBoostRegressor(
    iterations=300,
    learning_rate=0.05,
    depth=6,
    loss_function="RMSE",
    verbose=False,
    random_seed=42,
)

model.fit(
    X_train,
    y_train,
    cat_features=categorical_features,
)


# =========================
# 11. Make predictions
# =========================
y_pred = model.predict(X_test)


# =========================
# 12. Evaluate the model
# =========================
mae = mean_absolute_error(y_test, y_pred)
rmse = mean_squared_error(y_test, y_pred) ** 0.5
r2 = r2_score(y_test, y_pred)

print("\nModel evaluation:")
print(f"MAE  = {mae:.4f}")
print(f"RMSE = {rmse:.4f}")
print(f"R2   = {r2:.4f}")


# =========================
# 13. Show a few real vs predicted values
# =========================
results = pd.DataFrame(
    {
        "actual_yield": y_test.values,
        "predicted_yield": y_pred,
    }
)

print("\nSample predictions:")
print(results.head(10))



# =========================
# 14. Save the trained model
# =========================
artifacts_dir = BASE_DIR / "ml_artifacts"
artifacts_dir.mkdir(exist_ok=True)

model_path = artifacts_dir / "yield_catboost_model.cbm"
meta_path = artifacts_dir / "yield_catboost_model_meta.json"

model.save_model(str(model_path))

metadata = {
    "model_name": "CatBoostRegressor",
    "feature_columns": feature_columns,
    "categorical_features": categorical_features,
    "metrics": {
        "mae": round(float(mae), 4),
        "rmse": round(float(rmse), 4),
        "r2": round(float(r2), 4),
    },
    "train_rows": int(len(X_train)),
    "test_rows": int(len(X_test)),
    "total_rows": int(len(df)),
}

with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=4)

print("\nModel saved to:")
print(model_path)

print("\nMetadata saved to:")
print(meta_path)

# =========================
# 15. Show feature importance
# =========================
importance_df = pd.DataFrame(
    {
        "feature": feature_columns,
        "importance": model.get_feature_importance(),
    }
).sort_values(by="importance", ascending=False)

print("\nFeature importance:")
print(importance_df)