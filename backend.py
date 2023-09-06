import requests
import time
from bs4 import BeautifulSoup
import re
import urllib.parse
import pandas as pd
import io
from flask import Flask, request, send_file, jsonify, make_response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GEONAMES_USERNAME = "pranav1801"
unique_bakeries_set = set()

def infoScrapper(query, bakery_name):
    url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    email = ""
    website_url = "No Website"
    instagram_url = "-"
    facebook_url = "-"
    linkedin_url = "-"
    most_relevant_website = ""

    # Social links can be handled in a more efficient way
    social_links = {"instagram.com": instagram_url, "facebook.com": facebook_url, "linkedin.com": linkedin_url}
    
    website_url_tag = soup.find("div", class_="yuRUbf")
    most_relevant_website = website_url_tag.a["href"] if website_url_tag else None

    for link in soup.find_all("a"):
        website_url_temp = link.get("href")
        if website_url_temp:
            parsed_uri = urllib.parse.urlparse(website_url_temp)
            domain = '{uri.netloc}'.format(uri=parsed_uri)
            words_in_bakery_name = prepare_string_for_comparison(bakery_name)

            # Efficiently handle social links
            for social, url in social_links.items():
                if social in website_url_temp:
                    social_links[social] = website_url_temp
                    break

            if is_valid_website_url(domain, words_in_bakery_name):
                website_url = website_url_temp
                break

    email_regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    page_text = soup.get_text()
    email_match = re.search(email_regex, page_text)
    if email_match:
        email = email_match.group()

    # Retrieve the social links
    instagram_url, facebook_url, linkedin_url = social_links.values()

    return website_url, email, instagram_url, facebook_url, linkedin_url, most_relevant_website

def prepare_string_for_comparison(string):
    # Convert to lowercase and split into words
    return string.lower().split()

def is_valid_website_url(url, company_name):
    # Remove "https://" and "www." from the URL
    url = url.replace("https://", "").replace("www.", "")
    
    # Split the URL by "/"
    url_parts = url.split("/")
    
    # Consider the first part and check if it contains any word from the company name
    for word in company_name:
        if word.lower() in url_parts[0].lower() and len(word) > 1:
            return True
    
    return False


def fetch_bakeries(business_type, business_location):
    bakery_data = []
    base_url = "https://maps.googleapis.com/maps/api/place/"
    api_key = "AIzaSyCaA0nEwnBY2xRlNUBAJ-xK4FzohVGiIdA"
    try:
        place_query = urllib.parse.quote_plus(f"{business_type} in {business_location}")
        url = f"{base_url}textsearch/json?query={place_query}&key={api_key}"
        while True:
            response = requests.get(url)
            data = response.json()
            results = data['results']
            for bakery in results:
                bakery_name = bakery['name']
                bakery_type = ", ".join(bakery['types'])
                place_id = bakery['place_id']
                details_url = f"https://maps.googleapis.com/maps/api/place/details/json?placeid={place_id}&key={api_key}"
                details_response = requests.get(details_url)
                details_data = details_response.json()
                address = details_data['result'].get('formatted_address', 'No address')
                phone_number = details_data['result'].get('formatted_phone_number', 'No phone number')
                bakery_data.append((bakery_name, address, bakery_type, phone_number))
            if 'next_page_token' in data:
                next_page_token = data['next_page_token']
                url = f"{base_url}textsearch/json?pagetoken={next_page_token}&key={api_key}"
                time.sleep(2)
            else:
                break
    except Exception as e:
        print(f"An error occurred: {e}")
    return bakery_data


def get_geoname_id_from_location(location_name):
    base_url = f"http://api.geonames.org/search?name={location_name}&maxRows=1&username={GEONAMES_USERNAME}"
    response = requests.get(base_url)
    soup = BeautifulSoup(response.text, "xml")
    geoname_id = soup.find('geonameId')
    return geoname_id.text

def get_subregions_of_location(location_id):
    base_url = f"http://api.geonames.org/children?geonameId={location_id}&username={GEONAMES_USERNAME}"
    response = requests.get(base_url)
    soup = BeautifulSoup(response.text, "xml")
    subregions = []
    for city in soup.find_all('geoname'):
        subregions.append(city.find('name').text)
    return subregions


def main(business_type, business_location):
    df = pd.DataFrame(columns=['Bakery Name', 'Address', 'Bakery Type', 'Phone Number', 'Email', 'Instagram', 'Facebook', 'LinkedIn', 'Website URL', 'Most Relevant Website'])
    geoname_id = get_geoname_id_from_location(business_location)
    subregions = get_subregions_of_location(geoname_id)
    if business_location not in subregions:
        subregions.append(business_location)
    print(subregions)
    for subregion in subregions:
        bakery_data = fetch_bakeries(business_type, subregion)
        for bakery_name, address, bakery_type, phone_number in bakery_data:
            if bakery_name in unique_bakeries_set:
                continue
            unique_bakeries_set.add(bakery_name)
            
            try:
                query = bakery_name + " " + address
                business_name = bakery_name
                website_url, email, facebook_link, instagram_link, linkedin_link, most_relevant_website = infoScrapper(query, business_name)
            except Exception as e:
                print(f"Failed to scrape info for {query}: {e}")
                continue
            
            row_data = [bakery_name, address, bakery_type, phone_number, email, facebook_link, instagram_link, linkedin_link, website_url, most_relevant_website]
            df.loc[len(df)] = row_data
    
    return df

@app.route('/fetch_bakeries', methods=['POST'])
def fetch_bakeries_api():
    request_data = request.get_json()
    business_type = request_data['business_type']
    business_locations = request_data['business_locations']
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for business_location in business_locations:
            df = main(business_type, business_location)
            df.to_excel(writer, sheet_name=f"{business_location}", index=False)
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=output.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return response

if __name__ == '__main__':
    app.run(debug=True)
