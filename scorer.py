import os
import json
import anthropic
from dataclasses import dataclass

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC API KEY"))

SCORING_PROMPT = """
You are an expert used car analyst helping a buyer in Canada find the best deal.
Analyze the listing below and return a JSON object with the following structure.
Return ONLY valid JSON, no explanation, no markdown.
 
{
  "price_score": <0-100>,
  "mileage_score": <0-100>,
  "listing_quality_score": <0-100>,
  "overall_score": <0-100>,
  "green_flags": [<list of positive signals found, be specific>],
  "red_flags": [<list of warning signs found, be specific>],
  "missing_info": [<important info a buyer would want that is absent from listing>],
  "summary": "<2-3 sentence plain-English verdict a buyer can act on>",
  "recommended_action": "<one of: strong buy | worth investigating | proceed with caution | avoid>"
}
 
Scoring guidance:
 
price_score (40% of overall):
- Compare asking price to typical market value for this make/model/year in Canada
- 90-100: Significantly underpriced (great deal)
- 70-89: Slightly below or at market (fair)
- 50-69: Slightly above market (negotiation needed)
- 0-49: Overpriced for condition described
 
mileage_score (35% of overall):
- Average Canadian driver does ~20,000 km/year
- Score relative to age of vehicle (year vs current year 2025)
- 90-100: Well below average km for age
- 70-89: Around average km for age
- 50-69: Higher than average but acceptable
- 0-49: High mileage for age, increases risk
 
listing_quality_score (25% of overall):
- Green flags: maintenance records, service history, recent work, single owner,
  CARFAX available, detailed description, motivated but not desperate seller
- Red flags: "as-is", "selling quickly", "engine light", rust mentioned,
  transmission issues, vague description, no photos mentioned, salvage title
- Absent info penalty: no mention of accidents, ownership history, or maintenance
  on a high-km or older vehicle is itself a red flag
- Seller tone: confident and detailed = good, evasive or pressuring = bad
 
overall_score: weighted average (price 40%, mileage 35%, quality 25%)
 
LISTING TO ANALYZE:
{listing}
"""

@dataclass
class ScoredListings:
  title: str
  price: str
  url: str
  price_score: int
  mileage_score: int
  listing_quality_score: int
  overall_score: int
  green_flags: list[str]
  red_flags: list[str]
  missing_info: list[str]
  summary: str
  recommended_action: str

def score_listing(title: str, price: str, url: str, description: str) -> ScoredListings:
  """Score a single listing using Claude."""

  listing_text = """f
  Title: {title}
  Price: {price}
  URL: {url}
  Description: {description}
  """ 

  message = client.messages.create(
    model = "claude-opus-4-5",
    max_toxens = 1024,
    messages = [
      {
        "role": "user",
        "content": SCORING_PROMPT.replace("{listing}", listing_text)
      }
    ]
  )

  raw = message.content[0].text.strip()

  if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
      raw = raw[4:]

  data = json.loads(raw)
  