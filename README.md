# ❄️ AskMyData — Agentic Analytics on Snowflake Cortex

A clean analytics workspace over Snowflake with a sidebar of six sections:

- **Dashboard** — live KPIs (revenue, orders, customers, suppliers) and charts
  (revenue by year / region / segment, shipments by mode) straight from Snowflake.
- **Ask AI** — the agentic natural-language pipeline (below).
- **Data Explorer** — browse every TPC-H table with row counts and previews.
- **Auto Insights** — one click; the AI reads the whole business and returns
  key findings + a recommendation.
- **History** — your recent questions, click any to re-run.
- **Settings** — connection status, Snowflake version/warehouse, active LLM.

### Ask AI — the agentic pipeline

Ask questions in **plain English**. AskMyData runs an **agentic AI pipeline**
(Snowflake Cortex, with a free fallback) that:

1. **🧭 Plans** the analytical approach
2. **⚙️ Writes SQL** for the question
3. **❄️ Runs it on Snowflake** — and if it fails/returns nothing, a
   **🔎 Critic step diagnoses and rewrites the SQL** (self-correction)
4. **💡 Explains** the result in business language + a recommended action, and
   picks the best chart

No external LLM, no vector DB — every AI step is a single
`SNOWFLAKE.CORTEX.COMPLETE()` call. The demo runs on Snowflake's **free built-in
TPC-H sample dataset**, so there is nothing to upload.

---

## 🧱 Tech stack

- **Backend:** Django (server-rendered, one process — no separate API/React)
- **Data + AI:** Snowflake (`snowflake-connector-python`) + Cortex `COMPLETE`
- **Frontend:** Django template + vanilla JS + Chart.js (via CDN)
- **Dataset:** `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` (ships free with every account)
- **Django's own DB:** SQLite by default (the app stores no business data
  locally). MySQL optional — see below.

---

## ✅ Prerequisites

- **Python 3.11 or 3.12** (3.12 recommended; the Snowflake connector may lack
  wheels on very new versions like 3.14)
- A **Snowflake account** with **Cortex enabled**

### How to get a Snowflake account (free)

1. Go to <https://signup.snowflake.com/> and sign up for a **30-day free trial**.
2. **Pick a Cortex-supported region.** Choose **AWS – US West (Oregon)** to be
   safe — Cortex LLM functions are available there. (Cortex is not enabled in
   every region.)
3. After signup you land in **Snowsight** (the web UI). A warehouse called
   `COMPUTE_WH` is created for you automatically.

---

## 🔐 Filling in `.env` — where each value comes from

Open the `.env` file at the project root and fill these in:

| Variable | What it is / where to find it |
|---|---|
| `SNOWFLAKE_ACCOUNT` | In Snowsight, click your account name (bottom-left) → hover the account → **Copy account identifier**. Looks like `ABCDEFG-XY12345`. |
| `SNOWFLAKE_USER` | The username you log into Snowsight with. |
| `SNOWFLAKE_PASSWORD` | Your Snowsight password. |
| `SNOWFLAKE_ROLE` | Leave blank to use your default, or set `ACCOUNTADMIN` (trials have it). |
| `SNOWFLAKE_WAREHOUSE` | `COMPUTE_WH` (created automatically on trial). |
| `SNOWFLAKE_DATABASE` | `SNOWFLAKE_SAMPLE_DATA` (leave as-is). |
| `SNOWFLAKE_SCHEMA` | `TPCH_SF1` (leave as-is). |
| `SNOWFLAKE_CORTEX_MODEL` | `mistral-large2` (or `llama3.1-70b`, `mixtral-8x7b`). |
| `DJANGO_SECRET_KEY` | Any long random string. |

> `.env` is git-ignored — your secrets never get committed. Never hardcode
> credentials in code.

### Don't see `SNOWFLAKE_SAMPLE_DATA`?

It's shared with every account by default. If it's missing, create it once in a
Snowsight worksheet (needs `ACCOUNTADMIN`):

```sql
CREATE DATABASE IF NOT EXISTS SNOWFLAKE_SAMPLE_DATA
  FROM SHARE SFC_SAMPLES.SAMPLE_DATA;
```

---

## 🚀 Run it (step by step)

```bash
# 1. Go to the project folder
cd /Users/ayanhusainshaikh/HackDays

# 2. Create a virtual environment with Python 3.12
python3.12 -m venv .venv

# 3. Activate it
source .venv/bin/activate           # macOS / Linux
# .venv\Scripts\activate            # Windows (PowerShell)

# 4. Install dependencies
pip install -r requirements.txt

# 5. Copy the env template and fill in your Snowflake values
cp .env.example .env                # then edit .env
#    (a .env with placeholders already exists — just fill it in)

# 6. Set up Django's local DB (SQLite)
python manage.py migrate

# 7. Start the server
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in your browser.

- The badge top-right shows **“Snowflake connected”** when your `.env` is
  correct.
- Click a sample chip or type your own question and hit **Analyze**.
- You'll watch the agent's steps animate, then see the insight, chart, generated
  SQL, and data table.

### Quick connection test

Visit <http://127.0.0.1:8000/health/> — it returns your Snowflake version and
warehouse if the connection works, or a clear error if not.

---

## 🎤 Demo script (for judges)

1. Open the app — point out the live **Snowflake connected** badge.
2. Click **“Top 5 customers by total revenue, and which nation are they from?”**
3. Narrate the pipeline as it animates: *plan → SQL → run on Snowflake →
   self-verify → explain*.
4. Highlight the **Recommended action** line — “it doesn't just answer, it
   advises.”
5. Ask a follow-up like *“How did total revenue trend year by year from 1993 to
   1997?”* to show it auto-picks a **line chart**.
6. One-liner: *“Plan, generate, self-correct and explain — a junior analyst that
   lives entirely inside Snowflake Cortex.”*

---

## 🗂️ Project structure

```
HackDays/
├── manage.py
├── requirements.txt
├── .env / .env.example        # secrets (real / template)
├── askmydata/                 # Django project (settings, urls, wsgi)
│   └── settings.py            # reads .env; Snowflake + DB config
└── core/                      # the app
    ├── snowflake_client.py    # connector + Cortex COMPLETE + safe SQL guard
    ├── schema.py              # TPC-H schema context + sample questions
    ├── agent.py               # the agentic pipeline (plan/sql/critic/insight)
    ├── views.py               # / , /ask , /health
    ├── templates/core/index.html
    └── static/core/{style.css, app.js}
```

---

## 🧰 Using MySQL instead of SQLite (optional)

The app needs **no** relational DB for its data — everything comes from
Snowflake. SQLite is used only for Django's internal tables and needs zero
setup. If you specifically want MySQL:

1. `pip install mysqlclient`
2. In `.env` set `DB_ENGINE=mysql` and fill `DB_NAME`, `DB_USER`,
   `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
3. Create the database: `CREATE DATABASE askmydata;`
4. `python manage.py migrate`

---

## 🧠 LLM provider & free fallback (important for trial accounts)

Snowflake **trial accounts have Cortex AI disabled**, so `COMPLETE` returns
"not available for trial accounts". The app handles this with a pluggable LLM
layer controlled by `LLM_PROVIDER` in `.env`:

- `auto` (default) — try Snowflake Cortex first, fall back to a free external
  LLM if Cortex is unavailable. **The SQL still runs on Snowflake either way.**
- `cortex` — Cortex only (needs a paid/enabled account)
- `groq` / `gemini` — use that external provider only

### Get a free Groq key (30 seconds, recommended)

1. Go to <https://console.groq.com/keys> and sign in (free, no card).
2. Create an API key and copy it.
3. Paste it into `.env` as `GROQ_API_KEY=...` and keep `LLM_PROVIDER=auto`.
4. Restart the server. The pipeline now runs on Groq's free Llama model while
   your data stays on Snowflake.

(Prefer Google Gemini? Get a key at
<https://aistudio.google.com/app/apikey> and set `GEMINI_API_KEY` instead.)

> Pitch tip: if you can enable Cortex (add a card — still free within trial
> credits), keep `LLM_PROVIDER=cortex` for the pure "AI + data on one platform"
> story. The Groq fallback is your safety net so the demo never dies.

## 🩺 Troubleshooting

| Symptom | Fix |
|---|---|
| Badge says **not connected** | Check `.env` values; visit `/health/` for the exact error. |
| `COMPLETE is not available for trial accounts` / `Cortex Code is not enabled` | **Trial accounts have Cortex AI disabled.** Either add a credit card in Snowsight → Admin → Billing (stays free within trial credits) and run `GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE PUBLIC;`, **or** use the built-in free fallback: get a Groq key (below) and keep `LLM_PROVIDER=auto`. |
| `Cortex call failed` | Your region may not have Cortex — recreate the trial in **AWS US West (Oregon)**, or use the Groq fallback. |
| `Object 'SNOWFLAKE_SAMPLE_DATA...' does not exist` | Create the sample DB (see SQL above). |
| Connector install fails | Use **Python 3.12**, not 3.13/3.14. |
| `403 CSRF` when testing with curl | Expected — use the browser; the token/cookie are set automatically on page load. |

---

Built for a hackathon. The “magic”: **data + agentic AI on one platform —
Snowflake Cortex — with self-correction and business-ready insight.**
