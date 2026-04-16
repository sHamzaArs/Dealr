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