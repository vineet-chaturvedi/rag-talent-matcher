"""
Shared login for the developer scripts (Step 9): every API call now needs a logged-in user.

The scripts read the credentials from environment variables, or ask once:
    $env:RTM_EMAIL = "admin@company.local"      (PowerShell; lasts for this terminal window)
    $env:RTM_PASSWORD = "..."
"""
import getpass
import os

import httpx


def login(client: httpx.Client) -> None:
    """Log in and attach the token to every later request of this client."""
    email = os.environ.get("RTM_EMAIL") or input("Portal email: ").strip()
    password = os.environ.get("RTM_PASSWORD") or getpass.getpass("Password: ")
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        raise SystemExit(f"Login failed ({r.status_code}): {r.json().get('detail')}")
    user = r.json()["user"]
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    print(f"Logged in as {user['email']} ({user['role']})")
