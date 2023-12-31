import requests
import time
from bs4 import BeautifulSoup
import re
import urllib.parse
import pandas as pd
import io
import base64
from flask import Flask, request, send_file, jsonify, make_response
from flask_cors import CORS
from threading import Thread, Lock

app = Flask(__name__)
cors = CORS(app, resources={r"/*": {"origins": "*"}})

GEONAMES_USERNAME = "pranav1801"
free_trial_bakeries = 20
df_lock = Lock()
unique_bakeries_lock = Lock()


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
    api_key = "AIzaSyCb6FZ9JPihatKLxgXdjCk0DQfqhKjJ31A"
    try:
        place_query = urllib.parse.quote_plus(f"{business_type} in {business_location}")
        url = f"{base_url}textsearch/json?query={place_query}&key={api_key}"
        while True:
            response = requests.get(url)
            data = response.json()
            # print(data)
            results = data['results']
            for bakery in results:
                bakery_name = bakery['name']
                bakery_type = ", ".join(bakery['types'])
                place_id = bakery['place_id']
                details_url = f"https://maps.googleapis.com/maps/api/place/details/json?placeid={place_id}&key={api_key}"
                details_response = requests.get(details_url)
                details_data = details_response.json()
                address = details_data['result'].get('formatted_address', 'No address')
                if business_location not in address:
                    address = "Not Found"
                phone_number = details_data['result'].get('formatted_phone_number', 'No phone number')
                bakery_data.append((bakery_name, address, bakery_type, phone_number))
            if 'next_page_token' in data:
                next_page_token = data['next_page_token']
                url = f"{base_url}textsearch/json?pagetoken={next_page_token}&key={api_key}"
            else:
                break
    except Exception as e:
        print(f"An error occurred: {e}")
    return bakery_data


def get_geoname_id_from_location(location_name):
    base_url = f"http://api.geonames.org/search?name={location_name}&maxRows=1&username={GEONAMES_USERNAME}"
    response = requests.get(base_url)
    if (not response.ok):
        return "error"
    
    try:
        soup = BeautifulSoup(response.text, "xml")
        geoname_id = soup.find('geonameId')
        return_val = geoname_id.text
        return return_val
    except:
        return "error"


def get_population_from_osm(place_name):
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    overpass_query = f"""
    [out:json];
    area["name"="{place_name}"]->.searchArea;
    (
        node["name"="{place_name}"]["population"](area.searchArea);
        way["name"="{place_name}"]["population"](area.searchArea);
        relation["name"="{place_name}"]["population"](area.searchArea);
    );
    out body;
    """
    response = requests.get(overpass_url, params={'data': overpass_query})
    if (not response.ok):
        return 0
    
    try:

        data = response.json()
        
        for element in data['elements']:
            if 'tags' in element and 'population' in element['tags']:
                return float(element['tags']['population'])
        
        return 0 
    
    except:
        return 0

def get_subregions_of_location(location_id):
    base_url = f"http://api.geonames.org/children?geonameId={location_id}&username={GEONAMES_USERNAME}"
    subregions = []
    response = requests.get(base_url)
    if (not response.ok):
        return subregions
    
    try:
        soup = BeautifulSoup(response.text, "xml")
        for city in soup.find_all('geoname'):
            city_name = city.find('name').text
            population = get_population_from_osm(city_name)
            subregions.append((city_name, population))

        # print(subregions)
        sorted_subregions = [name for name, population in sorted(subregions, key=lambda x: x[1], reverse=True)]
        return sorted_subregions
    
    except:
        return subregions


def process_subregion(business_type, subregion, num_lines, fetch_all, output_df):
    bakery_data = fetch_bakeries(business_type, subregion)
    for bakery_name, address, bakery_type, phone_number in bakery_data:
        with unique_bakeries_lock:
            if bakery_name in unique_bakeries_set:
                continue
            unique_bakeries_set.add(bakery_name)
        print(len(unique_bakeries_set))
        if not fetch_all and len(unique_bakeries_set) > free_trial_bakeries:
            continue
        if fetch_all and len(output_df) >= int(num_lines):
            # print("hello")
            break
        try:
            query = bakery_name + " " + address
            business_name = bakery_name
            website_url, email, facebook_link, instagram_link, linkedin_link, most_relevant_website = infoScrapper(query, business_name)
        except Exception as e:
            # print(f"Failed to scrape info for {query}: {e}")
            continue
        row_data = [bakery_name, subregion, address, bakery_type, phone_number, email, facebook_link, instagram_link, linkedin_link, website_url, most_relevant_website]
        with df_lock:
            output_df.loc[len(output_df)] = row_data
            

def main(business_type, business_location, num_lines, fetch_all=True):
    global unique_bakeries_set
    unique_bakeries_set = set()
    output_df = pd.DataFrame(columns=['businessName', 'subRegion', 'address', 'type', 'phoneNumber', 'email', 'instagram', 'facebook', 'linkedIn', 'websiteBusiness', 'websiteRelevant'])
    geoname_id = get_geoname_id_from_location(business_location)
    subregions = []
    if geoname_id != "error":
        subregions = get_subregions_of_location(geoname_id)
        
    if business_location not in subregions:
        subregions.insert(0, business_location)

    threads = []
    print(subregions)
    for subregion in subregions:
        if fetch_all and len(output_df) >= int(num_lines):
            break
        thread = Thread(target=process_subregion, args=(business_type, subregion, num_lines, fetch_all, output_df))
        thread.start()
        threads.append(thread)
        
    for thread in threads:
        thread.join()

    return output_df

@app.route('/fetch_bakeries', methods=['POST'])
def fetch_bakeries_api():
    request_data = request.get_json()
    business_type = request_data['business_type']
    business_locations = request_data['business_locations']
    lines_requested = request_data['num_lines']
    business_locations = [city.split(',')[0].strip() for city in business_locations]
    output = io.BytesIO()
    num_locations = len(business_locations)
    start_lines = lines_requested / num_locations
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for business_location in business_locations:
            df = main(business_type, business_location, start_lines)
            if (len(df) == 0):
                continue
            num_locations = num_locations - 1
            if num_locations != 0:
                lines_requested = lines_requested - len(df)
                start_lines = lines_requested / num_locations
            df.to_excel(writer, sheet_name=f"{business_location}", index=False)
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=output.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return response

@app.route('/free_trial', methods=['POST'])
def free_trial():
    request_data = request.get_json()
    business_type = request_data['business_type']
    business_locations = request_data['business_locations']
    business_locations = [city.split(',')[0].strip() for city in business_locations]
    lines_requested = request_data['num_lines']
    lines_found = 0
    output = io.BytesIO()
    print(business_locations)
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for business_location in business_locations:
            df = main(business_type, business_location, lines_requested, fetch_all=False)
            if (len(df) == 0):
                continue
            lines_found = lines_found + len(unique_bakeries_set)
            df.to_excel(writer, sheet_name=f"{business_location}", index=False)
    
    output.seek(0)
    base64_excel = base64.b64encode(output.getvalue()).decode('utf-8')
    response_data = {
        'file': base64_excel,
        'unique_bakeries_count': lines_found
    }
    unique_bakeries_set.clear()
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)