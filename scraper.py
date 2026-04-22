import time
import random
from typing import Optional, List
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout


def _polite_delay():
    time.sleep(random.uniform(2, 4))


def _get_soup(page: Page, url: str, wait_selector: str = None) -> Optional[BeautifulSoup]:
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")

        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=10000)
            except PlaywrightTimeout:
                pass  # Parse whatever loaded

        # Extra wait for JS to render
        page.wait_for_timeout(2000)
        return BeautifulSoup(page.content(), "html.parser")

    except Exception as e:
        print(f"  Failed to load {url[:60]}: {e}")
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
        "rcp":      min(max_results, 15),
        "rcs":      0,
        "srt":      35,
    }

    search_url = f"https://www.autotrader.ca/cars/?{urlencode(params)}"
    print(f"  Fetching: {search_url[:80]}...")

    listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-CA",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # Block images/fonts to speed up loading
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

        soup = _get_soup(page, search_url, wait_selector="[class*='result-item'], [data-listing-id]")

        if not soup:
            browser.close()
            return []

        # Try standard card selectors
        cards = (soup.select("div[data-listing-id]") or
                 soup.select("div[class*='result-item']") or
                 soup.select("div[class*='listing-card']"))

        if cards:
            print(f"  Found {len(cards)} listing cards")
            for card in cards[:max_results]:
                listing = _parse_autotrader_card(card)
                if listing:
                    listings.append(listing)
        else:
            # Fallback: scrape listing URLs from links and visit each one
            print("  No cards found via selectors — trying link extraction...")
            links = soup.select("a[href*='/a/used/']") or soup.select("a[href*='autotrader.ca/a/']")
            urls  = list(dict.fromkeys(  # deduplicate while preserving order
                "https://www.autotrader.ca" + a["href"] if a["href"].startswith("/") else a["href"]
                for a in links if a.get("href")
            ))[:max_results]
            print(f"  Found {len(urls)} listing links")

            for url in urls:
                _polite_delay()
                detail_soup = _get_soup(page, url)
                if detail_soup:
                    listing = _parse_autotrader_detail_page(detail_soup, url)
                    if listing:
                        listings.append(listing)

        # Fetch detail pages for full descriptions if we got cards
        if listings and cards:
            print(f"  Fetching details for {len(listings)} listings...")
            for i, listing in enumerate(listings):
                if listing.get("url") and listing["url"] != "N/A":
                    _polite_delay()
                    detail_soup = _get_soup(page, listing["url"])
                    if detail_soup:
                        desc = _extract_autotrader_description(detail_soup)
                        if desc:
                            listing["description"] = desc
                if i % 5 == 0 and i > 0:
                    print(f"    {i}/{len(listings)} details fetched...")

        browser.close()

    return listings


def _parse_autotrader_card(card) -> Optional[dict]:
    try:
        title_el = (card.select_one("span.title-with-trim") or
                    card.select_one("[class*='title']"))
        price_el = (card.select_one("span.price-amount") or
                    card.select_one("[class*='price']"))
        link_el  = card.select_one("a[href*='/a/']") or card.select_one("a")
        km_el    = (card.select_one("[class*='kms']") or
                    card.select_one("[class*='mileage']") or
                    card.select_one("[class*='odometer']"))

        title = title_el.get_text(strip=True) if title_el else None
        price = price_el.get_text(strip=True) if price_el else "N/A"
        href  = link_el.get("href", "") if link_el else ""
        url   = ("https://www.autotrader.ca" + href) if href.startswith("/") else href or "N/A"
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


def _parse_autotrader_detail_page(soup: BeautifulSoup, url: str) -> Optional[dict]:
    try:
        title_el = (soup.select_one("h1[class*='title']") or
                    soup.select_one("h1"))
        price_el = (soup.select_one("[class*='price-amount']") or
                    soup.select_one("[class*='listing-price']"))
        km_el    = (soup.select_one("[class*='kms']") or
                    soup.select_one("[class*='mileage']"))

        title = title_el.get_text(strip=True) if title_el else "Unknown listing"
        price = price_el.get_text(strip=True) if price_el else "N/A"
        km    = km_el.get_text(strip=True) if km_el else "N/A"
        desc  = _extract_autotrader_description(soup) or f"Mileage: {km}"

        return {
            "source":      "AutoTrader CA",
            "title":       title,
            "price":       price,
            "mileage":     km,
            "url":         url,
            "description": desc,
        }
    except Exception:
        return None


def _extract_autotrader_description(soup: BeautifulSoup) -> Optional[str]:
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
    query    = f"{make} {model}".strip().lower().replace(" ", "-")
    params   = {
        "price": f"__0__{price_max}",
        "year":  f"{year_min}__{year_max}",
    }

    search_url = (f"https://www.kijiji.ca/b-cars-trucks/{loc_code}/"
                  f"{query}/k0c174?{urlencode(params)}")

    print(f"  Fetching: {search_url[:80]}...")

    listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-CA",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

        soup = _get_soup(page, search_url, wait_selector="[data-listing-id], article")

        if not soup:
            browser.close()
            return []

        cards = (soup.select("li[data-listing-id]") or
                 soup.select("article[class*='listing']") or
                 soup.select("div[class*='regular-ad']") or
                 soup.select("[data-testid='listing-card']"))

        print(f"  Found {len(cards)} cards on Kijiji")

        for card in cards[:max_results]:
            listing = _parse_kijiji_card(card)
            if listing:
                listings.append(listing)

        # Fetch detail pages
        if listings:
            print(f"  Fetching details for {len(listings)} Kijiji listings...")
            for i, listing in enumerate(listings):
                if listing.get("url") and listing["url"] != "N/A":
                    _polite_delay()
                    detail_soup = _get_soup(page, listing["url"])
                    if detail_soup:
                        desc = _extract_kijiji_description(detail_soup)
                        if desc:
                            listing["description"] = desc
                if i % 5 == 0 and i > 0:
                    print(f"    {i}/{len(listings)} details fetched...")

        browser.close()

    return listings


def _parse_kijiji_card(card) -> Optional[dict]:
    try:
        title_el = (card.select_one("[class*='title']") or
                    card.select_one("h3") or
                    card.select_one("a"))
        price_el = card.select_one("[class*='price']")
        link_el  = card.select_one("a[href*='/v-']") or card.select_one("a")
        km_el    = (card.select_one("[class*='mileage']") or
                    card.select_one("[class*='km']"))

        title = title_el.get_text(strip=True) if title_el else None
        price = price_el.get_text(strip=True) if price_el else "N/A"
        href  = link_el.get("href", "") if link_el else ""
        url   = f"https://www.kijiji.ca{href}" if href.startswith("/") else href or "N/A"
        km    = km_el.get_text(strip=True) if km_el else "N/A"

        if not title or len(title) < 3:
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


def _extract_kijiji_description(soup: BeautifulSoup) -> Optional[str]:
    desc_el = (soup.select_one("[class*='description']") or
               soup.select_one("[itemprop='description']") or
               soup.select_one("[data-testid='vip-description']") or
               soup.select_one("div[class*='Details']"))

    if desc_el:
        return desc_el.get_text(separator=" ", strip=True)[:2000]

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