# Deal Finder Web Scraper
## A Python web scraper that searches Walmart for products, ranks them by value using a deal score, and saves the best results to JSON.

# Features

Searches Walmart across multiple pages for any query
Scores products based on price, rating, and review count
Filters by max price, min rating, and availability
Saves all scraped products to products.json
Saves only the top deals to best_deals.json
Supports residential proxies (Bright Data) to avoid blocks
Retries failed requests with exponential backoff


# Requirements
Install dependencies with:
bashpip install requests beautifulsoup4 python-dotenv

Setup
1. Clone or download the script
Place walmart_deal_finder.py in a folder of your choice.
2. (Optional but recommended) Configure a proxy
Without a proxy, Walmart will likely block your requests after a few pages. This script supports Bright Data residential proxies.
Create a .env file in the same folder as the script:
BRD_USERNAME=your_bright_data_username
BRD_PASSWORD=your_bright_data_password
If no .env is found, the script will still run but may get blocked.

# Configuration
At the top of main() in the script, you can adjust these settings:
VariableDefaultDescriptionQUERY"xbox controller"What to search for on WalmartMAX_PRICE80Maximum price — set to None to disableMIN_RATING4.0Minimum average star rating — set to None to disableTOP_N10How many top deals to print and saveREQUEST_DELAY1.5Base seconds to wait between requests

# Usage
bashpython walmart_deal_finder.py
The script will print progress as it scrapes each page:
Proxy configured (Bright Data)
Searching Walmart for: 'xbox controller'

Fetching search page 1...
Page 1 done. Products collected so far: 18
Fetching search page 2...
Page 2 done. Products collected so far: 35
...
Saved all 35 products to products.json

Top 10 Deals for 'xbox controller':

1. PowerA Enhanced Wired Controller for Xbox
   $24.99 | 4.5 (320 reviews)
   IN_STOCK | Deal Score: 3.6029
   https://www.walmart.com/ip/...
...
Saved top 10 deals to best_deals.json

#Output Files
products.json
Contains every product scraped, with no filtering applied. Useful for doing your own analysis. Each product looks like:
json{
  "price": 24.99,
  "review_count": 320,
  "item_id": "228560043",
  "avg_rating": 4.5,
  "product_name": "PowerA Enhanced Wired Controller for Xbox",
  "brand": "PowerA",
  "availability": "IN_STOCK",
  "image_url": "https://i5.walmartimages.com/...",
  "short_description": "...",
  "url": "https://www.walmart.com/ip/..."
}
best_deals.json
Contains only the top TOP_N products after filtering and ranking. Same format as above.

How the Deal Score Works
Each product is scored using:
deal_score = (adjusted_rating × 20) / price
Where adjusted_rating = avg_rating × review_confidence and review_confidence scales from 0 to 1 based on review count (capped at 50 reviews). This prevents a product with 1 five-star review from outranking one with 500 four-star reviews.
A higher score means a better deal — lower price and higher trusted rating.

# Notes

Walmart caps search results at 99 pages, so the scraper stops there automatically
Products missing a price or name are automatically skipped
Duplicate URLs are deduplicated across pages
HTTP 412, 429, and 503 responses (bot blocks) trigger automatic retries with backoff
