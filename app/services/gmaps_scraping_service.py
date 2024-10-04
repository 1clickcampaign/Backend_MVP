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
    # Handle potential cookie consent popup
    try:
        consent_button = wait_for_element(driver, By.XPATH, "//button[contains(@aria-label, 'Accept')]", timeout=5)
        if consent_button:
            consent_button.click()
            logging.info("Clicked on cookie consent button")
    except:
        logging.info("No cookie consent popup found or unable to click")

    # Handle other potential popups here if needed

def wait_for_panel_update(driver, old_name, max_retries=3, timeout=15):
    for attempt in range(max_retries):
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(@class, 'DUwDvf')]"))
            )
            new_name = driver.find_element(By.XPATH, "//h1[contains(@class, 'DUwDvf')]").text.strip()
            if new_name != old_name:
                logging.info(f"Panel updated successfully: {old_name} -> {new_name}")
                return True
            else:
                logging.warning(f"Panel name unchanged: {old_name}")
        except TimeoutException:
            logging.warning(f"Timeout waiting for panel to update. Attempt {attempt + 1}/{max_retries}")
        
        if attempt < max_retries - 1:
            time.sleep(2)  # Wait a bit before retrying

    logging.error(f"Failed to update panel after {max_retries} attempts")
    return False

def extract_info_from_panel(driver):
    result = {
        "name": "Name not found",
        "address": "Address not found",
        "business_type": "Type not found",
        "website": "Website not found",
        "rating": "No rating",
        "num_reviews": "No reviews",
        "phone": "Phone not found"
    }

    try:
        # Extract name
        try:
            name_element = driver.find_element(By.XPATH, "//h1[contains(@class, 'DUwDvf')]")
            result["name"] = name_element.text.strip()
            logging.info(f"Extracted name: {result['name']}")
        except NoSuchElementException:
            logging.warning("Name element not found")

        # Extract rating and number of reviews
        try:
            rating_element = driver.find_element(By.XPATH, "//div[contains(@class, 'F7nice')]")
            result["rating"] = rating_element.find_element(By.XPATH, ".//span[@aria-hidden='true']").text.strip()
            reviews_element = rating_element.find_element(By.XPATH, ".//span[contains(@aria-label, 'reviews')]")
            result["num_reviews"] = reviews_element.text.strip().replace('(', '').replace(')', '')
            logging.info(f"Extracted rating: {result['rating']}, reviews: {result['num_reviews']}")
        except NoSuchElementException:
            logging.warning("Rating/reviews elements not found")

        # Extract business type
        try:
            business_type_element = driver.find_element(By.XPATH, "//button[contains(@class, 'DkEaL')]")
            result["business_type"] = business_type_element.text.strip()
            logging.info(f"Extracted business type: {result['business_type']}")
        except NoSuchElementException:
            logging.warning("Business type element not found")

        # Extract address
        try:
            address_element = driver.find_element(By.XPATH, "//button[@data-item-id='address']//div[contains(@class, 'Io6YTe')]")
            result["address"] = address_element.text.strip()
            logging.info(f"Extracted address: {result['address']}")
        except NoSuchElementException:
            logging.warning("Address element not found")

        # Extract website
        try:
            website_element = driver.find_element(By.XPATH, "//a[@data-item-id='authority']//div[contains(@class, 'Io6YTe')]")
            result["website"] = website_element.text.strip()
            logging.info(f"Extracted website: {result['website']}")
        except NoSuchElementException:
            logging.warning("Website element not found")

        # Extract phone number
        try:
            phone_element = driver.find_element(By.XPATH, "//button[contains(@data-item-id, 'phone:tel:')]//div[contains(@class, 'Io6YTe')]")
            result["phone"] = phone_element.text.strip()
            logging.info(f"Extracted phone: {result['phone']}")
        except NoSuchElementException:
            logging.warning("Phone element not found")

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
            time.sleep(2)  # Short delay between entries

        except Exception as e:
            logging.error(f"Error processing entry {index}: {str(e)}")
            # Even if an error occurs, we move to the next entry
            index += 1
            time.sleep(2)

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

def main():
    # User inputs
    search_query = "manufacturing in illinois"  # Example search query
    json_path = 'GoogleMapsData.json'

    # Setup WebDriver
    # Set headless=False for debugging to see the browser
    driver = setup_selenium(headless=False)

    try:
        # Generate the search URL
        url = generate_search_url(search_query)
        print(f"Generated search URL: {url}")

        # Scrape data
        results = scrape_google_maps(driver, url)
        print(f"Scraping completed. Found {len(results)} entries.")

        # Save results to JSON
        if results:
            save_results_to_json(results, json_path)
        else:
            print("No results to save.")

    finally:
        # Close the WebDriver
        driver.quit()
        print("WebDriver closed.")

if __name__ == "__main__":
    main()