import requests
from django.core.cache import cache

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

DEFAULT_CURRENT = [
    "temperature_2m",
    "precipitation",
    "wind_speed_10m",
    "weather_code",
]

DEFAULT_HOURLY = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "precipitation_probability",
    "wind_speed_10m",
    "wind_gusts_10m",
    "weather_code",
    "et0_fao_evapotranspiration",
]

DEFAULT_DAILY = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "weather_code",
    "et0_fao_evapotranspiration",
]


def fetch_open_meteo_forecast(
    lat: float,
    lon: float,
    days: int = 3,
    timezone: str = "auto",
    cache_ttl_seconds: int = 30 * 60,
):
    """
    Returns: (data: dict, from_cache: bool)
    """
    days = int(days)
    key = (
        f"openmeteo:v1:lat={lat:.6f}:lon={lon:.6f}:days={days}:tz={timezone}:"
        f"h={','.join(DEFAULT_HOURLY)}:d={','.join(DEFAULT_DAILY)}:c={','.join(DEFAULT_CURRENT)}"
    )

    cached = cache.get(key)
    if cached is not None:
        return cached, True

    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": timezone,          # timezone=auto supported :contentReference[oaicite:1]{index=1}
        "forecast_days": days,
        "current": ",".join(DEFAULT_CURRENT),
        "hourly": ",".join(DEFAULT_HOURLY),
        "daily": ",".join(DEFAULT_DAILY),
    }

    resp = requests.get(OPEN_METEO_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    cache.set(key, data, timeout=cache_ttl_seconds)
    return data, False
