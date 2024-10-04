import csv
import json

def read_leads_from_csv(filename):
    leads = []
    with open(filename, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Convert the stringified 'source_attributes' to a dictionary
            if 'source_attributes' in row:
                try:
                    row['source_attributes'] = json.loads(row['source_attributes'])
                except json.JSONDecodeError:
                    # Handle case where JSON decoding fails
                    continue
            leads.append(row)
    return leads

def filter_leads_with_empty_website(leads):
    # Filter leads where 'websites' in 'source_attributes' is an empty string
    filtered_leads = [lead for lead in leads if lead['source_attributes'].get('website') == '']
    return filtered_leads

def save_filtered_leads_to_csv(filtered_leads, output_filename):
    if filtered_leads:
        print(f"Saving {len(filtered_leads)} leads to {output_filename}...")
        
        # Define the columns we want in the output CSV
        fieldnames = ['name', 'business_phone', 'formatted_address']

        with open(output_filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            for lead in filtered_leads:
                # Extract only the required fields
                new_row = {
                    'name': lead.get('name', ''),
                    'business_phone': lead.get('business_phone', ''),
                    'formatted_address': lead['source_attributes'].get('formatted_address', '')
                }
                writer.writerow(new_row)
        
        print(f"Leads successfully saved to {output_filename}")
    else:
        print("No leads to save.")

# Example usage:
input_filename = 'leads_rows.csv'  # replace 'leads.csv' with the path to your CSV file
output_filename = 'filtered_leads.csv'  # output file name

leads = read_leads_from_csv(input_filename)
print(f"Number of total leads: {len(leads)}")

filtered_leads = filter_leads_with_empty_website(leads)
print(f"Number of filtered leads: {len(filtered_leads)}")

save_filtered_leads_to_csv(filtered_leads, output_filename)
