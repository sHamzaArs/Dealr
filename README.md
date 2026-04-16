# Car Deal Finder

An AI-powered CLI tool that scrapes used car listings from AutoTrader CA and Kijiji, then scores and ranks them based on price, mileage, and listing quality.

## How it works

1. Scrapes listings from AutoTrader CA and/or Kijiji using Apify
2. Deduplicates cross-platform listings
3. Scores each listing with Claude AI across three dimensions:
   - **Price** (40%) — vs. market average for that make/model/year
   - **Mileage** (35%) — age-adjusted km rating
   - **Listing quality** (25%) — maintenance history, red flag language, missing info
4. Ranks and displays results with plain-English verdicts

## Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo>
cd car_scorer
pip install -r requirements.txt
```

### 2. Get API keys

- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com)
- **Apify API token** — [apify.com](https://apify.com) (free tier gives $5/month credit)

### 3. Set environment variables

```bash
cp .env.example .env
# Edit .env with your keys
```

Then either `source .env` or use a tool like `python-dotenv`.

Or export directly:

```bash
export ANTHROPIC_API_KEY=your_key_here
export APIFY_API_TOKEN=your_token_here
```

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

────────────────────────────────────────────────────
#1 of 5  ★ STRONG BUY
2012 BMW 330i xDrive  —  $13,500
URL: https://www.autotrader.ca/...

  Overall score : 84/100
  Price         : 88/100
  Mileage       : 79/100
  Listing quality: 82/100

  Green flags:
    + Full service history mentioned
    + Recent brake job and oil change
    + Single owner, garage kept
    + CARFAX available on request

  Red flags:
    - High mileage for age (148,000 km)

  Missing info:
    ? Timing chain condition not mentioned (known issue on N52 engine)

  Verdict: Well-maintained example at a competitive price. Single owner with
  documented service history is rare for this model year. High mileage is the
  only concern — worth getting a pre-purchase inspection focused on the cooling
  system and timing chain.
```

## Cost estimate

Per search (15 listings × 2 sources = ~30 listings scored):
- **Apify**: ~$0.15–0.30 in compute credits
- **Anthropic API**: ~$0.03–0.05

Total: roughly **$0.20–0.35 per search** using your own keys.

## Project structure

```
car_scorer/
├── main.py          # CLI entry point
├── scraper.py       # Apify scraper integrations
├── scorer.py        # Claude AI scoring engine
├── requirements.txt
└── .env.example
```
