"""Gera dados FICTÍCIOS no formato bruto de cada plataforma.

Nenhum número aqui vem de empresa real. A ideia é simular, com realismo,
o que as APIs devolvem (cada uma com seu formato), para que o pipeline
de ETL tenha o mesmo trabalho que teria em produção.

- Google Ads: custo em micros, conversões como float
- Meta Ads: valores como string, conversões dentro de listas de "actions"
- Mercado Livre: um registro por pedido, com status de envio
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta

SEED = 42
END_DATE = date(2026, 10, 8)
DAYS = 120

# (nome da campanha, investimento base/dia R$, CPC médio R$, CTR, taxa de conversão, ticket médio R$)
GOOGLE_CAMPAIGNS = [
    ("Search | Marca", 180, 0.55, 0.112, 0.052, 189),
    ("Search | Genéricas", 420, 1.35, 0.046, 0.016, 172),
    ("Performance Max | Catálogo", 650, 0.90, 0.021, 0.0125, 205),
]
META_CAMPAIGNS = [
    ("Prospecção | Lookalike 3%", 520, 0.95, 0.013, 0.0098, 165),
    ("Remarketing | Carrinho abandonado", 210, 0.70, 0.024, 0.026, 198),
    ("Advantage+ Shopping", 480, 0.85, 0.016, 0.0135, 181),
]
ML_CAMPAIGNS = [
    ("Product Ads | Mais vendidos", 260, 0.60, 0.031, 0.030, 142),
    ("Product Ads | Lançamentos", 140, 0.75, 0.022, 0.0125, 156),
]

PROMO_DAYS = {date(2026, 9, 15): 2.6, date(2026, 9, 14): 1.5, date(2026, 9, 16): 1.4}  # Dia do Cliente


def _dates():
    start = END_DATE - timedelta(days=DAYS - 1)
    return [start + timedelta(days=i) for i in range(DAYS)]


def _day_factor(d: date, i: int) -> float:
    weekday = [1.05, 1.08, 1.04, 1.0, 0.97, 0.86, 0.9][d.weekday()]
    trend = 1 + 0.0025 * i  # crescimento leve ao longo do período
    wave = 1 + 0.06 * math.sin(i / 9)
    return weekday * trend * wave * PROMO_DAYS.get(d, 1.0)


def _simulate(campaigns, rng: random.Random):
    """Devolve linhas genéricas (campanha, dia, gasto, impressões, cliques, conv, receita)."""
    rows = []
    for i, d in enumerate(_dates()):
        f = _day_factor(d, i)
        for name, budget, cpc, ctr, cvr, ticket in campaigns:
            spend = budget * f * rng.uniform(0.85, 1.15)
            clicks = max(1, int(spend / (cpc * rng.uniform(0.9, 1.1))))
            impressions = int(clicks / (ctr * rng.uniform(0.9, 1.1)))
            conv_rate = cvr * (1.25 if d in PROMO_DAYS else 1.0) * rng.uniform(0.75, 1.25)
            conversions = round(clicks * conv_rate, 2)
            revenue = conversions * ticket * rng.uniform(0.9, 1.1)
            rows.append((name, d, spend, impressions, clicks, conversions, revenue))
    return rows


def google_ads_raw(rng: random.Random):
    """Formato parecido com a resposta do GAQL (google-ads-python)."""
    ids = {c[0]: 1000 + i for i, c in enumerate(GOOGLE_CAMPAIGNS)}
    out = []
    for name, d, spend, imp, clk, conv, rev in _simulate(GOOGLE_CAMPAIGNS, rng):
        out.append({
            "campaign": {"id": ids[name], "name": name},
            "segments": {"date": d.isoformat()},
            "metrics": {
                "cost_micros": int(spend * 1_000_000),
                "impressions": imp,
                "clicks": clk,
                "conversions": conv,
                "conversions_value": round(rev, 2),
            },
        })
    return out


def meta_ads_raw(rng: random.Random):
    """Formato parecido com /act_{id}/insights?level=campaign&time_increment=1."""
    out = []
    for name, d, spend, imp, clk, conv, rev in _simulate(META_CAMPAIGNS, rng):
        out.append({
            "campaign_name": name,
            "date_start": d.isoformat(),
            "date_stop": d.isoformat(),
            "spend": f"{spend:.2f}",
            "impressions": str(imp),
            "clicks": str(clk),
            "actions": [{"action_type": "purchase", "value": f"{conv:.2f}"}],
            "action_values": [{"action_type": "purchase", "value": f"{rev:.2f}"}],
        })
    return out


def mercado_livre_raw(rng: random.Random):
    """Product Ads (métricas diárias) + pedidos com status de envio."""
    ads, orders = [], []
    order_id = 2000000000
    for name, d, spend, imp, clk, conv, rev in _simulate(ML_CAMPAIGNS, rng):
        ads.append({
            "campaign_name": name, "date": d.isoformat(), "cost": round(spend, 2),
            "prints": imp, "clicks": clk, "units_quantity": conv, "total_amount": round(rev, 2),
        })
        for _ in range(int(round(conv))):
            order_id += 1
            age = (END_DATE - d).days
            r = rng.random()
            if age <= 2:
                status = "shipped" if r < 0.7 else "ready_to_ship"
            else:
                status = "delivered" if r < 0.93 else ("not_delivered" if r < 0.96 else "delayed")
            orders.append({
                "id": order_id, "date_created": d.isoformat(), "status": "paid",
                "total_amount": round(rev / max(conv, 1), 2), "shipping": {"status": status},
            })
    return ads, orders


def crm_sales_raw(rng: random.Random):
    """Vendas do CRM: aprovadas ficam separadas das que estão em análise."""
    out = []
    for i, d in enumerate(_dates()):
        f = _day_factor(d, i)
        approved = int(115 * f * rng.uniform(0.85, 1.15))
        pending = int(approved * rng.uniform(0.06, 0.14)) if (END_DATE - d).days < 5 else 0
        out.append({"date": d.isoformat(), "approved_orders": approved,
                    "approved_revenue": round(approved * rng.uniform(170, 190), 2),
                    "pending_orders": pending})
    return out


def rng():
    return random.Random(SEED)
