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

# AutoTrader province slugs
AUTOTRADER_REGIONS = {
    "ontario": "reg_on", "british columbia": "reg_bc", "alberta": "reg_ab",
    "quebec": "reg_qc", "manitoba": "reg_mb", "saskatchewan": "reg_sk",
    "nova scotia": "reg_ns", "new brunswick": "reg_nb",
    "toronto": "reg_on", "vancouver": "reg_bc", "calgary": "reg_ab",
    "edmonton": "reg_ab", "montreal": "reg_qc", "ottawa": "reg_on",
    "mississauga": "reg_on", "hamilton": "reg_on", "kitchener": "reg_on",
}

# Kijiji location IDs for their API
KIJIJI_LOCATION_IDS = {
    "ontario": 9004, "toronto": 1700273, "ottawa": 1700185,
    "hamilton": 1700194, "london": 1700214, "mississauga": 1700276,
    "brampton": 1700275, "kitchener": 1700209,
    "british columbia": 9007, "vancouver": 1700229,
    "alberta": 9003, "calgary": 1700199, "edmonton": 1700200,
    "quebec": 9005, "montreal": 1700281,
}


def _fetch(url: str, headers: dict = None) -> Optional[str]:
    try:
        if CURL_AVAILABLE:
            resp = cffi_requests.get(
                url,
                impersonate="chrome120",
                headers=headers or {},
                timeout=20,
            )
        else:
            h = headers or {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-CA,en;q=0.9",
            }
            resp = std_requests.get(url, headers=h, timeout=20)

        if resp.status_code == 200:
            return resp.text
        elif resp.status_code == 403:
            print(f"  ⛔ 403 Forbidden — make sure curl-cffi is installed: pip install curl-cffi")
            return None
        elif resp.status_code == 429:
            print(f"  ⏳ Rate limited — waiting 30s...")
            time.sleep(30)
            return _fetch(url, headers)
        else:
            print(f"  HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  Request error: {e}")
        return None


def _polite_delay():
    time.sleep(random.uniform(1.5, 3.0))


# ─────────────────────────────────────────────────────────────────
# AutoTrader CA
# ─────────────────────────────────────────────────────────────────

def scrape_autotrader(make: str, model: str, year_min: int, year_max: int,
                       price_max: int, location: str, max_results: int = 20) -> List[dict]:
    make_slug = make.lower().replace(" ", "_")
    region    = AUTOTRADER_REGIONS.get(location.lower(), "reg_on")

    params = {
        "yearMin":  year_min,
        "yearMax":  year_max,
        "priceMax": price_max,
        "sts":      "Used",
        "rcp":      min(max_results, 20),
        "rcs":      0,
        "srt":      35,
    }
    if model:
        params["mdl"] = model

    url = f"https://www.autotrader.ca/cars/{make_slug}/{region}/ot_used?{urlencode(params)}"
    print(f"  URL: {url}")

    html = _fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    tag  = soup.find("script", {"id": "__NEXT_DATA__"})

    if not tag or not tag.string:
        title = soup.find("title")
        print(f"  ❌ No __NEXT_DATA__ found. Page title: '{title.get_text() if title else 'none'}'")
        return []

    try:
        data = json.loads(tag.string)
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {e}")
        return []

    page_props   = data.get("props", {}).get("pageProps", {})
    raw_listings = page_props.get("listings", [])

    if not raw_listings:
        print(f"  ⚠️  No 'listings' key. pageProps keys: {list(page_props.keys())[:8]}")
        return []

    print(f"  ✅ {len(raw_listings)} listings in JSON — filtering by year {year_min}–{year_max}")

    results = []
    for item in raw_listings:
        parsed = _parse_autotrader_item(item)
        if not parsed:
            continue

        # Post-filter: AutoTrader's mdl= param doesn't filter reliably,
        # so we enforce year range ourselves
        vehicle_year = item.get("vehicle", {}).get("modelYear", 0)
        try:
            vehicle_year = int(vehicle_year)
        except (ValueError, TypeError):
            vehicle_year = 0

        if vehicle_year and (vehicle_year < year_min or vehicle_year > year_max):
            continue  # skip listings outside requested year range

        results.append(parsed)
        if len(results) >= max_results:
            break

    if not results:
        # If strict year filter got nothing, return all and let scorer handle it
        print(f"  ⚠️  No listings matched year range {year_min}–{year_max}. Returning all results.")
        results = [r for r in (_parse_autotrader_item(i) for i in raw_listings[:max_results]) if r]

    return results


def _parse_autotrader_item(item: dict) -> Optional[dict]:
    try:
        v         = item.get("vehicle", {})
        year      = v.get("modelYear", "")
        make      = v.get("make", "")
        model     = v.get("model", "")
        trim      = v.get("modelVersionInput") or ""
        km        = v.get("mileageInKm", "N/A")
        fuel      = v.get("fuel", "")

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

        return {
            "source":      "AutoTrader CA",
            "title":       title,
            "price":       price_str,
            "mileage":     str(km),
            "url":         url,
            "description": desc,
        }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────
# Kijiji — public JSON API (not scraping HTML)
# ─────────────────────────────────────────────────────────────────

def scrape_kijiji(make: str, model: str, year_min: int, year_max: int,
                   price_max: int, location: str, max_results: int = 20) -> List[dict]:
    loc_id = KIJIJI_LOCATION_IDS.get(location.lower(), 9004)
    query  = f"{make} {model}".strip()

    # Kijiji's internal search API
    params = {
        "q":              query,
        "locationId":     loc_id,
        "categoryId":     174,          # Cars & Trucks category
        "minPrice":       0,
        "maxPrice":       price_max,
        "minYear":        year_min,
        "maxYear":        year_max,
        "sortByName":     "dateDesc",
        "size":           min(max_results, 40),
        "page":           0,
    }

    api_url = f"https://www.kijiji.ca/v-cars-trucks/car-finder-search?{urlencode(params)}"

    # Try the API endpoint first
    api_headers = {
        "Accept":          "application/json",
        "Accept-Language": "en-CA,en;q=0.9",
        "Referer":         "https://www.kijiji.ca/",
    }

    print(f"  API: {api_url[:90]}...")
    html = _fetch(api_url, headers=api_headers)

    listings = []
    if html:
        try:
            data = json.loads(html)
            ads  = (data.get("ads") or
                    data.get("listings") or
                    data.get("results") or [])
            if ads:
                print(f"  ✅ {len(ads)} listings from Kijiji API")
                for ad in ads[:max_results]:
                    parsed = _parse_kijiji_api_item(ad)
                    if parsed:
                        listings.append(parsed)
                return listings
        except json.JSONDecodeError:
            pass

    # Fallback: try their GraphQL / internal search endpoint
    print("  ⚠️  API didn't return JSON, trying alternate endpoint...")
    listings = _kijiji_alternate(make, model, year_min, year_max, price_max, loc_id, max_results)
    return listings


def _parse_kijiji_api_item(ad: dict) -> Optional[dict]:
    try:
        title     = ad.get("title", "")
        if not title or len(title) < 3:
            return None

        price     = ad.get("price", {})
        if isinstance(price, dict):
            price_str = price.get("amount", price.get("formattedAmount", "N/A"))
        else:
            price_str = str(price) if price else "N/A"

        url_slug = ad.get("seoUrl", ad.get("url", ""))
        url      = f"https://www.kijiji.ca{url_slug}" if url_slug.startswith("/") else url_slug or "N/A"

        desc = ad.get("description", ad.get("shortDescription", ""))
        if desc:
            desc = BeautifulSoup(str(desc), "html.parser").get_text(separator=" ", strip=True)[:2000]

        # Extract mileage from attributes
        km    = "N/A"
        attrs = ad.get("attributes", ad.get("adAttributes", {}))
        if isinstance(attrs, dict):
            km = attrs.get("kilometres", attrs.get("mileage", "N/A"))
        elif isinstance(attrs, list):
            for a in attrs:
                if isinstance(a, dict) and a.get("machineKey", a.get("name", "")).lower() in ("kilometres", "mileage"):
                    km = a.get("localeSpecificValues", {}).get("en", {}).get("value", a.get("value", "N/A"))
                    break

        if not desc:
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


def _kijiji_alternate(make: str, model: str, year_min: int, year_max: int,
                       price_max: int, loc_id: int, max_results: int) -> List[dict]:
    query  = f"{make}+{model}".replace(" ", "+")
    params = {
        "price1":    f"0__{price_max}",
        "minYear":   year_min,
        "maxYear":   year_max,
        "address":   "Ontario",
        "ll":        "43.6532,-79.3832",
        "radius":    "500.0",
    }

    url = f"https://www.kijiji.ca/b-cars-trucks/{query}/k0c174l{loc_id}?{urlencode(params)}"
    print(f"  Trying: {url[:90]}...")

    html = _fetch(url)
    if not html:
        print(f"  ❌ No response from Kijiji")
        return []

    # Try __NEXT_DATA__
    soup = BeautifulSoup(html, "html.parser")
    tag  = soup.find("script", {"id": "__NEXT_DATA__"})
    if tag and tag.string:
        try:
            data       = json.loads(tag.string)
            page_props = data.get("props", {}).get("pageProps", {})
            ads        = _find_kijiji_ads(page_props)
            if ads:
                print(f"  ✅ {len(ads)} listings from Kijiji __NEXT_DATA__")
                return [r for r in (_parse_kijiji_api_item(a) for a in ads[:max_results]) if r]
        except json.JSONDecodeError:
            pass

    # Last resort: look for JSON-LD structured data
    json_ld_tags = soup.find_all("script", {"type": "application/ld+json"})
    for tag in json_ld_tags:
        try:
            ld = json.loads(tag.string)
            if isinstance(ld, dict) and ld.get("@type") in ("ItemList", "Product"):
                items = ld.get("itemListElement", ld.get("offers", []))
                if items:
                    print(f"  ✅ {len(items)} listings from JSON-LD")
                    listings = []
                    for it in items[:max_results]:
                        item = it.get("item", it)
                        title = item.get("name", "")
                        price = item.get("offers", {}).get("price", "N/A")
                        url   = item.get("url", "N/A")
                        if title:
                            listings.append({
                                "source": "Kijiji", "title": title,
                                "price": str(price), "mileage": "N/A",
                                "url": url, "description": item.get("description", ""),
                            })
                    if listings:
                        return listings
        except Exception:
            continue

    print("  ❌ All Kijiji methods failed — site is blocking requests")
    print("     Tip: Kijiji has aggressive bot protection. AutoTrader results are sufficient.")
    return []


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


# ─────────────────────────────────────────────────────────────────
# Shared
# ─────────────────────────────────────────────────────────────────

def deduplicate(listings: List[dict]) -> List[dict]:
    seen, unique = set(), []
    for listing in listings:
        key = (listing["title"][:40].lower().strip(), listing["price"])
        if key not in seen:
            seen.add(key)
            unique.append(listing)
    return unique