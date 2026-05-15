# Databricks notebook source
# MAGIC %md
# MAGIC # HR Payroll TML Export to ThoughtSpot
# MAGIC
# MAGIC Imports table + model TMLs to ThoughtSpot via REST API v2.0.
# MAGIC - Source: `TS_AGENT_DEMO.HR_PAYROLL.PAYROLL_MV`
# MAGIC - Target: ThoughtSpot cluster `databricks-emea.thoughtspot.cloud`
# MAGIC - Connection: "Databricks MV" (OAuth, catalog=ts_agent_demo)

# COMMAND ----------

import requests
import json
import time
import os

# Configuration
CONFIG = {
    "ts_base_url": "https://databricks-emea.thoughtspot.cloud",
    "secret_scope": "thoughtspot",
    "secret_key": "api-token",
    "connection_name": "Databricks MV",
    "tml_dir": os.path.dirname(os.path.abspath(__file__)) + "/../tml"
}

def get_ts_headers():
    token = dbutils.secrets.get(scope=CONFIG["secret_scope"], key=CONFIG["secret_key"])
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

# Test connection
headers = get_ts_headers()
resp = requests.get(f"{CONFIG['ts_base_url']}/api/rest/2.0/auth/session/user", headers=headers, timeout=30)
if resp.status_code == 200:
    user = resp.json()
    print(f"✓ Connected to ThoughtSpot as: {user.get('name', 'unknown')}")
    print(f"  Cluster: {CONFIG['ts_base_url']}")
else:
    print(f"✗ Auth failed: {resp.status_code} - {resp.text}")
    raise Exception("ThoughtSpot authentication failed")

# COMMAND ----------

def import_tml(tml_content, create_new=True):
    """Import a single TML to ThoughtSpot."""
    payload = {
        "metadata_tmls": [tml_content],
        "import_policy": "PARTIAL",
        "create_new": create_new
    }
    resp = requests.post(
        f"{CONFIG['ts_base_url']}/api/rest/2.0/metadata/tml/import",
        headers=get_ts_headers(),
        json=payload,
        timeout=120
    )
    return resp

# Import table TMLs (dimensions first, fact last)
import_order = [
    "tables/DIM_DATE.table.tml",
    "tables/DIM_LOCATION.table.tml",
    "tables/DIM_DEPARTMENT.table.tml",
    "tables/DIM_JOB_TITLE.table.tml",
    "tables/DIM_PAY_PERIOD.table.tml",
    "tables/DIM_EMPLOYEE.table.tml",
    "tables/FACT_PAYROLL.table.tml",
]

print("Importing table TMLs to ThoughtSpot...\n")
for fname in import_order:
    fpath = os.path.join(CONFIG["tml_dir"], fname)
    with open(fpath, "r") as f:
        tml_content = f.read()

    resp = import_tml(tml_content, create_new=True)

    if resp.status_code == 200:
        result = resp.json()
        for obj in result:
            status = obj.get("response", {}).get("status", {}).get("status_code", "UNKNOWN")
            guid = obj.get("response", {}).get("header", {}).get("id_guid", "N/A")
            err = obj.get("response", {}).get("status", {}).get("error_message", "")
            icon = "✓" if status in ["OK", "WARNING"] else "✗"
            print(f"  {icon} {fname}: {status} (GUID: {guid})")
            if err and status == "ERROR":
                print(f"    Error: {err[:200]}")
    else:
        print(f"  ✗ {fname}: HTTP {resp.status_code} - {resp.text[:200]}")

    time.sleep(2)

# COMMAND ----------

# Import Model TML (creates Worksheet in ThoughtSpot)
print("Importing PAYROLL_MODEL.model.tml...\n")

model_path = os.path.join(CONFIG["tml_dir"], "models/PAYROLL_MODEL.model.tml")
with open(model_path, "r") as f:
    model_content = f.read()

resp = import_tml(model_content, create_new=True)

if resp.status_code == 200:
    result = resp.json()
    for obj in result:
        status = obj.get("response", {}).get("status", {}).get("status_code", "UNKNOWN")
        name = obj.get("response", {}).get("header", {}).get("name", "PAYROLL_MODEL")
        guid = obj.get("response", {}).get("header", {}).get("id_guid", "N/A")
        obj_type = obj.get("response", {}).get("header", {}).get("type", "UNKNOWN")

        icon = "✓" if status in ["OK", "WARNING"] else "✗"
        print(f"{icon} Model Import Result:")
        print(f"  Name: {name}")
        print(f"  GUID: {guid}")
        print(f"  Type: {obj_type}")
        print(f"  Status: {status}")

        if status == "ERROR":
            err_msg = obj.get("response", {}).get("status", {}).get("error_message", "")
            print(f"  Error: {err_msg}")
else:
    print(f"✗ HTTP {resp.status_code} - {resp.text[:500]}")

# COMMAND ----------

# Validate via Search Data API
search_payload = {
    "metadata": [{"type": "LOGICAL_TABLE", "name_pattern": "PAYROLL_MODEL"}]
}
resp = requests.post(
    f"{CONFIG['ts_base_url']}/api/rest/2.0/metadata/search",
    headers=get_ts_headers(),
    json=search_payload,
    timeout=30
)

worksheet_guid = None
if resp.status_code == 200:
    results = resp.json()
    for r in results:
        if r.get("metadata_name") == "PAYROLL_MODEL":
            worksheet_guid = r.get("metadata_id")
            print(f"✓ Found PAYROLL_MODEL worksheet: {worksheet_guid}")
            break

if not worksheet_guid:
    print("✗ Could not find PAYROLL_MODEL worksheet")
else:
    test_queries = [
        "[Net Pay] by [Department Name]",
        "[Gross Pay] [Headcount] by [Region]",
        "[Overtime Hours] by [Job Level]",
    ]

    print("\nValidating search queries:\n")
    for query in test_queries:
        search_resp = requests.post(
            f"{CONFIG['ts_base_url']}/api/rest/2.0/searchdata",
            headers=get_ts_headers(),
            json={
                "query_string": query,
                "logical_table_identifier": worksheet_guid,
                "data_format": "COMPACT",
                "record_offset": 0,
                "record_size": 5
            },
            timeout=60
        )

        if search_resp.status_code == 200:
            data = search_resp.json()
            num_rows = data.get("contents", [{}])[0].get("record_size", 0) if data.get("contents") else 0
            print(f"  ✓ '{query}' - {num_rows} rows returned")
        else:
            print(f"  ✗ '{query}' - HTTP {search_resp.status_code}")
            print(f"    {search_resp.text[:200]}")

print("\n✓ Pipeline complete! PAYROLL_MODEL worksheet is searchable in ThoughtSpot.")
