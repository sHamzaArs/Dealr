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
    
def scrape_autotrader(make: str, model: str, year_min: int, year_max: int,
                       price_max: int, location: str, max_results: int = 20) -> list[dict]:
    """
    Scrape AutoTrader CA listings.
    Uses the epctex/autotrader-scraper actor on Apify.
    """
    search_url = (
        f"https://www.autotrader.ca/cars/{make.lower()}/{model.lower()}/"
        f"?rcp={max_results}&rcs=0&srt=35&yRng={year_min}%2C{year_max}"
        f"&pRng=%2C{price_max}&loc={location}&hprc=True&wcp=True&sts=New-Used"
    )
 
    run_input = {
        "startUrls": [{"url": search_url}],
        "maxItems": max_results,
        "proxy": {"useApifyProxy": True}
    }
 
    raw_items = _run_actor("epctex/autotrader-scraper", run_input)
 
    normalized = []
    for item in raw_items:
        try:
            normalized.append({
                "source": "AutoTrader CA",
                "title": f"{item.get('year', '')} {item.get('make', '')} {item.get('model', '')} {item.get('trim', '')}".strip(),
                "price": f"${item.get('price', 'N/A'):,}" if isinstance(item.get('price'), int) else str(item.get('price', 'N/A')),
                "mileage": item.get('mileage', 'N/A'),
                "url": item.get('url', 'N/A'),
                "description": item.get('description', '') or _build_description_from_fields(item),
            })
        except Exception:
            continue
 
    return normalized
 
 
def scrape_kijiji(make: str, model: str, year_min: int, year_max: int,
                   price_max: int, location: str, max_results: int = 20) -> list[dict]:
    """
    Scrape Kijiji Autos listings.
    Uses the epctex/kijiji-scraper actor on Apify.
    """
    search_url = (
        f"https://www.kijiji.ca/b-cars-trucks/{location.lower().replace(' ', '-')}/"
        f"{make.lower()}-{model.lower()}/k0c174l0"
        f"?price=0__{price_max}&year={year_min}__{year_max}"
    )
 
    run_input = {
        "startUrls": [{"url": search_url}],
        "maxItems": max_results,
        "proxy": {"useApifyProxy": True}
    }
 
    raw_items = _run_actor("epctex/kijiji-scraper", run_input)
 
    normalized = []
    for item in raw_items:
        try:
            normalized.append({
                "source": "Kijiji",
                "title": item.get('title', 'Unknown listing'),
                "price": item.get('price', 'N/A'),
                "mileage": item.get('attributes', {}).get('Kilometres', 'N/A'),
                "url": item.get('url', 'N/A'),
                "description": item.get('description', ''),
            })
        except Exception:
            continue
 
    return normalized
 
 
def _build_description_from_fields(item: dict) -> str:
    """Fallback: build a description string from structured fields when no free text is present."""
    parts = []
    if item.get("mileage"):
        parts.append(f"Mileage: {item['mileage']} km")
    if item.get("transmission"):
        parts.append(f"Transmission: {item['transmission']}")
    if item.get("drivetrain"):
        parts.append(f"Drivetrain: {item['drivetrain']}")
    if item.get("engine"):
        parts.append(f"Engine: {item['engine']}")
    if item.get("colour"):
        parts.append(f"Colour: {item['colour']}")
    if item.get("doors"):
        parts.append(f"Doors: {item['doors']}")
    if item.get("bodyType"):
        parts.append(f"Body type: {item['bodyType']}")
    return ". ".join(parts) if parts else "No description available."
 
 
def deduplicate(listings: list[dict]) -> list[dict]:
    """
    Remove duplicate listings that appear on multiple platforms.
    Matches on (normalized title + approximate price).
    """
    seen = set()
    unique = []
    for listing in listings:
        # Simple key: first 40 chars of title + price
        key = (listing["title"][:40].lower().strip(), listing["price"])
        if key not in seen:
            seen.add(key)
            unique.append(listing)
    return unique
