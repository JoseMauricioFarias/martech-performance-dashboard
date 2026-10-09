"""Conector Google Ads.

Em produção usa a biblioteca oficial `google-ads` com uma consulta GAQL.
Em modo demo devolve dados fictícios no mesmo formato da API.
"""

from __future__ import annotations

import os

from src import demo_data

GAQL = """
SELECT
  campaign.id,
  campaign.name,
  segments.date,
  metrics.cost_micros,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions,
  metrics.conversions_value
FROM campaign
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND campaign.status != 'REMOVED'
"""


def fetch(start: str, end: str, demo: bool = True) -> list[dict]:
    if demo:
        return demo_data.google_ads_raw(demo_data.rng())

    from google.ads.googleads.client import GoogleAdsClient  # pip install google-ads

    client = GoogleAdsClient.load_from_env()  # GOOGLE_ADS_DEVELOPER_TOKEN, credenciais OAuth etc.
    service = client.get_service("GoogleAdsService")
    rows = []
    stream = service.search_stream(
        customer_id=os.environ["GOOGLE_ADS_CUSTOMER_ID"], query=GAQL.format(start=start, end=end)
    )
    for batch in stream:
        for r in batch.results:
            rows.append({
                "campaign": {"id": r.campaign.id, "name": r.campaign.name},
                "segments": {"date": r.segments.date},
                "metrics": {
                    "cost_micros": r.metrics.cost_micros,
                    "impressions": r.metrics.impressions,
                    "clicks": r.metrics.clicks,
                    "conversions": r.metrics.conversions,
                    "conversions_value": r.metrics.conversions_value,
                },
            })
    return rows
