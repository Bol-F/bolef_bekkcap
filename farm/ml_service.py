import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
from catboost import CatBoostRegressor
from django.conf import settings
from django.utils import timezone

from .models import YieldRecord

MODEL_DIR = Path(settings.BASE_DIR) / "ml_artifacts"
MODEL_PATH = MODEL_DIR / "yield_catboost_model.cbm"
META_PATH = MODEL_DIR / "yield_catboost_model_meta.json"

IRRIGATION_MAP = {
    "drip": "drip",
    "sprinkler": "sprinkler",
    "manual": "manual",
    "flood": "flood",
    "rain-fed": "rainfed",
    "rain fed": "rainfed",
    "rainfed": "rainfed",
}

SOIL_MAP = {
    "loamy": "loamy",
    "sandy": "sandy",
    "clay": "clay",
    "silty": "silty",
    "peaty": "peaty",
}

SEASON_MAP = {
    "kharif": "kharif",
    "rabi": "rabi",
    "zaid": "zaid",
}


def _normalize(value, mapping: dict[str, str], default: str = "other") -> str:
    key = str(value or "").strip().lower()
    return mapping.get(key, default)


def normalize_irrigation(value) -> str:
    return _normalize(value, IRRIGATION_MAP)


def normalize_soil(value) -> str:
    return _normalize(value, SOIL_MAP)


def normalize_season(value) -> str:
    return _normalize(value, SEASON_MAP)


@lru_cache(maxsize=1)
def load_model_and_metadata() -> tuple[CatBoostRegressor, dict]:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")
    if not META_PATH.exists():
        raise FileNotFoundError(f"Metadata file not found: {META_PATH}")

    model = CatBoostRegressor()
    model.load_model(str(MODEL_PATH))

    with open(META_PATH, "r", encoding="utf-8") as fh:
        metadata = json.load(fh)

    return model, metadata


def build_features_from_yield_record(
    record: YieldRecord, feature_columns: list[str]
) -> pd.DataFrame:
    data = {
        "crop_type": str(record.crop_type).strip(),
        "farm_area_acres": float(record.farm_area_acres),
        "irrigation_type": normalize_irrigation(record.irrigation_type),
        "fertilizer_used_tons": float(record.fertilizer_used_tons),
        "pesticide_used_kg": float(record.pesticide_used_kg),
        "soil_type": normalize_soil(record.soil_type),
        "season": normalize_season(record.season),
        "water_usage_cubic_meters": float(record.water_usage_cubic_meters),
    }

    missing = [c for c in feature_columns if c not in data]
    if missing:
        raise KeyError(
            f"Model expects feature columns that are not produced here: {missing}"
        )

    return pd.DataFrame([data])[feature_columns]


def predict_yield_for_record(record: YieldRecord) -> dict:
    model, metadata = load_model_and_metadata()
    feature_columns = metadata["feature_columns"]

    features_df = build_features_from_yield_record(record, feature_columns)
    predicted_value = float(model.predict(features_df)[0])

    record.predicted_yield_tons = round(predicted_value, 2)
    record.model_name = metadata.get("model_name", "CatBoostRegressor")
    record.prediction_created_at = timezone.now()
    record.save(
        update_fields=[
            "predicted_yield_tons",
            "model_name",
            "prediction_created_at",
        ]
    )

    return {
        "yield_record_id": record.id,
        "predicted_yield_tons": record.predicted_yield_tons,
        "model_name": record.model_name,
        "prediction_created_at": record.prediction_created_at,
    }
