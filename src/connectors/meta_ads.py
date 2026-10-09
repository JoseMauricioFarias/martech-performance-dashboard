"""Conector Meta Ads (Marketing API / Graph API).

Endpoint: GET /{versao}/act_{ad_account_id}/insights
Em modo demo devolve dados fictícios no mesmo formato da API.
"""

from __future__ import annotations

import json
import os

from src import demo_data

FIELDS = "campaign_name,spend,impressions,clicks,actions,action_values"


def fetch(start: str, end: str, demo: bool = True) -> list[dict]:
    if demo:
        return demo_data.meta_ads_raw(demo_data.rng())

    import requests

    version = os.environ.get("META_API_VERSION", "v21.0")
    url = f"https://graph.facebook.com/{version}/act_{os.environ['META_AD_ACCOUNT_ID']}/insights"
    params = {
        "level": "campaign",
        "fields": FIELDS,
        "time_increment": 1,
        "time_range": json.dumps({"since": start, "until": end}),
        "limit": 500,
        "access_token": os.environ["META_ACCESS_TOKEN"],
    }
    rows = []
    while url:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        rows.extend(payload.get("data", []))
        url = payload.get("paging", {}).get("next")  # paginação por cursor
        params = None  # a URL "next" já traz os parâmetros
    return rows
