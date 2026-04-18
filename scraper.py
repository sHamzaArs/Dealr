import os
import time
import requests

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
APIFY_BASE = "https://api.apify.com/v2"

def _run_actor(actor_id: str, run_input: dict, timeout: int = 120) -> list[dict]:
    headers = {"Content-Type": "application/json"}
    params = {"token": APIFY_TOKEN}

    #begin actor run
    run_resp = requests.post(
        f"{APIFY_BASE}/acts/{actor_id}/runs",
        json=run_input,
        params=params,
        headers=headers
    )
    run_resp.raise_for_status()
    run_id = run_resp.json()["data"]["id"]

    print(f" Actor {actor_id} started (run {run_id}), waiting...")
    elapsed = 0  
    while elapsed < timeout:
        time.sleep(5)
        elapsed += 5
        status_resp = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}"
            params=params
        )
        status = status_resp.json()["data"]["defaultDatasetId"]
        items_resp = requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": APIFY_TOKEN, "format": "json"}
        )
        items_resp.raise_for_status()
        return items_resp.json()
