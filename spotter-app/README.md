# 🔭 Spotter — ThoughtSpot NLQ Agent for Analytics

A Databricks App that lets business users ask questions in plain English and get instant answers from ThoughtSpot semantic models — no SQL, no dashboards, no training required.

## Architecture

```
User (browser) → Databricks App (Streamlit)
    → Databricks LLM (NL → ThoughtSpot search syntax)
    → ThoughtSpot REST API (search execution)
    → Tabular results displayed in chat
```

## How It Works

1. **User asks a question** in plain English (e.g., "What are the top 5 departments by net pay?")
2. **Databricks LLM** translates to ThoughtSpot search syntax (`[Net Pay] by [Department Name] top 5`)
3. **ThoughtSpot API** executes the query against the semantic model
4. **Results** are displayed as a table in the chat interface

## Setup

### Prerequisites

- Databricks workspace with Apps enabled
- ThoughtSpot Cloud instance with a semantic model (e.g., PAYROLL_MODEL)
- Databricks secrets scope `thoughtspot` with key `ts-password`

### 1. Store ThoughtSpot credentials in Databricks Secrets

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
w.secrets.put_secret(scope="thoughtspot", key="ts-password", string_value="<your-password>")
```

### 2. Configure `app.yaml`

Edit environment variables:
- `TS_BASE_URL`: Your ThoughtSpot instance URL
- `TS_USERNAME`: ThoughtSpot username (recommend a service account)
- `TS_MODEL`: Name of the ThoughtSpot model to query

### 3. Deploy

1. App switcher → Databricks Apps → Create App
2. Set source path to the `Spotter-app/` folder
3. Deploy

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit chat application |
| `app.yaml` | Databricks App deployment config |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

## Security

- **No credentials in code or config** — password stored in Databricks secrets
- **Session-based auth** — password sent once in POST body, subsequent calls use cookies
- **Proxy-safe** — works with Databricks App runtime proxy (which strips Authorization headers)
- **Recommendation**: Use a dedicated service account with read-only permissions instead of admin

## Key Design Decisions

1. **Session login over Bearer tokens**: Databricks Apps proxy strips `Authorization` headers on external requests. Password-based session login sends credentials in POST body → returns cookies → cookies survive the proxy.

2. **Databricks SDK for secrets**: Internal SDK calls (workspace → secrets) are not affected by the proxy, so we read the password at runtime.

3. **Direct REST for LLM**: The Databricks serving endpoint call uses the SDK's built-in auth (internal, not proxied), avoiding the SDK response parsing issues.

## Available Measures & Dimensions (PAYROLL_MODEL)

**Measures**: Gross Pay, Net Pay, Total Tax, Total Deductions, Headcount, Avg Gross Pay, Tax Burden Pct, Base Pay, Overtime Pay, Bonus Pay, Regular Hours, Overtime Hours

**Dimensions**: Department Name, Job Title, Job Level, Job Family, Location Name, City, State, Region, Employment Status, Gender, Pay Date, Pay Frequency, Fiscal Year, Fiscal Quarter
