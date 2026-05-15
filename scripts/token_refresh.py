# ============================================================
# ThoughtSpot Token Refresh Script
# Schedule as Databricks Job: every 12 hours
# Cron: 0 0 */12 * * ? *
# ============================================================

import requests
import json
from datetime import datetime

# Configuration
TS_BASE_URL = "https://databricks-emea.thoughtspot.cloud"
SECRET_SCOPE = "thoughtspot"
TOKEN_VALIDITY = 86400  # 24 hours

def refresh_token():
    """Refresh ThoughtSpot bearer token and store in Databricks Secrets."""
    from databricks.sdk import WorkspaceClient

    # Read credentials from secrets
    username = dbutils.secrets.get(scope=SECRET_SCOPE, key="username")
    password = dbutils.secrets.get(scope=SECRET_SCOPE, key="password")

    # Request new token
    resp = requests.post(
        f"{TS_BASE_URL}/api/rest/2.0/auth/token/full",
        json={
            "username": username,
            "password": password,
            "validity_time_in_sec": TOKEN_VALIDITY
        },
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    if resp.status_code == 200:
        token = resp.json().get("token")

        # Store in Databricks Secrets
        w = WorkspaceClient()
        w.secrets.put_secret(
            scope=SECRET_SCOPE,
            key="api-token",
            string_value=token
        )

        print(f"✓ Token refreshed at {datetime.now().isoformat()}")
        print(f"  Valid for {TOKEN_VALIDITY // 3600} hours")
        print(f"  Stored in scope='{SECRET_SCOPE}', key='api-token'")
    else:
        print(f"✗ Token refresh failed: {resp.status_code}")
        print(f"  {resp.text[:200]}")
        raise Exception("Token refresh failed")

# Execute
refresh_token()
