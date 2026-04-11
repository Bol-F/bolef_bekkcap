from __future__ import annotations

from statistics import mean, stdev


def analyze_trend(time_series: list[dict]) -> dict:
    cleaned = _normalize_series(time_series)

    if not cleaned:
        return {
            "trend": "unknown",
            "change": 0,
            "change_pct": 0,
            "insight": "No data available for this period.",
            "anomalies": [],
            "season_summary": {},
        }

    if len(cleaned) == 1:
        r = cleaned[0]
        return {
            "trend": "stable",
            "change": 0,
            "change_pct": 0,
            "period_start": r["date"],
            "period_end": r["date"],
            "ndvi_start": r["ndvi_mean"],
            "ndvi_end": r["ndvi_mean"],
            "insight": _single_insight(r["ndvi_mean"], r.get("status", "unknown")),
            "anomalies": [],
            "season_summary": _season_summary(cleaned),
        }

    first = cleaned[0]
    last = cleaned[-1]

    change = round(last["ndvi_mean"] - first["ndvi_mean"], 4)
    change_pct = (
        round((change / first["ndvi_mean"]) * 100, 1) if first["ndvi_mean"] else 0
    )

    if change > 0.05:
        trend = "improving"
    elif change < -0.05:
        trend = "declining"
    else:
        trend = "stable"

    anomalies = detect_anomalies(cleaned)
    summary = _season_summary(cleaned)

    return {
        "trend": trend,
        "change": change,
        "change_pct": change_pct,
        "period_start": first["date"],
        "period_end": last["date"],
        "ndvi_start": first["ndvi_mean"],
        "ndvi_end": last["ndvi_mean"],
        "insight": _build_insight(trend, change, change_pct, first, last, anomalies),
        "anomalies": anomalies,
        "season_summary": summary,
    }


def detect_anomalies(time_series: list[dict]) -> list[dict]:
    cleaned = _normalize_series(time_series)

    if len(cleaned) < 2:
        return []

    anomalies = []
    low_streak = 0
    low_start = None

    for i, rec in enumerate(cleaned):
        if i > 0:
            prev = cleaned[i - 1]
            delta = rec["ndvi_mean"] - prev["ndvi_mean"]

            if delta < -0.15:
                anomalies.append(
                    {
                        "type": "sudden_drop",
                        "date": rec["date"],
                        "delta": round(delta, 4),
                        "from": prev["ndvi_mean"],
                        "to": rec["ndvi_mean"],
                        "message": (
                            f"NDVI dropped {abs(delta):.3f} on {rec['date']} "
                            f"({prev['ndvi_mean']:.3f} → {rec['ndvi_mean']:.3f}). "
                            "Possible drought, disease, pests, or harvest."
                        ),
                    }
                )
            elif delta > 0.20:
                anomalies.append(
                    {
                        "type": "sudden_spike",
                        "date": rec["date"],
                        "delta": round(delta, 4),
                        "from": prev["ndvi_mean"],
                        "to": rec["ndvi_mean"],
                        "message": (
                            f"NDVI increased sharply by {delta:.3f} on {rec['date']}. "
                            "Possible irrigation, rainfall, or sensor artifact."
                        ),
                    }
                )

        if rec["ndvi_mean"] < 0.2:
            if low_streak == 0:
                low_start = rec["date"]
            low_streak += 1

            if low_streak == 3:
                anomalies.append(
                    {
                        "type": "persistent_low",
                        "date": low_start,
                        "message": (
                            f"NDVI stayed below 0.2 for 3+ periods starting {low_start}. "
                            "Field may be bare, flooded, harvested, or heavily stressed."
                        ),
                    }
                )
        else:
            low_streak = 0
            low_start = None

    return anomalies


def _normalize_series(time_series: list[dict]) -> list[dict]:
    cleaned = []

    for item in time_series or []:
        if "date" not in item or "ndvi_mean" not in item:
            continue
        try:
            ndvi = float(item["ndvi_mean"])
        except (TypeError, ValueError):
            continue

        cleaned.append(
            {
                "date": str(item["date"]),
                "ndvi_mean": ndvi,
                "status": item.get("status", _overall(ndvi)),
            }
        )

    cleaned.sort(key=lambda x: x["date"])
    return cleaned


def _season_summary(time_series: list[dict]) -> dict:
    if not time_series:
        return {}

    values = [float(r["ndvi_mean"]) for r in time_series]
    peak = max(time_series, key=lambda r: r["ndvi_mean"])
    trough = min(time_series, key=lambda r: r["ndvi_mean"])
    growing = [r for r in time_series if r["ndvi_mean"] > 0.3]
    avg = mean(values)

    return {
        "peak_ndvi": round(float(peak["ndvi_mean"]), 4),
        "peak_date": peak["date"],
        "trough_ndvi": round(float(trough["ndvi_mean"]), 4),
        "trough_date": trough["date"],
        "mean_ndvi": round(avg, 4),
        "std_ndvi": round(stdev(values), 4) if len(values) > 1 else 0,
        "growing_season_periods": len(growing),
        "overall_status": _overall(avg),
    }


def _overall(avg: float) -> str:
    if avg < 0.2:
        return "bare"
    if avg < 0.4:
        return "poor"
    if avg < 0.6:
        return "moderate"
    return "healthy"


def _single_insight(ndvi: float, status: str) -> str:
    messages = {
        "bare": f"NDVI {ndvi:.3f} — Bare soil or no active vegetation.",
        "poor": f"NDVI {ndvi:.3f} — Low vegetation health. Water stress is possible.",
        "moderate": f"NDVI {ndvi:.3f} — Moderate vegetation condition. Continue monitoring.",
        "healthy": f"NDVI {ndvi:.3f} — Healthy vegetation. No immediate concern.",
    }
    return messages.get(status, f"NDVI {ndvi:.3f} — status: {status}.")


def _build_insight(trend, change, change_pct, first, last, anomalies) -> str:
    direction = "increased" if change > 0 else "decreased"
    abs_pct = abs(change_pct)

    base = (
        f"NDVI {direction} from {first['ndvi_mean']:.3f} to {last['ndvi_mean']:.3f} "
        f"({abs(change):.3f} / {abs_pct:.1f}%) from {first['date']} to {last['date']}."
    )

    if trend == "improving":
        advice = (
            " Vegetation is improving."
            if last.get("status") != "healthy"
            else " Vegetation is healthy and strong."
        )
    elif trend == "declining":
        if abs_pct > 30:
            advice = " Strong decline detected. Field inspection is recommended."
        elif abs_pct > 15:
            advice = (
                " Moderate decline detected. Check irrigation and stress indicators."
            )
        else:
            advice = " Slight decline. Monitor the next observation."
    else:
        advice = f" Vegetation is stable at '{last.get('status', 'unknown')}' level."

    if anomalies:
        advice += f" {len(anomalies)} anomaly event(s) detected."

    return base + advice
