import json
import time
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    MoveTargetOutOfBoundsException,
    StaleElementReferenceException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_selenium(headless=False):
    """
    Initializes the Selenium WebDriver with Firefox options.
    
    Args:
        headless (bool): Whether to run the browser in headless mode.
    
    Returns:
        driver (WebDriver): The initialized Selenium WebDriver instance.
    """
    options = webdriver.FirefoxOptions()
    if headless:
        options.add_argument("--headless")
    # Additional options for stability
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Firefox(options=options)
    return driver

def generate_search_url(search_query):
    """
    Generates the Google Maps search URL based on a search query.
    
    Args:
        search_query (str): The search query (e.g., "factories in chicago").
    
    Returns:
        str: Google Maps search URL with plus signs replacing spaces.
    """
    encoded_query = urllib.parse.quote_plus(search_query)  # Replace spaces with '+' and URL-encode
    url = f"https://www.google.com/maps/search/{encoded_query}"
    return url

def wait_for_element(driver, by, value, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        logging.warning(f"Timeout waiting for element: {value}")
        return None

def handle_popups(driver):
    popup_buttons = [
        (By.XPATH, "//button[contains(@aria-label, 'Accept')]"),
        (By.XPATH, "//button[contains(text(), 'Accept')]"),
        (By.XPATH, "//button[contains(@aria-label, 'Agree')]"),
        (By.XPATH, "//button[contains(text(), 'Agree')]"),
        (By.XPATH, "//button[contains(@aria-label, 'OK')]"),
        (By.XPATH, "//button[contains(text(), 'OK')]"),
        (By.ID, "L2AGLb")  # Google's "I agree" button ID
    ]

    for by, selector in popup_buttons:
        try:
            button = WebDriverWait(driver, 1).until(EC.element_to_be_clickable((by, selector)))
            button.click()
            logging.info(f"Clicked popup button: {selector}")
            time.sleep(1)  # Wait a bit for the popup to disappear
            return
        except TimeoutException:
            continue

    logging.info("No clickable popup buttons found")

def wait_for_panel_update(driver, old_name, max_retries=5, timeout=10):
    for attempt in range(max_retries):
        try:
            # Wait for the name element to be present
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(@class, 'DUwDvf')]"))
            )
            
            # Get the new name
            new_name = driver.find_element(By.XPATH, "//h1[contains(@class, 'DUwDvf')]").text.strip()
            
            # Check if the name has changed
            if new_name != old_name:
                logging.info(f"Panel updated successfully: {old_name} -> {new_name}")
                return True, new_name
            else:
                logging.warning(f"Panel name unchanged: {old_name}")
        except (TimeoutException, StaleElementReferenceException):
            logging.warning(f"Timeout or stale element. Attempt {attempt + 1}/{max_retries}")
        
        if attempt < max_retries - 1:
            time.sleep(0.2)  # Short wait before retrying

    logging.error(f"Failed to update panel after {max_retries} attempts")
    return False, old_name

def extract_info_from_panel(driver):
    result = {
        "name": None,
        "address": None,
        "business_type": None,
        "website": None,
        "rating": None,
        "num_reviews": None,
        "phone": None
    }

    try:
        # Extract name
        try:
            name_element = driver.find_element(By.XPATH, "//h1[contains(@class, 'DUwDvf')]")
            result["name"] = name_element.text.strip()
        except NoSuchElementException:
            pass

        # Extract rating and number of reviews
        try:
            rating_element = driver.find_element(By.XPATH, "//div[contains(@class, 'F7nice')]")
            result["rating"] = rating_element.find_element(By.XPATH, ".//span[@aria-hidden='true']").text.strip()
            reviews_element = rating_element.find_element(By.XPATH, ".//span[contains(@aria-label, 'reviews')]")
            result["num_reviews"] = reviews_element.text.strip().replace('(', '').replace(')', '')
        except NoSuchElementException:
            pass

        # Extract business type
        try:
            business_type_element = driver.find_element(By.XPATH, "//button[contains(@class, 'DkEaL')]")
            result["business_type"] = business_type_element.text.strip()
        except NoSuchElementException:
            pass

        # Extract address
        try:
            address_element = driver.find_element(By.XPATH, "//button[@data-item-id='address']//div[contains(@class, 'Io6YTe')]")
            result["address"] = address_element.text.strip()
        except NoSuchElementException:
            pass

        # Extract website
        try:
            website_element = driver.find_element(By.XPATH, "//a[@data-item-id='authority']//div[contains(@class, 'Io6YTe')]")
            result["website"] = website_element.text.strip()
        except NoSuchElementException:
            pass

        # Extract phone number
        try:
            phone_element = driver.find_element(By.XPATH, "//button[contains(@data-item-id, 'phone:tel:')]//div[contains(@class, 'Io6YTe')]")
            result["phone"] = phone_element.text.strip()
        except NoSuchElementException:
            pass
    except Exception as e:
        logging.error(f"Error in extract_info_from_panel: {str(e)}")

    logging.info(f"Final extracted info: {result}")
    return result

def scrape_google_maps(driver, url):
    driver.get(url)
    logging.info(f"Navigating to {url}")
    
    handle_popups(driver)

    try:
        wait_for_element(driver, By.XPATH, "//div[contains(@class, 'Nv2PK')]", timeout=20)
        logging.info("Search results loaded successfully")
    except TimeoutException:
        logging.error("Timeout waiting for search results to load")
        return []

    index = 1
    results = []
    old_name = ""
    while True:
        xpath = f"(//div[contains(@class, 'Nv2PK')])[{index}]"
        try:
            entry = wait_for_element(driver, By.XPATH, xpath, timeout=15)
            if not entry:
                logging.info(f"No more entries found. Stopping at index {index}.")
                break

            driver.execute_script("arguments[0].scrollIntoView();", entry)
            ActionChains(driver).move_to_element(entry).click().perform()
            logging.info(f"Clicked on entry {index}")

            # Wait for panel update
            if not wait_for_panel_update(driver, old_name, max_retries=5, timeout=10):
                logging.warning(f"Panel did not update for entry {index}. Skipping.")
                index += 1
                continue

            # Extract information
            result = extract_info_from_panel(driver)
            
            # Verify that we got new information
            if result['name'] == old_name:
                logging.warning(f"Panel information did not change for entry {index}. Retrying.")
                continue

            results.append(result)
            old_name = result['name']
            logging.info(f"Successfully scraped entry {index}: {result['name']}")

            index += 1
            
            # Wait for the next entry to be clickable
            next_entry_xpath = f"(//div[contains(@class, 'Nv2PK')])[{index}]"
            wait_for_element(driver, By.XPATH, next_entry_xpath, timeout=10)

        except Exception as e:
            logging.error(f"Error processing entry {index}: {str(e)}")
            # Even if an error occurs, we move to the next entry
            index += 1

    logging.info(f"Scraping completed. Found {len(results)} entries.")
    return results

def save_results_to_json(results, json_path):
    """
    Saves results to a JSON file, avoiding duplicates.
    
    Args:
        results (list): List of new business entries to save.
        json_path (str): Path to the JSON file.
    """
    # Load existing data with error handling for empty or corrupted JSON files
    try:
        with open(json_path, 'r', encoding='utf-8') as file:
            existing_data = json.load(file)
            print(f"Loaded {len(existing_data)} existing entries from {json_path}.")
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Warning: JSON file {json_path} not found or corrupted. Starting with an empty list.")
        existing_data = []

    # Convert existing data to a set of names for quick duplicate checking
    existing_names = {entry['name'] for entry in existing_data}
    print(f"Existing names: {existing_names}")

    # Add only new entries that are not already in the existing data
    new_entries = [entry for entry in results if entry['name'] not in existing_names]
    print(f"New entries to add: {len(new_entries)}")

    existing_data.extend(new_entries)

    # Save updated data back to the JSON file
    try:
        with open(json_path, 'w', encoding='utf-8') as file:
            json.dump(existing_data, file, indent=4, ensure_ascii=False)
        print(f"Saved {len(new_entries)} new entries to {json_path}")
    except Exception as e:
        print(f"Error saving to JSON file: {e}")

def wait_for_element_to_be_stale(driver, element, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(EC.staleness_of(element))
    except TimeoutException:
        logging.warning("Timeout waiting for element to become stale")

def wait_for_element(driver, locator, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))

def wait_for_elements(driver, locator, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located(locator))

def clean_address(address, business_type):
    # Remove business hours
    address = re.sub(r'\d{1,2}(?::\d{2})?\s*[AaPp][Mm]', '', address)
    
    # Remove days of the week
    address = re.sub(r'\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', '', address, flags=re.IGNORECASE)
    
    # Remove "Open", "Closed", "Opens", etc.
    address = re.sub(r'\b(Open|Closed|Opens|Closes)\b', '', address, flags=re.IGNORECASE)
    
    # Remove phone numbers
    address = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '', address)
    
    # Remove "24 hours"
    address = address.replace('24 hours', '')
    
    # Remove business type and its variations
    if business_type:
        business_type_variations = [
            business_type,
            business_type.lower(),
            business_type.replace(' ', ''),
            business_type.replace('/', ' '),
            business_type.replace('&', 'and'),
            business_type.replace('and', '&'),
            'Association',
            'Organization',
            'Nonprofit organization',
            'Non-profit organization'
        ]
        for variation in business_type_variations:
            address = re.sub(r'\b' + re.escape(variation) + r'\b', '', address, flags=re.IGNORECASE)
    
    # Remove extra whitespace and punctuation
    address = re.sub(r'\s+', ' ', address)
    address = re.sub(r'[^\w\s]', '', address)
    
    # Extract the most likely address part
    address_pattern = r'\d+\s+[A-Za-z0-9\s]+'
    matches = re.findall(address_pattern, address)
    if matches:
        # Return the first match (assuming it's the most complete address)
        return matches[0].strip()
    
    return address.strip()

def scrape_google_maps_fast(driver, url, max_scrolls=100):
    driver.get(url)
    logging.info(f"Navigating to {url}")
    
    handle_popups(driver)

    results = []
    processed_items = set()
    scroll_count = 0
    last_height = 0

    try:
        results_container = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']"))
        )
    except TimeoutException:
        logging.error("Couldn't find results container. Page source:")
        logging.error(driver.page_source)
        return results

    while scroll_count < max_scrolls:
        items = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")
        logging.info(f"Found {len(items)} items")

        for item in items:
            if item.id not in processed_items:
                try:
                    result = {
                        'name': None,
                        'href': None,
                        'rating': None,
                        'num_reviews': None,
                        'business_type': None,
                        'address': None,
                        'phone': None,
                        'website': None
                    }
                    
                    # Extract name and href (keep as is)
                    name_element = item.find_element(By.CSS_SELECTOR, "div.qBF1Pd")
                    result['name'] = name_element.text.strip()

                    href_element = item.find_element(By.CSS_SELECTOR, "a.hfpxzc")
                    result['href'] = href_element.get_attribute('href')
                    
                    # Extract all W4Efsd elements
                    w4efsd_elements = item.find_elements(By.CSS_SELECTOR, "div.W4Efsd")
                    
                    address_parts = []
                    for element in w4efsd_elements:
                        text = element.text.strip()
                        
                        # Check if it's the rating element
                        if '(' in text and ')' in text and text[0].isdigit():
                            rating_parts = text.split('(')
                            if len(rating_parts) == 2:
                                result['rating'] = rating_parts[0].strip()
                                result['num_reviews'] = rating_parts[1].strip('()')
                            continue
                        
                        # Split by middot character
                        parts = text.split('·')
                        
                        for part in parts:
                            part = part.strip()
                            
                            # Check for phone number
                            if result['phone'] is None and re.match(r'^\(?[0-9]{3}\)?[-\s]?[0-9]{3}[-\s]?[0-9]{4}$', part):
                                result['phone'] = part
                            else:
                                address_parts.append(part)

                    # Process address parts to extract business type and address
                    if address_parts:
                        # Find the part that doesn't contain numbers and is not at the beginning
                        for i, part in enumerate(address_parts):
                            if i > 0 and not any(char.isdigit() for char in part):
                                result['business_type'] = part
                                address_parts.remove(part)
                                break
                        
                        # Join the remaining parts for the address
                        full_address = ' '.join(address_parts)
                        result['address'] = clean_address(full_address, result['business_type'])

                    # Extract website if available
                    try:
                        website_button = item.find_element(By.CSS_SELECTOR, "a.lcr4fd[data-value='Website']")
                        result['website'] = website_button.get_attribute('href')
                    except NoSuchElementException:
                        pass

                    # Remove duplicates in address
                    if result['address']:
                        address_parts = result['address'].split()
                        result['address'] = ' '.join(dict.fromkeys(address_parts))

                    # Ensure business_type is not set to "No reviews"
                    if result['business_type'] == "No reviews":
                        result['business_type'] = None

                    results.append(result)
                    processed_items.add(item.id)
                    logging.info(f"Scraped business: {result['name']}")
                except (NoSuchElementException, StaleElementReferenceException) as e:
                    logging.error(f"Error processing entry: {str(e)}")

        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", results_container)
        scroll_count += 1
        
        try:
            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script("return arguments[0].scrollHeight", results_container) > last_height
            )
        except TimeoutException:
            logging.info("No new results loaded after scrolling")
            break

        last_height = driver.execute_script("return arguments[0].scrollHeight", results_container)
        
        logging.info(f"Scrolled {scroll_count} times, found {len(results)} results so far")

        try:
            end_message = driver.find_element(By.XPATH, "//span[contains(text(), \"You've reached the end of the list\")]")
            if end_message.is_displayed():
                logging.info("Reached the end of the list")
                break
        except NoSuchElementException:
            pass

    logging.info(f"Fast scraping completed. Found {len(results)} entries after {scroll_count} scrolls.")
    return results

def main():
    # User inputs
    search_query = "businesses in Louisiana"  # Example search query
    json_path = 'GoogleMapsDataFast.json'

    # Setup WebDriver
    # Set headless=False for debugging to see the browser
    driver = setup_selenium(headless=False)

    try:
        # Generate the search URL
        url = generate_search_url(search_query)
        print(f"Generated search URL: {url}")
        
        # Add this block to test the fast scraping function
        print("Starting fast scraping...")
        fast_results = scrape_google_maps_fast(driver, url)
        print(f"Fast scraping completed. Found {len(fast_results)} entries.")

        # Scrape data
        #results = scrape_google_maps(driver, url)
        #print(f"Scraping completed. Found {len(results)} entries.")

        # Save results to JSON
        if fast_results:
            save_results_to_json(fast_results, json_path)
        else:
            print("No results to save.")


    finally:
        # Close the WebDriver
        driver.quit()
        print("WebDriver closed.")

if __name__ == "__main__":
    main()