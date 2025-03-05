import asyncio
import json
from camoufox.async_api import AsyncCamoufox

async def scrape_product(browser, url):
    """Scrape a single product page"""
    try:
        page = await browser.new_page()
        print(f"Navigating to {url}")
        await page.goto(url)
        await page.wait_for_load_state(state="domcontentloaded")
        await page.wait_for_load_state('networkidle')
        
        # Wait a bit for any dynamic content to load
        await asyncio.sleep(5)
        
        # Click on the product image area
        print(f"Clicking on product image")
        await page.mouse.click(210, 290)
        await asyncio.sleep(5)
        
        # Get product details
        product_title = await page.evaluate('() => document.querySelector("h1.product-title")?.innerText || "Unknown"')
        price = await page.evaluate('() => document.querySelector(".price-main-container .price")?.innerText || "Unknown"')
        
        # Additional information
        specifications = {}
        spec_elements = await page.query_selector_all('.specifications-table tr')
        
        for spec_el in spec_elements:
            spec_text = await spec_el.evaluate('(el) => el.innerText')
            if ':' in spec_text:
                key, value = spec_text.split(':', 1)
                specifications[key.strip()] = value.strip()
        
        product_data = {
            "url": url,
            "title": product_title,
            "price": price,
            "specifications": specifications
        }
        
        print(f"Successfully scraped: {product_title} - {price}")
        
        page_content = await page.content()
        with open(f"product_page_{product_title.replace(' ', '_')}.html", "w", encoding="utf-8") as f:
            f.write(page_content)
        
        await page.close()
        return product_data
    
    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")
        try:
            await page.close()
        except:
            pass
        return {"url": url, "error": str(e)}

async def main():
    # Array of product URLs to scrape
    product_urls = [
        'https://www.apmex.com/product/310462/2025-australia-1-4-oz-gold-kangaroo-proof-box-coa',
        'https://www.apmex.com/product/51681/2025-australia-1-oz-gold-kangaroo-bu',
        'https://www.apmex.com/product/310457/2025-australia-1-oz-gold-kangaroo-proof-box-coa',
        'https://www.apmex.com/product/310460/2025-australia-1-2-oz-gold-kangaroo-proof-box-coa',
        'https://www.apmex.com/product/310464/2025-australia-1-10-oz-gold-kangaroo-proof-box-coa'
    ]
    
    results = []
    
    async with AsyncCamoufox(headless=False, humanize=True, window=(1280, 720)) as browser:
        # Process one page at a time
        for url in product_urls:
            print(f"\n--- Processing {url} ---")
            result = await scrape_product(browser, url)
            results.append(result)
            
            # Add a pause between requests to be more human-like
            await asyncio.sleep(3)
        
        # Save results to JSON file
        with open('gold_kangaroo_products.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nScraped {len(results)} products")
        
        # Print a summary of the results
        print("\nSummary:")
        for product in results:
            if "error" in product:
                print(f"Failed: {product['url']}: {product['error']}")
            else:
                print(f"Success: {product['title']} - {product['price']}")

if __name__ == "__main__":
    asyncio.run(main())