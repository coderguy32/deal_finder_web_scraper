from bs4 import BeautifulSoup
import requests
import json
import time
import random
import os
from dotenv import load_dotenv

load_dotenv()


HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
}

BASE_URL = "https://www.walmart.com"

# --- Bright Data Proxy Setup ---
# Add these to a .env file in the same directory:
#   BRD_USERNAME=your_username
#   BRD_PASSWORD=your_password
_brd_username = os.environ.get("BRD_USERNAME")
_brd_password = os.environ.get("BRD_PASSWORD")

PROXIES = None
if _brd_username and _brd_password:
    proxy_url = f"http://{_brd_username}:{_brd_password}@brd.superproxy.io:22225"
    PROXIES = {"http": proxy_url, "https": proxy_url}
    print("Proxy configured (Bright Data)")
else:
    print("No proxy configured. Add BRD_USERNAME and BRD_PASSWORD to a .env file to avoid blocks.")


def make_request(url, max_retries=4, base_delay=2):
    """Request with exponential backoff + jitter. Uses proxy if configured."""
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                proxies=PROXIES,
                timeout=15
            )
            response.raise_for_status()
            return response

        except requests.ConnectionError as e:
            wait = (base_delay ** attempt) + random.uniform(1, 3)
            print(f"  Connection error (attempt {attempt + 1}/{max_retries}), retrying in {wait:.1f}s...")
            time.sleep(wait)

        except requests.HTTPError as e:
            status = e.response.status_code
            if status in (412, 429, 503):
                wait = (base_delay ** attempt) + random.uniform(1, 3)
                print(f"  Blocked ({status}), retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                print(f"  HTTP {status} for {url}, skipping.")
                return None

        except requests.RequestException as e:
            print(f"  Request failed: {e}")
            return None

    print(f"Giving up after {max_retries} attempts: {url}")
    return None


def get_product_links(query, page_number=1, seen_urls=None):
    if seen_urls is None:
        seen_urls = set()

    search_url = f"{BASE_URL}/search?q={query}&page={page_number}"

    response = make_request(search_url)
    if response is None:
        print(f"Failed to fetch search page {page_number} for '{query}'")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.find_all("a", href=True)

    product_links = []
    for link in links:
        href = link["href"]
        if "/ip/" in href:
            full_url = href if href.startswith("https") else BASE_URL + href
            # Strip query params to normalize the URL
            full_url = full_url.split("?")[0]
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                product_links.append(full_url)

    return product_links


def extract_product_info(url):
    response = make_request(url)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    script_tag = soup.find("script", id="__NEXT_DATA__")

    # Guard against blocked or invalid pages
    if script_tag is None:
        print(f"No __NEXT_DATA__ found for: {url} (likely blocked)")
        return None

    try:
        data = json.loads(script_tag.string)
        initial_data = data["props"]["pageProps"]["initialData"]["data"]
        product_data = initial_data["product"]
        reviews_data = initial_data.get("reviews", {})

        product_info = {
            "price": product_data.get("priceInfo", {}).get("currentPrice", {}).get("price"),
            "review_count": reviews_data.get("totalReviewCount", 0),
            "item_id": product_data.get("usItemId"),
            "avg_rating": reviews_data.get("averageOverallRating", 0),
            "product_name": product_data.get("name"),
            "brand": product_data.get("brand", ""),
            "availability": product_data.get("availabilityStatus"),
            "image_url": product_data.get("imageInfo", {}).get("thumbnailUrl", ""),
            "short_description": product_data.get("shortDescription", ""),
            "url": url,
        }

        # Skip products missing critical fields
        if product_info["price"] is None or product_info["product_name"] is None:
            return None

        return product_info

    except (KeyError, json.JSONDecodeError) as e:
        print(f"Failed to parse product data for: {url} — {e}")
        return None


def calculate_deal_score(product):
    """Score products — higher is better deal."""
    price = product.get("price") or 0
    rating = product.get("avg_rating", 0)
    review_count = product.get("review_count", 0)

    if price <= 0:
        return 0

    # Reduce confidence for products with few reviews
    review_confidence = min(review_count / 50, 1.0)
    adjusted_rating = rating * review_confidence

    return (adjusted_rating * 20) / price


def main():
    QUERY = "xbox controller"   # Change this to search for anything
    MAX_PRICE = 80              # Maximum price filter (set to None to disable)
    MIN_RATING = 4.0            # Minimum average rating (set to None to disable)
    TOP_N = 10                  # Number of top deals to display and save
    REQUEST_DELAY = 1.5         # Seconds to wait between product requests
    OUTPUT_FILE = "best_deals.json"

    all_products = []
    seen_urls = set()
    page_number = 1

    print(f"Searching Walmart for: '{QUERY}'\n")

    while True:
        print(f"Fetching search page {page_number}...")
        links = get_product_links(QUERY, page_number, seen_urls)

        if not links or page_number > 99:
            print("No more pages found. Moving to ranking...\n")
            break

        for link in links:
            product_info = extract_product_info(link)
            if product_info:
                all_products.append(product_info)
            time.sleep(REQUEST_DELAY + random.uniform(0.5, 2.0))

        print(f"Page {page_number} done. Products collected so far: {len(all_products)}")
        page_number += 1

    # Save ALL products to products.json
    with open("products.json", "w") as f:
        json.dump(all_products, f, indent=2)
    print(f"\nSaved all {len(all_products)} products to products.json")

    # Apply filters
    filtered = []
    for p in all_products:
        if MAX_PRICE is not None and (p.get("price") or 0) > MAX_PRICE:
            continue
        if MIN_RATING is not None and (p.get("avg_rating") or 0) < MIN_RATING:
            continue
        if p.get("availability") not in ("IN_STOCK", "ONLINE_ONLY"):
            continue
        filtered.append(p)

    if not filtered:
        print("No products matched your filters. Try relaxing MAX_PRICE or MIN_RATING.")
        return

    # Sort by deal score
    ranked = sorted(filtered, key=calculate_deal_score, reverse=True)

    # Display top deals
    print(f"\nTop {TOP_N} Deals for '{QUERY}':\n")
    for i, product in enumerate(ranked[:TOP_N], 1):
        score = calculate_deal_score(product)
        print(f"{i}. {product['product_name']}")
        print(f"${product['price']} | {product['avg_rating']} ({product['review_count']} reviews)")
        print(f"{product['availability']} | Deal Score: {score:.4f}")
        print(f"{product['url']}\n")

    # Save top deals to best_deals.json
    with open(OUTPUT_FILE, "w") as f:
        json.dump(ranked[:TOP_N], f, indent=2)
    print(f"Saved top {TOP_N} deals to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
