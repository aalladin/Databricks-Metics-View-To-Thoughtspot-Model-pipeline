import streamlit as st
import requests
import pandas as pd
import os

# ============================================================
# Spotter — ThoughtSpot's NLQ Agent for Analytics
# Ask business questions in plain English, get instant answers
# ============================================================

st.set_page_config(
    page_title="Spotter",
    page_icon="🔭",
    layout="wide"
)

# --- ThoughtSpot Configuration ---
TS_BASE_URL = os.getenv("TS_BASE_URL", "https://databricks-emea.thoughtspot.cloud")
TS_USERNAME = os.getenv("TS_USERNAME", "tsadmin")
TS_PASSWORD = os.getenv("TS_PASSWORD", "")  # Set via app.yaml (not committed to git)
DEFAULT_MODEL = os.getenv("TS_MODEL", "PAYROLL_MODEL")


def get_ts_session() -> requests.Session:
    """Create an authenticated ThoughtSpot session.
    
    The Databricks App runtime proxy strips Authorization headers on outbound
    requests. We authenticate via password-based session login which sends
    credentials in the POST body and receives cookies for subsequent requests.
    """
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json"
    })

    if not TS_PASSWORD:
        raise ValueError("TS_PASSWORD env var not set. Configure it in app.yaml.")

    resp = session.post(
        f"{TS_BASE_URL}/api/rest/2.0/auth/session/login",
        json={"username": TS_USERNAME, "password": TS_PASSWORD, "remember_me": True},
        timeout=30
    )
    if resp.status_code in (200, 204):
        return session

    raise ValueError(
        f"ThoughtSpot authentication failed ({resp.status_code}): {resp.text[:300]}"
    )


# Cache the session to avoid re-authenticating on every request
if "ts_session" not in st.session_state:
    st.session_state.ts_session = None


def get_authenticated_session() -> requests.Session:
    """Get or create an authenticated ThoughtSpot session."""
    if st.session_state.ts_session is None:
        st.session_state.ts_session = get_ts_session()
    return st.session_state.ts_session


def resolve_model_guid(name: str) -> str:
    """Resolve ThoughtSpot model name to GUID."""
    session = get_authenticated_session()
    resp = session.post(
        f"{TS_BASE_URL}/api/rest/2.0/metadata/search",
        json={"metadata": [{"type": "LOGICAL_TABLE", "name_pattern": name}]},
        timeout=30
    )
    if resp.status_code == 401:
        st.session_state.ts_session = get_ts_session()
        session = st.session_state.ts_session
        resp = session.post(
            f"{TS_BASE_URL}/api/rest/2.0/metadata/search",
            json={"metadata": [{"type": "LOGICAL_TABLE", "name_pattern": name}]},
            timeout=30
        )
    if resp.status_code != 200:
        raise ValueError(f"ThoughtSpot API error {resp.status_code}: {resp.text[:500]}")
    for r in resp.json():
        if r.get("metadata_name") == name:
            return r["metadata_id"]
    raise ValueError(f"Model '{name}' not found")


def search_thoughtspot(query: str, model: str, max_rows: int = 100) -> pd.DataFrame:
    """Execute a ThoughtSpot search query and return DataFrame."""
    guid = resolve_model_guid(model)
    session = get_authenticated_session()
    payload = {
        "query_string": query,
        "logical_table_identifier": guid,
        "data_format": "COMPACT",
        "record_offset": 0,
        "record_size": max_rows
    }
    resp = session.post(
        f"{TS_BASE_URL}/api/rest/2.0/searchdata",
        json=payload,
        timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    contents = data.get("contents", [{}])[0]
    raw_cols = contents.get("column_names", [])
    if raw_cols and isinstance(raw_cols[0], dict):
        columns = [col.get("column_name", f"col_{i}") for i, col in enumerate(raw_cols)]
    elif raw_cols and isinstance(raw_cols[0], str):
        columns = raw_cols
    else:
        columns = [f"col_{i}" for i in range(len(contents.get("data_rows", [[]])[0]))]
    rows = contents.get("data_rows", [])
    return pd.DataFrame(rows, columns=columns)


def translate_to_ts_query(question: str) -> str:
    """Use Databricks Foundation Model API to translate natural language to ThoughtSpot search syntax."""
    from databricks.sdk import WorkspaceClient

    system_prompt = """You are Spotter, ThoughtSpot's NLQ agent for analytics.
Convert the user's natural language question into ThoughtSpot search syntax.

Rules:
- Wrap column names in square brackets: [Column Name]
- Use 'by' for grouping dimensions
- Use 'sort by [column] descending' or 'sort by [column] ascending' for ordering
- IMPORTANT: Do NOT use 'desc' or 'asc' — always spell out 'descending' or 'ascending'
- Use 'top N' for limiting results

Available MEASURES (numeric, aggregated):
  [Gross Pay], [Net Pay], [Total Tax], [Total Deductions], [Headcount],
  [Avg Gross Pay], [Tax Burden Pct], [Base Pay], [Overtime Pay], [Bonus Pay],
  [Regular Hours], [Overtime Hours]

Available ATTRIBUTES (dimensions, for grouping with 'by'):
  [Department Name], [Job Title], [Job Level], [Job Family],
  [Location Name], [City], [State], [Region],
  [Employment Status], [Gender], [Pay Date], [Pay Frequency],
  [Fiscal Year], [Fiscal Quarter]

Return ONLY the ThoughtSpot query string, nothing else."""

    w = WorkspaceClient()
    host = w.config.host.rstrip("/")
    header_factory = w.config.authenticate
    auth_headers = header_factory()

    resp = requests.post(
        f"{host}/serving-endpoints/databricks-claude-sonnet-4/invocations",
        headers={
            "Authorization": auth_headers.get("Authorization", ""),
            "Content-Type": "application/json"
        },
        json={
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "max_tokens": 200
        },
        timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


# --- UI Layout ---
st.title("🔭 Spotter")
st.markdown("**ThoughtSpot's NLQ agent for analytics** — ask business questions in plain English, powered by Databricks")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    model_name = st.text_input("ThoughtSpot Model", value=DEFAULT_MODEL)
    max_rows = st.slider("Max rows", 10, 500, 100)
    st.divider()
    st.markdown("**Example questions:**")
    st.markdown("- What are the top 5 departments by net pay?")
    st.markdown("- Show me overtime hours by region")
    st.markdown("- Average gross pay by job level")
    st.markdown("- Total deductions by fiscal quarter")
    st.markdown("- Headcount by department and gender")
    st.divider()
    st.caption("Powered by ThoughtSpot + Databricks")

    # --- Demo: Test Connection ---
    if st.button("🩺 Test Connection"):
        try:
            session = get_ts_session()
            resp = session.get(
                f"{TS_BASE_URL}/api/rest/2.0/auth/session/user",
                timeout=15
            )
            if resp.status_code == 200:
                user = resp.json()
                st.success(f"✅ Connected as: {user.get('name', user.get('user_name', 'unknown'))}")
            else:
                st.error(f"❌ Status {resp.status_code}: {resp.text[:300]}")
        except Exception as e:
            st.error(f"❌ {str(e)}")

# Chat interface
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("dataframe") is not None:
            st.dataframe(message["dataframe"], use_container_width=True)
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask Spotter anything about your data..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Spotter is thinking..."):
            try:
                ts_query = translate_to_ts_query(prompt)
                st.caption(f"🔎 Query: `{ts_query}`")

                df = search_thoughtspot(ts_query, model_name, max_rows)

                if len(df) > 0:
                    st.dataframe(df, use_container_width=True)
                    summary = f"✅ Found **{len(df)} rows** across **{len(df.columns)} columns**"
                    st.markdown(summary)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"🔎 Query: `{ts_query}`\n\n{summary}",
                        "dataframe": df
                    })
                else:
                    msg = "No results found. Try rephrasing your question."
                    st.warning(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg, "dataframe": None})

            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg, "dataframe": None})
