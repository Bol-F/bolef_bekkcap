import requests


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Thresholds (in mm over the next 24h and mm/day of evapotranspiration).
HEAVY_RAIN_MM = 10.0
DRY_RAIN_MM = 2.0
LIGHT_RAIN_MM = 5.0
HIGH_ETO_MM = 4.0


def get_field_weather_forecast(latitude, longitude):
    if latitude is None or longitude is None:
        raise ValueError("Latitude and longitude are required.")

    params = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "hourly": "precipitation,reference_evapotranspiration,temperature_2m",
        "forecast_days": 2,
        "timezone": "auto",
    }

    response = requests.get(OPEN_METEO_URL, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()

    if "hourly" not in data:
        raise ValueError("Weather API response does not contain 'hourly' data.")

    return data


def _safe_sum(values):
    return sum(float(v or 0) for v in values)


def _safe_avg(values):
    numbers = [float(v) for v in values if v is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 2)


def calculate_watering_status(weather_data):
    hourly = weather_data.get("hourly") or {}
    precipitation = hourly.get("precipitation") or []
    eto = hourly.get("reference_evapotranspiration") or []
    temperatures = hourly.get("temperature_2m") or []

    # Precipitation is the primary signal. Without it we can't decide.
    if not precipitation:
        return {
            "status": "unknown",
            "reason": "Weather forecast data is incomplete. Unable to calculate watering status reliably.",
            "recommended_window": None,
            "rain_24h_mm": None,
            "eto_24h": None,
            "avg_temp_24h": None,
        }

    precipitation_24h = precipitation[:24]
    eto_24h = eto[:24]
    temperatures_24h = temperatures[:24]

    total_rain_24h = _safe_sum(precipitation_24h)
    total_eto_24h = _safe_sum(eto_24h) if eto_24h else None
    avg_temp_24h = _safe_avg(temperatures_24h)

    rain_rounded = round(total_rain_24h, 2)
    eto_rounded = round(total_eto_24h, 2) if total_eto_24h is not None else None

    base_payload = {
        "rain_24h_mm": rain_rounded,
        "eto_24h": eto_rounded,
        "avg_temp_24h": avg_temp_24h,
    }

    if total_rain_24h >= HEAVY_RAIN_MM:
        return {
            "status": "rain_expected",
            "reason": f"Rain forecast is high in the next 24h ({rain_rounded:.2f} mm).",
            "recommended_window": None,
            **base_payload,
        }

    if (
        total_rain_24h < DRY_RAIN_MM
        and total_eto_24h is not None
        and total_eto_24h >= HIGH_ETO_MM
    ):
        return {
            "status": "water_now",
            "reason": (
                f"Low rain expected ({rain_rounded:.2f} mm) and elevated "
                f"evapotranspiration ({eto_rounded:.2f})."
            ),
            "recommended_window": "early_morning",
            **base_payload,
        }

    if total_rain_24h < LIGHT_RAIN_MM:
        return {
            "status": "watch",
            "reason": f"Limited rain forecast in the next 24h ({rain_rounded:.2f} mm).",
            "recommended_window": "evening",
            **base_payload,
        }

    return {
        "status": "no_need",
        "reason": "Moisture conditions look acceptable for now.",
        "recommended_window": None,
        **base_payload,
    }
