import argparse
from curl_cffi import requests
from parsel import Selector
from datetime import datetime
import logging
import json
import re
import csv
import os
import time
from urllib.parse import urlparse
from tqdm import tqdm

# Set up argument parser
parser = argparse.ArgumentParser(description='Scrape APMEX product data')
parser.add_argument('-i', '--input', default='urls.txt', help='Input file with URLs (default: urls.txt)')
parser.add_argument('-o', '--output', default='apmex_products.csv', help='Output CSV file (default: apmex_products.csv)')
parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
parser.add_argument('-d', '--delay', type=float, default=2.0, help='Delay between requests in seconds (default: 2.0)')
args = parser.parse_args()

# Configure logging
log_level = logging.DEBUG if args.verbose else logging.INFO
log_filename = f"apmex_scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

# Initialize CSV fields
csv_fields = [
    "crawl_date", "dealer", "URL", "metal_type", "product_type", "Mint", 
    "category", "product_Name", "sku", "Weight (Troy Ounces)", 
    "Price_Lowest_Quantity_(Check/Wire)", "Dealer_Spot_Value", "Year", 
    "Product ID", "Grade", "Stock_Status"
]

def validate_url(url):
    """Validate if the URL is from APMEX domain."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.endswith('apmex.com') and parsed.scheme in ['http', 'https']
    except:
        return False

def scrape_apmex_url(url):
    """Scrape data from a single APMEX URL."""
    logging.info(f"Processing URL: {url}")
    crawl_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # Request with browser impersonation
        logging.debug(f"Sending request to {url}")
        r = requests.get(url, impersonate="chrome")
        
        if r.status_code != 200:
            logging.error(f"Failed to fetch URL: {url}, Status code: {r.status_code}")
            return None
            
        response = Selector(r.text)
        logging.debug(f"Successfully fetched URL: {url}")
        
        # Extracting the JSON-LD data
        parsing_data = response.xpath('(//script[@type="application/ld+json"]/text())[2]').get()
        if not parsing_data:
            logging.error(f"No JSON-LD data found for URL: {url}")
            return None
        
        logging.debug(f"Found JSON-LD data for URL: {url}")
        json_data = json.loads(parsing_data)
        
        # Extract category and clean it
        category_raw = json_data.get("category", [])[0] if isinstance(json_data.get("category", []), list) else ""
        category = re.sub(r"^\d+\s*oz\s*", "", category_raw).strip()
        
        # Extract metal type
        metal_type = json_data.get("material", "")
        
        # Extract grade
        grade = response.xpath("//li[contains(text(), 'Grade:')]/span/text()").get(default="").strip()
        
        # Extract dealer spot value
        dealer_spot = response.xpath('//ul[@class="spotprice-embed"]/li[a/div[@class="metal"][text()="Gold"]]/a/div[@class="price"]/span[@class="current"]/text()').get()
        logging.debug(f"Dealer spot value: {dealer_spot}")
        
        # Extract lowest check/wire price
        lowest_price = next(
            (price["price"] for price in json_data.get("offers", {}).get("priceSpecification", []) 
            if "ByBankTransferInAdvance" in str(price.get("appliesToPaymentMethod", ""))), ""
        )
        
        # Build product data dictionary
        product_data = {
            "crawl_date": crawl_date,
            "dealer": 'APMEX',  # Changed from 'gold' to actual dealer name
            "URL": url,  # Use the input URL instead of from JSON
            "metal_type": metal_type,
            "product_type": json_data.get("additionalProperty", {}).get("value", ""),
            "Mint": json_data.get("manufacturer", {}).get("name", ""),
            "category": category,
            "product_Name": json_data.get("name", ""),
            "sku": json_data.get("sku", ""),
            "Weight (Troy Ounces)": json_data.get("weight", {}).get("value", ""),
            "Price_Lowest_Quantity_(Check/Wire)": lowest_price,
            "Dealer_Spot_Value": dealer_spot,
            "Year": json_data.get("productionDate", ""),
            "Product ID": json_data.get("productID", ""),
            "Grade": grade,  
            "Stock_Status": "In Stock" if "InStock" in json_data.get("offers", {}).get("availability", "") else "Out of Stock",
        }
        
        logging.info(f"Successfully extracted data for {json_data.get('name', 'Unknown Product')}")
        logging.debug(f"Product data: {product_data}")
        
        return product_data
        
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error for {url}: {str(e)}")
    except requests.RequestsError as e:
        logging.error(f"Request error for {url}: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error while processing {url}: {str(e)}", exc_info=True)
    
    return None

def main():
    """Main function to handle the scraping process."""
    logging.info(f"Starting APMEX scraper with input file: {args.input}, output file: {args.output}")
    
    # Check if input file exists
    if not os.path.exists(args.input):
        logging.error(f"Input file not found: {args.input}")
        return
    
    # Read URLs from input file
    try:
        with open(args.input, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        logging.info(f"Found {len(urls)} URLs in the input file")
        
        # Validate URLs
        valid_urls = [url for url in urls if validate_url(url)]
        
        if len(valid_urls) < len(urls):
            logging.warning(f"Filtered out {len(urls) - len(valid_urls)} invalid URLs")
        
        if not valid_urls:
            logging.error("No valid URLs found to process")
            return
            
        # Initialize results list
        results = []
        
        # Process each URL with progress bar
        for url in tqdm(valid_urls, desc="Scraping URLs"):
            product_data = scrape_apmex_url(url)
            if product_data:
                results.append(product_data)
            
            # Add delay between requests
            if args.delay > 0:
                time.sleep(args.delay)
        
        # Write results to CSV
        if results:
            logging.info(f"Writing {len(results)} products to {args.output}")
            try:
                with open(args.output, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=csv_fields)
                    writer.writeheader()
                    writer.writerows(results)
                logging.info(f"Successfully wrote data to {args.output}")
            except Exception as e:
                logging.error(f"Error writing CSV file: {str(e)}", exc_info=True)
        else:
            logging.warning("No data was collected, CSV file not created")
            
    except Exception as e:
        logging.error(f"Error in main process: {str(e)}", exc_info=True)

if __name__ == "__main__":
    # Record start time
    start_time = time.time()
    
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("Process interrupted by user")
    except Exception as e:
        logging.critical(f"Fatal error: {str(e)}", exc_info=True)
    finally:
        # Record end time and calculate duration
        end_time = time.time()
        duration = end_time - start_time
        logging.info(f"Script completed in {duration:.2f} seconds")
