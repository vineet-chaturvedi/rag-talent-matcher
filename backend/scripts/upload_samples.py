"""
Loads the sample pack through the REAL API, exactly like the admin portal will:
  1. POST employees.csv  -> /api/employees/import
  2. POST all resumes    -> /api/resumes/bulk
  3. Poll /api/resumes/stats until the worker has processed everything

Run from backend/ while the server is running in another terminal:
    python -m scripts.upload_samples
    python -m scripts.upload_samples --base-url http://127.0.0.1:8010 --samples ../samples
"""
import argparse
import time
from pathlib import Path

import httpx

from scripts.api_login import login

MIME = {".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def main(base_url: str, samples: Path) -> None:
    with httpx.Client(base_url=base_url, timeout=120) as client:
        login(client)
        # 1. Employees
        csv_path = samples / "employees.csv"
        with csv_path.open("rb") as fh:
            r = client.post("/api/employees/import", files={"file": (csv_path.name, fh, "text/csv")})
        r.raise_for_status()
        print("Employee import:", r.json())

        # 2. Resumes, all in one multipart request
        paths = sorted(p for p in (samples / "resumes").iterdir() if p.suffix.lower() in MIME)
        handles = [p.open("rb") for p in paths]
        try:
            files = [("files", (p.name, fh, MIME[p.suffix.lower()])) for p, fh in zip(paths, handles)]
            r = client.post("/api/resumes/bulk", files=files)
        finally:
            for fh in handles:
                fh.close()
        r.raise_for_status()
        result = r.json()
        print(f"\nBulk upload: {result['uploaded']} uploaded, {result['failed']} failed")
        for item in result["items"]:
            if not item["ok"]:
                print(f"  x {item['filename']}: {item['error']}")

        # 3. Wait for the worker
        print("\nWaiting for the worker...")
        while True:
            stats = client.get("/api/resumes/stats").json()
            pending = stats["by_status"]["queued"] + stats["by_status"]["parsing"]
            counts = ", ".join(f"{k}={v}" for k, v in stats["by_status"].items() if v)
            print(f"  {counts}")
            if pending == 0:
                break
            time.sleep(2)

        # 4. Summary per resume
        print("\nResult per resume:")
        for res in client.get("/api/resumes", params={"limit": 500}).json():
            detail = client.get(f"/api/resumes/{res['id']}").json()
            extra = f"{detail['text_length']:>5} chars" if res["status"] == "parsed" else res["error_message"]
            print(f"  #{res['id']:<3} {detail['employee_code']:<9} {res['status']:<7} {res['original_filename']:<40} {extra}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--samples", type=Path, default=Path("../samples"))
    args = parser.parse_args()
    main(args.base_url, args.samples)