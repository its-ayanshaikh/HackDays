# AskMyData

AskMyData is a Snowflake-powered analytics workspace that turns natural-language questions and warehouse signals into verified insights, focused market analysis, anomaly detection, and recommended actions.

## Features

- **Business dashboard** — live revenue, order, customer, and supplier metrics with temporal, polar, radar, and relationship visualizations.
- **Ask AI** — plans an analysis, generates read-only Snowflake SQL, executes it, retries failed or empty queries, and explains the result.
- **Market Focus** — compares one market with the overall baseline to identify strengths, underperforming segments, likely causes, and growth actions.
- **Anomaly Radar** — uses Snowflake SQL window functions and Z-scores to detect unusual monthly segment behavior.
- **Data-quality detection** — separates incomplete reporting periods from genuine business anomalies to reduce false alerts.
- **Relationship mapping** — visualizes region-to-segment revenue flows as an interactive network constellation.
- **Data Explorer** — previews the built-in TPC-H tables and their row counts.
- **History** — stores recent successful questions locally in the browser for quick reruns.
- **Connection settings** — displays the active Snowflake warehouse, version, dataset, and LLM provider.

## How it works

### Agentic question pipeline

1. The planner identifies the required tables, joins, and business metric.
2. The SQL generator creates one read-only Snowflake query.
3. Snowflake executes the query against the configured dataset.
4. If the query fails or returns no rows, a critic diagnoses the issue and regenerates it once.
5. The insight step returns a headline, explanation, recommended action, and visualization configuration.

### Anomaly pipeline

1. Snowflake aggregates revenue and orders by month and market segment.
2. Native SQL window functions calculate averages, standard deviation, previous-period change, and Z-scores.
3. The scanner classifies statistically unusual signals by severity.
4. Reporting periods with fewer than 20 active days are marked as data-quality alerts rather than business failures.
5. The AI investigator summarizes likely causes, supporting evidence, recommended actions, and the next metric to monitor.

## Snowflake usage

Snowflake is the primary data and analytics engine. The application uses it for:

- Multi-table analytical queries over TPC-H data
- Aggregations and market comparisons
- `DATE_TRUNC`, `AVG OVER`, `STDDEV_SAMP`, and `LAG` window calculations
- Statistical Z-score anomaly detection
- Region-to-segment relationship aggregation
- Optional Snowflake Cortex completions when the account supports AI functions

The built-in sample dataset contains approximately 1.5 million orders and 6 million line items.

## Technology stack

- **Backend:** Django
- **Data warehouse:** Snowflake
- **AI layer:** Snowflake Cortex when available, with optional Groq or Gemini fallback
- **Frontend:** Django templates, vanilla JavaScript, Chart.js, and custom SVG visualizations
- **Dataset:** `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1`
- **Local Django database:** SQLite by default; MySQL is optional

## Prerequisites

- Python 3.11 or 3.12; Python 3.12 is recommended
- A Snowflake account
- A Snowflake virtual warehouse such as `COMPUTE_WH`
- Optional Cortex access, Groq API key, or Gemini API key for AI-generated explanations

## Installation

```bash
git clone <your-repository-url>
cd <repository-directory>

python3.12 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/dashboard/>.

## Environment configuration

Store all credentials in `.env`. The real `.env` file is ignored by Git; only `.env.example` should be committed.

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | A long random secret used by Django |
| `DJANGO_DEBUG` | Set to `True` for local development |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed host names |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier from the Snowsight account menu |
| `SNOWFLAKE_USER` | Snowflake username |
| `SNOWFLAKE_PASSWORD` | Snowflake password |
| `SNOWFLAKE_ROLE` | Optional role; blank uses the user's default role |
| `SNOWFLAKE_WAREHOUSE` | Virtual warehouse, for example `COMPUTE_WH` |
| `SNOWFLAKE_DATABASE` | Defaults to `SNOWFLAKE_SAMPLE_DATA` |
| `SNOWFLAKE_SCHEMA` | Defaults to `TPCH_SF1` |
| `SNOWFLAKE_CORTEX_MODEL` | Cortex model used when Cortex is selected |
| `LLM_PROVIDER` | `auto`, `cortex`, `groq`, or `gemini` |
| `GROQ_API_KEY` | Optional Groq API key |
| `GROQ_MODEL` | Optional model override; leave blank for automatic model selection |
| `GEMINI_API_KEY` | Optional Gemini API key |
| `GEMINI_MODEL` | Gemini model identifier |
| `DB_ENGINE` | `sqlite` or `mysql` |

### LLM provider behavior

- `auto` tries Snowflake Cortex first and falls back to a configured Groq or Gemini provider.
- `cortex` uses only Snowflake Cortex and requires an account with Cortex AI access.
- `groq` and `gemini` use only the corresponding provider.

Snowflake self-service trial accounts may have AI functions disabled. In that case, configure a fallback provider while keeping all data storage, SQL execution, statistical detection, and analytical computation in Snowflake.

## Sample data

Most Snowflake accounts include `SNOWFLAKE_SAMPLE_DATA`. If it is unavailable, an account administrator can create it from the sample share:

```sql
CREATE DATABASE IF NOT EXISTS SNOWFLAKE_SAMPLE_DATA
  FROM SHARE SFC_SAMPLES.SAMPLE_DATA;
```

## Application routes

| Route | Page |
|---|---|
| `/dashboard/` | Business dashboard |
| `/ask-ai/` | Natural-language analytics agent |
| `/market-focus/` | Single-market analysis |
| `/anomaly-radar/` | Statistical anomaly and data-quality scanner |
| `/data-explorer/` | Snowflake table explorer |
| `/history/` | Recent questions |
| `/settings/` | Connection and provider information |
| `/health/` | Snowflake connection health response |

The page route is preserved during refresh and browser back/forward navigation.

## Security controls

- Secrets are loaded from `.env` and are not hardcoded.
- Generated SQL is restricted to a single `SELECT` or `WITH` statement.
- Mutation and administrative keywords are rejected before execution.
- Multiple SQL statements are blocked.
- Result sets are limited to prevent unbounded responses.
- Data Explorer table names use an explicit whitelist.
- Django CSRF protection remains enabled for POST requests.

For public deployment, add user authentication and use a least-privilege Snowflake role rather than an administrative role.

## Optional MySQL configuration

The analytical data remains in Snowflake. MySQL is only needed if you want to replace SQLite for Django's internal tables.

```bash
pip install mysqlclient
```

Set the following values in `.env`:

```env
DB_ENGINE=mysql
DB_NAME=askmydata
DB_USER=root
DB_PASSWORD=your-password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Create the database, then run:

```bash
python manage.py migrate
```

## Project structure

```text
.
├── manage.py
├── requirements.txt
├── .env.example
├── askmydata/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── core/
    ├── agent.py
    ├── analytics.py
    ├── llm.py
    ├── schema.py
    ├── snowflake_client.py
    ├── urls.py
    ├── views.py
    ├── templates/core/index.html
    └── static/core/
        ├── app.js
        └── style.css
```

## Troubleshooting

| Problem | Resolution |
|---|---|
| Snowflake shows as disconnected | Verify the account, username, password, role, and warehouse in `.env`; then open `/health/` for the exact error. |
| Cortex is unavailable on a trial account | Configure `GROQ_API_KEY` or `GEMINI_API_KEY` and keep `LLM_PROVIDER=auto`. |
| The TPC-H schema is missing | Create `SNOWFLAKE_SAMPLE_DATA` from the sample share or update the database/schema variables. |
| Snowflake connector installation fails | Use Python 3.12 and recreate the virtual environment. |
| A POST request returns HTTP 403 | Load the application page first and send the Django CSRF cookie/token with the request. |
