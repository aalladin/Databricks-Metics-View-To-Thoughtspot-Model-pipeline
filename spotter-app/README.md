# 🔭 Spotter — ThoughtSpot NLQ Agent for Analytics

A Databricks App that lets business users ask questions in plain English and get instant answers from ThoughtSpot semantic models — no SQL, no dashboards, no training required.

---

## Executive Summary

**What this is:** A production-ready chat interface (hosted on Databricks) that connects business users to ThoughtSpot's governed semantic layer via natural language. Users type a question, get a table of results — nothing else required.

**What we built (end to end):**

1. **Data Modeling** — Star schema (fact + dim tables) in Unity Catalog (`ts_agent_demo.hr_payroll`), UC Metric View (`PAYROLL_MV`) with 18 dimensions and 12 measures, plus a denormalized flat SQL view.

2. **TML Pipeline** — Auto-generated Table and Model TMLs from UC metadata, imported to ThoughtSpot as worksheets via REST API. Fully scripted, repeatable, repo'd.

3. **AI Agent Skills** — Databricks-native Python class with LangChain wrappers: `search_data`, `generate_tml`, `import_tml`, `list_objects`, `get_liveboard`. Users can ask questions in English; the agent chooses and executes the right skill.

4. **Spotter App (this repo)** — Streamlit chat UI deployed as a Databricks App. Business users get a clean URL, zero code, zero setup. Questions are translated by a Databricks-hosted LLM into ThoughtSpot search syntax, executed against the semantic model, and results returned in seconds.

**Business value:**
- Time-to-insight: days → seconds (no analyst queue, no ticket backlog)
- Governance preserved — all queries flow through ThoughtSpot's permission model on top of Unity Catalog
- Zero training — if you can type a question, you can use it
- Fully open and portable — code is repo'd on GitHub, works across any Databricks workspace

---

## Why We Built This

Databricks has **Genie Spaces** for natural language querying, but Genie queries only Databricks SQL tables directly — it cannot invoke ThoughtSpot's semantic layer, apply ThoughtSpot's governed metrics, or deliver NLQ answers powered by a curated business model.

ThoughtSpot's semantic layer adds critical value that raw SQL can't provide:
- **Governed metric definitions** (Net Pay = Gross Pay - Deductions - Tax, consistently everywhere)
- **Business-friendly column names** (not `fact_payroll.net_pay` but `[Net Pay]`)
- **Pre-built joins and relationships** (no need to know which tables join on which keys)
- **Access control at the model level** (row-level security, column masking)

Business users shouldn't need to know SQL, table names, or join logic. They should ask "What are the top departments by overtime?" and get a governed, correct answer instantly.

**Spotter fills this gap**: a Databricks-native app that routes natural language questions through ThoughtSpot's semantic layer, combining Databricks' compute and hosting with ThoughtSpot's analytics governance.

---

## Architecture

```
User (browser) → Databricks App (Streamlit)
    → Databricks LLM (NL → ThoughtSpot search syntax)
    → ThoughtSpot REST API (search execution against semantic model)
    → Tabular results displayed in chat
```

## How It Works

1. **User asks a question** in plain English (e.g., "What are the top 5 departments by net pay?")
2. **Databricks LLM** (Claude Sonnet via serving endpoint) translates to ThoughtSpot search syntax (`[Net Pay] by [Department Name] top 5`)
3. **ThoughtSpot API** executes the query against the governed semantic model (PAYROLL_MODEL)
4. **Results** are displayed as a table in the chat interface

---

## Setup

### Prerequisites

- Databricks workspace with Apps enabled
- ThoughtSpot Cloud instance with a semantic model (e.g., PAYROLL_MODEL)
- ThoughtSpot service account credentials

### 1. Configure `app.yaml`

Edit environment variables:
- `TS_BASE_URL`: Your ThoughtSpot instance URL
- `TS_USERNAME`: ThoughtSpot username (recommend a dedicated service account, not admin)
- `TS_PASSWORD`: ThoughtSpot password (set directly in app.yaml, which stays in workspace only — never committed to git)
- `TS_MODEL`: Name of the ThoughtSpot model to query

### 2. Deploy

1. App switcher (grid icon, top-left) → **Databricks Apps** → **Create App**
2. Set source path to the `Spotter-app/` folder in your workspace
3. Click **Deploy**
4. Access at the generated URL (e.g., `https://spotter-<workspace-id>.aws.databricksapps.com/`)

---

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit chat application |
| `app.yaml` | Databricks App deployment config (credentials here, not in git) |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |
| `.gitignore` | Prevents accidental credential commits |

---

## Security

- **No credentials in git** — `app.yaml` in repo has placeholders; real password only in workspace
- **Session-based auth** — password sent once in POST body, subsequent calls use cookies
- **Proxy-safe** — works with Databricks App runtime proxy (which strips Authorization headers on external requests)
- **Recommendation**: Create a dedicated ThoughtSpot service account with read-only permissions on the target model (avoid using admin in production)

---

## Key Design Decisions

1. **Session login over Bearer tokens**: Databricks Apps proxy strips `Authorization` headers on all outbound external HTTPS requests. Password-based session login sends credentials in the POST body → returns cookies → cookies survive the proxy.

2. **Password in app.yaml (not secrets)**: The app's service principal doesn't have Databricks Secrets read permission. Env vars in `app.yaml` are the only viable path for external credentials. The file stays in the workspace and is never committed to git.

3. **Direct REST for LLM**: The Databricks serving endpoint call uses the SDK's built-in auth (internal call, not proxied). We call the `/invocations` endpoint directly to avoid SDK response parsing issues across versions.

---

## Available Measures & Dimensions (PAYROLL_MODEL)

**Measures**: Gross Pay, Net Pay, Total Tax, Total Deductions, Headcount, Avg Gross Pay, Tax Burden Pct, Base Pay, Overtime Pay, Bonus Pay, Regular Hours, Overtime Hours

**Dimensions**: Department Name, Job Title, Job Level, Job Family, Location Name, City, State, Region, Employment Status, Gender, Pay Date, Pay Frequency, Fiscal Year, Fiscal Quarter

---

## Related Repos

- [Databricks Metrics View → ThoughtSpot Model Pipeline (Sales)](https://github.com/aalladin/Databricks-Metics-View-To-Thoughtspot-Model-pipeline)
- [HR Payroll TML Pipeline](https://github.com/aalladin/hr-payroll-thoughtspot-tml-pipeline)
- [ThoughtSpot Agent Skills (multi-platform)](https://github.com/aalladin/thoughtspot-agent-skills)
