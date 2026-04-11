import requests


def get_field_weather_forecast(latitude, longitude):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "hourly": "precipitation,reference_evapotranspiration,temperature_2m",
        "forecast_days": 2,
        "timezone": "auto",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def calculate_watering_status(weather_data):
    hourly = weather_data.get("hourly", {})
    precipitation = hourly.get("precipitation", [])[:24]
    eto = hourly.get("reference_evapotranspiration", [])[:24]

    total_rain_24h = sum(float(x or 0) for x in precipitation)
    total_eto_24h = sum(float(x or 0) for x in eto)

    if total_rain_24h >= 10:
        return {
            "status": "rain_expected",
            "reason": f"Rain forecast is high in next 24h ({total_rain_24h:.2f} mm).",
            "recommended_window": None,
        }

    if total_rain_24h < 2 and total_eto_24h >= 4:
        return {
            "status": "water_now",
            "reason": (
                f"Low rain ({total_rain_24h:.2f} mm) and higher "
                f"evapotranspiration ({total_eto_24h:.2f})."
            ),
            "recommended_window": "early_morning",
        }

    if total_rain_24h < 5:
        return {
            "status": "watch",
            "reason": f"Limited rain forecast in next 24h ({total_rain_24h:.2f} mm).",
            "recommended_window": "evening",
        }

    return {
        "status": "no_need",
        "reason": "Moisture conditions look acceptable for now.",
        "recommended_window": None,
    }