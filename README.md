# Databricks HR Payroll → ThoughtSpot TML Pipeline

Publish a **Databricks Unity Catalog Metric View** as a searchable ThoughtSpot Worksheet via TML REST API.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Databricks Unity Catalog                      │
│                                                                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
│  │FACT_PAYROLL│  │DIM_EMPLOYEE│  │DIM_DEPT   │  │DIM_JOB_TITLE│  │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └──────┬──────┘  │
│        │               │               │               │          │
│        └───────────────┴───────────────┴───────────────┘          │
│                              │                                    │
│                    ┌─────────▼─────────┐                         │
│                    │    PAYROLL_MV      │  UC Metric View         │
│                    │  (18 dims, 12 meas)│                         │
│                    └─────────┬─────────┘                         │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   TML Generation     │
                    │  7 table + 1 model   │
                    └──────────┬──────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│                    ThoughtSpot                                     │
│                    ┌─────────▼─────────┐                         │
│                    │  PAYROLL_MODEL     │  Worksheet              │
│                    │  (Spotter-enabled) │                         │
│                    └───────────────────┘                         │
└──────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
hr-payroll-thoughtspot-pipeline/
├── README.md
├── .gitignore
├── sql/
│   ├── 01_create_tables.sql
│   ├── 02_create_metric_view.sql
│   └── 03_create_flat_view.sql
├── tml/
│   ├── tables/
│   │   ├── FACT_PAYROLL.table.tml
│   │   ├── DIM_EMPLOYEE.table.tml
│   │   ├── DIM_DEPARTMENT.table.tml
│   │   ├── DIM_JOB_TITLE.table.tml
│   │   ├── DIM_LOCATION.table.tml
│   │   ├── DIM_PAY_PERIOD.table.tml
│   │   └── DIM_DATE.table.tml
│   ├── models/
│   │   └── PAYROLL_MODEL.model.tml
│   └── PAYROLL_SV.table.tml
├── notebooks/
│   └── tml_export_to_thoughtspot.py
└── scripts/
    └── token_refresh.py
```

## Quick Start

### 1. Create Tables
```sql
-- Run sql/01_create_tables.sql in Databricks to create the HR schema
USE CATALOG ts_agent_demo;
CREATE SCHEMA IF NOT EXISTS hr_payroll;
```

### 2. Create Metric View
```sql
-- Run sql/02_create_metric_view.sql
-- Creates PAYROLL_MV with 18 dimensions and 12 measures
```

### 3. Store ThoughtSpot Credentials
```python
# In Databricks, create a secret scope and store your token
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
w.secrets.create_scope(scope="thoughtspot")
w.secrets.put_secret(scope="thoughtspot", key="api-token", string_value="<your-token>")
```

### 4. Configure Connection
In ThoughtSpot, ensure connection "Databricks MV" has:
- OAuth with service principal
- Advanced settings: `catalog = ts_agent_demo`

### 5. Run the Pipeline
```bash
# Import notebook to Databricks and run all cells
# Or run from CLI:
databricks workspace import notebooks/tml_export_to_thoughtspot.py
```

### 6. Validate
Search in ThoughtSpot:
- `[Net Pay] by [Department Name]`
- `[Gross Pay] [Headcount] by [Region]`
- `[Overtime Hours] by [Job Level]`

## Two Approaches

| Feature | Model (implemented) | Flat View (alternative) |
|---------|-------------------|----------------------|
| TML files | 7 table + 1 model | 1 table (PAYROLL_SV) |
| Joins | Defined in model | Pre-computed in view |
| Formulas | ThoughtSpot-side | SQL-side (row-level) |
| Synonyms | Yes (Spotter NL) | No |
| AI Context | Yes | No |
| Maintenance | Update model TML | Update SQL view |
| Flexibility | High (change formulas) | Low (change view DDL) |

## TML Format Reference

### Table TML
```yaml
table:
  name: FACT_PAYROLL
  db: ts_agent_demo
  schema: hr_payroll
  db_table: fact_payroll
  connection:
    name: Databricks MV
  columns:
  - name: NET_PAY
    db_column_name: net_pay
    properties:
      column_type: MEASURE
      aggregation: SUM
      index_type: DONT_INDEX
    db_column_properties:
      data_type: DOUBLE
```

### Model TML
```yaml
model:
  name: PAYROLL_MODEL
  formulas:
  - id: formula_Net Pay
    name: Net Pay
    expr: "sum ( [FACT_PAYROLL::NET_PAY] )"
  columns:
  - name: Net Pay
    formula_id: formula_Net Pay
    properties:
      column_type: MEASURE
      synonyms:
      - Take Home Pay
      - Net Salary
      ai_context: "Net compensation after all taxes and deductions."
```

## Token Management

| Approach | Method | Lifetime |
|----------|--------|----------|
| A. Manual | Generate in ThoughtSpot UI | Until revoked |
| B. Scheduled Job | `scripts/token_refresh.py` on cron | 24h (refresh every 12h) |
| C. OAuth | Service principal (recommended) | Auto-managed |
| D. Trusted Auth | Databricks → ThoughtSpot SSO | Session-based |

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `DataType VARCHAR does not match CDW DataType` | Boolean column typed as VARCHAR | Use `data_type: BOOL` for boolean columns |
| `Tables do not exist` | Model imported before tables | Import all table TMLs first |
| `aggregation: NONE` rejected | API doesn't accept explicit NONE | Remove `aggregation` line for attributes |
| WARNING on import | No guid, matched by name | Benign — ThoughtSpot auto-matched |
| `create_new: True` fails | Object already exists | Switch to `create_new: False` |
| Connection not found | Missing catalog setting | Set `catalog = ts_agent_demo` in Advanced |

## Key Learnings

1. **Tables before Model**: Table TMLs must be imported before Model TML (model references tables by name)
2. **BOOL not VARCHAR**: Databricks BOOLEAN columns must use `data_type: BOOL` in TML — ThoughtSpot validates against live connection metadata
3. **UC = lowercase**: All `db`, `schema`, `db_table`, `db_column_name` must be lowercase for Unity Catalog
4. **OAuth needs catalog**: Service principal connections require `catalog` in Advanced settings
5. **Model = Worksheet**: Model TML creates a Worksheet object with joins + formulas + Spotter support
6. **Spotter uses synonyms**: Add `synonyms` and `ai_context` to columns for natural language search

## Schema Details

- **Catalog**: `TS_AGENT_DEMO`
- **Schema**: `HR_PAYROLL`
- **Fact Table**: `fact_payroll` (21 columns — pay, taxes, deductions, hours)
- **Dimensions**: `dim_employee`, `dim_department`, `dim_job_title`, `dim_location`, `dim_pay_period`, `dim_date`
- **Metric View**: `PAYROLL_MV` (18 dimensions, 12 measures including window measures)
- **Canonical Metric**: Net Pay
- **ThoughtSpot GUID**: `585a5b59-f81e-4401-8ace-083e009a283b`
