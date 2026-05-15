# Databricks UC Metric View → ThoughtSpot TML Pipeline - Modular Prompts

Each module is standalone and can be run independently. Run in order (1→7) for a full pipeline, or cherry-pick as needed. Modules 3-4 depend on Module 1 (tables must exist). Module 5 depends on Modules 3-4 (TMLs must exist).

---

## Module 1: Create UC Metric View

```
I have the following tables in Databricks Unity Catalog:

- Catalog: <CATALOG_NAME>
- Schema: <SCHEMA_NAME>
- Tables: <TABLE_1>, <TABLE_2>, <TABLE_3>, ...

Relationships:
- <TABLE_1>.<col> → <TABLE_2>.<col> (many-to-one)
- <TABLE_2>.<col> → <TABLE_3>.<col> (many-to-one)
- ...

Create a UC Metric View named <CATALOG>.<SCHEMA>.<NAME>_MV using
CREATE OR REPLACE VIEW ... WITH METRICS LANGUAGE YAML AS $$ ... $$ syntax.

Include:
- Dimensions: <list key business dimensions like dates, categories, names, regions>
  - Include at least one CASE mapping dimension (e.g., status codes → labels)
  - Include a DATE_TRUNC dimension for period-over-period analysis
- Measures:
  - <list key metrics like revenue, count, averages, ratios>
  - Include at least one composed measure (e.g., avg = measure1 / measure2)
- Window measures:
  - Current period (semiadditive: last, range: current)
  - Previous period (semiadditive: last, range: trailing 1 month/quarter)
  - Period-over-period growth % (composed from the above)
  - Cumulative running total (range: cumulative)

Designate one measure as the canonical metric and note it in the view comment.
```

---

## Module 2: Create Flat SQL View

```
I have a UC Metric View at <CATALOG>.<SCHEMA>.<NAME>_MV that joins
<TABLE_1> → <TABLE_2> → <TABLE_3> → ...

Create a regular SQL view named <CATALOG>.<SCHEMA>.<NAME>_SV that:
- Joins all tables with the same relationships as the metric view
- Exposes dimensions as columns (lowercase aliases, Unity Catalog convention)
- Exposes measures as row-level computed columns that ThoughtSpot can SUM:
  - For additive measures: expose the raw expression (e.g., price * (1 - discount))
  - For count measures: use literal 1 (ThoughtSpot SUMs these)
  - For identifiers used in COUNT DISTINCT: expose the key column

This view is for ThoughtSpot which cannot use MEASURE() syntax.
All column aliases should be lowercase (Unity Catalog convention).
```

---

## Module 3: Generate Table TMLs

```
Generate ThoughtSpot table TML files for these Databricks tables:
- Catalog: <catalog>, Schema: <schema>
- Connection name: "<CONNECTION_NAME>"
- Tables: <list each table with column names>

Rules:
- db, schema, db_table, db_column_name: LOWERCASE (Unity Catalog stores lowercase)
- Column display name: UPPERCASE
- Numeric columns (money, quantities, hours):
  column_type: MEASURE, aggregation: SUM, index_type: DONT_INDEX
- String columns: column_type: ATTRIBUTE (no aggregation line — API rejects "NONE")
- Date columns: column_type: ATTRIBUTE, index_type: DONT_INDEX
- Boolean columns (is_*, has_*, flag columns):
  column_type: ATTRIBUTE, data_type: BOOL
  *** CRITICAL: ThoughtSpot validates data_type against the actual CDW connection
  metadata. Databricks BOOLEAN columns MUST use "BOOL" — not "VARCHAR". Using
  VARCHAR for boolean columns causes import failure with error: "DataType VARCHAR
  does not match CDW DataType for column". ***
- Primary/foreign key integers (_id, _key columns):
  column_type: ATTRIBUTE (they are identifiers, not summable)
- Integer metadata columns (year, quarter, month, week_of_year):
  column_type: ATTRIBUTE
- Data types must match actual Databricks column types EXACTLY:
  - VARCHAR → string columns
  - DOUBLE → decimal/float/double columns
  - INT64 → integer/bigint/long columns
  - DATE → date columns
  - BOOL → boolean columns
  - DATETIME → timestamp columns
  ThoughtSpot validates these against the live connection. Mismatches = import failure.
- Include at table level: spotter_config: is_spotter_enabled: false
- Do NOT include guid or obj_id fields (ThoughtSpot assigns these on import)

Reference TML format:

    table:
      name: <TABLE_NAME>
      db: <catalog>
      schema: <schema>
      db_table: <table_name_lowercase>
      connection:
        name: <CONNECTION_NAME>
      columns:
      - name: COLUMN_DISPLAY_NAME
        db_column_name: column_name_lowercase
        properties:
          column_type: ATTRIBUTE | MEASURE
          aggregation: SUM          # measures only
          index_type: DONT_INDEX    # measures and dates only
        db_column_properties:
          data_type: VARCHAR | DOUBLE | INT64 | DATE | BOOL
      spotter_config:
        is_spotter_enabled: false

Output one .table.tml file per table.
```

---

## Module 4: Generate Model TML

```
Generate a ThoughtSpot Model TML named <MODEL_NAME> that creates a Worksheet
representing the UC Metric View <CATALOG>.<SCHEMA>.<NAME>_MV.

The model references these already-imported tables:
<TABLE_1>, <TABLE_2>, <TABLE_3>, ...

Include:

1. model_tables with joins:
   - <TABLE_1> → <TABLE_2>: [<T1>::<KEY>] = [<T2>::<KEY>], INNER, MANY_TO_ONE
   - <TABLE_2> → <TABLE_3>: [<T2>::<KEY>] = [<T3>::<KEY>], INNER, MANY_TO_ONE
   - ... (all dimension joins)

2. formulas (ThoughtSpot syntax):
   - <Measure1>: sum ( [<TABLE>::<COL>] )
   - <Measure2>: sum ( [<TABLE>::<COL>] * ( 1 - [<TABLE>::<COL2>] ) )
   - <Count>: unique count ( [<TABLE>::<KEY>] )
   - <Composed>: "[formula_<Measure1>] / [formula_<Count>]"
   - <Pct>: "[formula_<X>] / [formula_<Y>] * 100"

3. columns (Title Case names) referencing column_id or formula_id:
   - Measures: all formula-based calculated metrics
   - Attributes: key dimensions from dimension tables (column_id: TABLE::COL)

4. Per column:
   - synonyms: 2-3 natural language alternatives for Spotter search
   - ai_context: one-sentence description of what the column represents

5. Properties:
   - is_bypass_rls: false
   - join_progressive: true
   - spotter_config: is_spotter_enabled: true

Description: "<Model description>. <Canonical metric> is the primary metric."

Reference join format:
  "on": "[TABLE_A::KEY] = [TABLE_B::KEY]"
  type: INNER
  cardinality: MANY_TO_ONE

Reference formula format:
  - id: formula_<Name>
    name: <Name>
    expr: "sum ( [TABLE::COLUMN] )"
```

---

## Module 5: Import Pipeline Notebook

```
Create a Databricks notebook (Python) that imports ThoughtSpot TML files
via the REST API v2.0.

Configuration:
- ThoughtSpot cluster: <TS_URL>
- Auth: Bearer token from Databricks Secrets (scope: "<scope>", key: "<key>")
- Connection name: "<CONNECTION_NAME>"
- TML directory: <path to TML files>

Steps:
1. Authenticate and test connection (GET /api/rest/2.0/auth/session/user)
2. Load TML files from output directory
3. Import TABLE TMLs first (dimension tables before fact tables)
   — order: smallest/leaf dimensions first, fact table last
4. Import MODEL TML second (depends on all tables existing)
5. Validate via Search Data API (POST /api/rest/2.0/searchdata):
   - "<query1>"
   - "<query2>"

Import settings:
- import_policy: "PARTIAL"
- create_new: True (first time) or False (updates)
- timeout: 120s per request
- Pause 2s between imports (avoid rate limits)

Error handling:
- Print clear success/error status for each TML with name and GUID
- On data type mismatch errors: check that TML data_type matches actual
  Databricks column type (common issue: BOOL vs VARCHAR for boolean columns)
- On "Tables do not exist" error: ensure all table TMLs imported before model
- On WARNING status: benign — ThoughtSpot matched by db/schema/dbTable name

Print clear success/error status for each TML with name and GUID.
```

---

## Module 6: Token Refresh Script

```
Create a Python script for Databricks that refreshes a ThoughtSpot bearer token
and stores it in Databricks Secrets.

Configuration:
- ThoughtSpot cluster: <TS_URL>
- Credentials stored in: scope="<scope>", keys="username" and "password"
- Token stored in: scope="<scope>", key="api-token"
- Token validity: 86400 seconds (24 hours)

The script should:
1. Read username/password from Databricks Secrets
2. POST to /api/rest/2.0/auth/token/full with username, password, validity_time_in_sec
3. Store the returned token in Databricks Secrets (api-token key)
4. Print success with timestamp

This is meant to run as a scheduled Databricks Job every 12 hours
(cron: 0 0 */12 * * ? *).
```

---

## Module 7: GitHub Repo Packaging

```
Package the following artifacts into a GitHub-ready directory structure
with a README.md:

Files to include:
- sql/01_create_tables.sql (CREATE TABLE statements)
- sql/02_create_metric_view.sql (UC Metric View DDL)
- sql/03_create_flat_view.sql (flat denormalized view DDL)
- tml/tables/ (.table.tml files for each physical table)
- tml/models/ (<MODEL_NAME>.model.tml)
- tml/<FLAT_VIEW>.table.tml (flat view alternative)
- notebooks/<notebook_name>.py
- scripts/token_refresh.py
- .gitignore (exclude __pycache__, .env, *.pyc, .DS_Store)

README.md should include:
- Architecture diagram (ASCII art showing Databricks → TML → ThoughtSpot flow)
- Directory structure tree
- Quick-start steps (1-6)
- Two approaches section (Model vs Flat View with pros/cons table)
- TML format reference (table + model examples)
- Token management section (4 approaches: manual, scheduled job, OAuth, PAT)
- Troubleshooting table (common errors and fixes):
  - DataType mismatch → check BOOL vs VARCHAR for boolean columns
  - Tables do not exist → import table TMLs before model
  - aggregation: NONE rejected → omit aggregation for attributes
  - Connection not found → verify connection name matches exactly
- Key learnings (5-6 bullet points)
```

---

## Quick Reference: Key Lessons

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| DataType VARCHAR does not match CDW DataType | Boolean column typed as VARCHAR | Use data_type: BOOL for boolean columns |
| Tables do not exist in model import | Table TMLs not imported yet | Import all table TMLs before model TML |
| aggregation: NONE rejected | API doesn't accept explicit NONE | Omit the aggregation field entirely for attributes |
| Model import WARNING | No guid, matched by db/schema/table | Benign — ThoughtSpot auto-matched the object |
| create_new: True fails on re-run | Object already exists | Use create_new: False for updates |
| Connection not found | Name mismatch or missing catalog | Verify connection Advanced settings: catalog = \<catalog\> |

---

## Applied Example: HR Payroll (ts_agent_demo.hr_payroll)

**Schema:**
- Fact: fact_payroll (20 cols — pay, taxes, deductions, hours)
- Dims: dim_employee, dim_department, dim_job_title, dim_location, dim_pay_period, dim_date

**Results:**
- Metric View: `TS_AGENT_DEMO.HR_PAYROLL.PAYROLL_MV` (18 dimensions, 12 measures)
- Flat View: `TS_AGENT_DEMO.HR_PAYROLL.PAYROLL_SV`
- Model: PAYROLL_MODEL → GUID: `585a5b59-f81e-4401-8ace-083e009a283b`
- All search queries validated successfully

**Boolean columns identified (used BOOL):**
- dim_date: `is_weekend`, `is_holiday`
- dim_location: `is_remote`
- dim_job_title: `is_exempt`

---

## Applied Example: Sales (ts_agent_demo.sales)

**Schema:**
- Fact: lineitem (16 cols)
- Dims: orders, customer, nation, region

**Results:**
- Metric View: `TS_AGENT_DEMO.SALES.SALES_MV` (9 dimensions, 9 measures)
- Flat View: `TS_AGENT_DEMO.SALES.SALES_SV`
- Model: SALES_MODEL → GUID: `77b04883-6fe9-46a6-bf3e-dad36b3325f2`
- Canonical metric: Net Revenue
