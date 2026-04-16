#!/usr/bin/env python3
"""
main.py — Car Deal Finder CLI
Usage: python main.py --make BMW --model "330i" --year-min 2010 --year-max 2014 \
                      --price-max 18000 --location "Ontario" --results 15
"""
 
import argparse
import sys
from scraper import scrape_autotrader, scrape_kijiji, deduplicate
from scorer import score_all

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
 
 
ACTION_COLOURS = {
    "strong buy":           GREEN,
    "worth investigating":  CYAN,
    "proceed with caution": YELLOW,
    "avoid":                RED,
}
 
ACTION_ICONS = {
    "strong buy":           "★",
    "worth investigating":  "◆",
    "proceed with caution": "▲",
    "avoid":                "✗",
}

def print_result(rank: int, listing, total: int):
    colour = ACTION_COLOURS.get(listing.recommended_action.lower(), RESET)
    icon   = ACTION_ICONS.get(listing.recommended_action.lower(), "•")
 
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}#{rank} of {total}  {colour}{icon} {listing.recommended_action.upper()}{RESET}")
    print(f"{BOLD}{listing.title}{RESET}  —  {listing.price}")
    print(f"URL: {listing.url}")
    print()
    print(f"  Overall score : {colour}{listing.overall_score}/100{RESET}")
    print(f"  Price         : {listing.price_score}/100")
    print(f"  Mileage       : {listing.mileage_score}/100")
    print(f"  Listing quality: {listing.listing_quality_score}/100")
 
    if listing.green_flags:
        print(f"\n  {GREEN}Green flags:{RESET}")
        for flag in listing.green_flags:
            print(f"    + {flag}")
 
    if listing.red_flags:
        print(f"\n  {RED}Red flags:{RESET}")
        for flag in listing.red_flags:
            print(f"    - {flag}")
 
    if listing.missing_info:
        print(f"\n  {YELLOW}Missing info:{RESET}")
        for item in listing.missing_info:
            print(f"    ? {item}")
 
    print(f"\n  {BOLD}Verdict:{RESET} {listing.summary}")
 
 
def main():
    parser = argparse.ArgumentParser(
        description="Find and score used car listings from AutoTrader CA and Kijiji."
    )
    parser.add_argument("--make",      required=True, help="e.g. BMW")
    parser.add_argument("--model",     required=True, help="e.g. 330i")
    parser.add_argument("--year-min",  type=int, required=True, help="e.g. 2010")
    parser.add_argument("--year-max",  type=int, required=True, help="e.g. 2014")
    parser.add_argument("--price-max", type=int, required=True, help="e.g. 18000")
    parser.add_argument("--location",  default="Ontario", help="Province or city (default: Ontario)")
    parser.add_argument("--results",   type=int, default=15, help="Max listings to fetch per source (default: 15)")
    parser.add_argument("--top",       type=int, default=5,  help="How many top results to show (default: 5)")
    parser.add_argument("--sources",   nargs="+", default=["autotrader", "kijiji"],
                        choices=["autotrader", "kijiji"],
                        help="Which sources to scrape (default: both)")
    args = parser.parse_args()
 
    print(f"\n{BOLD}Car Deal Finder{RESET}")
    print(f"Searching: {args.year_min}–{args.year_max} {args.make} {args.model}")
    print(f"Max price: ${args.price_max:,}  |  Location: {args.location}")
    print(f"Sources: {', '.join(args.sources)}")
    print()
 
    # --- Scrape ---
    all_listings = []
 
    if "autotrader" in args.sources:
        print(f"Scraping AutoTrader CA...")
        try:
            at = scrape_autotrader(
                make=args.make, model=args.model,
                year_min=args.year_min, year_max=args.year_max,
                price_max=args.price_max, location=args.location,
                max_results=args.results
            )
            print(f"  Found {len(at)} listings on AutoTrader CA")
            all_listings.extend(at)
        except Exception as e:
            print(f"  {RED}AutoTrader scrape failed: {e}{RESET}")
 
    if "kijiji" in args.sources:
        print(f"Scraping Kijiji...")
        try:
            kj = scrape_kijiji(
                make=args.make, model=args.model,
                year_min=args.year_min, year_max=args.year_max,
                price_max=args.price_max, location=args.location,
                max_results=args.results
            )
            print(f"  Found {len(kj)} listings on Kijiji")
            all_listings.extend(kj)
        except Exception as e:
            print(f"  {RED}Kijiji scrape failed: {e}{RESET}")
 
    if not all_listings:
        print(f"\n{RED}No listings found. Check your search parameters or API keys.{RESET}")
        sys.exit(1)
 
    all_listings = deduplicate(all_listings)
    print(f"\nTotal unique listings: {len(all_listings)}")
 
    # --- Score ---
    print(f"\nScoring listings with AI (this takes ~{len(all_listings) * 3}s)...")
    scored = score_all(all_listings)
 
    # --- Display ---
    top_n = scored[:args.top]
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}Top {len(top_n)} deals for {args.year_min}–{args.year_max} {args.make} {args.model}{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")
 
    for i, listing in enumerate(top_n, 1):
        print_result(i, listing, len(top_n))
 
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"Scored {len(scored)} listings total. Showing top {len(top_n)}.")
    print(f"Run with --top {len(scored)} to see all results.\n")
 
 
if __name__ == "__main__":
    main()