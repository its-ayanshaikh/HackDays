"""
The AskMyData agent — an agentic pipeline running entirely on Snowflake Cortex.

Unlike a naive "one LLM call" text-to-SQL, this agent runs four reasoning
steps and can self-correct:

    1. PLAN     -> break the question into an analytical approach
    2. SQL      -> write a single read-only SQL query for TPC-H
    3. EXECUTE  -> run it on Snowflake (with a CRITIC retry if it fails or
                   returns nothing useful)
    4. INSIGHT  -> explain the result in plain English + a "so what" action,
                   and pick a chart config for the frontend

Every LLM step goes through core.llm.complete(), which prefers Snowflake Cortex
and transparently falls back to a free external LLM when Cortex is unavailable
(e.g. on trial accounts). Data is always queried on Snowflake.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .llm import LLMError, complete as llm_complete
from .schema import SCHEMA_CONTEXT
from .snowflake_client import SnowflakeError, run_query


# ---------------------------------------------------------------------------
# Helpers to coax clean JSON / SQL out of an LLM response
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response."""
    if not text:
        return {}
    # Strip ```json fences if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    # Fall back to the first {...} block.
    if not fenced:
        brace = re.search(r"\{.*\}", candidate, re.DOTALL)
        if brace:
            candidate = brace.group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {}


def _extract_sql(text: str) -> str:
    """Pull a SQL statement out of an LLM response."""
    if not text:
        return ""
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    sql = fenced.group(1) if fenced else text
    # If the model prefixed prose, jump to the first SELECT/WITH.
    m = re.search(r"\b(SELECT|WITH)\b", sql, re.IGNORECASE)
    if m:
        sql = sql[m.start():]
    return sql.strip().rstrip(";").strip()


# ---------------------------------------------------------------------------
# Step 1 — PLAN
# ---------------------------------------------------------------------------

def step_plan(question: str) -> str:
    prompt = f"""You are a senior data analyst. A user asked a question about a
wholesale-supplier database (TPC-H). In 2-3 short sentences, describe the
approach to answer it: which tables/joins and which metric. Do NOT write SQL.

Schema:
{SCHEMA_CONTEXT}

Question: {question}

Approach:"""
    return llm_complete(prompt)


# ---------------------------------------------------------------------------
# Step 2 — SQL GENERATION
# ---------------------------------------------------------------------------

def step_generate_sql(question: str, plan: str, feedback: str = "") -> str:
    fb = f"\nThe previous attempt had this problem, fix it:\n{feedback}\n" if feedback else ""
    prompt = f"""You are an expert Snowflake SQL developer. Write ONE read-only
SQL query (SELECT or WITH only) that answers the question for the TPC-H schema.

Rules:
- Fully-qualify tables as SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.<TABLE>.
- Revenue = SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT)).
- Use YEAR(O_ORDERDATE) for year filters (data covers 1992-1998).
- Return at most ~20 rows unless clearly asked for more (use LIMIT / GROUP BY).
- Give friendly column aliases (e.g. "Total Revenue").
- Output ONLY the SQL inside a ```sql code block, nothing else.

Schema:
{SCHEMA_CONTEXT}

Question: {question}
Approach: {plan}{fb}

SQL:"""
    return _extract_sql(llm_complete(prompt))


# ---------------------------------------------------------------------------
# Step 3 — CRITIC (decides if a failed/empty result needs a retry)
# ---------------------------------------------------------------------------

def step_critic(question: str, sql: str, error: str) -> str:
    prompt = f"""A SQL query meant to answer a question either errored or
returned no rows. Briefly (1-2 sentences) state the most likely cause and how
to fix the SQL. Be specific about columns/joins.

Question: {question}
SQL:
{sql}
Problem: {error}

Diagnosis and fix:"""
    return llm_complete(prompt)


# ---------------------------------------------------------------------------
# Step 4 — INSIGHT + chart selection
# ---------------------------------------------------------------------------

def step_insight(question: str, columns: list[str], rows: list[list[Any]]) -> dict:
    # Keep the prompt small: send at most 30 rows as context.
    preview = [dict(zip(columns, r)) for r in rows[:30]]
    prompt = f"""You are a data analyst presenting results to a business
manager. Given the question and the query result, respond with a JSON object
ONLY (no prose outside the JSON) with these keys:

- "headline": a one-line answer to the question (<= 120 chars).
- "insight": 2-3 sentences explaining what the data shows.
- "action": one concrete recommendation starting with a verb.
- "chart": an object describing the best chart, or null if a chart doesn't fit:
    {{
      "type": "bar" | "line" | "pie",
      "label_column": "<column name to use as x-axis / labels>",
      "value_column": "<numeric column name to plot>",
      "title": "<short chart title>"
    }}

Use EXACT column names from the result. Prefer "line" for anything over time
(years/dates), "bar" for category comparisons, "pie" only for small share
breakdowns.

Question: {question}
Columns: {columns}
Rows (JSON): {json.dumps(preview, default=str)}

JSON:"""
    data = _extract_json(llm_complete(prompt))
    if not data:
        data = {
            "headline": "Here are your results.",
            "insight": "The query ran successfully. See the table below.",
            "action": "Review the returned rows for the detail you need.",
            "chart": None,
        }
    return data


# ---------------------------------------------------------------------------
# Chart data builder (pure Python, no LLM)
# ---------------------------------------------------------------------------

def _build_chart(chart_spec: dict | None, columns: list[str],
                 rows: list[list[Any]]) -> dict | None:
    if not chart_spec or not isinstance(chart_spec, dict):
        return None
    label_col = chart_spec.get("label_column")
    value_col = chart_spec.get("value_column")
    if label_col not in columns or value_col not in columns:
        return None

    li = columns.index(label_col)
    vi = columns.index(value_col)

    labels: list[str] = []
    values: list[float] = []
    for r in rows[:20]:
        try:
            values.append(float(r[vi]))
        except (TypeError, ValueError):
            continue
        labels.append(str(r[li]))

    if not values:
        return None

    return {
        "type": chart_spec.get("type", "bar"),
        "title": chart_spec.get("title", ""),
        "labels": labels,
        "values": values,
        "value_label": value_col,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_pipeline(question: str) -> dict:
    """Run the full agentic pipeline and return a structured result dict."""
    steps: list[dict] = []
    question = (question or "").strip()
    if not question:
        return {"ok": False, "error": "Please enter a question."}

    try:
        # 1) PLAN
        plan = step_plan(question)
        steps.append({"name": "Planner", "status": "done", "detail": plan})

        # 2) SQL
        sql = step_generate_sql(question, plan)
        steps.append({"name": "SQL Generator", "status": "done", "detail": sql})

        # 3) EXECUTE with one self-correcting retry
        columns: list[str] = []
        rows: list[list[Any]] = []
        critic_note = ""
        last_error = ""
        for attempt in range(2):
            try:
                columns, rows = run_query(sql)
                if rows:
                    break
                last_error = "Query returned zero rows."
            except SnowflakeError as exc:
                last_error = str(exc)

            if attempt == 0:
                # CRITIC: diagnose, then regenerate SQL once.
                critic_note = step_critic(question, sql, last_error)
                steps.append({
                    "name": "Critic",
                    "status": "retry",
                    "detail": critic_note,
                })
                sql = step_generate_sql(question, plan, feedback=critic_note)
                steps.append({
                    "name": "SQL Generator (retry)",
                    "status": "done",
                    "detail": sql,
                })

        execute_detail = (
            f"{len(rows)} row(s) returned."
            if rows
            else f"No rows. {last_error}"
        )
        steps.append({
            "name": "Execute on Snowflake",
            "status": "done" if rows else "warn",
            "detail": execute_detail,
        })

        if not rows:
            return {
                "ok": False,
                "error": last_error or "The query returned no data.",
                "sql": sql,
                "steps": steps,
            }

        # 4) INSIGHT
        insight = step_insight(question, columns, rows)
        chart = _build_chart(insight.get("chart"), columns, rows)
        steps.append({
            "name": "Insight",
            "status": "done",
            "detail": insight.get("headline", ""),
        })

        return {
            "ok": True,
            "question": question,
            "sql": sql,
            "columns": columns,
            "rows": rows[:200],
            "row_count": len(rows),
            "headline": insight.get("headline", ""),
            "insight": insight.get("insight", ""),
            "action": insight.get("action", ""),
            "chart": chart,
            "steps": steps,
        }

    except (SnowflakeError, LLMError) as exc:
        steps.append({"name": "Error", "status": "error", "detail": str(exc)})
        return {"ok": False, "error": str(exc), "steps": steps}
    except Exception as exc:  # noqa: BLE001
        steps.append({"name": "Error", "status": "error", "detail": str(exc)})
        return {"ok": False, "error": f"Unexpected error: {exc}", "steps": steps}
