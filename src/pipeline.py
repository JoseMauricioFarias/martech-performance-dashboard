"""Pipeline ETL: extrai das 3 plataformas, padroniza e exporta para o painel.

Uso:
    python -m src.pipeline            # modo demo (dados fictícios)
    python -m src.pipeline --live     # usa as APIs reais (exige credenciais no .env)
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

from src import demo_data
from src.connectors import google_ads, meta_ads, mercado_livre

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ["date", "channel", "campaign", "spend", "impressions", "clicks", "conversions", "revenue"]


# ---------- Transformação: cada plataforma -> um esquema único ----------

def normalize_google(rows: list[dict]) -> pd.DataFrame:
    df = pd.json_normalize(rows)
    return pd.DataFrame({
        "date": df["segments.date"],
        "channel": "Google Ads",
        "campaign": df["campaign.name"],
        "spend": df["metrics.cost_micros"] / 1_000_000,  # micros -> R$
        "impressions": df["metrics.impressions"],
        "clicks": df["metrics.clicks"],
        "conversions": df["metrics.conversions"],
        "revenue": df["metrics.conversions_value"],
    })


def _action(actions: list[dict] | float, kind: str = "purchase") -> float:
    if not isinstance(actions, list):
        return 0.0
    return sum(float(a["value"]) for a in actions if a.get("action_type") == kind)


def normalize_meta(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    return pd.DataFrame({
        "date": df["date_start"],
        "channel": "Meta Ads",
        "campaign": df["campaign_name"],
        "spend": df["spend"].astype(float),  # a Meta devolve números como texto
        "impressions": df["impressions"].astype(int),
        "clicks": df["clicks"].astype(int),
        "conversions": df["actions"].map(_action),
        "revenue": df["action_values"].map(_action),
    })


def normalize_ml_ads(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    return pd.DataFrame({
        "date": df["date"],
        "channel": "Mercado Livre",
        "campaign": df["campaign_name"],
        "spend": df["cost"],
        "impressions": df["prints"],
        "clicks": df["clicks"],
        "conversions": df["units_quantity"],
        "revenue": df["total_amount"],
    })


def normalize_ml_orders(rows: list[dict]) -> pd.DataFrame:
    df = pd.json_normalize(rows)
    return df.rename(columns={"date_created": "date", "shipping.status": "shipping_status"})[
        ["id", "date", "total_amount", "shipping_status"]
    ]


# ---------- Qualidade de dados ----------

def validate(df: pd.DataFrame) -> pd.DataFrame:
    assert list(df.columns) == SCHEMA, "esquema inesperado"
    assert df["date"].notna().all(), "datas vazias"
    assert (df[["spend", "impressions", "clicks", "conversions", "revenue"]] >= 0).all().all(), "valores negativos"
    assert (df["clicks"] <= df["impressions"]).all(), "cliques maiores que impressões"
    dupes = df.duplicated(["date", "channel", "campaign"]).sum()
    assert dupes == 0, f"{dupes} linhas duplicadas"
    return df


# ---------- Execução ----------

def run(live: bool = False) -> None:
    end = demo_data.END_DATE
    start = end - timedelta(days=demo_data.DAYS - 1)
    s, e = start.isoformat(), end.isoformat()
    demo = not live

    ml_ads, ml_orders = mercado_livre.fetch(s, e, demo=demo)
    campaigns = validate(pd.concat([
        normalize_google(google_ads.fetch(s, e, demo=demo)),
        normalize_meta(meta_ads.fetch(s, e, demo=demo)),
        normalize_ml_ads(ml_ads),
    ], ignore_index=True).round(2))
    orders = normalize_ml_orders(ml_orders)
    crm = pd.DataFrame(demo_data.crm_sales_raw(demo_data.rng()))

    (ROOT / "data").mkdir(exist_ok=True)
    campaigns.to_csv(ROOT / "data" / "campanhas_diario.csv", index=False)
    orders.to_csv(ROOT / "data" / "pedidos_mercado_livre.csv", index=False)
    crm.to_csv(ROOT / "data" / "vendas_crm.csv", index=False)

    # JSON compacto para o painel (o front faz os filtros por período e canal)
    ship = orders.groupby(["date", "shipping_status"]).size().unstack(fill_value=0).reset_index()
    payload = {
        "generated_for": e,
        "demo": demo,
        "campaigns": campaigns[["campaign", "channel"]].drop_duplicates().values.tolist(),
        "rows": campaigns.assign(
            campaign=campaigns["campaign"].map({c: i for i, c in enumerate(campaigns["campaign"].unique())})
        )[["date", "campaign", "spend", "impressions", "clicks", "conversions", "revenue"]].values.tolist(),
        "ml_shipping": ship.to_dict(orient="records"),
        "crm": crm.to_dict(orient="records"),
    }
    out = ROOT / "docs" / "data" / "dashboard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    summary = campaigns.groupby("channel")[["spend", "revenue", "conversions"]].sum()
    summary["roas"] = summary["revenue"] / summary["spend"]
    summary["cpa"] = summary["spend"] / summary["conversions"]
    print(summary.round(2).to_string())
    print(f"\n{len(campaigns)} linhas de campanha · {len(orders)} pedidos ML -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="usar APIs reais em vez de dados fictícios")
    run(live=parser.parse_args().live)
