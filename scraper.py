import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from typing import Optional, List

# Rotating user agents — mimics real browsers so we don't get blocked immediately
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def _get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-CA,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _polite_delay():
    time.sleep(random.uniform(2, 4))


def _fetch(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=15)
        if resp.status_code == 200:
            return BeautifulSoup(resp.text, "html.parser")
        elif resp.status_code == 403:
            print(f"  Blocked (403) on {url[:60]}... — try again later")
        elif resp.status_code == 429:
            print(f"  Rate limited (429) — waiting 30s...")
            time.sleep(30)
        else:
            print(f"  HTTP {resp.status_code} on {url[:60]}...")
    except requests.RequestException as e:
        print(f"  Request failed: {e}")
    return None

def scrape_autotrader(make: str, model: str, year_min: int, year_max: int,
                       price_max: int, location: str, max_results: int = 20) -> List[dict]:

    params = {
        "make": make,
        "model": model,
        "yearMin": year_min,
        "yearMax": year_max,
        "priceMax": price_max,
        "loc": location,
        "hprc": "True",
        "wcp": "True",
        "sts": "Used",
        "rcp": min(max_results, 15),
        "rcs": 0,
        "srt": 35,
    }

    url = f"https://www.autotrader.ca/cars/?{urlencode(params)}"
    print(f"  Fetching: {url[:80]}...")

    soup = _fetch(url)
    if not soup:
        return []

    listings = []
    cards = soup.select("div[class*='result-item']") or soup.select("div[data-listing-id]")

    if not cards:
        # Fallback: try embedded JSON state
        import json, re
        for script in soup.find_all("script", string=re.compile(r'"price"')):
            try:
                match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', script.string or "")
                if match:
                    data = json.loads(match.group(1))
                    raw_listings = (data.get("searchResults", {})
                                       .get("listingsContainer", {})
                                       .get("listings", []))
                    for item in raw_listings[:max_results]:
                        listing = _normalize_autotrader_json(item)
                        if listing:
                            listings.append(listing)
                    break
            except Exception:
                continue
    else:
        for card in cards[:max_results]:
            listing = _parse_autotrader_card(card)
            if listing:
                listings.append(listing)

    if listings:
        print(f"  Found {len(listings)} listings on AutoTrader CA — fetching details...")
        for i, listing in enumerate(listings[:max_results]):
            if listing.get("url") and listing.get("url") != "N/A":
                _polite_delay()
                detail = _fetch_autotrader_detail(listing["url"])
                if detail:
                    listing["description"] = detail
            if i % 5 == 0 and i > 0:
                print(f"    {i}/{len(listings)} details fetched...")

    return listings


def _parse_autotrader_card(card) -> Optional[dict]:
    try:
        title_el = card.select_one("span.title-with-trim") or card.select_one("[class*='title']")
        price_el = card.select_one("span.price-amount") or card.select_one("[class*='price']")
        link_el  = card.select_one("a[href*='/a/']") or card.select_one("a")
        km_el    = card.select_one("span[class*='kms']") or card.select_one("[class*='mileage']")

        title = title_el.get_text(strip=True) if title_el else None
        price = price_el.get_text(strip=True) if price_el else "N/A"
        url   = "https://www.autotrader.ca" + link_el["href"] if link_el and link_el.get("href") else "N/A"
        km    = km_el.get_text(strip=True) if km_el else "N/A"

        if not title:
            return None

        return {
            "source":      "AutoTrader CA",
            "title":       title,
            "price":       price,
            "mileage":     km,
            "url":         url,
            "description": f"Mileage: {km}",
        }
    except Exception:
        return None


def _normalize_autotrader_json(item: dict) -> Optional[dict]:
    try:
        year  = item.get("year", "")
        make  = item.get("make", "")
        model = item.get("model", "")
        trim  = item.get("trim", "")
        price = item.get("price", {})
        km    = item.get("mileage", "N/A")
        url   = item.get("link", "N/A")

        price_str = f"${price.get('value', 'N/A'):,}" if isinstance(price, dict) else str(price)
        title = f"{year} {make} {model} {trim}".strip()

        return {
            "source":      "AutoTrader CA",
            "title":       title,
            "price":       price_str,
            "mileage":     str(km),
            "url":         f"https://www.autotrader.ca{url}" if url.startswith("/") else url,
            "description": f"Mileage: {km} km",
        }
    except Exception:
        return None


def _fetch_autotrader_detail(url: str) -> Optional[str]:
    soup = _fetch(url)
    if not soup:
        return None

    desc_el = (soup.select_one("div.vdp-description") or
               soup.select_one("[class*='description']") or
               soup.select_one("section[class*='details']"))

    if desc_el:
        return desc_el.get_text(separator=" ", strip=True)[:2000]

    specs = soup.select("dt, dd")
    if specs:
        return " | ".join(s.get_text(strip=True) for s in specs)[:2000]

    return None

KIJIJI_LOCATION_CODES = {
    "ontario":          "l1700272",
    "toronto":          "l1700273",
    "ottawa":           "l1700185",
    "hamilton":         "l1700194",
    "london":           "l1700214",
    "mississauga":      "l1700276",
    "brampton":         "l1700275",
    "kitchener":        "l1700209",
    "british columbia": "l1700228",
    "vancouver":        "l1700229",
    "alberta":          "l1700192",
    "calgary":          "l1700199",
    "edmonton":         "l1700200",
    "quebec":           "l1700264",
    "montreal":         "l1700281",
}


def scrape_kijiji(make: str, model: str, year_min: int, year_max: int,
                   price_max: int, location: str, max_results: int = 20) -> List[dict]:

    loc_code = KIJIJI_LOCATION_CODES.get(location.lower(), "l1700272")
    query = f"{make} {model}".strip()

    params = {
        "price": f"__0__{price_max}",
        "year":  f"{year_min}__{year_max}",
    }

    url = (f"https://www.kijiji.ca/b-cars-trucks/{loc_code}/"
           f"{query.lower().replace(' ', '-')}/k0c174?{urlencode(params)}")

    print(f"  Fetching: {url[:80]}...")

    soup = _fetch(url)
    if not soup:
        return []

    cards = soup.select("li[data-listing-id]") or soup.select("div[class*='regular-ad']")
    print(f"  Found {len(cards)} cards on Kijiji")

    listings = []
    for card in cards[:max_results]:
        listing = _parse_kijiji_card(card)
        if listing:
            listings.append(listing)

    if listings:
        print(f"  Fetching details for {len(listings)} Kijiji listings...")
        for i, listing in enumerate(listings):
            if listing.get("url") and listing["url"] != "N/A":
                _polite_delay()
                detail = _fetch_kijiji_detail(listing["url"])
                if detail:
                    listing["description"] = detail
            if i % 5 == 0 and i > 0:
                print(f"    {i}/{len(listings)} details fetched...")

    return listings


def _parse_kijiji_card(card) -> Optional[dict]:
    try:
        title_el = card.select_one("[class*='title']") or card.select_one("a[class*='title']")
        price_el = card.select_one("[class*='price']")
        link_el  = card.select_one("a[href*='/v-']") or card.select_one("a")
        km_el    = card.select_one("[class*='mileage']") or card.select_one("[class*='km']")

        title = title_el.get_text(strip=True) if title_el else None
        price = price_el.get_text(strip=True) if price_el else "N/A"
        href  = link_el["href"] if link_el and link_el.get("href") else None
        url   = f"https://www.kijiji.ca{href}" if href and href.startswith("/") else (href or "N/A")
        km    = km_el.get_text(strip=True) if km_el else "N/A"

        if not title:
            return None

        return {
            "source":      "Kijiji",
            "title":       title,
            "price":       price,
            "mileage":     km,
            "url":         url,
            "description": f"Mileage: {km}",
        }
    except Exception:
        return None


def _fetch_kijiji_detail(url: str) -> Optional[str]:
    soup = _fetch(url)
    if not soup:
        return None

    desc_el = (soup.select_one("div[class*='description']") or
               soup.select_one("[itemprop='description']") or
               soup.select_one("div[class*='Details']"))

    if desc_el:
        return desc_el.get_text(separator=" ", strip=True)[:2000]

    return None

def deduplicate(listings: List[dict]) -> List[dict]:
    seen = set()
    unique = []
    for listing in listings:
        key = (listing["title"][:40].lower().strip(), listing["price"])
        if key not in seen:
            seen.add(key)
            unique.append(listing)
    return unique