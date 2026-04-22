# Car Deal Finder

An AI-powered CLI tool that scrapes used car listings from AutoTrader CA and Kijiji, then scores and ranks them based on price, mileage, and listing quality.

## How it works

1. Scrapes listings directly from AutoTrader CA and/or Kijiji using `requests` and `BeautifulSoup`
2. Fetches individual listing pages to extract full descriptions
3. Deduplicates cross-platform listings
4. Scores each listing with Claude AI across three dimensions:
   - **Price** (40%) — vs. market average for that make/model/year in Canada
   - **Mileage** (35%) — age-adjusted km rating (~20,000 km/year is average in Canada)
   - **Listing quality** (25%) — maintenance history, red flag language, missing info, seller tone
5. Ranks and displays results with plain-English verdicts

## Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo>
cd car_scorer
pip install -r requirements.txt
```

### 2. Get your Anthropic API key

Sign up at [console.anthropic.com](https://console.anthropic.com) and create an API key. New accounts get free credits to start.

### 3. Set your API key

Paste this in your terminal before running the tool:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

To make it permanent so you don't have to re-paste every session:

```bash
echo 'export ANTHROPIC_API_KEY=your_key_here' >> ~/.zshrc
source ~/.zshrc
```

(Use `.bashrc` instead of `.zshrc` if you're on bash.)

## Usage

```bash
python main.py --make BMW --model "330i" --year-min 2010 --year-max 2014 --price-max 18000
```

### All options

| Flag | Description | Default |
|------|-------------|---------|
| `--make` | Car make (required) | — |
| `--model` | Car model (required) | — |
| `--year-min` | Minimum year (required) | — |
| `--year-max` | Maximum year (required) | — |
| `--price-max` | Maximum price in CAD (required) | — |
| `--location` | Province or city | Ontario |
| `--results` | Listings to fetch per source | 15 |
| `--top` | How many top results to display | 5 |
| `--sources` | Which sources: `autotrader` `kijiji` | both |

### Examples

```bash
# Search for a Honda Civic in Ontario
python main.py --make Honda --model Civic --year-min 2015 --year-max 2019 --price-max 15000

# AutoTrader only, show top 10
python main.py --make Toyota --model Camry --year-min 2012 --year-max 2016 \
               --price-max 14000 --sources autotrader --top 10

# Specific city
python main.py --make Mazda --model "CX-5" --year-min 2017 --year-max 2021 \
               --price-max 22000 --location "Toronto"
```

## Sample output

```
Car Deal Finder
Searching: 2010–2014 BMW 330i
Max price: $18,000  |  Location: Ontario
Sources: autotrader, kijiji

Scraping AutoTrader CA...
  Found 14 listings on AutoTrader CA — fetching details...
Scraping Kijiji...
  Found 11 listings on Kijiji

Total unique listings: 23
Scoring listings with AI (this takes ~69s)...

════════════════════════════════════════════════════════════
Top 5 deals for 2010–2014 BMW 330i
════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────
#1 of 5  ★ STRONG BUY
2012 BMW 330i xDrive  —  $13,500
URL: https://www.autotrader.ca/...

  Overall score :  84/100
  Price         :  88/100
  Mileage       :  79/100
  Listing quality: 82/100

  Green flags:
    + Full service history mentioned
    + Recent brake job and oil change
    + Single owner, garage kept
    + CARFAX available on request

  Red flags:
    - Higher than average mileage for age (148,000 km)

  Missing info:
    ? Timing chain condition not mentioned (known issue on N52 engine)

  Verdict: Well-maintained example at a competitive price. Single owner with
  documented service history is rare for this model year. High mileage is the
  only concern — worth getting a pre-purchase inspection focused on the cooling
  system and timing chain.
```

## Cost estimate

The only cost is the Anthropic API for scoring. Scraping is completely free.

Per search (~25 listings scored):
- **Anthropic API**: ~$0.03–0.05 total

Effectively free for personal use.

## Project structure

```
car_scorer/
├── main.py          # CLI entry point and result display
├── scraper.py       # Direct scrapers for AutoTrader CA and Kijiji
├── scorer.py        # Claude AI scoring engine
├── requirements.txt
└── .env.example
```

## Notes

- Scraping is done respectfully with 2–4 second delays between requests and rotating user agents
- Results may vary depending on how AutoTrader and Kijiji structure their pages — both sites update their HTML periodically
- Built for personal/educational use