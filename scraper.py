import json
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from typing import Optional, List

try:
    from curl_cffi import requests as cffi_requests
    CURL_AVAILABLE = True
except ImportError:
    import requests as std_requests
    CURL_AVAILABLE = False
    print("WARNING: curl_cffi not installed. Run: pip install curl-cffi")
    print("         Falling back to plain requests (may get blocked).")


AUTOTRADER_REGIONS = {
    "ontario": "reg_on", "british columbia": "reg_bc", "alberta": "reg_ab",
    "quebec": "reg_qc", "manitoba": "reg_mb", "saskatchewan": "reg_sk",
    "nova scotia": "reg_ns", "new brunswick": "reg_nb",
    "toronto": "reg_on", "vancouver": "reg_bc", "calgary": "reg_ab",
    "edmonton": "reg_ab", "montreal": "reg_qc", "ottawa": "reg_on",
    "mississauga": "reg_on", "hamilton": "reg_on", "kitchener": "reg_on",
    "london": "reg_on",
}

KIJIJI_LOCATIONS = {
    "ontario": "l1700272", "toronto": "l1700273", "ottawa": "l1700185",
    "hamilton": "l1700194", "london": "l1700214", "mississauga": "l1700276",
    "brampton": "l1700275", "kitchener": "l1700209",
    "british columbia": "l1700228", "vancouver": "l1700229",
    "alberta": "l1700192", "calgary": "l1700199", "edmonton": "l1700200",
    "quebec": "l1700264", "montreal": "l1700281",
}


def _fetch(url: str) -> Optional[str]:
    try:
        if CURL_AVAILABLE:
            resp = cffi_requests.get(url, impersonate="chrome120", timeout=20)
        else:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-CA,en;q=0.9",
            }
            resp = std_requests.get(url, headers=headers, timeout=20)

        if resp.status_code == 200:
            return resp.text
        elif resp.status_code == 403:
            print(f"  X 403 Forbidden. Make sure curl-cffi is installed: pip install curl-cffi")
            return None
        elif resp.status_code == 429:
            print(f"  Rate limited, waiting 30s...")
            time.sleep(30)
            return _fetch(url)
        else:
            print(f"  HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  Request error: {e}")
        return None


def _parse_next_data(html: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tag  = soup.find("script", {"id": "__NEXT_DATA__"})
    if not tag or not tag.string:
        title = soup.find("title")
        print(f"  X No __NEXT_DATA__ found. Page title: '{title.get_text() if title else 'none'}'")
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError as e:
        print(f"  X JSON parse error: {e}")
        return None


def _polite_delay():
    time.sleep(random.uniform(1.5, 3.0))


# ── AutoTrader CA ─────────────────────────────────────────────

def scrape_autotrader(make: str, model: str, year_min: int, year_max: int,
                       price_max: int, location: str, max_results: int = 20) -> List[dict]:
    make_slug = make.lower().replace(" ", "_")
    region    = AUTOTRADER_REGIONS.get(location.lower(), "reg_on")
    params    = {
        "yearMin": year_min, "yearMax": year_max,
        "priceMax": price_max, "sts": "Used",
        "rcp": min(max_results, 20), "rcs": 0, "srt": 35,
    }
    if model:
        params["mdl"] = model

    url = f"https://www.autotrader.ca/cars/{make_slug}/{region}/ot_used?{urlencode(params)}"
    print(f"  URL: {url}")

    html = _fetch(url)
    if not html:
        return []

    data = _parse_next_data(html)
    if not data:
        return []

    page_props   = data.get("props", {}).get("pageProps", {})
    raw_listings = page_props.get("listings", [])

    if not raw_listings:
        print(f"  No 'listings' key. pageProps keys: {list(page_props.keys())[:8]}")
        return []

    print(f"  OK {len(raw_listings)} listings found")
    return [r for r in (_parse_autotrader_item(i) for i in raw_listings[:max_results]) if r]


def _parse_autotrader_item(item: dict) -> Optional[dict]:
    try:
        v = item.get("vehicle", {})
        year  = v.get("modelYear", "")
        make  = v.get("make", "")
        model = v.get("model", "")
        trim  = v.get("modelVersionInput") or ""
        km    = v.get("mileageInKm", "N/A")
        fuel  = v.get("fuel", "")

        title = f"{year} {make} {model}".strip()
        if trim:
            title += f" {trim}"

        price_str = item.get("price", {}).get("priceFormatted", "N/A")
        url       = item.get("url", "N/A")
        loc       = item.get("location", {})
        city      = loc.get("city", "")
        province  = loc.get("provinceCode", "")
        dealer    = item.get("seller", {}).get("companyName", "")

        desc = item.get("description", "")
        if desc:
            desc = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)[:2000]
        else:
            parts = [x for x in [
                f"Fuel: {fuel}" if fuel else "",
                f"Mileage: {km}" if km else "",
                f"Location: {city}, {province}" if city else "",
                f"Seller: {dealer}" if dealer else "",
            ] if x]
            desc = ". ".join(parts)

        return {"source": "AutoTrader CA", "title": title, "price": price_str,
                "mileage": str(km), "url": url, "description": desc}
    except Exception:
        return None


# ── Kijiji ────────────────────────────────────────────────────

def scrape_kijiji(make: str, model: str, year_min: int, year_max: int,
                   price_max: int, location: str, max_results: int = 20) -> List[dict]:
    loc_code = KIJIJI_LOCATIONS.get(location.lower(), "l1700272")
    query    = f"{make} {model}".strip().lower().replace(" ", "-")
    params   = {"price": f"__0__{price_max}", "year": f"{year_min}__{year_max}"}
    url = f"https://www.kijiji.ca/b-cars-trucks/{loc_code}/{query}/k0c174?{urlencode(params)}"
    print(f"  URL: {url}")

    html = _fetch(url)
    if not html:
        return []

    data     = _parse_next_data(html)
    listings = []

    if data:
        page_props   = data.get("props", {}).get("pageProps", {})
        raw_listings = _find_kijiji_ads(page_props)
        if raw_listings:
            print(f"  OK {len(raw_listings)} listings found in JSON")
            listings = [r for r in (_parse_kijiji_item(i) for i in raw_listings[:max_results]) if r]

    if not listings:
        print("  JSON failed, trying HTML fallback...")
        soup     = BeautifulSoup(html, "html.parser")
        listings = _kijiji_html_fallback(soup, max_results)

    return listings


def _find_kijiji_ads(page_props: dict) -> List[dict]:
    for key in ("listings", "ads", "searchResults"):
        val = page_props.get(key)
        if isinstance(val, list) and val:
            return val
    for sk in ("initialProps", "initialData", "searchData", "srp"):
        section = page_props.get(sk, {})
        if isinstance(section, dict):
            for key in ("listings", "ads", "searchResults"):
                val = section.get(key)
                if isinstance(val, list) and val:
                    return val
    return []


def _parse_kijiji_item(item: dict) -> Optional[dict]:
    try:
        title = item.get("title", item.get("headline", ""))
        if not title or len(title) < 3:
            return None
        price    = item.get("price", {})
        url_path = item.get("seoUrl", item.get("url", ""))
        desc     = item.get("description", "")
        attrs    = item.get("attributes", {})

        price_str = price.get("amount", price.get("displayPrice", "N/A")) if isinstance(price, dict) else str(price or "N/A")
        url = f"https://www.kijiji.ca{url_path}" if str(url_path).startswith("/") else str(url_path) or "N/A"

        km = "N/A"
        if isinstance(attrs, dict):
            km = attrs.get("kilometres", attrs.get("mileage", "N/A"))
        elif isinstance(attrs, list):
            for a in attrs:
                if isinstance(a, dict) and a.get("name", "").lower() in ("kilometres", "mileage"):
                    km = a.get("value", "N/A"); break

        if desc:
            desc = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)[:2000]
        else:
            desc = f"Mileage: {km}"

        return {"source": "Kijiji", "title": title, "price": str(price_str),
                "mileage": str(km), "url": url, "description": desc}
    except Exception:
        return None


def _kijiji_html_fallback(soup: BeautifulSoup, max_results: int) -> List[dict]:
    cards = (soup.select("li[data-listing-id]") or
             soup.select("[data-testid='listing-card']") or
             soup.select("article[class*='listing']") or
             soup.select("div[class*='regular-ad']"))
    print(f"  HTML fallback: {len(cards)} cards found")
    listings = []
    for card in cards[:max_results]:
        try:
            title_el = card.select_one("[class*='title']") or card.select_one("h3")
            price_el = card.select_one("[class*='price']")
            link_el  = card.select_one("a[href*='/v-']") or card.select_one("a[href*='/a-']")
            km_el    = card.select_one("[class*='mileage']")
            title = title_el.get_text(strip=True) if title_el else None
            if not title or len(title) < 3:
                continue
            price = price_el.get_text(strip=True) if price_el else "N/A"
            href  = link_el.get("href", "") if link_el else ""
            url   = f"https://www.kijiji.ca{href}" if href.startswith("/") else href or "N/A"
            km    = km_el.get_text(strip=True) if km_el else "N/A"
            listings.append({"source": "Kijiji", "title": title, "price": price,
                              "mileage": km, "url": url, "description": f"Mileage: {km}"})
        except Exception:
            continue
    return listings


# ── Shared ────────────────────────────────────────────────────

def deduplicate(listings: List[dict]) -> List[dict]:
    seen, unique = set(), []
    for listing in listings:
        key = (listing["title"][:40].lower().strip(), listing["price"])
        if key not in seen:
            seen.add(key)
            unique.append(listing)
    return unique