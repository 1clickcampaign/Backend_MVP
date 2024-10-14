import logging
import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from queue import Queue
from threading import Lock
from typing import Any, Dict, List, Optional, Set
import urllib.parse
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib.parse import parse_qs, urlparse
import threading
import time
import json
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

class GoogleMapsScraper:
    def __init__(self, headless: bool = True, max_threads: int = 4):
        self.headless = headless
        self.max_threads = max_threads
        self.driver_pool = Queue(maxsize=max_threads)
        self.lock = Lock()
        self.results_queue = Queue()
        self.processed_items: Set[str] = set()
        self.timing_log_file = "scraper_timing.txt"
        self.start_time = time.time()
        self._initialize_driver_pool()

    def _initialize_driver_pool(self):
        for _ in range(self.max_threads):
            driver = self._setup_selenium(headless=self.headless)
            self.driver_pool.put(driver)

    def _setup_selenium(self, headless=True):
        chrome_options = ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.binary_location = "/usr/bin/google-chrome-stable"
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)

    @staticmethod
    def generate_search_url(search_query: str) -> str:
        """
        Generates the Google Maps search URL based on a search query.

        Args:
            search_query (str): The search query (e.g., "factories in chicago").

        Returns:
            str: Google Maps search URL with plus signs replacing spaces.
        """
        encoded_query = urllib.parse.quote_plus(search_query)
        return f"https://www.google.com/maps/search/{encoded_query}"

    def _wait_for_element(self, driver, by, selector, timeout=10):
        """
        Waits for an element to be present on the page.

        Args:
            driver (WebDriver): The Selenium WebDriver instance.
            by (By): The method used to locate the element.
            selector (str): The selector string.
            timeout (int): Maximum time to wait for the element.

        Returns:
            WebElement: The found element.
        """
        try:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
        except TimeoutException:
            logging.warning(f"Element not found: {selector}")
            return None

    def _handle_popups(self):
        """
        Handles common popups by attempting to click on known popup buttons.
        """
        popup_buttons = [
            (By.XPATH, "//button[contains(@aria-label, 'Accept')]"),
            (By.XPATH, "//button[contains(text(), 'Accept')]"),
            (By.XPATH, "//button[contains(@aria-label, 'Agree')]"),
            (By.XPATH, "//button[contains(text(), 'Agree')]"),
            (By.XPATH, "//button[contains(@aria-label, 'OK')]"),
            (By.XPATH, "//button[contains(text(), 'OK')]"),
            (By.ID, "L2AGLb"),  # Google's "I agree" button ID
        ]

        for by, selector in popup_buttons:
            try:
                button = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((by, selector))
                )
                button.click()
                logging.info(f"Clicked popup button: {selector}")
                WebDriverWait(self.driver, 2).until(
                    EC.invisibility_of_element_located((by, selector))
                )
                return
            except TimeoutException:
                continue

        logging.info("No clickable popup buttons found")

    @staticmethod
    def save_results_to_json(results: List[Dict[str, Any]], json_path: str):
        """
        Saves results to a JSON file, avoiding duplicates.

        Args:
            results (List[Dict[str, Any]]): List of new business entries to save.
            json_path (str): Path to the JSON file.
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as file:
                existing_data = json.load(file)
                logging.info(f"Loaded {len(existing_data)} existing entries from {json_path}.")
        except (FileNotFoundError, json.JSONDecodeError):
            logging.warning(f"JSON file {json_path} not found or corrupted. Starting with an empty list.")
            existing_data = []

        existing_names = {entry['name'] for entry in existing_data if 'name' in entry}
        new_entries = [entry for entry in results if entry.get('name') not in existing_names]
        logging.info(f"New entries to add: {len(new_entries)}")

        if new_entries:
            existing_data.extend(new_entries)
            try:
                with open(json_path, 'w', encoding='utf-8') as file:
                    json.dump(existing_data, file, indent=4, ensure_ascii=False)
                logging.info(f"Saved {len(new_entries)} new entries to {json_path}")
            except Exception as e:
                logging.error(f"Error saving to JSON file: {e}")

    @staticmethod
    def _clean_address(address: str, business_type: Optional[str]) -> str:
        """
        Cleans the address string by removing unwanted information.

        Args:
            address (str): The raw address string.
            business_type (Optional[str]): The type of business to remove from the address.

        Returns:
            str: The cleaned address.
        """
        address = re.sub(r'\d{1,2}(?::\d{2})?\s*[AaPp][Mm]', '', address)
        address = re.sub(
            r'\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
            '',
            address,
            flags=re.IGNORECASE,
        )
        address = re.sub(
            r'\b(Open|Closed|Opens|Closes)\b', '', address, flags=re.IGNORECASE
        )
        address = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '', address)
        address = address.replace('24 hours', '')

        if business_type:
            business_type_variations = [
                business_type.lower(),
                business_type.replace(' ', ''),
                business_type.replace('/', ' '),
                business_type.replace('&', 'and'),
                business_type.replace('and', '&'),
                'Association',
                'Organization',
                'Nonprofit organization',
                'Non-profit organization',
            ]
            for variation in business_type_variations:
                address = re.sub(r'\b' + re.escape(variation) + r'\b', '', address, flags=re.IGNORECASE)

        address = re.sub(r'\s+', ' ', address)
        address = re.sub(r'[^\w\s]', '', address)

        address_pattern = r'\d+\s+[A-Za-z0-9\s]+'
        matches = re.findall(address_pattern, address)
        if matches:
            return matches[0].strip()

        return address.strip()

    def scrape_business_details(self, driver: webdriver.Chrome) -> Dict[str, Any]:
        """
        Scrapes detailed information of a single business.

        Args:
            driver (WebDriver): The Selenium WebDriver instance.

        Returns:
            Dict[str, Any]: A dictionary containing business details.
        """
        details = {}
        try:
            # Use the passed driver instance instead of self.driver
            details['name'] = self._wait_for_element(driver, By.CSS_SELECTOR, 'h1.DUwDvf', timeout=10).text

            if not details['name']:
                logging.error("Timed out waiting for business name to appear")
                return details

            # Rating and total reviews || note to self: this is not working
            try:
                rating_element = driver.find_element(By.CSS_SELECTOR, 'div.F7nice')
                rating_text = rating_element.find_element(By.CSS_SELECTOR, 'span[aria-hidden="true"]').text
                details['rating'] = float(rating_text) if rating_text else None

                reviews_text = rating_element.find_element(By.CSS_SELECTOR, 'span[aria-label]').get_attribute('aria-label')
                reviews_count = ''.join(filter(str.isdigit, reviews_text))
                details['total_reviews'] = int(reviews_count) if reviews_count else None
            except (NoSuchElementException, ValueError):
                details['rating'] = None
                details['total_reviews'] = None

            # Business type
            try:
                details['business_type'] = driver.find_element(By.CSS_SELECTOR, 'button.DkEaL').text
            except NoSuchElementException:
                details['business_type'] = None

            # Wheelchair accessibility
            try:
                details['wheelchair_accessible'] = driver.find_element(By.CSS_SELECTOR, 'span.wmQCje').is_displayed()
            except NoSuchElementException:
                details['wheelchair_accessible'] = None

            # Address
            try:
                details['address'] = driver.find_element(By.CSS_SELECTOR, 'button[data-item-id="address"] div.fontBodyMedium').text
            except NoSuchElementException:
                details['address'] = None

            # Hours
            try:
                hours_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[data-hide-tooltip-on-mouse-move="true"]'))
                )
                hours_button.click()

                hours_table = self._wait_for_element(driver, By.CSS_SELECTOR, 'table.eK4R0e', timeout=10)
                if hours_table:
                    details['hours'] = {}
                    for row in hours_table.find_elements(By.CSS_SELECTOR, 'tr'):
                        day = row.find_element(By.CSS_SELECTOR, 'td.ylH6lf').text
                        time_slot = row.find_element(By.CSS_SELECTOR, 'td.mxowUb').text
                        details['hours'][day] = time_slot
                else:
                    details['hours'] = None
            except (NoSuchElementException, TimeoutException):
                details['hours'] = None

            # Website
            try:
                website_element = driver.find_element(By.CSS_SELECTOR, 'a[data-item-id="authority"]')
                details['website'] = website_element.get_attribute('href')
            except NoSuchElementException:
                details['website'] = None

            # Phone number
            try:
                details['phone'] = driver.find_element(By.CSS_SELECTOR, 'button[data-item-id^="phone:tel"] div.fontBodyMedium').text
            except NoSuchElementException:
                details['phone'] = None

            # Region (Plus code)
            try:
                details['region'] = driver.find_element(By.CSS_SELECTOR, 'button[data-item-id="oloc"] div.fontBodyMedium').text
            except NoSuchElementException:
                details['region'] = None

            # Additional properties
            try:
                additional_props = driver.find_elements(By.CSS_SELECTOR, 'div[data-item-id="place-info-links:"]')
                details['additional_properties'] = [
                    prop.find_element(By.CSS_SELECTOR, 'div.fontBodyMedium').text for prop in additional_props
                ]
            except NoSuchElementException:
                details['additional_properties'] = []

            # Images
            try:
                image_elements = driver.find_elements(By.CSS_SELECTOR, 'button.aoRNLd img')
                details['images'] = [img.get_attribute('src') for img in image_elements]
            except NoSuchElementException:
                details['images'] = []

            # Reviews
            details['reviews'] = self._scrape_reviews(driver, max_reviews=10)

            # Similar businesses
            try:
                similar_businesses_section = self._wait_for_element(driver, By.CSS_SELECTOR, "div.fp2VUc", timeout=10)
                if similar_businesses_section:
                    self.driver.execute_script("arguments[0].scrollIntoView();", similar_businesses_section)
                    WebDriverWait(self.driver, 2).until(EC.visibility_of(similar_businesses_section))
                    details['similar_businesses'] = self._scrape_similar_businesses(driver)
                else:
                    details['similar_businesses'] = []
            except TimeoutException:
                logging.warning("Similar businesses section not found or not visible")
                details['similar_businesses'] = []

            # About section
            try:
                about_tab = self._wait_for_element(driver, By.XPATH, "//button[@role='tab' and contains(@aria-label, 'About')]", timeout=10)
                if about_tab:
                    about_tab.click()
                    WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.iP2t7d.fontBodyMedium"))
                    )
                    details['about'] = self._scrape_about_section(driver)
            except (NoSuchElementException, TimeoutException) as e:
                logging.error(f"Error clicking About tab: {e}")
                details['about'] = {}

        except Exception as e:
            logging.error(f"Unexpected error while scraping business details: {e}")
            logging.debug(traceback.format_exc())

        return details

    def _scrape_about_section(self, driver: webdriver.Firefox) -> Dict[str, List[str]]:
        """
        Scrapes the About section of a business.

        Args:
            driver (WebDriver): The Selenium WebDriver instance.

        Returns:
            Dict[str, List[str]]: A dictionary containing about section details.
        """
        about_details = {}
        try:
            about_sections = driver.find_elements(By.CSS_SELECTOR, "div.iP2t7d.fontBodyMedium")

            for section in about_sections:
                section_title_elem = section.find_elements(By.CSS_SELECTOR, "h2.iL3Qke.fontTitleSmall")
                section_title = section_title_elem[0].text if section_title_elem else "Unknown"

                section_items = section.find_elements(By.CSS_SELECTOR, "li.hpLkke span")
                about_details[section_title] = [item.text for item in section_items]
        except NoSuchElementException as e:
            logging.error(f"Error scraping About section: {e}")

        return about_details

    def _scrape_similar_businesses(self, driver: webdriver.Firefox) -> List[Dict[str, Any]]:
        """
        Scrapes similar businesses from the similar businesses section.

        Args:
            driver (WebDriver): The Selenium WebDriver instance.

        Returns:
            List[Dict[str, Any]]: A list of similar businesses.
        """
        similar_businesses = []
        try:
            business_cards = driver.find_elements(By.CSS_SELECTOR, "div.Ymd7jc.Lnaw4c")
            logging.debug(f"Found {len(business_cards)} business cards")

            for index, card in enumerate(business_cards):
                try:
                    name = card.find_element(By.CSS_SELECTOR, "span.GgK1If.fontTitleSmall").text

                    rating_element = card.find_elements(By.CSS_SELECTOR, "span.ZkP5Je")
                    if rating_element:
                        rating_text = rating_element[0].get_attribute("aria-label")
                        rating = float(re.search(r"(\d+(\.\d+)?)", rating_text).group(1)) if re.search(r"(\d+(\.\d+)?)", rating_text) else None

                        reviews_count = int(re.search(r"(\d+)", rating_text).group(1)) if re.search(r"(\d+)", rating_text) else None
                    else:
                        no_review_element = card.find_elements(By.CSS_SELECTOR, "span.Q5g20.e4rVHe.fontBodyMedium")
                        if no_review_element and no_review_element[0].text.lower() == "no reviews":
                            rating = 0.0
                            reviews_count = 0
                        else:
                            rating = None
                            reviews_count = None

                    business_type = card.find_element(By.CSS_SELECTOR, "div.Q5g20").text

                    aria_label = card.get_attribute("aria-label")
                    place_id_match = re.search(r"ChIJ\w+", aria_label)
                    href = f"https://www.google.com/maps/place/?q=place_id:{place_id_match.group()}" if place_id_match else None

                    try:
                        img_element = card.find_element(By.CSS_SELECTOR, "img.W7kqEc")
                        img_url = img_element.get_attribute("src")
                    except NoSuchElementException:
                        img_url = None

                    similar_businesses.append({
                        "name": name,
                        "rating": rating,
                        "reviews_count": reviews_count,
                        "business_type": business_type,
                        "href": href,
                        "img_url": img_url
                    })
                except Exception as e:
                    logging.error(f"Error extracting data for similar business {index + 1}: {e}")
                    logging.debug(traceback.format_exc())

        except Exception as e:
            logging.error(f"Error scraping similar businesses: {e}")
            logging.debug(traceback.format_exc())

        logging.debug(f"Scraped {len(similar_businesses)} similar businesses")
        return similar_businesses

    def _scrape_reviews(self, driver: webdriver.Firefox, max_reviews: int = 10) -> List[Dict[str, Any]]:
        """
        Scrapes reviews for a business.

        Args:
            driver (WebDriver): The Selenium WebDriver instance.
            max_reviews (int): Maximum number of reviews to scrape.

        Returns:
            List[Dict[str, Any]]: A list of reviews.
        """
        reviews = []
        try:
            reviews_container = self._wait_for_element(driver, By.CSS_SELECTOR, '.dS8AEf', timeout=10)
            if not reviews_container:
                logging.warning("Reviews container not found")
                return reviews

            last_height = driver.execute_script("return arguments[0].scrollHeight", reviews_container)
            while len(reviews) < max_reviews:
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", reviews_container)
                WebDriverWait(driver, 2).until(
                    lambda d: driver.execute_script("return arguments[0].scrollHeight", reviews_container) > last_height
                )
                new_height = driver.execute_script("return arguments[0].scrollHeight", reviews_container)
                if new_height == last_height:
                    break
                last_height = new_height

                review_elements = driver.find_elements(By.CSS_SELECTOR, "div.jftiEf")
                for review in review_elements:
                    if len(reviews) >= max_reviews:
                        break
                    review_data = self._extract_review_data(review)
                    if review_data and review_data['id'] not in {r['id'] for r in reviews}:
                        reviews.append(review_data)

        except TimeoutException:
            logging.error("Timeout during review scraping")
        except Exception as e:
            logging.error(f"Error during review scraping: {e}")
            logging.debug(traceback.format_exc())

        return reviews[:max_reviews]

    def _extract_review_data(self, review: Any) -> Optional[Dict[str, Any]]:
        """
        Extracts data from a single review element.

        Args:
            review (WebElement): The Selenium WebElement representing a review.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing review data or None if extraction fails.
        """
        try:
            review_id = review.get_attribute('data-review-id')

            # Reviewer name and stats
            try:
                reviewer_element = review.find_element(By.CSS_SELECTOR, "div.WNxzHc")
                reviewer_name = reviewer_element.find_element(By.CSS_SELECTOR, "div.d4r55").text
                reviewer_stats = reviewer_element.find_element(By.CSS_SELECTOR, "div.RfnDt").text
                reviewer_total_reviews = self._extract_number(reviewer_stats, 'review')
                reviewer_total_photos = self._extract_number(reviewer_stats, 'photo')
            except NoSuchElementException:
                reviewer_name = "Unknown"
                reviewer_total_reviews = None
                reviewer_total_photos = None

            # Rating
            try:
                rating_element = review.find_element(By.CSS_SELECTOR, "span.kvMYJc")
                
                # Count filled stars
                filled_stars = rating_element.find_elements(By.CSS_SELECTOR, "span.hCCjke.google-symbols.NhBTye.elGi1d")
                rating = len(filled_stars)
                
                # Double-check with aria-label
                aria_label = rating_element.get_attribute("aria-label")
                if aria_label:
                    aria_rating = int(aria_label.split()[0])
                    if aria_rating != rating:
                        logging.warning(f"Mismatch between counted stars ({rating}) and aria-label ({aria_rating})")
                        rating = aria_rating  # Prefer aria-label if there's a mismatch
                
                logging.debug(f"Extracted rating: {rating}")
            except (NoSuchElementException, ValueError, AttributeError) as e:
                logging.error(f"Error extracting rating: {e}")
                rating = None

            # Date
            try:
                date_text = review.find_element(By.CSS_SELECTOR, "span.rsqaWe").text
                date = self._parse_date(date_text)
            except NoSuchElementException:
                date = None

            # Review text
            try:
                text_element = review.find_element(By.CSS_SELECTOR, "span.wiI7pd")
                text = text_element.text
            except NoSuchElementException:
                text = None

            # Image
            try:
                image_element = review.find_element(By.CSS_SELECTOR, "button.Tya61d")
                image_style = image_element.get_attribute('style')
                image = re.search(r'url\("(.+?)"\)', image_style).group(1) if image_style else None
            except (NoSuchElementException, AttributeError):
                image = None

            # Likes
            try:
                likes_element = review.find_element(By.CSS_SELECTOR, "span.pkWtMe")
                likes = int(likes_element.text)
            except (NoSuchElementException, ValueError):
                likes = 0

            # Owner response
            try:
                response_element = review.find_element(By.CSS_SELECTOR, "div.CDe7pd")
                response_text = response_element.find_element(By.CSS_SELECTOR, "div.wiI7pd").text
                response_date_text = response_element.find_element(By.CSS_SELECTOR, "span.DZSIDd").text
                owner_response = {
                    'text': response_text,
                    'date': self._parse_date(response_date_text)
                }
            except NoSuchElementException:
                owner_response = None

            return {
                'id': review_id,
                'reviewer_name': reviewer_name,
                'reviewer_total_reviews': reviewer_total_reviews,
                'reviewer_total_photos': reviewer_total_photos,
                'rating': rating,
                'date': date,
                'text': text,
                'image': image,
                'likes': likes,
                'owner_response': owner_response
            }
        except Exception as e:
            logging.error(f"Error extracting review data: {e}")
            logging.debug(traceback.format_exc())
            return None

    @staticmethod
    def _extract_number(text: str, keyword: str) -> Optional[int]:
        """
        Extracts a number associated with a keyword from a text string.

        Args:
            text (str): The text to search within.
            keyword (str): The keyword to associate with the number.

        Returns:
            Optional[int]: The extracted number or None if not found.
        """
        match = re.search(rf'(\d+)\s*{keyword}', text.lower())
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_date(date_text: str) -> str:
        """
        Parses a relative date string into an ISO formatted date.

        Args:
            date_text (str): The relative date string (e.g., "2 weeks ago").

        Returns:
            str: The ISO formatted date string.
        """
        now = datetime.now()
        if not date_text:
            return now.isoformat()

        match = re.search(r'(\d+)\s*(year|month|week|day|hour|minute)s?', date_text.lower())
        if not match:
            return now.isoformat()

        value, unit = match.groups()
        value = int(value)

        if 'year' in unit:
            date = now - timedelta(days=value * 365)
        elif 'month' in unit:
            date = now - timedelta(days=value * 30)
        elif 'week' in unit:
            date = now - timedelta(weeks=value)
        elif 'day' in unit:
            date = now - timedelta(days=value)
        elif 'hour' in unit:
            date = now - timedelta(hours=value)
        elif 'minute' in unit:
            date = now - timedelta(minutes=value)
        else:
            date = now

        return date.isoformat()

    def _process_item(self, item: Any) -> None:
        try:
            # Extract name and href first
            name_element = item.find_element(By.CSS_SELECTOR, "div.qBF1Pd")
            name = name_element.text.strip()
            href_element = item.find_element(By.CSS_SELECTOR, "a.hfpxzc")
            href = href_element.get_attribute('href')

            # Check if this item has already been processed
            if name in self.processed_items:
                logging.info(f"Skipping duplicate entry: {name}")
                return

            # Add the name to the set of processed items
            self.processed_items.add(name)

            result = {
                'name': name,
                'href': href,
                'rating': None,
                'num_reviews': None,
                'business_type': None,
                'address': None,
                'phone': None,
                'website': None,
                'latitude': None,
                'longitude': None
            }

            # Extract latitude and longitude from href
            parsed_url = urlparse(result['href'])
            query_params = parse_qs(parsed_url.query)
            
            if 'data' in query_params:
                data_param = query_params['data'][0]
                coords_match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', data_param)
                if coords_match:
                    result['latitude'] = float(coords_match.group(1))
                    result['longitude'] = float(coords_match.group(2))
            else:
                # If 'data' is not in query params, try to extract from the path
                path_parts = parsed_url.path.split('/')
                if len(path_parts) > 2 and '@' in path_parts[2]:
                    coords = path_parts[2].split('@')[1].split(',')
                    if len(coords) >= 2:
                        result['latitude'] = float(coords[0])
                        result['longitude'] = float(coords[1])

            # Extract all W4Efsd elements
            w4efsd_elements = item.find_elements(By.CSS_SELECTOR, "div.W4Efsd")

            info_parts = []
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
                info_parts.extend([part.strip() for part in parts if part.strip()])

            # Process info_parts to extract business type, address, and phone
            for part in info_parts:
                if re.match(r'^\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}$', part):
                    result['phone'] = part
                elif any(char.isdigit() for char in part):
                    if not result['address']:
                        result['address'] = part
                elif not result['business_type']:
                    result['business_type'] = part
                elif not result['address']:
                    result['address'] = part

            # If we still don't have a business type or address, use the remaining parts
            remaining_parts = [part for part in info_parts if part != result['phone']]
            if len(remaining_parts) == 1:
                if not result['business_type']:
                    result['business_type'] = remaining_parts[0]
                elif not result['address']:
                    result['address'] = remaining_parts[0]
            elif len(remaining_parts) > 1:
                if not result['business_type']:
                    result['business_type'] = remaining_parts[0]
                if not result['address']:
                    result['address'] = ' '.join(remaining_parts[1:])

            # Clean the address
            if result['address']:
                result['address'] = self._clean_address(result['address'], result['business_type'])

            # Extract website if available
            try:
                website_button = item.find_element(By.CSS_SELECTOR, "a.lcr4fd[data-value='Website']")
                result['website'] = website_button.get_attribute('href')
            except NoSuchElementException:
                pass

            # Ensure no field is set to "No reviews"
            for key in result:
                if result[key] == "No reviews":
                    result[key] = None

            with self.lock:
                self.results_queue.put(result)
                logging.info(f"Scraped basic info for business: {result['name']}")
        except (NoSuchElementException, StaleElementReferenceException) as e:
            logging.error(f"Error processing entry: {e}")

    async def scrape_google_maps_fast(self, url: str, max_scrolls: int = 100) -> List[Dict[str, Any]]:
        """
        Performs fast scraping of Google Maps search results using async.

        Args:
            url (str): The Google Maps search URL.
            max_scrolls (int): Maximum number of scroll actions.

        Returns:
            List[Dict[str, Any]]: A list of scraped business entries.
        """
        driver = self.driver_pool.get()
        try:
            driver.get(url)
            logging.info(f"Navigating to {url}")

            #self._handle_popups()

            results: List[Dict[str, Any]] = []
            scroll_count = 0
            last_height = 0
            last_processed_index = 0
            no_new_items_count = 0

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
                new_items = len(items) - last_processed_index

                if new_items > 0:
                    logging.info(f"Found {len(items)} items, {new_items} new")
                    for item in items[last_processed_index:]:
                        try:
                            await self._process_item_async(item)
                        except (NoSuchElementException, StaleElementReferenceException) as e:
                            logging.error(f"Error processing item: {e}")
                    last_processed_index = len(items)
                    no_new_items_count = 0
                else:
                    logging.info("No new items found in this scroll")
                    no_new_items_count += 1
                    if no_new_items_count >= 3:
                        logging.info("No new items found in 3 consecutive scrolls, stopping")
                        break

                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", results_container)
                scroll_count += 1            
                await asyncio.sleep(1)  # Use asyncio.sleep for non-blocking delay
                
                new_height = driver.execute_script("return arguments[0].scrollHeight", results_container)
                if new_height == last_height:
                    logging.info("Scroll height didn't change, may have reached the end")
                    break
                last_height = new_height
                
                logging.info(f"Scrolled {scroll_count} times, collected {self.results_queue.qsize()} results so far")

                try:
                    end_message = driver.find_element(By.XPATH, "//span[contains(text(), \"You've reached the end of the list\")]")
                    if end_message.is_displayed():
                        logging.info("Reached the end of the list")
                        break
                except NoSuchElementException:
                    pass

            # Collect results from the queue
            while not self.results_queue.empty():
                results.append(self.results_queue.get())

            logging.info(f"Fast scraping completed. Found {len(results)} unique entries after {scroll_count} scrolls.")
            
            # Now perform detailed scraping using multithreading
            detailed_results = await self._scrape_businesses_details_async(results)
            
            return detailed_results
        finally:
            self.driver_pool.put(driver)

    async def _process_item_async(self, item: Any) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._process_item, item)

    async def _scrape_businesses_details_async(self, businesses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        detailed_results = []
        
        async def scrape_single_business_async(business):
            details = await self._scrape_single_business_async(business['href'])
            business.update(details)
            return business

        tasks = [scrape_single_business_async(business) for business in businesses]
        detailed_results = await asyncio.gather(*tasks)
        
        return detailed_results

    async def _scrape_single_business_async(self, href: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._scrape_single_business, href)

    def _scrape_single_business(self, href: str) -> Dict[str, Any]:
        details = {}
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            driver = self.driver_pool.get()
            start_time = time.time()
            try:
                driver.get(href)
                logging.info(f"Scraping single business from {href}")
                #self._handle_popups(driver)
                details = self.scrape_business_details(driver)
                logging.info(f"Scraped details: {details}")
                return details
            except WebDriverException as e:
                logging.warning(f"WebDriver error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logging.error(f"Error scraping single business: {e}")
                logging.debug(traceback.format_exc())
            finally:
                self.driver_pool.put(driver)
                duration = time.time() - start_time
                self.log_timing(f"WebDriver usage for {href}", duration)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

        logging.error(f"Failed to scrape business after {max_retries} attempts: {href}")
        return details

    def log_timing(self, operation, duration):
        with open(self.timing_log_file, "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{timestamp} - {operation}: {duration:.2f} seconds\n")

    def log_overall_time(self):
        overall_duration = time.time() - self.start_time
        self.log_timing("Overall scraping process", overall_duration)

    def close(self):
        """
        Closes all WebDriver instances in the pool.
        """
        while not self.driver_pool.empty():
            driver = self.driver_pool.get()
            driver.quit()
        logging.info("All WebDrivers closed.")

async def main_async():
    # User inputs
    search_query = "personal care manufacturers near denver"  # Example search query
    json_path = 'GoogleMapsDataFast.json'

    scraper = GoogleMapsScraper(headless=True, max_threads=4)

    try:
        # Generate the search URL
        url = scraper.generate_search_url(search_query)
        logging.info(f"Generated search URL: {url}")

        # Scrape basic data
        logging.info("Starting fast scraping...")
        results = await scraper.scrape_google_maps_fast(url)
        logging.info(f"Fast scraping completed. Found {len(results)} entries.")

        # Save results to JSON
        if results:
            scraper.save_results_to_json(results, json_path)
        else:
            logging.info("No results to save.")
    except Exception as e:
        logging.error(f"An error occurred during scraping: {e}")
        logging.debug(traceback.format_exc())
    finally:
        # Close the WebDriver pool
        scraper.close()

if __name__ == "__main__":
    asyncio.run(main_async())