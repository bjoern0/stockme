"""Abruf von Wirtschaftsdaten über die FRED API (Federal Reserve Economic Data)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import requests
import pandas as pd

logger = logging.getLogger(__name__)

FRED_API_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_fred_series(api_key: str, series_id: str, days: int = 365) -> dict | None:
    """Fetches data for a single FRED series."""
    if not api_key:
        logger.warning("FRED_API_KEY not set, skipping FRED data fetch for %s", series_id)
        return None

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date.strftime("%Y-%m-%d"),
        "observation_end": end_date.strftime("%Y-%m-%d"),
        "sort_order": "desc",  # Get most recent first
        "limit": 1,  # Only need the latest observation
    }

    try:
        response = requests.get(FRED_API_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        observations = data.get("observations")
        if observations:
            latest_obs = observations[0]
            value = latest_obs.get("value")
            if value != ".":  # FRED uses "." for missing values
                return {"date": latest_obs.get("date"), "value": float(value)}
        logger.warning("No valid data found for FRED series %s", series_id)
        return None
    except requests.exceptions.RequestException as e:
        logger.error("Error fetching FRED series %s: %s", series_id, e)
        return None
    except Exception as e:
        logger.error("Unexpected error processing FRED data for %s: %s", series_id, e)
        return None


def fetch_all_fred_data(api_key: str, series_configs: list[dict]) -> dict[str, dict]:
    """Fetches data for multiple FRED series."""
    if not api_key:
        logger.warning("FRED_API_KEY not set, skipping all FRED data fetches.")
        return {}

    fred_data = {}
    for config in series_configs:
        series_id = config.get("id")
        display_name = config.get("name", series_id)
        if series_id:
            data = fetch_fred_series(api_key, series_id)
            if data:
                fred_data[series_id] = {"display_name": display_name, **data}
    return fred_data