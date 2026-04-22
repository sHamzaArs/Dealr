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


def _get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-CA,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
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
            print(f"  HTTP {resp.status_code} on {url[:60]}")
            return None
    except requests.RequestException as e:
        print(f"  Request failed: {e}")
        return None

def scrape_autotrader(make: str, model: str, year_min: int, year_max: int,
                       price_max: int, location: str, max_results: int = 20) -> List[dict]:
    params = {
        "make":     make,
        "model":    model,
        "yearMin":  year_min,
        "yearMax":  year_max,
        "priceMax": price_max,
        "loc":      location,
        "hprc":     "True",
        "wcp":      "True",
        "sts":      "Used",
        "rcp":      min(max_results, 20),
        "rcs":      0,
        "srt":      35,
    }

    url = f"https://www.autotrader.ca/cars/?{urlencode(params)}"
    print(f"  Fetching: {url[:80]}...")

    html = _fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    # AutoTrader embeds all listing data in a <script id="__NEXT_DATA__"> tag
    next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if not next_data_tag:
        print("  Could not find __NEXT_DATA__ JSON blob in page")
        return []

    try:
        data = json.loads(next_data_tag.string)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"  Failed to parse __NEXT_DATA__ JSON: {e}")
        return []

    # Navigate the JSON structure to get listings
    try:
        raw_listings = (
            data["props"]["pageProps"]["listings"]
        )
    except (KeyError, TypeError):
        print("  Could not find listings in JSON structure")
        return []

    print(f"  Found {len(raw_listings)} listings in JSON")

    listings = []
    for item in raw_listings[:max_results]:
        listing = _parse_autotrader_json_listing(item)
        if listing:
            listings.append(listing)

    # Fetch detail pages for full descriptions
    if listings:
        print(f"  Fetching descriptions for {len(listings)} listings...")
        for i, listing in enumerate(listings):
            if listing.get("url") and listing["url"] != "N/A":
                _polite_delay()
                desc = _fetch_autotrader_description(listing["url"])
                if desc:
                    listing["description"] = desc
            if i > 0 and i % 5 == 0:
                print(f"    {i}/{len(listings)} done...")

    return listings


def _parse_autotrader_json_listing(item: dict) -> Optional[dict]:
    try:
        vehicle  = item.get("vehicle", {})
        price    = item.get("price", {})
        location = item.get("location", {})
        seller   = item.get("seller", {})

        year  = vehicle.get("modelYear", "")
        make  = vehicle.get("make", "")
        model = vehicle.get("model", "")
        trim  = vehicle.get("modelVersionInput", "") or ""
        km    = vehicle.get("mileageInKm", "N/A")
        fuel  = vehicle.get("fuel", "")

        title = f"{year} {make} {model}".strip()
        if trim:
            title += f" {trim}"

        price_str = price.get("priceFormatted", "N/A")
        url = item.get("url", "N/A")
        city = location.get("city", "")
        province = location.get("provinceCode", "")
        seller_name = seller.get("companyName", "")

        # Use description from JSON if available, otherwise build from fields
        description = item.get("description", "")
        if description:
            # Strip HTML tags from description
            desc_soup = BeautifulSoup(description, "html.parser")
            description = desc_soup.get_text(separator=" ", strip=True)[:2000]
        else:
            parts = []
            if km:
                parts.append(f"Mileage: {km}")
            if fuel:
                parts.append(f"Fuel: {fuel}")
            if city:
                parts.append(f"Location: {city}, {province}")
            if seller_name:
                parts.append(f"Seller: {seller_name}")
            description = ". ".join(parts)

        return {
            "source":      "AutoTrader CA",
            "title":       title,
            "price":       price_str,
            "mileage":     str(km),
            "url":         url,
            "description": description,
        }
    except Exception as e:
        return None


def _fetch_autotrader_description(url: str) -> Optional[str]:
    html = _fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})

    if next_data_tag:
        try:
            data = json.loads(next_data_tag.string)
            # Try to find description in detail page JSON
            props = data.get("props", {}).get("pageProps", {})
            listing = props.get("listing", props.get("vehicle", {}))
            desc = listing.get("description", "")
            if desc:
                desc_soup = BeautifulSoup(desc, "html.parser")
                return desc_soup.get_text(separator=" ", strip=True)[:2000]
        except Exception:
            pass

    # Fallback: parse HTML description elements
    for selector in ["div.vdp-description", "[class*='description']", "[class*='Details']"]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(separator=" ", strip=True)[:2000]

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

    print(f"  Fetching: {url[:80]}...")

    html = _fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    # Try __NEXT_DATA__ first (Kijiji is also Next.js)
    next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    listings = []

    if next_data_tag:
        try:
            data = json.loads(next_data_tag.string)
            raw_listings = _extract_kijiji_listings_from_json(data)
            if raw_listings:
                print(f"  Found {len(raw_listings)} listings in JSON")
                for item in raw_listings[:max_results]:
                    listing = _parse_kijiji_json_listing(item)
                    if listing:
                        listings.append(listing)
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: try HTML card parsing if JSON extraction failed
    if not listings:
        print("  JSON extraction failed, trying HTML cards...")
        listings = _scrape_kijiji_html(soup, max_results)

    # Fetch detail pages for full descriptions
    if listings:
        print(f"  Fetching descriptions for {len(listings)} Kijiji listings...")
        for i, listing in enumerate(listings):
            if listing.get("url") and listing["url"] != "N/A":
                _polite_delay()
                desc = _fetch_kijiji_description(listing["url"])
                if desc:
                    listing["description"] = desc
            if i > 0 and i % 5 == 0:
                print(f"    {i}/{len(listings)} done...")

    return listings


def _extract_kijiji_listings_from_json(data: dict) -> List[dict]:
    try:
        # Kijiji structure varies — try common paths
        page_props = data.get("props", {}).get("pageProps", {})

        # Try path 1: listings directly
        items = page_props.get("listings", page_props.get("ads", []))
        if items:
            return items

        # Try path 2: nested under initialProps or similar
        for key in ["initialProps", "initialData", "searchData", "srp"]:
            section = page_props.get(key, {})
            if isinstance(section, dict):
                items = section.get("listings", section.get("ads", []))
                if items:
                    return items

        return []
    except Exception:
        return []


def _parse_kijiji_json_listing(item: dict) -> Optional[dict]:
    try:
        title     = item.get("title", item.get("headline", "Unknown"))
        price     = item.get("price", {})
        url_path  = item.get("seoUrl", item.get("url", ""))
        desc      = item.get("description", "")
        attrs     = item.get("attributes", {})

        price_str = price.get("amount", "N/A") if isinstance(price, dict) else str(price)
        if isinstance(price_str, (int, float)):
            price_str = f"${price_str:,.0f}"

        url = f"https://www.kijiji.ca{url_path}" if url_path.startswith("/") else url_path or "N/A"

        km = "N/A"
        if isinstance(attrs, dict):
            km = attrs.get("kilometres", attrs.get("mileage", "N/A"))
        elif isinstance(attrs, list):
            for attr in attrs:
                if isinstance(attr, dict) and attr.get("name", "").lower() in ("kilometres", "mileage"):
                    km = attr.get("value", "N/A")
                    break

        if desc:
            desc_soup = BeautifulSoup(desc, "html.parser")
            desc = desc_soup.get_text(separator=" ", strip=True)[:2000]
        else:
            desc = f"Mileage: {km}"

        if not title or len(title) < 3:
            return None

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
             soup.select("article[class*='listing']"))

    print(f"  Found {len(cards)} HTML cards")
    listings = []

    for card in cards[:max_results]:
        try:
            title_el = card.select_one("[class*='title']") or card.select_one("h3")
            price_el = card.select_one("[class*='price']")
            link_el  = card.select_one("a[href*='/v-']") or card.select_one("a")
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


def _fetch_kijiji_description(url: str) -> Optional[str]:
    html = _fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Try __NEXT_DATA__ first
    next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if next_data_tag:
        try:
            data = json.loads(next_data_tag.string)
            props = data.get("props", {}).get("pageProps", {})
            for key in ["ad", "listing", "vip"]:
                item = props.get(key, {})
                if isinstance(item, dict):
                    desc = item.get("description", "")
                    if desc:
                        return BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)[:2000]
        except Exception:
            pass

    # Fallback HTML
    for selector in ["[class*='description']", "[itemprop='description']", "[data-testid='vip-description']"]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(separator=" ", strip=True)[:2000]

    return None

def deduplicate(listings: List[dict]) -> List[dict]:
    seen   = set()
    unique = []
    for listing in listings:
        key = (listing["title"][:40].lower().strip(), listing["price"])
        if key not in seen:
            seen.add(key)
            unique.append(listing)
    return unique