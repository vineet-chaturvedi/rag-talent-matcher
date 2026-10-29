"""
Creates the sample projects and roles from samples/roles.json through the REAL API, then asks
the LLM to parse each role's description into structured requirements.

Safe to run again: projects and roles that already exist (same names) are reused, not duplicated.
Roles that are already parsed are skipped unless you pass --reparse.

Run from backend/ while the server is running in another terminal:
    python -m scripts.load_roles
    python -m scripts.load_roles --reparse
"""
import argparse
import json
import time
from pathlib import Path

import httpx

from scripts.api_login import login

ROLE_FIELDS = ("title", "description", "location", "allocation_percent", "start_date", "headcount")


def main(base_url: str, roles_file: Path, reparse: bool) -> None:
    roles = json.loads(roles_file.read_text(encoding="utf-8"))
    with httpx.Client(base_url=base_url, timeout=600) as client:   # parsing can take a minute on a CPU
        login(client)
        projects = {p["name"]: p for p in client.get("/api/projects").raise_for_status().json()}

        for spec in roles:
            # 1. Project (reuse by name)
            project = projects.get(spec["project"])
            if project is None:
                project = client.post("/api/projects", json={
                    "name": spec["project"], "client_name": spec.get("client_name"),
                    "status": "planned", "start_date": spec.get("start_date"),
                }).raise_for_status().json()
                projects[project["name"]] = project
                print(f"+ project  {project['name']} (id {project['id']})")

            # 2. Role (reuse by title inside the project)
            role = next((r for r in project.get("roles", []) if r["title"] == spec["title"]), None)
            if role is None:
                role = client.post(f"/api/projects/{project['id']}/roles",
                                   json={k: spec[k] for k in ROLE_FIELDS if k in spec}).raise_for_status().json()
                project.setdefault("roles", []).append(role)
                print(f"+ role     {role['title']} (id {role['id']})")

            # 3. LLM parses the description into requirements
            if role.get("requirements") and not reparse:
                print(f"= parsed   {role['title']} (already parsed; --reparse to redo)")
            else:
                t0 = time.perf_counter()
                role = client.post(f"/api/roles/{role['id']}/requirements/parse").raise_for_status().json()
                print(f"~ parsed   {role['title']} in {time.perf_counter() - t0:.0f} s")

            req = role["requirements"]
            must = ", ".join(f"{s['name']}" + (f" ({s['min_years']}y)" if s["min_years"] else "") for s in req["must_have"])
            nice = ", ".join(s["name"] for s in req["nice_to_have"])
            print(f"    role id {role['id']} | seniority {req['seniority']} | min years {req['min_total_years']}")
            print(f"    must-have:    {must or '-'}")
            print(f"    nice-to-have: {nice or '-'}")
            print(f"    summary:      {req['search_summary']}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--roles", type=Path, default=Path("../samples/roles.json"))
    parser.add_argument("--reparse", action="store_true", help="ask the LLM again even if already parsed")
    args = parser.parse_args()
    main(args.base_url, args.roles, args.reparse)
