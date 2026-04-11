import time

import requests
from django.conf import settings


class SentinelAuthError(Exception):
    pass


class SentinelAPIError(Exception):
    pass


class SentinelService:
    def __init__(self):
        self._access_token = None
        self._expires_at = 0

    def _get_token(self) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token

        if not settings.SENTINEL_CLIENT_ID or not settings.SENTINEL_CLIENT_SECRET:
            raise SentinelAuthError(
                "Missing SENTINEL_CLIENT_ID or SENTINEL_CLIENT_SECRET in .env"
            )

        response = requests.post(
            settings.SENTINEL_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": settings.SENTINEL_CLIENT_ID,
                "client_secret": settings.SENTINEL_CLIENT_SECRET,
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise SentinelAuthError(
                f"Token request failed: {response.status_code} {response.text}"
            )

        data = response.json()
        self._access_token = data["access_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_ndvi_time_series(
        self,
        polygon: list[list[float]],
        date_from: str,
        date_to: str,
        max_cloud: int = 30,
    ) -> list[dict]:
        polygon = self._normalize_polygon(polygon)

        evalscript = """
        //VERSION=3
        function setup() {
          return {
            input: [{
              bands: ["B04", "B08", "dataMask"],
              units: "REFLECTANCE"
            }],
            output: [
              { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
              { id: "dataMask", bands: 1 }
            ]
          };
        }

        function evaluatePixel(sample) {
          let denom = sample.B08 + sample.B04;
          let ndvi = denom === 0 ? 0 : (sample.B08 - sample.B04) / denom;

          return {
            ndvi: [ndvi],
            dataMask: [sample.dataMask]
          };
        }
        """.strip()

        payload = {
            "input": {
                "bounds": {
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [polygon],
                    },
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                    },
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "maxCloudCoverage": max_cloud,
                            "mosaickingOrder": "leastCC",
                        },
                    }
                ],
            },
            "aggregation": {
                "timeRange": {
                    "from": f"{date_from}T00:00:00Z",
                    "to": f"{date_to}T23:59:59Z",
                },
                "aggregationInterval": {"of": "P10D"},
                "evalscript": evalscript,
                "resx": 10,
                "resy": 10,
            },
        }

        response = requests.post(
            settings.SENTINEL_STATS_API_URL,
            headers=self._headers(),
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            raise SentinelAPIError(
                f"Statistical API error {response.status_code}: {response.text}"
            )

        return self._parse_stats(response.json())

    def _parse_stats(self, data: dict) -> list[dict]:
        intervals = []

        for item in data.get("data", []):
            try:
                stats = item["outputs"]["ndvi"]["bands"]["B0"]["stats"]
            except KeyError:
                continue

            sample_count = stats.get("sampleCount", 0)
            no_data_count = stats.get("noDataCount", 0)

            if sample_count == 0 or sample_count == no_data_count:
                continue

            mean_val = stats.get("mean")
            if mean_val is None:
                continue

            intervals.append(
                {
                    "date": item["interval"]["from"][:10],
                    "ndvi_mean": round(float(mean_val), 4),
                    "ndvi_min": round(float(stats.get("min", mean_val)), 4),
                    "ndvi_max": round(float(stats.get("max", mean_val)), 4),
                    "ndvi_std": round(float(stats.get("stDev", 0)), 4),
                    "evi_mean": None,
                    "tcg_mean": None,
                    "cloud_coverage": None,
                    "status": _classify(float(mean_val)),
                    "source": "sentinel_api",
                }
            )

        if not intervals:
            raise SentinelAPIError("No valid NDVI statistics found for this request.")

        return sorted(intervals, key=lambda x: x["date"])

    def get_ndvi_map_png(
        self,
        polygon: list[list[float]],
        date: str,
        width: int = 512,
        height: int = 512,
    ) -> bytes:
        polygon = self._normalize_polygon(polygon)

        evalscript = """
        //VERSION=3
        function setup() {
          return {
            input: ["B04", "B08"],
            output: { bands: 3 }
          };
        }

        function evaluatePixel(s) {
          let n = (s.B08 - s.B04) / (s.B08 + s.B04);
          if (n < 0.2) return [0.8, 0.2, 0.1];
          if (n < 0.4) return [0.95, 0.75, 0.15];
          if (n < 0.6) return [0.45, 0.8, 0.2];
          return [0.1, 0.5, 0.1];
        }
        """.strip()

        payload = {
            "input": {
                "bounds": {
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [polygon],
                    }
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "timeRange": {
                                "from": f"{date}T00:00:00Z",
                                "to": f"{date}T23:59:59Z",
                            },
                            "maxCloudCoverage": 30,
                        },
                    }
                ],
            },
            "output": {
                "width": width,
                "height": height,
                "responses": [
                    {
                        "identifier": "default",
                        "format": {"type": "image/png"},
                    }
                ],
            },
            "evalscript": evalscript,
        }

        response = requests.post(
            settings.SENTINEL_PROCESS_API_URL,
            headers=self._headers(),
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            raise SentinelAPIError(
                f"Process API error {response.status_code}: {response.text}"
            )

        return response.content

    def _normalize_polygon(self, polygon: list[list[float]]) -> list[list[float]]:
        if not polygon or len(polygon) < 4:
            raise SentinelAPIError(
                "A valid polygon with at least 4 points is required."
            )

        normalized = [[float(pt[0]), float(pt[1])] for pt in polygon]
        if normalized[0] != normalized[-1]:
            normalized.append(normalized[0])

        return normalized


def _classify(v: float) -> str:
    if v < 0.2:
        return "bare"
    if v < 0.4:
        return "poor"
    if v < 0.6:
        return "moderate"
    return "healthy"


sentinel_service = SentinelService()
