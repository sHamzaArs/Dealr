from playwright.sync_api import sync_playwright

def dump_page(url: str, filename: str, wait_seconds: int = 4):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-CA",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(wait_seconds * 1000)

        html = page.content()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"Saved {len(html)} chars to {filename}")
        browser.close()

if __name__ == "__main__":
    print("Dumping AutoTrader CA...")
    dump_page(
        "https://www.autotrader.ca/cars/?make=BMW&model=330i&yearMin=2010&yearMax=2014&priceMax=18000&loc=Ontario&sts=Used&rcp=15&rcs=0&srt=35",
        "autotrader_debug.html"
    )

    print("Dumping Kijiji...")
    dump_page(
        "https://www.kijiji.ca/b-cars-trucks/l1700272/bmw-330i/k0c174?price=__0__18000&year=2010__2014",
        "kijiji_debug.html"
    )

    print("\nDone. Open autotrader_debug.html and kijiji_debug.html in your browser")
    print("and use Ctrl+F to search for a listing title to find the right HTML structure.")