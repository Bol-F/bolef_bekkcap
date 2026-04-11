import logging
import math
import random
from datetime import datetime, timedelta

import pandas as pd
from django.conf import settings

logger = logging.getLogger(__name__)

_hf_df = None


def get_ndvi_data(
    center_lat: float | None,
    center_lon: float | None,
    date_from: str,
    date_to: str,
    polygon: list[list[float]] | None = None,
    bbox_padding: float = 0.05,
) -> list[dict]:
    source = getattr(settings, "NDVI_DATA_SOURCE", "synthetic")

    if center_lat is None or center_lon is None:
        if polygon:
            center_lat, center_lon = _polygon_centroid(polygon)
        else:
            raise ValueError(
                "Either center_lat/center_lon or polygon must be provided."
            )

    if source == "huggingface":
        try:
            return _load_huggingface(
                center_lat=center_lat,
                center_lon=center_lon,
                date_from=date_from,
                date_to=date_to,
                bbox_padding=bbox_padding,
            )
        except Exception as exc:
            logger.warning("HuggingFace failed (%s). Falling back to synthetic.", exc)
            return _synthetic(center_lat, center_lon, date_from, date_to)

    if source == "sentinel_api":
        try:
            from ndvi.services.sentinel import sentinel_service

            use_polygon = polygon or _bbox_polygon(center_lat, center_lon, bbox_padding)
            records = sentinel_service.get_ndvi_time_series(
                polygon=use_polygon,
                date_from=date_from,
                date_to=date_to,
            )
            return [{**r, "source": "sentinel_api"} for r in records]
        except Exception as exc:
            logger.warning("Sentinel API failed (%s). Falling back to synthetic.", exc)
            return _synthetic(center_lat, center_lon, date_from, date_to)

    return _synthetic(center_lat, center_lon, date_from, date_to)


def _load_huggingface(
    center_lat: float,
    center_lon: float,
    date_from: str,
    date_to: str,
    bbox_padding: float,
) -> list[dict]:
    global _hf_df

    if _hf_df is None:
        from datasets import load_dataset

        logger.info("Loading HuggingFace dataset into memory...")
        ds = load_dataset(
            settings.HF_DATASET_ID,
            split="train",
            trust_remote_code=True,
        )
        _hf_df = ds.to_pandas()
        _hf_df.columns = [str(c).lower() for c in _hf_df.columns]

        date_col = _find_column(_hf_df.columns, ["date", "datetime", "timestamp"])
        lat_col = _find_column(_hf_df.columns, ["latitude", "lat"])
        lon_col = _find_column(_hf_df.columns, ["longitude", "lon", "lng"])
        ndvi_col = _find_column(_hf_df.columns, ["ndvi"])

        if not all([date_col, lat_col, lon_col, ndvi_col]):
            raise ValueError(
                f"Dataset columns are incompatible. Found: {list(_hf_df.columns)}"
            )

        _hf_df[date_col] = pd.to_datetime(_hf_df[date_col], errors="coerce")
        _hf_df["_date"] = _hf_df[date_col]
        _hf_df["_lat"] = pd.to_numeric(_hf_df[lat_col], errors="coerce")
        _hf_df["_lon"] = pd.to_numeric(_hf_df[lon_col], errors="coerce")
        _hf_df["_ndvi"] = pd.to_numeric(_hf_df[ndvi_col], errors="coerce")

        _hf_df = _hf_df.dropna(subset=["_date", "_lat", "_lon", "_ndvi"]).copy()

    mask = (
        (_hf_df["_lat"] >= center_lat - bbox_padding)
        & (_hf_df["_lat"] <= center_lat + bbox_padding)
        & (_hf_df["_lon"] >= center_lon - bbox_padding)
        & (_hf_df["_lon"] <= center_lon + bbox_padding)
        & (_hf_df["_date"] >= pd.Timestamp(date_from))
        & (_hf_df["_date"] <= pd.Timestamp(date_to))
    )
    sub = _hf_df[mask].copy()

    if sub.empty:
        logger.warning("No HuggingFace rows for this area. Using synthetic fallback.")
        return _synthetic(center_lat, center_lon, date_from, date_to)

    sub["period"] = sub["_date"].dt.to_period("10D")

    agg = (
        sub.groupby("period")
        .agg(
            ndvi_mean=("_ndvi", "mean"),
            ndvi_min=("_ndvi", "min"),
            ndvi_max=("_ndvi", "max"),
            ndvi_std=("_ndvi", "std"),
        )
        .reset_index()
    )

    results = []
    for _, row in agg.iterrows():
        ndvi = round(float(row["ndvi_mean"]), 4)
        ndvi_std = row["ndvi_std"]

        results.append(
            {
                "date": str(row["period"].start_time.date()),
                "ndvi_mean": ndvi,
                "ndvi_min": round(float(row["ndvi_min"]), 4),
                "ndvi_max": round(float(row["ndvi_max"]), 4),
                "ndvi_std": round(float(ndvi_std), 4) if pd.notna(ndvi_std) else None,
                "evi_mean": None,
                "tcg_mean": None,
                "cloud_coverage": None,
                "status": _classify(ndvi),
                "source": "huggingface",
            }
        )

    return sorted(results, key=lambda x: x["date"])


def _find_column(columns, candidates):
    lowered = [str(c).lower() for c in columns]
    for candidate in candidates:
        if candidate in lowered:
            return candidate
    return None


def _synthetic(
    center_lat: float,
    center_lon: float,
    date_from: str,
    date_to: str,
    interval_days: int = 10,
) -> list[dict]:
    seed = int(abs(center_lat * 1000 + center_lon * 100)) % 999999
    rng = random.Random(seed)

    d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
    d_to = datetime.strptime(date_to, "%Y-%m-%d").date()

    results = []
    current = d_from

    while current <= d_to:
        if rng.random() < 0.15:
            current += timedelta(days=interval_days)
            continue

        doy = current.timetuple().tm_yday
        base = _seasonal_ndvi(doy, rng)
        ndvi = max(0.0, min(1.0, base + rng.gauss(0, 0.02)))
        half = rng.uniform(0.04, 0.09)

        results.append(
            {
                "date": str(current),
                "ndvi_mean": round(ndvi, 4),
                "ndvi_min": round(max(0.0, ndvi - half), 4),
                "ndvi_max": round(min(1.0, ndvi + half), 4),
                "ndvi_std": round(rng.uniform(0.03, 0.09), 4),
                "evi_mean": round(max(0.0, ndvi * rng.uniform(0.72, 0.82)), 4),
                "tcg_mean": round(rng.gauss(-0.04, 0.02), 4),
                "cloud_coverage": round(rng.uniform(0, 10), 1),
                "status": _classify(ndvi),
                "source": "synthetic",
            }
        )

        current += timedelta(days=interval_days)

    return results


def _seasonal_ndvi(doy: int, rng: random.Random) -> float:
    winter = rng.uniform(0.08, 0.18)
    spring_peak = rng.uniform(0.55, 0.72) * math.exp(
        -((doy - rng.randint(125, 140)) ** 2) / (2 * 35**2)
    )
    summer_peak = rng.uniform(0.48, 0.65) * math.exp(
        -((doy - rng.randint(188, 205)) ** 2) / (2 * 40**2)
    )
    return winter + spring_peak + summer_peak


def _classify(v: float) -> str:
    if v < 0.2:
        return "bare"
    if v < 0.4:
        return "poor"
    if v < 0.6:
        return "moderate"
    return "healthy"


def _bbox_polygon(lat: float, lon: float, padding: float) -> list[list[float]]:
    min_lon = lon - padding
    max_lon = lon + padding
    min_lat = lat - padding
    max_lat = lat + padding

    return [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]


def _polygon_centroid(polygon: list[list[float]]) -> tuple[float, float]:
    points = polygon[:-1] if polygon and polygon[0] == polygon[-1] else polygon
    if not points:
        raise ValueError("Polygon is empty.")

    center_lon = sum(p[0] for p in points) / len(points)
    center_lat = sum(p[1] for p in points) / len(points)
    return center_lat, center_lon
