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

