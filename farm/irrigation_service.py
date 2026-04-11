import requests


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_field_weather_forecast(latitude, longitude):
    if latitude is None or longitude is None:
        raise ValueError("Latitude and longitude are required.")

    url = OPEN_METEO_URL
    params = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "hourly": "precipitation,reference_evapotranspiration,temperature_2m",
        "forecast_days": 2,
        "timezone": "auto",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()

    if "hourly" not in data:
        raise ValueError("Weather API response does not contain 'hourly' data.")

    return data


def calculate_watering_status(weather_data):
    hourly = weather_data.get("hourly") or {}
    precipitation = hourly.get("precipitation") or []
    eto = hourly.get("reference_evapotranspiration") or []
    temperatures = hourly.get("temperature_2m") or []

    if not precipitation or not eto:
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
    temperatures_24h = temperatures[:24] if temperatures else []

    total_rain_24h = sum(float(x or 0) for x in precipitation_24h)
    total_eto_24h = sum(float(x or 0) for x in eto_24h)
    avg_temp_24h = (
        round(sum(float(x or 0) for x in temperatures_24h) / len(temperatures_24h), 2)
        if temperatures_24h
        else None
    )

    if total_rain_24h >= 10:
        return {
            "status": "rain_expected",
            "reason": f"Rain forecast is high in the next 24h ({total_rain_24h:.2f} mm).",
            "recommended_window": None,
            "rain_24h_mm": round(total_rain_24h, 2),
            "eto_24h": round(total_eto_24h, 2),
            "avg_temp_24h": avg_temp_24h,
        }

    if total_rain_24h < 2 and total_eto_24h >= 4:
        return {
            "status": "water_now",
            "reason": (
                f"Low rain expected ({total_rain_24h:.2f} mm) and elevated "
                f"evapotranspiration ({total_eto_24h:.2f})."
            ),
            "recommended_window": "early_morning",
            "rain_24h_mm": round(total_rain_24h, 2),
            "eto_24h": round(total_eto_24h, 2),
            "avg_temp_24h": avg_temp_24h,
        }

    if total_rain_24h < 5:
        return {
            "status": "watch",
            "reason": f"Limited rain forecast in the next 24h ({total_rain_24h:.2f} mm).",
            "recommended_window": "evening",
            "rain_24h_mm": round(total_rain_24h, 2),
            "eto_24h": round(total_eto_24h, 2),
            "avg_temp_24h": avg_temp_24h,
        }

    return {
        "status": "no_need",
        "reason": "Moisture conditions look acceptable for now.",
        "recommended_window": None,
        "rain_24h_mm": round(total_rain_24h, 2),
        "eto_24h": round(total_eto_24h, 2),
        "avg_temp_24h": avg_temp_24h,
    }
