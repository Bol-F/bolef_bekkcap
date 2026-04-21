import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, mean_absolute_percentage_error
from catboost import CatBoostRegressor

df = pd.read_csv("datasets/crop_yield_dataset.csv")

X = df[
    [
        "Crop_Type",
        "Farm_Area(acres)",
        "Irrigation_Type",
        "Fertilizer_Used(tons)",
        "Pesticide_Used(kg)",
        "Soil_Type",
        "Season",
        "Water_Usage(cubic meters)",
    ]
]

y = df["Yield(tons)"]

categorical_features = [
    "Crop_Type",
    "Irrigation_Type",
    "Soil_Type",
    "Season",
]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = CatBoostRegressor(
    iterations=300,
    depth=6,
    learning_rate=0.05,
    loss_function="RMSE",
    verbose=0
)

model.fit(X_train, y_train, cat_features=categorical_features)

y_pred = model.predict(X_test)

mae = mean_absolute_error(y_test, y_pred)
rmse = mean_squared_error(y_test, y_pred) ** 0.5
r2 = r2_score(y_test, y_pred)
mape = mean_absolute_percentage_error(y_test, y_pred) * 100

result = pd.DataFrame({
    "actual": y_test.values,
    "predicted": y_pred
})

result["absolute_error"] = abs(result["actual"] - result["predicted"])
result["percent_error"] = (result["absolute_error"] / result["actual"]) * 100

print(result)
print()
print("MAE:", round(mae, 4))
print("RMSE:", round(rmse, 4))
print("R2:", round(r2, 4))
print("MAPE:", round(mape, 2), "%")
print("Approx Accuracy:", round(100 - mape, 2), "%")