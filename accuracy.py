"""Evaluate a CatBoost yield-prediction model on the crop yield dataset.

Trains a model using the same feature names and normalization as
`farm.ml_service`, so the reported metrics are comparable with the
model served in production.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    r2_score,
    root_mean_squared_error,
)
from sklearn.model_selection import train_test_split

DATASET_PATH = "datasets/crop_yield_dataset.csv"
RANDOM_STATE = 42
TEST_SIZE = 0.2

COLUMN_RENAME = {
    "Crop_Type": "crop_type",
    "Farm_Area(acres)": "farm_area_acres",
    "Irrigation_Type": "irrigation_type",
    "Fertilizer_Used(tons)": "fertilizer_used_tons",
    "Pesticide_Used(kg)": "pesticide_used_kg",
    "Soil_Type": "soil_type",
    "Season": "season",
    "Water_Usage(cubic meters)": "water_usage_cubic_meters",
}

FEATURE_COLUMNS = list(COLUMN_RENAME.values())
CATEGORICAL_FEATURES = ["crop_type", "irrigation_type", "soil_type", "season"]
TARGET_COLUMN = "Yield(tons)"


def load_dataset(path: str) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(path)
    df = df.rename(columns=COLUMN_RENAME)

    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype(str).str.strip().str.lower()

    x = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    return x, y


def train_model(x_train: pd.DataFrame, y_train: pd.Series) -> CatBoostRegressor:
    model = CatBoostRegressor(
        iterations=300,
        depth=6,
        learning_rate=0.05,
        loss_function="RMSE",
        random_seed=RANDOM_STATE,
        verbose=0,
    )
    model.fit(x_train, y_train, cat_features=CATEGORICAL_FEATURES)
    return model


def compute_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(root_mean_squared_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
        "mape_percent": float(mean_absolute_percentage_error(y_true, y_pred) * 100),
    }


def build_per_row_report(y_true: pd.Series, y_pred: np.ndarray) -> pd.DataFrame:
    actual = y_true.to_numpy(dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    absolute_error = np.abs(actual - predicted)

    # Avoid division-by-zero for rows where the actual yield is zero.
    with np.errstate(divide="ignore", invalid="ignore"):
        percent_error = np.where(
            actual != 0,
            (absolute_error / np.abs(actual)) * 100,
            np.nan,
        )

    return pd.DataFrame(
        {
            "actual": actual,
            "predicted": predicted,
            "absolute_error": absolute_error,
            "percent_error": percent_error,
        }
    )


def print_report(report: pd.DataFrame, metrics: dict[str, float]) -> None:
    with pd.option_context("display.max_rows", 20, "display.width", 120):
        print(report)

    print()
    print(f"MAE:  {metrics['mae']:.4f}")
    print(f"RMSE: {metrics['rmse']:.4f}")
    print(f"R2:   {metrics['r2']:.4f}")
    print(f"MAPE: {metrics['mape_percent']:.2f} %")
    print(f"Approx accuracy (100 - MAPE): {100 - metrics['mape_percent']:.2f} %")


def main() -> None:
    x, y = load_dataset(DATASET_PATH)

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    model = train_model(x_train, y_train)
    y_pred = model.predict(x_test)

    metrics = compute_metrics(y_test, y_pred)
    report = build_per_row_report(y_test, y_pred)
    print_report(report, metrics)


if __name__ == "__main__":
    main()
