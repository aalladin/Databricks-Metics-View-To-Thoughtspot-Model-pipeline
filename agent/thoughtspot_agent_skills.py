# Databricks notebook source
# MAGIC %pip install langchain-databricks langchain-core -q

# COMMAND ----------

# MAGIC %md
# MAGIC # ThoughtSpot Agent Skills
# MAGIC 
# MAGIC Python-callable skills for invoking ThoughtSpot from Databricks agents.
# MAGIC 
# MAGIC | Skill | Description | API Endpoint |
# MAGIC | --- | --- | --- |
# MAGIC | `search_data` | Natural language → tabular results | `/api/rest/2.0/searchdata` |
# MAGIC | `generate_tml` | UC table metadata → TML YAML | Local (DESCRIBE TABLE) |
# MAGIC | `import_tml` | Push TMLs to ThoughtSpot | `/api/rest/2.0/metadata/tml/import` |
# MAGIC | `get_liveboard` | Fetch liveboard data as DataFrame | `/api/rest/2.0/report/liveboard` |
# MAGIC | `list_objects` | Find worksheets, answers, liveboards | `/api/rest/2.0/metadata/search` |
# MAGIC
# MAGIC **Usage:** Run all cells in sequence, then ask the agent natural language questions.

# COMMAND ----------

import requests
import json
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class TSConfig:
    """ThoughtSpot connection configuration.
    
    Update these values to match your ThoughtSpot environment:
    - base_url: Your ThoughtSpot cluster URL
    - secret_scope: Databricks secret scope containing your API token
    - secret_key: Key name within the scope
    - connection_name: ThoughtSpot connection name for your Databricks source
    - default_catalog: Unity Catalog catalog to use
    """
    base_url: str = "https://databricks-emea.thoughtspot.cloud"
    secret_scope: str = "thoughtspot"
    secret_key: str = "api-token"
    connection_name: str = "Databricks MV"
    default_catalog: str = "ts_agent_demo"

class ThoughtSpotClient:
    """Databricks-native ThoughtSpot agent skills."""

    def __init__(self, config: Optional[TSConfig] = None):
        self.config = config or TSConfig()
        self._headers = None

    @property
    def headers(self) -> dict:
        if self._headers is None:
            token = dbutils.secrets.get(
                scope=self.config.secret_scope,
                key=self.config.secret_key
            )
            self._headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        return self._headers

    def _post(self, endpoint: str, payload: dict, timeout: int = 60) -> dict:
        resp = requests.post(
            f"{self.config.base_url}{endpoint}",
            headers=self.headers,
            json=payload,
            timeout=timeout
        )
        resp.raise_for_status()
        return resp.json()

    def _get(self, endpoint: str, timeout: int = 30) -> dict:
        resp = requests.get(
            f"{self.config.base_url}{endpoint}",
            headers=self.headers,
            timeout=timeout
        )
        resp.raise_for_status()
        return resp.json()

    def test_connection(self) -> str:
        user = self._get("/api/rest/2.0/auth/session/user")
        return f"Connected as: {user.get('name', 'unknown')}"

    # ----------------------------------------------------------
    # Skill 1: search_data
    # ----------------------------------------------------------
    def search_data(self, query: str, worksheet: str, max_rows: int = 100, as_dataframe: bool = True) -> Any:
        """Search ThoughtSpot using natural language bracket syntax.
        
        Args:
            query: ThoughtSpot search string, e.g. "[Net Pay] by [Department Name]"
            worksheet: Name or GUID of the worksheet
            max_rows: Maximum rows to return
            as_dataframe: Return pandas DataFrame (True) or raw dict
        """
        if len(worksheet) != 36 or "-" not in worksheet:
            guid = self._resolve_worksheet_guid(worksheet)
        else:
            guid = worksheet

        payload = {
            "query_string": query,
            "logical_table_identifier": guid,
            "data_format": "COMPACT",
            "record_offset": 0,
            "record_size": max_rows
        }
        data = self._post("/api/rest/2.0/searchdata", payload)

        if not as_dataframe:
            return data

        import pandas as pd
        contents = data.get("contents", [{}])[0]
        raw_cols = contents.get("column_names", [])
        if raw_cols and isinstance(raw_cols[0], dict):
            columns = [col.get("column_name", f"col_{i}") for i, col in enumerate(raw_cols)]
        elif raw_cols and isinstance(raw_cols[0], str):
            columns = raw_cols
        else:
            raw_cols = contents.get("columns", [])
            if raw_cols and isinstance(raw_cols[0], dict):
                columns = [col.get("name", col.get("column_name", f"col_{i}")) for i, col in enumerate(raw_cols)]
            else:
                columns = [f"col_{i}" for i in range(len(contents.get("data_rows", [[]])[0]))]
        rows = contents.get("data_rows", [])
        df = pd.DataFrame(rows, columns=columns if columns else None)
        print(f"Search returned {len(df)} rows, {len(df.columns)} columns")
        return df

    def _resolve_worksheet_guid(self, name: str) -> str:
        results = self._post("/api/rest/2.0/metadata/search", {
            "metadata": [{"type": "LOGICAL_TABLE", "name_pattern": name}]
        })
        for r in results:
            if r.get("metadata_name") == name:
                return r["metadata_id"]
        raise ValueError(f"Worksheet '{name}' not found in ThoughtSpot")

    # ----------------------------------------------------------
    # Skill 2: generate_tml
    # ----------------------------------------------------------
    def generate_tml(self, catalog: str, schema: str, tables: List[str],
                     connection_name: Optional[str] = None, output_dir: Optional[str] = None) -> Dict[str, str]:
        """Auto-generate ThoughtSpot table TMLs from Unity Catalog metadata.
        
        Args:
            catalog: UC catalog name
            schema: UC schema name
            tables: List of table names
            connection_name: ThoughtSpot connection name (default: from config)
            output_dir: Optional directory to write .tml files
        """
        import os
        conn = connection_name or self.config.connection_name
        result = {}
        type_map = {
            "string": "VARCHAR", "varchar": "VARCHAR", "char": "VARCHAR",
            "int": "INT64", "integer": "INT64", "bigint": "INT64",
            "long": "INT64", "smallint": "INT64", "tinyint": "INT64",
            "double": "DOUBLE", "float": "DOUBLE", "decimal": "DOUBLE",
            "numeric": "DOUBLE",
            "date": "DATE", "timestamp": "DATETIME",
            "boolean": "BOOL",
        }
        for table in tables:
            cols_df = spark.sql(f"DESCRIBE TABLE {catalog}.{schema}.{table}").collect()
            columns_yaml = []
            for row in cols_df:
                col_name = row["col_name"]
                data_type_raw = row["data_type"].lower().split("(")[0]
                if col_name.startswith("#") or col_name == "" or data_type_raw == "":
                    continue
                ts_type = type_map.get(data_type_raw, "VARCHAR")
                display_name = col_name.upper()
                is_key = col_name.endswith("_id") or col_name.endswith("_key")
                is_date = ts_type in ("DATE", "DATETIME")
                is_numeric = ts_type in ("DOUBLE", "INT64")
                is_measure = is_numeric and not is_key and not col_name.startswith("is_")
                lines = []
                lines.append(f"  - name: {display_name}")
                lines.append(f"    db_column_name: {col_name}")
                lines.append(f"    properties:")
                if is_measure:
                    lines.append(f"      column_type: MEASURE")
                    lines.append(f"      aggregation: SUM")
                    lines.append(f"      index_type: DONT_INDEX")
                else:
                    lines.append(f"      column_type: ATTRIBUTE")
                    if is_date:
                        lines.append(f"      index_type: DONT_INDEX")
                lines.append(f"    db_column_properties:")
                lines.append(f"      data_type: {ts_type}")
                columns_yaml.append("
".join(lines))
            tml = f"""table:
  name: {table.upper()}
  db: {catalog.lower()}
  schema: {schema.lower()}
  db_table: {table.lower()}
  connection:
    name: {conn}
  columns:
{chr(10).join(columns_yaml)}
  spotter_config:
    is_spotter_enabled: false
"""
            filename = f"{table.upper()}.table.tml"
            result[filename] = tml
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                with open(os.path.join(output_dir, filename), "w") as f:
                    f.write(tml)
        print(f"Generated {len(result)} TML(s): {list(result.keys())}")
        return result

    # ----------------------------------------------------------
    # Skill 3: import_tml
    # ----------------------------------------------------------
    def import_tml(self, tml_content: str, create_new: bool = True, import_policy: str = "PARTIAL") -> Dict[str, Any]:
        """Import a TML string or file path to ThoughtSpot."""
        import os
        if tml_content.strip().endswith(".tml") and os.path.exists(tml_content.strip()):
            with open(tml_content.strip(), "r") as f:
                tml_content = f.read()
        payload = {"metadata_tmls": [tml_content], "import_policy": import_policy, "create_new": create_new}
        resp = requests.post(f"{self.config.base_url}/api/rest/2.0/metadata/tml/import",
                             headers=self.headers, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        output = []
        for obj in result:
            status = obj.get("response", {}).get("status", {}).get("status_code", "UNKNOWN")
            name = obj.get("response", {}).get("header", {}).get("name", "unknown")
            guid = obj.get("response", {}).get("header", {}).get("id_guid", "N/A")
            obj_type = obj.get("response", {}).get("header", {}).get("type", "UNKNOWN")
            err = obj.get("response", {}).get("status", {}).get("error_message", "")
            entry = {"name": name, "guid": guid, "type": obj_type, "status": status}
            if err:
                entry["error"] = err
            print(f"  {name}: {status} (GUID: {guid})")
            output.append(entry)
        return output[0] if len(output) == 1 else output

    def import_tml_batch(self, file_paths: List[str], create_new: bool = True, pause_seconds: float = 2.0) -> List[Dict[str, Any]]:
        """Import multiple TML files in sequence with rate-limit pauses."""
        results = []
        print(f"Importing {len(file_paths)} TMLs...")
        for path in file_paths:
            result = self.import_tml(path, create_new=create_new)
            results.append(result)
            time.sleep(pause_seconds)
        ok = sum(1 for r in results if isinstance(r, dict) and r.get("status") in ("OK", "WARNING"))
        print(f"{ok}/{len(results)} imported successfully")
        return results

    # ----------------------------------------------------------
    # Skill 4: get_liveboard
    # ----------------------------------------------------------
    def get_liveboard(self, liveboard: str, viz_id: Optional[str] = None,
                      as_dataframe: bool = True, file_format: str = "CSV") -> Any:
        """Fetch data from a ThoughtSpot Liveboard."""
        import pandas as pd
        import io
        if len(liveboard) != 36 or "-" not in liveboard:
            guid = self._resolve_liveboard_guid(liveboard)
        else:
            guid = liveboard
        payload = {"metadata_identifier": guid, "file_format": file_format}
        if viz_id:
            payload["visualization_identifiers"] = [{"identifier": viz_id}]
        resp = requests.post(f"{self.config.base_url}/api/rest/2.0/report/liveboard",
                             headers={**self.headers, "Accept": "application/octet-stream"},
                             json=payload, timeout=120)
        resp.raise_for_status()
        if not as_dataframe or file_format != "CSV":
            return resp.content
        df = pd.read_csv(io.BytesIO(resp.content))
        print(f"Fetched liveboard: {len(df)} rows, {len(df.columns)} columns")
        return df

    def _resolve_liveboard_guid(self, name: str) -> str:
        results = self._post("/api/rest/2.0/metadata/search", {
            "metadata": [{"type": "LIVEBOARD", "name_pattern": name}]
        })
        for r in results:
            if r.get("metadata_name") == name:
                return r["metadata_id"]
        raise ValueError(f"Liveboard '{name}' not found")

    # ----------------------------------------------------------
    # Skill 5: list_objects
    # ----------------------------------------------------------
    def list_objects(self, object_type: str = "LOGICAL_TABLE", name_pattern: Optional[str] = None,
                     tag: Optional[str] = None, owner: Optional[str] = None, max_results: int = 25) -> List[Dict[str, str]]:
        """Search and list ThoughtSpot objects."""
        payload = {"metadata": [{"type": object_type}], "record_size": max_results}
        if name_pattern:
            payload["metadata"][0]["name_pattern"] = name_pattern
        if tag:
            payload["tag_identifiers"] = [tag]
        if owner:
            payload["owner_identifiers"] = [owner]
        results = self._post("/api/rest/2.0/metadata/search", payload)
        objects = []
        for r in results:
            objects.append({
                "name": r.get("metadata_name", ""),
                "id": r.get("metadata_id", ""),
                "type": r.get("metadata_type", ""),
                "owner": r.get("metadata_owner", ""),
                "modified": r.get("modified_at", "")
            })
        print(f"Found {len(objects)} {object_type}(s)")
        return objects

# Initialize client
ts = ThoughtSpotClient()
print(ts.test_connection())

# COMMAND ----------

# MAGIC %md
# MAGIC ## LangChain Agent Tools
# MAGIC The following cell wraps the skills as LangChain tools and binds them to a Databricks-hosted LLM.

# COMMAND ----------

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from databricks_langchain import ChatDatabricks

@tool
def thoughtspot_search(query: str, worksheet: str = "PAYROLL_MODEL") -> str:
    """Search ThoughtSpot data using natural language.
    Use bracket syntax: [Measure] by [Dimension].
    Returns tabular data as a formatted string.
    
    Args:
        query: ThoughtSpot search query, e.g. '[Net Pay] by [Department Name]'
        worksheet: Name of the ThoughtSpot worksheet to search
    """
    df = ts.search_data(query, worksheet)
    return df.to_string(index=False)

@tool
def thoughtspot_list(object_type: str = "LOGICAL_TABLE", name_pattern: str = "") -> str:
    """List ThoughtSpot objects (worksheets, liveboards, answers).
    
    Args:
        object_type: One of LOGICAL_TABLE, LIVEBOARD, ANSWER
        name_pattern: Optional name filter (supports wildcards)
    """
    results = ts.list_objects(object_type, name_pattern or None)
    return json.dumps(results[:10], indent=2)

@tool
def thoughtspot_generate_tml(catalog: str, schema: str, tables: str) -> str:
    """Generate ThoughtSpot TML files from Databricks Unity Catalog tables.
    
    Args:
        catalog: UC catalog name (e.g. 'ts_agent_demo')
        schema: UC schema name (e.g. 'hr_payroll')
        tables: Comma-separated table names (e.g. 'fact_payroll,dim_employee')
    """
    table_list = [t.strip() for t in tables.split(",")]
    tmls = ts.generate_tml(catalog, schema, table_list, output_dir="/tmp/tml_agent")
    return f"Generated {len(tmls)} TMLs: {list(tmls.keys())}. Saved to /tmp/tml_agent/"

@tool
def thoughtspot_import(file_path: str, create_new: bool = True) -> str:
    """Import a TML file to ThoughtSpot.
    
    Args:
        file_path: Path to the .tml file to import
        create_new: True to create new, False to update existing
    """
    result = ts.import_tml(file_path, create_new=create_new)
    return json.dumps(result)

@tool
def thoughtspot_liveboard(liveboard_name: str) -> str:
    """Fetch data from a ThoughtSpot Liveboard as CSV.
    
    Args:
        liveboard_name: Name or GUID of the liveboard
    """
    df = ts.get_liveboard(liveboard_name)
    return df.to_string(index=False)

# Collect all tools
ts_tools = [
    thoughtspot_search,
    thoughtspot_list,
    thoughtspot_generate_tml,
    thoughtspot_import,
    thoughtspot_liveboard
]

print(f"{len(ts_tools)} LangChain tools ready")
for t in ts_tools:
    print(f"  - {t.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Invoke the Agent
# MAGIC Ask a natural language question. The LLM autonomously picks the right ThoughtSpot tool.

# COMMAND ----------

# Bind tools to a Databricks-hosted LLM
llm = ChatDatabricks(endpoint="databricks-claude-sonnet-4")
llm_with_tools = llm.bind_tools(ts_tools)

# Ask a question
question = "What are the top 5 departments by net pay?"

print(f"User: {question}")
print("=" * 50)

# Step 1: LLM decides which tool to call
response = llm_with_tools.invoke([HumanMessage(content=question)])

if response.tool_calls:
    tool_call = response.tool_calls[0]
    print(f"Agent chose: {tool_call['name']}")
    print(f"  Args: {json.dumps(tool_call['args'], indent=2)}")
    
    # Step 2: Execute the tool
    tool_map = {t.name: t for t in ts_tools}
    tool_result = tool_map[tool_call["name"]].invoke(tool_call["args"])
    
    print(f"\nResult:")
    print(tool_result[:500] if len(str(tool_result)) > 500 else tool_result)
else:
    print(f"Agent: {response.content}")
