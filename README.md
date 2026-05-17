# Databricks → ThoughtSpot Agent Pipeline

End-to-end pipeline that connects Databricks Unity Catalog to ThoughtSpot via an AI agent.
The agent uses LangChain tools to query, generate, and push ThoughtSpot artifacts — all from a Databricks notebook.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Databricks Unity Catalog       LangChain Agent        ThoughtSpot   │
│  ┌──────────────────────┐    ┌────────────────┐    ┌──────────────────┐  │
│  │ Tables (fact/dim)      │────┤ generate_tml   │────┤ Table TMLs       │  │
│  │ Metric Views (MV)     │    │ import_tml     │    │ Models/Worksheets│  │
│  │ Flat Views (SV)       │    │ search_data    │    │ Liveboards       │  │
│  └──────────────────────┘    │ get_liveboard  │    └──────────────────┘  │
│                                │ list_objects   │                       │
│                                └────────────────┘                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup: ThoughtSpot Connection](#1-setup-thoughtspot-connection)
3. [Setup: Databricks Secrets](#2-setup-databricks-secrets)
4. [Setup: Install Dependencies](#3-setup-install-dependencies)
5. [Configure the Agent](#4-configure-the-agent)
6. [Run the Agent](#5-run-the-agent)
7. [Agent Skills Reference](#agent-skills-reference)
8. [Example: Full Pipeline (TML Generation → Import → Query)](#example-full-pipeline)
9. [Troubleshooting](#troubleshooting)
10. [Key Learnings](#key-learnings)

---

## Prerequisites

| Component | Requirement |
| --- | --- |
| Databricks workspace | Unity Catalog enabled |
| Databricks Runtime | 14.3+ (Python 3.12) |
| Compute | Serverless (CPU) or any cluster with internet access |
| ThoughtSpot | Cloud instance with REST API v2 enabled |
| ThoughtSpot connection | Databricks connection configured (OAuth or PAT) |
| Python packages | `langchain-databricks`, `langchain-core`, `requests` |
| Model endpoint | `databricks-claude-sonnet-4` (or any Foundation Model) |

---

## 1. Setup: ThoughtSpot Connection

In your ThoughtSpot cluster:

1. Navigate to **Data → Connections → Add Connection → Databricks**
2. Configure:
   - **Connection name**: `Databricks MV` (or your preferred name)
   - **Host**: Your Databricks SQL warehouse hostname
   - **HTTP Path**: SQL warehouse HTTP path
   - **Auth**: OAuth 2.0 with service principal (recommended) or PAT
3. In **Advanced Settings**, set:
   ```
   catalog = your_catalog_name
   ```
   > ⚠️ This is required for Unity Catalog — without it, table discovery fails.

4. Select the tables/views you want to expose to ThoughtSpot.

---

## 2. Setup: Databricks Secrets

Store your ThoughtSpot API token securely using Databricks Secrets:

```bash
# Create a secret scope (one-time)
databricks secrets create-scope thoughtspot

# Store the ThoughtSpot API bearer token
databricks secrets put-secret thoughtspot api-token --string-value "<your-token>"

# (Optional) Store credentials for token refresh
databricks secrets put-secret thoughtspot username --string-value "<service-principal-client-id>"
databricks secrets put-secret thoughtspot password --string-value "<service-principal-secret>"
```

### Get a ThoughtSpot API Token

```python
import requests

resp = requests.post(
    "https://your-cluster.thoughtspot.cloud/api/rest/2.0/auth/token/full",
    json={
        "username": "<client_id>",
        "password": "<client_secret>",
        "validity_time_in_sec": 86400  # 24 hours
    }
)
token = resp.json()["token"]
print(f"Token: {token[:20]}...")
```

> **Token Refresh**: Tokens expire after 24h. Schedule `scripts/token_refresh.py` as a Databricks Job (every 12h) or use the ThoughtSpot trusted authentication flow for auto-refresh.

---

## 3. Setup: Install Dependencies

In your Databricks notebook, run:

```python
%pip install langchain-databricks langchain-core -q
dbutils.library.restartPython()
```

---

## 4. Configure the Agent

Edit `TSConfig` in the notebook/script to match your environment:

```python
@dataclass
class TSConfig:
    base_url: str = "https://your-cluster.thoughtspot.cloud"  # Your TS URL
    secret_scope: str = "thoughtspot"                         # Databricks secret scope
    secret_key: str = "api-token"                             # Key within scope
    connection_name: str = "Databricks MV"                    # TS connection name
    default_catalog: str = "your_catalog"                     # UC catalog
```

---

## 5. Run the Agent

### Option A: Import as Databricks Notebook

1. Import `agent/thoughtspot_agent_skills.py` into your Databricks workspace
2. Attach to Serverless (CPU) or any Python cluster
3. Run All Cells
4. Modify the `question` variable in the final cell:

```python
question = "Show me revenue by region for last quarter"
```

### Option B: Use in Your Own Notebook

```python
# 1. Initialize ThoughtSpot client
from thoughtspot_agent_skills import ThoughtSpotClient, TSConfig
ts = ThoughtSpotClient(TSConfig(
    base_url="https://your-cluster.thoughtspot.cloud"
))

# 2. Use skills directly (no LLM required)
df = ts.search_data("[Net Pay] by [Department Name]", "PAYROLL_MODEL")
tmls = ts.generate_tml("ts_agent_demo", "hr_payroll", ["fact_payroll"])
ts.import_tml("/tmp/tml/FACT_PAYROLL.table.tml")
```

### Option C: Full Agent Loop (LLM decides which tools to call)

```python
from langchain_core.messages import HumanMessage
from databricks_langchain import ChatDatabricks

# Bind ThoughtSpot tools to a Databricks-hosted LLM
llm = ChatDatabricks(endpoint="databricks-claude-sonnet-4")
llm_with_tools = llm.bind_tools(ts_tools)

# Ask anything — the agent picks the right tool
response = llm_with_tools.invoke([HumanMessage(content="What are our top customers?")])

# Execute the chosen tool
if response.tool_calls:
    tool_map = {t.name: t for t in ts_tools}
    result = tool_map[response.tool_calls[0]["name"]].invoke(response.tool_calls[0]["args"])
    print(result)
```

---

## Agent Skills Reference

| Skill | Method | Description |
| --- | --- | --- |
| **search_data** | `ts.search_data(query, worksheet)` | Query ThoughtSpot with bracket syntax `[Measure] by [Dimension]` |
| **generate_tml** | `ts.generate_tml(catalog, schema, tables)` | Auto-generate table TMLs from Unity Catalog DESCRIBE metadata |
| **import_tml** | `ts.import_tml(content_or_path)` | Push TML YAML string or file to ThoughtSpot |
| **import_tml_batch** | `ts.import_tml_batch(file_paths)` | Import multiple TMLs with rate-limit pauses |
| **get_liveboard** | `ts.get_liveboard(name_or_guid)` | Fetch liveboard data as pandas DataFrame |
| **list_objects** | `ts.list_objects(type, pattern)` | Find worksheets, liveboards, answers |

### LangChain Tool Names (for agent binding)

| Tool Name | Wraps |
| --- | --- |
| `thoughtspot_search` | `ts.search_data()` |
| `thoughtspot_list` | `ts.list_objects()` |
| `thoughtspot_generate_tml` | `ts.generate_tml()` |
| `thoughtspot_import` | `ts.import_tml()` |
| `thoughtspot_liveboard` | `ts.get_liveboard()` |

---

## Example: Full Pipeline

Complete workflow from UC tables to a searchable ThoughtSpot worksheet:

```python
# 1. Generate TMLs from Unity Catalog tables
tmls = ts.generate_tml(
    catalog="ts_agent_demo",
    schema="hr_payroll",
    tables=["dim_department", "dim_employee", "dim_date", "fact_payroll"],
    output_dir="/tmp/tml"
)

# 2. Import table TMLs (dimensions first, then facts)
ts.import_tml_batch([
    "/tmp/tml/DIM_DEPARTMENT.table.tml",
    "/tmp/tml/DIM_EMPLOYEE.table.tml",
    "/tmp/tml/DIM_DATE.table.tml",
    "/tmp/tml/FACT_PAYROLL.table.tml"
])

# 3. Import the model TML (creates a Worksheet with joins + formulas)
ts.import_tml("/path/to/PAYROLL_MODEL.model.tml")

# 4. Query the new worksheet
df = ts.search_data("[Net Pay] by [Department Name]", "PAYROLL_MODEL")
print(df.head())
```

---

## Troubleshooting

| Issue | Root Cause | Fix |
| --- | --- | --- |
| `DataType VARCHAR does not match CDW DataType` | Boolean column typed as VARCHAR | Use `data_type: BOOL` for boolean columns in TML |
| `Tables do not exist` on model import | Table TMLs not imported yet | Import all table TMLs before model TML |
| `aggregation: NONE` rejected | API doesn't accept explicit NONE | Omit `aggregation` field entirely for attributes |
| Model import WARNING | No guid, matched by db/schema/table | Benign — ThoughtSpot auto-matched |
| `create_new: True` fails on re-run | Object already exists | Use `create_new=False` for updates |
| Connection not found | Name mismatch or missing catalog | Verify connection name + Advanced settings `catalog` |
| Token expired (401) | Bearer token >24h old | Run `scripts/token_refresh.py` or refresh manually |
| `ModuleNotFoundError: langchain_databricks` | Package not installed | Run `%pip install langchain-databricks` |

---

## Key Learnings

1. **BOOL not VARCHAR**: ThoughtSpot validates `data_type` against live DB metadata. Databricks BOOLEAN must be `BOOL` in TML.
2. **Import order matters**: Table TMLs must exist before Model TML can reference them.
3. **UC lowercase convention**: `db`, `schema`, `db_table`, `db_column_name` must all be lowercase.
4. **Model = Worksheet**: A Model TML creates a `WORKSHEET` object in ThoughtSpot (searchable via Spotter).
5. **Rate limits**: Use 2-second pauses between consecutive TML imports.
6. **OAuth catalog**: Service principal connections require `catalog = <name>` in ThoughtSpot Advanced settings.
7. **Spotter support**: Add `synonyms` and `ai_context` to model columns for better natural language search.
8. **Token lifecycle**: Tokens are short-lived (~24h). Automate refresh with a scheduled Databricks Job.
9. **Flat view alternative**: For simpler schemas, a single denormalized view + table TML works without a model.
10. **Agent autonomy**: The LLM picks the right tool based on the question — no manual routing needed.

---

## Repository Structure

```
├── README.md                  ← This file
├── MODULE_PROMPTS.md          ← Modular prompt templates for each pipeline stage
├── agent/
│   └── thoughtspot_agent_skills.py   ← Complete notebook (Databricks .py format)
├── sql/
│   ├── 01_create_tables.sql     ← DDL for fact + dimension tables
│   ├── 02_create_metric_view.sql ← UC Metric View definition
│   └── 03_create_flat_view.sql   ← Flat denormalized view
├── tml/
│   ├── tables/                  ← Generated table TMLs
│   └── models/                  ← Model TML (creates Worksheet)
├── notebooks/
│   └── tml_export_to_thoughtspot.py  ← Batch export pipeline
└── scripts/
    └── token_refresh.py         ← Schedulable token refresh
```

---

## License

MIT
