"""Conector Mercado Livre.

- Pedidos: GET https://api.mercadolibre.com/orders/search?seller={id}
- Envios:  campo shipping.status de cada pedido
- Product Ads: relatório de métricas por campanha

Em modo demo devolve dados fictícios no mesmo formato.
"""

from __future__ import annotations

import os

from src import demo_data

API = "https://api.mercadolibre.com"


def fetch(start: str, end: str, demo: bool = True) -> tuple[list[dict], list[dict]]:
    """Retorna (métricas de Product Ads, pedidos)."""
    if demo:
        return demo_data.mercado_livre_raw(demo_data.rng())

    import requests

    headers = {"Authorization": f"Bearer {os.environ['ML_ACCESS_TOKEN']}"}
    seller = os.environ["ML_SELLER_ID"]
    orders, offset = [], 0
    while True:
        resp = requests.get(
            f"{API}/orders/search",
            headers=headers,
            params={
                "seller": seller,
                "order.date_created.from": f"{start}T00:00:00.000-03:00",
                "order.date_created.to": f"{end}T23:59:59.000-03:00",
                "offset": offset,
                "limit": 50,
            },
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        orders.extend(page["results"])
        offset += 50
        if offset >= page["paging"]["total"]:
            break

    ads = []  # métricas de Product Ads: endpoint de relatórios da conta de publicidade
    return ads, orders
