"""
Analytics helpers for the Dashboard, Data Explorer and Auto-Insights features.

All the "dashboard" numbers come from curated, hand-written SQL (fast, reliable,
no LLM needed). Auto-Insights feeds those numbers to the LLM for a narrative.
Everything runs on SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.
"""

from __future__ import annotations

import time
from typing import Any

from .llm import complete as llm_complete
from .snowflake_client import SnowflakeError, run_query

FQ = "SNOWFLAKE_SAMPLE_DATA.TPCH_SF1"

# Tables exposed in the Data Explorer (whitelist — prevents SQL injection).
EXPLORER_TABLES = [
    "CUSTOMER", "ORDERS", "LINEITEM", "PART",
    "SUPPLIER", "PARTSUPP", "NATION", "REGION",
]

# ---------------------------------------------------------------------------
# tiny in-process cache so the dashboard is instant after first load
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, Any]] = {}
_TTL = 600  # seconds


def _cached(key: str, producer):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    value = producer()
    _cache[key] = (now, value)
    return value


def _scalar(sql: str):
    _cols, rows = run_query(sql, limit=1)
    return rows[0][0] if rows and rows[0] else None


def _pairs(sql: str) -> tuple[list[str], list[float]]:
    """Run a two-column (label, value) query -> (labels, values)."""
    _cols, rows = run_query(sql, limit=50)
    labels, values = [], []
    for r in rows:
        labels.append(str(r[0]))
        try:
            values.append(round(float(r[1]), 2))
        except (TypeError, ValueError):
            values.append(0.0)
    return labels, values


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def _dashboard_uncached() -> dict:
    revenue_expr = "SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT))"

    kpis = {
        "revenue": _scalar(f"SELECT {revenue_expr} FROM {FQ}.LINEITEM"),
        "orders": _scalar(f"SELECT COUNT(*) FROM {FQ}.ORDERS"),
        "customers": _scalar(f"SELECT COUNT(*) FROM {FQ}.CUSTOMER"),
        "suppliers": _scalar(f"SELECT COUNT(*) FROM {FQ}.SUPPLIER"),
    }

    year_labels, year_values = _pairs(f"""
        SELECT YEAR(O_ORDERDATE) AS yr, {revenue_expr} AS revenue
        FROM {FQ}.LINEITEM
        JOIN {FQ}.ORDERS ON L_ORDERKEY = O_ORDERKEY
        GROUP BY 1 ORDER BY 1
    """)

    region_labels, region_values = _pairs(f"""
        SELECT R_NAME, {revenue_expr} AS revenue
        FROM {FQ}.LINEITEM
        JOIN {FQ}.ORDERS   ON L_ORDERKEY  = O_ORDERKEY
        JOIN {FQ}.CUSTOMER ON O_CUSTKEY   = C_CUSTKEY
        JOIN {FQ}.NATION   ON C_NATIONKEY = N_NATIONKEY
        JOIN {FQ}.REGION   ON N_REGIONKEY = R_REGIONKEY
        GROUP BY 1 ORDER BY 2 DESC
    """)

    seg_labels, seg_values = _pairs(f"""
        SELECT C_MKTSEGMENT, {revenue_expr} AS revenue
        FROM {FQ}.LINEITEM
        JOIN {FQ}.ORDERS   ON L_ORDERKEY = O_ORDERKEY
        JOIN {FQ}.CUSTOMER ON O_CUSTKEY  = C_CUSTKEY
        GROUP BY 1 ORDER BY 2 DESC
    """)

    ship_labels, ship_values = _pairs(f"""
        SELECT L_SHIPMODE, COUNT(*) AS shipments
        FROM {FQ}.LINEITEM
        GROUP BY 1 ORDER BY 2 DESC
    """)

    return {
        "ok": True,
        "kpis": kpis,
        "charts": {
            "revenue_by_year": {"labels": year_labels, "values": year_values},
            "revenue_by_region": {"labels": region_labels, "values": region_values},
            "revenue_by_segment": {"labels": seg_labels, "values": seg_values},
            "shipments_by_mode": {"labels": ship_labels, "values": ship_values},
        },
    }


def dashboard() -> dict:
    try:
        return _cached("dashboard", _dashboard_uncached)
    except SnowflakeError as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Data Explorer
# ---------------------------------------------------------------------------

def table_list() -> dict:
    def producer():
        out = []
        for t in EXPLORER_TABLES:
            count = _scalar(f"SELECT COUNT(*) FROM {FQ}.{t}")
            out.append({"name": t, "rows": count})
        return {"ok": True, "tables": out}

    try:
        return _cached("tables", producer)
    except SnowflakeError as exc:
        return {"ok": False, "error": str(exc)}


def table_preview(name: str, limit: int = 50) -> dict:
    name = (name or "").upper()
    if name not in EXPLORER_TABLES:
        return {"ok": False, "error": "Unknown table."}
    try:
        columns, rows = run_query(f"SELECT * FROM {FQ}.{name} LIMIT {int(limit)}")
        return {
            "ok": True,
            "name": name,
            "columns": columns,
            "rows": [[_json_safe(c) for c in r] for r in rows],
        }
    except SnowflakeError as exc:
        return {"ok": False, "error": str(exc)}


def _json_safe(v):
    from datetime import date, datetime
    from decimal import Decimal
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


# ---------------------------------------------------------------------------
# Auto-Insights (AI narrative over the dashboard numbers)
# ---------------------------------------------------------------------------

def auto_insights() -> dict:
    data = dashboard()
    if not data.get("ok"):
        return data

    import json
    summary = {
        "kpis": {k: _json_safe(v) for k, v in data["kpis"].items()},
        "revenue_by_year": data["charts"]["revenue_by_year"],
        "revenue_by_region": data["charts"]["revenue_by_region"],
        "revenue_by_segment": data["charts"]["revenue_by_segment"],
    }
    prompt = f"""You are a data analyst reviewing a wholesale supplier's business
(TPC-H). Given the aggregated metrics below, return a JSON object ONLY with:

- "summary": one sentence describing overall business health.
- "insights": an array of 3-4 objects, each {{"title": "<short>", "detail":
  "<one sentence with a specific number/trend>"}}.
- "recommendation": one concrete action starting with a verb.

Metrics (JSON):
{json.dumps(summary, default=str)}

JSON:"""
    try:
        from .agent import _extract_json
        result = _extract_json(llm_complete(prompt))
        if not result:
            result = {"summary": "", "insights": [], "recommendation": ""}
        result["ok"] = True
        return result
    except SnowflakeError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Insight generation failed: {exc}"}


# ---------------------------------------------------------------------------
# Market Focus — targeted, single-nation deep dive (not global)
# ---------------------------------------------------------------------------

_REV = "SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT))"

# LINEITEM -> ORDERS -> CUSTOMER -> NATION join used across focus queries.
_BASE_JOIN = f"""
    FROM {FQ}.LINEITEM
    JOIN {FQ}.ORDERS   ON L_ORDERKEY  = O_ORDERKEY
    JOIN {FQ}.CUSTOMER ON O_CUSTKEY   = C_CUSTKEY
    JOIN {FQ}.NATION   ON C_NATIONKEY = N_NATIONKEY
"""


def nations() -> dict:
    def producer():
        _cols, rows = run_query(f"SELECT N_NAME FROM {FQ}.NATION ORDER BY N_NAME")
        return {"ok": True, "nations": [r[0] for r in rows]}
    try:
        return _cached("nations", producer)
    except SnowflakeError as exc:
        return {"ok": False, "error": str(exc)}


def _nation_revenue() -> list[tuple[str, float]]:
    """Revenue per nation (cached globally) — used for ranking & averages."""
    def producer():
        _cols, rows = run_query(
            f"SELECT N_NAME, {_REV} AS r {_BASE_JOIN} GROUP BY 1 ORDER BY 2 DESC",
            limit=50,
        )
        return [(r[0], float(r[1])) for r in rows]
    return _cached("nation_revenue", producer)


def _valid_nation(name: str) -> str | None:
    name = (name or "").upper().strip()
    valid = set(nations().get("nations", []))
    return name if name in valid else None


def _focus(nation: str) -> dict:
    # 1) headline numbers for the nation (single query)
    _cols, rows = run_query(
        f"""SELECT {_REV} AS revenue,
                   COUNT(DISTINCT O_ORDERKEY) AS orders,
                   COUNT(DISTINCT C_CUSTKEY) AS customers
            {_BASE_JOIN}
            WHERE N_NAME = '{nation}'""",
        limit=1,
    )
    rev, orders, customers = (rows[0] if rows else (0, 0, 0))
    rev = float(rev or 0)

    # 2) segment mix within the nation
    seg_labels, seg_values = _pairs(
        f"SELECT C_MKTSEGMENT, {_REV} {_BASE_JOIN} "
        f"WHERE N_NAME = '{nation}' GROUP BY 1 ORDER BY 1"
    )

    # 3) top product types sold into the nation
    type_labels, type_values = _pairs(
        f"""SELECT P_TYPE, {_REV} AS r
            FROM {FQ}.LINEITEM
            JOIN {FQ}.ORDERS   ON L_ORDERKEY  = O_ORDERKEY
            JOIN {FQ}.CUSTOMER ON O_CUSTKEY   = C_CUSTKEY
            JOIN {FQ}.NATION   ON C_NATIONKEY = N_NATIONKEY
            JOIN {FQ}.PART     ON L_PARTKEY   = P_PARTKEY
            WHERE N_NAME = '{nation}'
            GROUP BY 1 ORDER BY 2 DESC LIMIT 8"""
    )

    # 4) yearly trend for the nation
    year_labels, year_values = _pairs(
        f"SELECT YEAR(O_ORDERDATE), {_REV} {_BASE_JOIN} "
        f"WHERE N_NAME = '{nation}' GROUP BY 1 ORDER BY 1"
    )

    # 5) ranking & average across all nations (cached)
    nat_rev = _nation_revenue()
    total_all = sum(v for _n, v in nat_rev) or 1.0
    avg_nation = total_all / len(nat_rev) if nat_rev else 0.0
    rank = next((i + 1 for i, (n, _v) in enumerate(nat_rev) if n == nation), None)

    # 6) segment share: this nation vs the global picture (over/under-index)
    global_seg = dashboard().get("charts", {}).get("revenue_by_segment", {})
    g_map = dict(zip(global_seg.get("labels", []), global_seg.get("values", [])))
    g_total = sum(g_map.values()) or 1.0
    n_total = sum(seg_values) or 1.0
    seg_compare = []
    for lbl, val in zip(seg_labels, seg_values):
        nation_share = val / n_total * 100
        global_share = (g_map.get(lbl, 0) / g_total * 100) if g_map else 0
        seg_compare.append({
            "segment": lbl,
            "nation_share": round(nation_share, 1),
            "global_share": round(global_share, 1),
            "delta": round(nation_share - global_share, 1),
        })

    metrics = {
        "nation": nation,
        "revenue": rev,
        "orders": int(orders or 0),
        "customers": int(customers or 0),
        "rank": rank,
        "nation_count": len(nat_rev),
        "vs_average_pct": round((rev / avg_nation - 1) * 100, 1) if avg_nation else 0,
        "segments": {"labels": seg_labels, "values": seg_values},
        "product_types": {"labels": type_labels, "values": type_values},
        "trend": {"labels": year_labels, "values": year_values},
        "segment_compare": seg_compare,
    }
    metrics["ai"] = _focus_ai(metrics)
    metrics["ok"] = True
    return metrics


def _focus_ai(m: dict) -> dict:
    import json
    from .agent import _extract_json

    over = [s for s in m["segment_compare"] if s["delta"] > 1]
    under = [s for s in m["segment_compare"] if s["delta"] < -1]
    brief = {
        "nation": m["nation"],
        "rank": f"{m['rank']} of {m['nation_count']}",
        "vs_average_pct": m["vs_average_pct"],
        "top_products": m["product_types"]["labels"][:5],
        "over_indexed_segments": [s["segment"] for s in over],
        "under_indexed_segments": [s["segment"] for s in under],
        "segment_compare": m["segment_compare"],
        "trend": m["trend"],
    }
    prompt = f"""You are a regional market strategist analyzing ONE market
(the nation "{m['nation']}") for a wholesale supplier. Focus only on this
market — compare it against the average nation, and explain WHY some product
segments do better or worse here and how to improve. Return JSON ONLY:

{{
  "summary": "<2 sentences on how this market is performing>",
  "strengths": [{{"title": "<short>", "detail": "<why it works here, with a number>"}}],
  "weaknesses": [{{"title": "<segment/product that underperforms here>",
                   "reason": "<likely reason it lags vs other markets>"}}],
  "recommendations": ["<action to grow this specific market>", "..."]
}}

Give 2-3 items in each list. Be specific and use the numbers provided.

Market data (JSON):
{json.dumps(brief, default=str)}

JSON:"""
    try:
        result = _extract_json(llm_complete(prompt)) or {}
    except Exception as exc:  # noqa: BLE001
        result = {"summary": f"AI narrative unavailable: {exc}",
                  "strengths": [], "weaknesses": [], "recommendations": []}
    return result


def market_focus(nation: str) -> dict:
    valid = _valid_nation(nation)
    if not valid:
        return {"ok": False, "error": "Unknown nation."}
    try:
        return _cached(f"focus:{valid}", lambda: _focus(valid))
    except SnowflakeError as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Anomaly Radar — Snowflake-native statistical scan + AI investigation
# ---------------------------------------------------------------------------

def _anomaly_scan_uncached() -> dict:
    """Scan monthly segment signals with z-scores calculated in Snowflake SQL."""
    signal_sql = f"""
        WITH monthly AS (
            SELECT
                DATE_TRUNC('MONTH', O_ORDERDATE) AS signal_month,
                C_MKTSEGMENT AS segment,
                SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT)) AS revenue,
                COUNT(DISTINCT O_ORDERKEY) AS orders,
                COUNT(DISTINCT O_ORDERDATE) AS active_days
            FROM {FQ}.LINEITEM
            JOIN {FQ}.ORDERS ON L_ORDERKEY = O_ORDERKEY
            JOIN {FQ}.CUSTOMER ON O_CUSTKEY = C_CUSTKEY
            GROUP BY 1, 2
        ), statistics AS (
            SELECT
                signal_month,
                segment,
                revenue,
                orders,
                active_days,
                AVG(revenue) OVER (PARTITION BY segment) AS mean_revenue,
                STDDEV_SAMP(revenue) OVER (PARTITION BY segment) AS revenue_stddev,
                LAG(revenue) OVER (
                    PARTITION BY segment ORDER BY signal_month
                ) AS previous_revenue
            FROM monthly
        )
        SELECT
            TO_CHAR(signal_month, 'YYYY-MM') AS period,
            segment,
            revenue,
            orders,
            active_days,
            ROUND((revenue - mean_revenue) / NULLIF(revenue_stddev, 0), 3) AS z_score,
            ROUND(100 * (revenue - previous_revenue) / NULLIF(previous_revenue, 0), 2)
                AS change_pct
        FROM statistics
        ORDER BY signal_month, segment
        LIMIT 1000
    """
    columns, rows = run_query(signal_sql, limit=1000)
    records = [dict(zip([c.lower() for c in columns], row)) for row in rows]

    clean_signals = []
    by_segment: dict[str, list[dict]] = {}
    for record in records:
        signal = {
            "period": str(record["period"]),
            "segment": str(record["segment"]),
            "revenue": float(record["revenue"] or 0),
            "orders": int(record["orders"] or 0),
            "active_days": int(record["active_days"] or 0),
            "z_score": float(record["z_score"] or 0),
            "change_pct": float(record["change_pct"] or 0),
        }
        clean_signals.append(signal)
        by_segment.setdefault(signal["segment"], []).append(signal)

    anomaly_threshold = 1.7
    anomalies = sorted(
        (signal for signal in clean_signals if abs(signal["z_score"]) >= anomaly_threshold),
        key=lambda signal: abs(signal["z_score"]),
        reverse=True,
    )[:12]
    for anomaly in anomalies:
        magnitude = abs(anomaly["z_score"])
        anomaly["severity"] = (
            "data_quality" if anomaly["active_days"] < 20 else
            "critical" if magnitude >= 2.5 else
            "elevated" if magnitude >= 2.0 else
            "watch"
        )
        anomaly["direction"] = "surge" if anomaly["z_score"] > 0 else "drop"
        anomaly["diagnostic"] = (
            f"Partial period: only {anomaly['active_days']} active day(s)"
            if anomaly["severity"] == "data_quality" else
            "Statistical behavior anomaly"
        )

    radar = []
    for segment, segment_signals in sorted(by_segment.items()):
        valid_signals = [item for item in segment_signals if item["active_days"] >= 20]
        abs_scores = [abs(item["z_score"]) for item in valid_signals]
        max_score = max(abs_scores, default=0)
        avg_score = sum(abs_scores) / max(len(abs_scores), 1)
        anomaly_count = sum(score >= anomaly_threshold for score in abs_scores)
        radar.append({
            "segment": segment,
            "risk": round(min(100, max_score * 28 + anomaly_count * 5), 1),
            "volatility": round(min(100, avg_score * 62), 1),
            "stability": round(max(0, 100 - avg_score * 48), 1),
            "anomalies": anomaly_count,
        })

    years = sorted({item["period"][:4] for item in clean_signals})
    segments = sorted(by_segment)
    heatmap = []
    for year in years:
        for segment in segments:
            cells = [
                item for item in by_segment.get(segment, [])
                if item["period"].startswith(year)
            ]
            heatmap.append({
                "year": year,
                "segment": segment,
                "score": round(max((abs(item["z_score"]) for item in cells), default=0), 2),
                "revenue": round(sum(item["revenue"] for item in cells), 2),
                "quality_issue": any(item["active_days"] < 20 for item in cells),
            })

    network_columns, network_rows = run_query(f"""
        SELECT
            R_NAME AS region,
            C_MKTSEGMENT AS segment,
            SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT)) AS revenue
        FROM {FQ}.LINEITEM
        JOIN {FQ}.ORDERS ON L_ORDERKEY = O_ORDERKEY
        JOIN {FQ}.CUSTOMER ON O_CUSTKEY = C_CUSTKEY
        JOIN {FQ}.NATION ON C_NATIONKEY = N_NATIONKEY
        JOIN {FQ}.REGION ON N_REGIONKEY = R_REGIONKEY
        GROUP BY 1, 2
        ORDER BY 3 DESC
        LIMIT 50
    """, limit=50)
    network_records = [dict(zip([c.lower() for c in network_columns], row)) for row in network_rows]
    network = [{
        "region": str(item["region"]),
        "segment": str(item["segment"]),
        "revenue": float(item["revenue"] or 0),
    } for item in network_records]

    critical_count = sum(item["severity"] == "critical" for item in anomalies)
    data_quality_count = sum(item["severity"] == "data_quality" for item in anomalies)
    business_anomaly_count = len(anomalies) - data_quality_count
    health_score = round(max(0, 100 - business_anomaly_count * 2.8 - critical_count * 4.5 - data_quality_count * 1.5))
    result = {
        "ok": True,
        "meta": {
            "signals_scanned": len(clean_signals),
            "anomalies_found": len(anomalies),
            "critical_count": critical_count,
            "data_quality_count": data_quality_count,
            "health_score": health_score,
            "engine": "Snowflake SQL statistical windows",
            "threshold": anomaly_threshold,
        },
        "anomalies": anomalies,
        "radar": radar,
        "heatmap": {"years": years, "segments": segments, "cells": heatmap},
        "network": network,
    }
    result["ai"] = _explain_anomalies(result)
    return result


def _explain_anomalies(scan: dict) -> dict:
    """Ask the configured LLM to investigate only statistically detected signals."""
    import json
    from .agent import _extract_json

    evidence = {
        "scan_meta": scan["meta"],
        "top_anomalies": scan["anomalies"][:8],
        "segment_risk": scan["radar"],
    }
    prompt = f"""You are an anomaly investigator for a wholesale business.
Snowflake SQL has already detected unusual monthly segment performance using
z-scores. Signals with severity "data_quality" come from partial periods with
fewer than 20 active days; identify incomplete coverage as the primary cause
instead of treating it as a real business decline. Analyze ONLY the evidence
below. Never claim certainty about other causes; call them likely explanations
that should be validated.

Return JSON only with this exact shape:
{{
  "verdict": "<one sentence command-center status>",
  "likely_causes": [
    {{"signal": "<segment and period>", "evidence": "<specific z-score/change>",
      "reason": "<plausible business explanation>"}}
  ],
  "actions": ["<specific investigation or corrective action>", "..."],
  "watch_next": "<single metric or segment to monitor next>"
}}
Give 3 likely_causes and 3 actions. Keep every item concise.

Evidence:
{json.dumps(evidence, default=str)}

JSON:"""
    try:
        explanation = _extract_json(llm_complete(prompt)) or {}
    except Exception as exc:  # noqa: BLE001
        explanation = {
            "verdict": "Statistical scan completed; AI investigation is temporarily unavailable.",
            "likely_causes": [],
            "actions": ["Review the highest absolute z-score signals manually."],
            "watch_next": str(exc),
        }
    return explanation


def anomaly_radar() -> dict:
    """Return the cached Snowflake anomaly scan and AI investigation."""
    try:
        return _cached("anomaly_radar:v2", _anomaly_scan_uncached)
    except SnowflakeError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Anomaly scan failed: {exc}"}
