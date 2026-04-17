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
        f"{APIFY_BASE}"
    )