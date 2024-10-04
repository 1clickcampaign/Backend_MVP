import requests
from bs4 import BeautifulSoup
import time
import random
import string
from urllib.parse import urlparse, urljoin
import json
import re
from openai import AzureOpenAI
from selenium import webdriver
from stem import Signal
from stem.control import Controller
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from emailfinder.extractor import *
from difflib import SequenceMatcher

# Tor Scraper setup
def renew_tor_ip():
    with Controller.from_port(port=9051) as controller:
        controller.authenticate(password="your_password")
        controller.signal(Signal.NEWNYM)

def setup_selenium_with_tor():
    options = webdriver.FirefoxOptions()
    options.add_argument("--proxy-server=socks5://127.0.0.1:9050")
    driver = webdriver.Firefox(options=options)
    return driver

def scrape_with_tor(urls):
    html = []
    driver = setup_selenium_with_tor()
    try:
        for i, url in enumerate(urls):
            if i % 5 == 0:
                renew_tor_ip()
                time.sleep(10)
            driver.get(url)
            html.append(driver.page_source)
            try:
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                print(f"Scraped: {url}")
            except Exception as e:
                print(f"Failed to load {url}: {e}")
    finally:
        driver.quit()
        return html

# Azure OpenAI setup
client = AzureOpenAI(
    azure_endpoint='https://1clickcampaign.openai.azure.com/',
    api_key="e0666bd51a474639a729e9105fa0f677",
    api_version="2024-02-01"
)

def CallGPT(message):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=message
    )
    return response.choices[0].message.content

# Utility functions
def get_website_html(url):
    if not url.startswith('http'):
        url = 'https://' + url
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {str(e)}")
        return ""

def html_to_text(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ')

def sanitize_query(query):
    return query.translate(str.maketrans('', '', string.punctuation))

def get_top_google_search_links(query, num_results=3, max_retries=3):
    print(f"Searching Google for: {query}")
    query = sanitize_query(query)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    
    for retries in range(max_retries):
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.select('div.yuRUbf a')
            links = [link['href'] for link in results if link['href'].startswith('http')][:num_results]
            if links:
                return links
        except Exception as e:
            print(f"Attempt {retries + 1} failed: {str(e)}")
        time.sleep(random.uniform(1, 5))
    
    print("Failed to fetch search results after multiple retries.")
    return []

def find_domain(name):
    links = get_top_google_search_links(name)
    return url_with_least_subdirectories(links)

def url_with_least_subdirectories(urls):
    if not urls:
        return ""
    return min(urls, key=lambda url: len([part for part in urlparse(url).path.split('/') if part]))

def GetPublicEmailsWithWebPages(name, domain):
    print(f"Getting public emails with web pages for {name} at {domain}")
    publicEmails = GetPublicEmails(domain)
    emails = []
    email2link = {}
    EmailDomain = urlparse(domain).netloc

    for email in publicEmails:
        print(f"Searching for pages containing email: {email}")
        link = get_top_google_search_links(name + f'"{email}"')
        links = []
        for l in link:
            if EmailDomain == urlparse(l).netloc:
                emails.append(email)
                links.append(l)
        if links:
            email2link[email] = links
            print(f"Found {len(links)} pages for email {email}")
        else:
            print(f"No pages found for email {email}")

    print(f"Total public emails found: {len(emails)}")
    print(f"Emails with associated pages: {len(email2link)}")
    return emails, email2link

def GetPublicEmails(domain):
    print(f"Searching for public emails for domain: {domain}")
    email_domain = get_email_domain(domain)
    print(f"Email domain: {email_domain}")
    
    try:
        html = get_website_html(domain)
        emails = extract_emails_from_html(html, email_domain)
        print(f"Emails found from website scraping: {emails}")
        return emails
    except Exception as e:
        print(f"Error scraping website for emails: {str(e)}")
        return []

def extract_emails_from_html(html, domain):
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    emails = email_pattern.findall(html)
    return [email for email in set(emails) if domain in email]

def get_email_domain(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain

def filter_websites_by_domain(website_list, reference_link):
    reference_domain = urlparse(reference_link).netloc
    return [website for website in website_list if urlparse(website).netloc == reference_domain]

def extract_phone_numbers(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()
    phone_pattern = re.compile(r'\+?1?\s*\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
    return set(phone_pattern.findall(text))

def extract_address_from_schema_org(html):
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and 'address' in data:
                address = data['address']
                return f"{address.get('streetAddress', '')}, {address.get('addressLocality', '')}, {address.get('addressRegion', '')} {address.get('postalCode', '')}"
        except json.JSONDecodeError:
            continue
    return None

def extract_addresses(html):
    address_pattern = re.compile(
        r'\d{1,5}\s+\w+\s+(Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Square|Sq|Parkway|Pkwy|Circle|Cir)\b[^\d]*\d{5}(?:-\d{4})?',
        re.IGNORECASE
    )
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ')
    full_addresses = [match[0] for match in address_pattern.finditer(text)]
    return list(set(full_addresses))

def get_social_media_links(html, base_url, business_name):
    soup = BeautifulSoup(html, 'html.parser')
    social_patterns = {
        'facebook': r'facebook\.com',
        'instagram': r'instagram\.com',
        'twitter': r'twitter\.com',
        'linkedin': r'linkedin\.com',
        'youtube': r'youtube\.com',
        'tiktok': r'tiktok\.com',
        'pinterest': r'pinterest\.com'
    }
    
    social_links = {platform: set() for platform in social_patterns}
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        for platform, pattern in social_patterns.items():
            if re.search(pattern, href, re.I):
                full_url = urljoin(base_url, href)
                social_links[platform].add(full_url)
    
    # Filter and score the links
    filtered_links = {}
    for platform, links in social_links.items():
        if links:
            best_link, best_score = max(
                ((link, calculate_similarity(link, business_name)) for link in links),
                key=lambda x: x[1]
            )
            if best_score > 0.3:  # Adjust this threshold as needed
                filtered_links[platform] = best_link
    
    return filtered_links

def calculate_similarity(url, business_name):
    # Extract the relevant part of the URL (usually the last part of the path)
    url_part = url.split('/')[-1].lower()
    business_name = business_name.lower()
    
    # Remove common words that might not be part of the business name in social media handles
    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of'}
    url_words = set(re.findall(r'\w+', url_part)) - common_words
    business_words = set(re.findall(r'\w+', business_name)) - common_words
    
    # Calculate Jaccard similarity
    intersection = len(url_words & business_words)
    union = len(url_words | business_words)
    jaccard_sim = intersection / union if union > 0 else 0
    
    # Calculate sequence similarity
    seq_sim = SequenceMatcher(None, url_part, business_name).ratio()
    
    # Combine the two similarity measures (you can adjust the weights)
    combined_sim = (jaccard_sim * 0.7) + (seq_sim * 0.3)
    
    return combined_sim

def enrich_lead(lead):
    print(f"\nStarting enrichment for lead: {lead['name']}")
    
    business_name = lead['name']
    address = lead['source_attributes']['formatted_address']
    phone = lead['business_phone']
    website = lead['source_attributes'].get('website', '')

    print(f"Initial data: Name: {business_name}, Address: {address}, Phone: {phone}, Website: {website}")

    if not website:
        website = find_domain(business_name)
        print(f"Found website: {website}")
    
    print("Getting public emails...")
    public_emails = GetPublicEmails(website)
    print(f"Found {len(public_emails)} public emails")

    print("Getting relevant pages...")
    relevant_links = get_relevant_pages(business_name, website)
    print(f"Found {len(relevant_links)} relevant links")

    print("Scraping pages...")
    scraped_pages = scrape_pages(relevant_links)
    print(f"Scraped {len(scraped_pages)} pages")

    # Extract all information from scraped pages
    all_emails = set()
    all_phones = set()
    all_social_links = {}

    for html in scraped_pages:
        all_emails.update(extract_emails_from_html(html, get_email_domain(website)))
        all_phones.update(extract_phone_numbers(html))
        all_social_links.update(get_social_media_links(html, website, business_name))

    print("Finding decision maker info...")
    decision_maker_info = find_decision_maker(business_name, website, scraped_pages)
    print(f"Decision maker info: {decision_maker_info}")

    lead['business_email'] = list(all_emails)[0] if all_emails else None
    lead['business_phone'] = phone or (list(all_phones)[0] if all_phones else None)
    lead['decision_maker_name'] = decision_maker_info.get('name')
    lead['decision_maker_linkedin'] = decision_maker_info.get('linkedin')
    lead['decision_maker_email'] = decision_maker_info.get('email')
    lead['decision_maker_phone'] = decision_maker_info.get('phone')
    lead['source_attributes']['website'] = website
    lead['source_attributes']['social_media'] = all_social_links

    print("Enrichment completed. Updated lead data:")
    print(json.dumps(lead, indent=2))

    return lead

def get_relevant_pages(business_name, website):
    print(f"Getting relevant pages for {business_name} at {website}")
    relevant_links = [website]
    
    # First, try to find important pages on the company's website
    important_paths = ['about', 'contact', 'team', 'our-story', 'faq']
    for path in important_paths:
        url = urljoin(website, path)
        if check_url_exists(url):
            relevant_links.append(url)
    
    # If we don't have enough links, perform a limited Google search
    if len(relevant_links) < 3:
        try:
            additional_links = get_top_google_search_links(f'site:{website}', num_results=2)
            relevant_links.extend(additional_links)
        except Exception as e:
            print(f"Error getting additional links: {str(e)}")
    
    relevant_links = list(set(relevant_links))  # Remove duplicates
    print(f"Found {len(relevant_links)} relevant links")
    return relevant_links

def check_url_exists(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def scrape_pages(relevant_links):
    scraped_pages = {}
    for link in relevant_links:
        html = get_website_html(link)
        scraped_pages[link] = {
            'html': html,
            'text': html_to_text(html)
        }
    return scraped_pages

def find_decision_maker(business_name, website, scraped_pages):
    decision_maker = {
        'name': None,
        'linkedin': None,
        'email': None,
        'phone': None
    }
    combined_text = "\n".join([page_data['text'] for page_data in scraped_pages.values()])
    gpt_prompt = f"Extract the name, LinkedIn profile, email, and phone number of a key decision maker (e.g., CEO, Founder, or Manager) for the company {business_name} from the following text:\n\n{combined_text}"
    gpt_response = CallGPT([{"role": "user", "content": gpt_prompt}])
    parsed_response = parse_gpt_response(gpt_response)
    decision_maker.update(parsed_response)
    if not decision_maker['email'] and decision_maker['name']:
        email_domain = get_email_domain(website)
        decision_maker['email'] = generate_email(decision_maker['name'], email_domain)
    return decision_maker

def parse_gpt_response(gpt_response):
    parsed = {
        'name': None,
        'linkedin': None,
        'email': None,
        'phone': None
    }
    lines = gpt_response.split('\n')
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            if key in parsed:
                parsed[key] = value
    return parsed

def generate_email(name, domain):
    first_name, last_name = name.split(' ', 1)
    email_formats = [
        f"{first_name.lower()}@{domain}",
        f"{first_name[0].lower()}{last_name.lower()}@{domain}",
        f"{first_name.lower()}.{last_name.lower()}@{domain}",
        f"{last_name.lower()}{first_name[0].lower()}@{domain}"
    ]
    return email_formats[0]

def enrich_leads(leads):
    enriched_leads = []
    for i, lead in enumerate(leads):
        print(f"\nProcessing lead {i+1} of {len(leads)}")
        try:
            enriched_lead = enrich_lead(lead)
            enriched_leads.append(enriched_lead)
        except Exception as e:
            print(f"Error enriching lead {lead['name']}: {str(e)}")
            print("Traceback:")
            import traceback
            traceback.print_exc()
    return enriched_leads

def get_emails_from_google(emaildomain):
    print(f"Searching Google for emails with domain: {emaildomain}")
    query = f"@{emaildomain}"
    search_results = get_top_google_search_links(query, num_results=10)
    
    emails = []
    for result in search_results:
        try:
            html = get_website_html(result)
            page_emails = extract_emails_from_html(html)
            emails.extend([email for email in page_emails if email.endswith(emaildomain)])
        except Exception as e:
            print(f"Error extracting emails from {result}: {str(e)}")
    
    emails = list(set(emails))  # Remove duplicates
    print(f"Found {len(emails)} unique emails from Google search")
    return emails

# Usage
if __name__ == "__main__":
    path = "testleads.json"
    leads = [
   {
      "name":"Break Your Fast",
      "source":"Google Maps",
      "external_id":"ChIJgQ6GjmGVj4ARUtNoph98p30",
      "business_phone":"+1 510-324-8599",
      "business_email":None,
      "decision_maker_name":None,
      "decision_maker_linkedin":None,
      "decision_maker_email":None,
      "decision_maker_phone":None,
      "source_attributes":{
         "formatted_address":"1688 Decoto Rd, Union City, CA 94587, USA",
         "website":"http://www.breakyourfast510.com/",
         "rating":4.3,
         "user_ratings_total":380
      }
   },
   {
      "name":"Thai Bangkok Cuisine",
      "source":"Google Maps",
      "external_id":"ChIJmxBXOUS0j4ARbvRDJAlCdUs",
      "business_phone":"+1 669-342-7300",
      "business_email":None,
      "decision_maker_name":None,
      "decision_maker_linkedin":None,
      "decision_maker_email":None,
      "decision_maker_phone":None,
      "source_attributes":{
         "formatted_address":"21670 Stevens Creek Blvd, Cupertino, CA 95014, USA",
         "website":"https://www.thaibangkokcuisineca.com/",
         "rating":4.2,
         "user_ratings_total":263
      }
   },
   {
      "name":"Duarte's Tavern",
      "source":"Google Maps",
      "external_id":"ChIJgxElIjQHj4ARHW9wyBWSwVI",
      "business_phone":"+1 650-879-0464",
      "business_email":None,
      "decision_maker_name":None,
      "decision_maker_linkedin":None,
      "decision_maker_email":None,
      "decision_maker_phone":None,
      "source_attributes":{
         "formatted_address":"202 Stage Rd, Pescadero, CA 94060, USA",
         "website":"http://www.duartestavern.com/",
         "rating":4.3,
         "user_ratings_total":1425
      }
   },
   {
      "name":"Terra Mia",
      "source":"Google Maps",
      "external_id":"ChIJU2_rcm_nj4ARCElXTmEXea8",
      "business_phone":"+1 925-456-3333",
      "business_email":None,
      "decision_maker_name":None,
      "decision_maker_linkedin":None,
      "decision_maker_email":None,
      "decision_maker_phone":None,
      "source_attributes":{
         "formatted_address":"4040 East Ave, Livermore, CA 94550, USA",
         "website":"http://www.terramialivermore.com/",
         "rating":4.4,
         "user_ratings_total":480
      }
   },
    ]

    enriched_leads = enrich_leads(leads)

    # Save enriched leads to a new JSON file
    with open('enriched_leads.json', 'w') as f:
        json.dump(enriched_leads, f, indent=2)