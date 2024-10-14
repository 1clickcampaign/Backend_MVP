import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import logging


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
