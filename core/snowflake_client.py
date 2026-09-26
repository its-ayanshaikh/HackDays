"""
Thin wrapper around the Snowflake Python connector.

Responsibilities:
  * open a connection using credentials from settings.SNOWFLAKE
  * run read-only SQL and return rows + column names
  * call the Cortex LLM (SNOWFLAKE.CORTEX.COMPLETE) for the agent

Nothing here is app-specific; agent.py builds the intelligence on top.
"""

from __future__ import annotations

import re
from typing import Any

import snowflake.connector
from django.conf import settings


class SnowflakeError(Exception):
    """Raised for connection / query problems so views can report cleanly."""


def _config() -> dict:
    cfg = settings.SNOWFLAKE
    missing = [k for k in ("ACCOUNT", "USER", "PASSWORD") if not cfg.get(k)]
    if missing:
        raise SnowflakeError(
            "Missing Snowflake credentials in .env: "
            + ", ".join("SNOWFLAKE_" + m for m in missing)
        )
    return cfg


def get_connection():
    """Open a new Snowflake connection. Caller is responsible for closing."""
    cfg = _config()
    params = {
        "account": cfg["ACCOUNT"],
        "user": cfg["USER"],
        "password": cfg["PASSWORD"],
        "warehouse": cfg["WAREHOUSE"],
        "database": cfg["DATABASE"],
        "schema": cfg["SCHEMA"],
        "client_session_keep_alive": True,
    }
    if cfg.get("ROLE"):
        params["role"] = cfg["ROLE"]
    try:
        return snowflake.connector.connect(**params)
    except Exception as exc:  # noqa: BLE001 - surface a clean message
        raise SnowflakeError(f"Could not connect to Snowflake: {exc}") from exc


# ---------------------------------------------------------------------------
# Read-only SQL execution
# ---------------------------------------------------------------------------

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE|"
    r"CALL|COPY|PUT|REMOVE|USE)\b",
    re.IGNORECASE,
)


def is_safe_select(sql: str) -> bool:
    """Only allow a single read-only SELECT / WITH statement."""
    stripped = sql.strip().rstrip(";").strip()
    if ";" in stripped:  # block multiple statements
        return False
    if not re.match(r"^(SELECT|WITH)\b", stripped, re.IGNORECASE):
        return False
    if _FORBIDDEN.search(stripped):
        return False
    return True


def run_query(sql: str, limit: int = 200) -> tuple[list[str], list[list[Any]]]:
    """Run a read-only query and return (columns, rows).

    A LIMIT is appended when the query has none, to keep result sets sane.
    """
    if not is_safe_select(sql):
        raise SnowflakeError("Only read-only SELECT queries are allowed.")

    safe_sql = sql.strip().rstrip(";")
    if not re.search(r"\blimit\b", safe_sql, re.IGNORECASE):
        safe_sql = f"{safe_sql}\nLIMIT {limit}"

    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(safe_sql)
            columns = [c[0] for c in cur.description]
            rows = [list(r) for r in cur.fetchall()]
            return columns, rows
        finally:
            cur.close()
    except SnowflakeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SnowflakeError(f"Query failed: {exc}") from exc
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Cortex LLM
# ---------------------------------------------------------------------------

def cortex_complete(prompt: str, model: str | None = None) -> str:
    """Call SNOWFLAKE.CORTEX.COMPLETE(model, prompt) and return the text."""
    model = model or settings.SNOWFLAKE["CORTEX_MODEL"]
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)", (model, prompt)
            )
            row = cur.fetchone()
            return (row[0] or "").strip() if row else ""
        finally:
            cur.close()
    except Exception as exc:  # noqa: BLE001
        raise SnowflakeError(
            f"Cortex call failed (is Cortex enabled in your region / does the "
            f"role have access?): {exc}"
        ) from exc
    finally:
        conn.close()


def test_connection() -> dict:
    """Lightweight connectivity check used by the /health endpoint."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT CURRENT_VERSION(), CURRENT_WAREHOUSE()")
            version, warehouse = cur.fetchone()
            return {"ok": True, "version": version, "warehouse": warehouse}
        finally:
            cur.close()
    finally:
        conn.close()
