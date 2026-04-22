import json
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from typing import Optional, List


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# Map province/city names to AutoTrader region slugs
AUTOTRADER_REGIONS = {
    "ontario":          "reg_on",
    "british columbia": "reg_bc",
    "alberta":          "reg_ab",
    "quebec":           "reg_qc",
    "manitoba":         "reg_mb",
    "saskatchewan":     "reg_sk",
    "nova scotia":      "reg_ns",
    "new brunswick":    "reg_nb",
    "toronto":          "reg_on",
    "vancouver":        "reg_bc",
    "calgary":          "reg_ab",
    "edmonton":         "reg_ab",
    "montreal":         "reg_qc",
    "ottawa":           "reg_on",
    "mississauga":      "reg_on",
    "hamilton":         "reg_on",
}


def _get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-CA,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }


def _polite_delay():
    time.sleep(random.uniform(2, 4))


def _fetch_html(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=20)
        if resp.status_code == 200:
            return resp.text
        elif resp.status_code == 429:
            print(f"  Rate limited — waiting 30s...")
            time.sleep(30)
            resp = requests.get(url, headers=_get_headers(), timeout=20)
            return resp.text if resp.status_code == 200 else None
        else:
            print(f"  HTTP {resp.status_code} for {url[:80]}")
            return None
    except requests.RequestException as e:
        print(f"  Request failed: {e}")
        return None

def scrape_autotrader(make: str, model: str, year_min: int, year_max: int,
                       price_max: int, location: str, max_results: int = 20) -> List[dict]:
    # Build the path-based URL AutoTrader actually uses
    make_slug = make.lower().replace(" ", "_").replace("-", "_")
    region    = AUTOTRADER_REGIONS.get(location.lower(), "reg_on")

    params = {
        "priceMax": price_max,
        "yearMin":  year_min,
        "yearMax":  year_max,
        "sts":      "Used",
        "rcp":      min(max_results, 20),
        "rcs":      0,
        "srt":      35,
        "prxl":     "500",  # radius
    }

    # Add model to params if provided (AutoTrader uses it as a query param)
    if model:
        params["mdl"] = model

    url = f"https://www.autotrader.ca/cars/{make_slug}/{region}/ot_used?{urlencode(params)}"
    print(f"  Fetching: {url}")

    html = _fetch_html(url)
    if not html:
        return []

    return _extract_from_next_data(html, "AutoTrader CA", max_results)


def _extract_from_next_data(html: str, source_name: str, max_results: int) -> List[dict]:
    """Extract listings from __NEXT_DATA__ JSON blob."""
    soup = BeautifulSoup(html, "html.parser")
    tag  = soup.find("script", {"id": "__NEXT_DATA__"})

    if not tag:
        print(f"  ❌ No __NEXT_DATA__ tag found in page")
        # Print page title so we know what we got
        title = soup.find("title")
        print(f"  Page title: {title.get_text() if title else 'unknown'}")
        return []

    try:
        data = json.loads(tag.string)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"  ❌ JSON parse failed: {e}")
        return []

    page_props = data.get("props", {}).get("pageProps", {})
    raw_listings = page_props.get("listings", [])

    if not raw_listings:
        # Debug: show what keys ARE present
        print(f"  ⚠️  No 'listings' key found. pageProps keys: {list(page_props.keys())[:10]}")
        return []

    print(f"  ✅ Found {len(raw_listings)} listings in JSON")

    listings = []
    for item in raw_listings[:max_results]:
        listing = _parse_autotrader_listing(item, source_name)
        if listing:
            listings.append(listing)

    # Descriptions are already in the JSON — skip fetching detail pages to save time
    # (The JSON already includes full descriptions as seen in autotrader_debug.html)
    return listings


def _parse_autotrader_listing(item: dict, source: str) -> Optional[dict]:
    try:
        vehicle  = item.get("vehicle", {})
        price    = item.get("price", {})
        location = item.get("location", {})
        seller   = item.get("seller", {})

        year  = vehicle.get("modelYear", "")
        make  = vehicle.get("make", "")
        model = vehicle.get("model", "")
        trim  = vehicle.get("modelVersionInput") or ""
        km    = vehicle.get("mileageInKm", "N/A")
        fuel  = vehicle.get("fuel", "")

        title = f"{year} {make} {model}".strip()
        if trim:
            title += f" {trim}"

        price_str   = price.get("priceFormatted", "N/A")
        url         = item.get("url", "N/A")
        city        = location.get("city", "")
        province    = location.get("provinceCode", "")
        seller_name = seller.get("companyName", "")

        # Description is embedded in the JSON (confirmed in debug HTML)
        description = item.get("description", "")
        if description:
            desc_soup   = BeautifulSoup(description, "html.parser")
            description = desc_soup.get_text(separator=" ", strip=True)[:2000]
        else:
            parts = []
            if fuel:        parts.append(f"Fuel: {fuel}")
            if km:          parts.append(f"Mileage: {km}")
            if city:        parts.append(f"Location: {city}, {province}")
            if seller_name: parts.append(f"Seller: {seller_name}")
            description = ". ".join(parts)

        return {
            "source":      source,
            "title":       title,
            "price":       price_str,
            "mileage":     str(km),
            "url":         url,
            "description": description,
        }
    except Exception as e:
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
    query    = f"{make} {model}".strip().lower().replace(" ", "-")
    params   = {
        "price": f"__0__{price_max}",
        "year":  f"{year_min}__{year_max}",
    }

    url = (f"https://www.kijiji.ca/b-cars-trucks/{loc_code}/"
           f"{query}/k0c174?{urlencode(params)}")

    print(f"  Fetching: {url}")

    html = _fetch_html(url)
    if not html:
        return []

    soup     = BeautifulSoup(html, "html.parser")
    listings = []

    # Try __NEXT_DATA__ JSON first
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if tag:
        try:
            data         = json.loads(tag.string)
            page_props   = data.get("props", {}).get("pageProps", {})
            raw_listings = _find_kijiji_listings(page_props)

            if raw_listings:
                print(f"  ✅ Found {len(raw_listings)} listings in JSON")
                for item in raw_listings[:max_results]:
                    listing = _parse_kijiji_listing(item)
                    if listing:
                        listings.append(listing)
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: HTML card parsing
    if not listings:
        print("  ⚠️  JSON failed, trying HTML cards...")
        listings = _scrape_kijiji_html(soup, max_results)

    return listings


def _find_kijiji_listings(page_props: dict) -> List[dict]:
    # Direct key
    for key in ("listings", "ads", "searchResults"):
        val = page_props.get(key)
        if isinstance(val, list) and val:
            return val

    # One level deep
    for key in ("initialProps", "initialData", "searchData", "srp", "listingData"):
        section = page_props.get(key)
        if isinstance(section, dict):
            for sub in ("listings", "ads", "searchResults"):
                val = section.get(sub)
                if isinstance(val, list) and val:
                    return val

    return []


def _parse_kijiji_listing(item: dict) -> Optional[dict]:
    try:
        title    = item.get("title", item.get("headline", ""))
        price    = item.get("price", {})
        url_path = item.get("seoUrl", item.get("url", ""))
        desc     = item.get("description", "")
        attrs    = item.get("attributes", {})

        if not title or len(title) < 3:
            return None

        if isinstance(price, dict):
            price_str = price.get("amount", price.get("displayPrice", "N/A"))
        else:
            price_str = str(price) if price else "N/A"

        url = (f"https://www.kijiji.ca{url_path}"
               if url_path.startswith("/") else url_path or "N/A")

        km = "N/A"
        if isinstance(attrs, dict):
            km = attrs.get("kilometres", attrs.get("mileage", "N/A"))
        elif isinstance(attrs, list):
            for attr in attrs:
                if isinstance(attr, dict) and attr.get("name", "").lower() in ("kilometres", "mileage"):
                    km = attr.get("value", "N/A")
                    break

        if desc:
            desc = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)[:2000]
        else:
            desc = f"Mileage: {km}"

        return {
            "source":      "Kijiji",
            "title":       title,
            "price":       str(price_str),
            "mileage":     str(km),
            "url":         url,
            "description": desc,
        }
    except Exception:
        return None


def _scrape_kijiji_html(soup: BeautifulSoup, max_results: int) -> List[dict]:
    cards = (soup.select("li[data-listing-id]") or
             soup.select("[data-testid='listing-card']") or
             soup.select("article[class*='listing']") or
             soup.select("div[class*='regular-ad']"))

    print(f"  Found {len(cards)} HTML cards")
    listings = []

    for card in cards[:max_results]:
        try:
            title_el = (card.select_one("[class*='title']") or
                        card.select_one("h3") or
                        card.select_one("a[data-listing-id]"))
            price_el = card.select_one("[class*='price']")
            link_el  = (card.select_one("a[href*='/v-']") or
                        card.select_one("a[href*='/a-']"))
            km_el    = card.select_one("[class*='mileage']") or card.select_one("[class*='km']")

            title = title_el.get_text(strip=True) if title_el else None
            if not title or len(title) < 3:
                continue

            price = price_el.get_text(strip=True) if price_el else "N/A"
            href  = link_el.get("href", "") if link_el else ""
            url   = f"https://www.kijiji.ca{href}" if href.startswith("/") else href or "N/A"
            km    = km_el.get_text(strip=True) if km_el else "N/A"

            listings.append({
                "source":      "Kijiji",
                "title":       title,
                "price":       price,
                "mileage":     km,
                "url":         url,
                "description": f"Mileage: {km}",
            })
        except Exception:
            continue

    return listings

def deduplicate(listings: List[dict]) -> List[dict]:
    seen   = set()
    unique = []
    for listing in listings:
        key = (listing["title"][:40].lower().strip(), listing["price"])
        if key not in seen:
            seen.add(key)
            unique.append(listing)
    return unique