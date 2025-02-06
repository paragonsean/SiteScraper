import json
import re



def load_and_extract(json_file_path):
    # Open the large JSON file and process it
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Initialize the extracted data list
    extracted_data = []
    counter = 1
    # Regex pattern to capture lines mentioning publication names or journals
    publication_pattern = re.compile(r"(published in|published)\s+([A-Za-z\s]+)", re.IGNORECASE)

    # Iterate through each entry in the JSON list
    for entry in data:
        # Extract the required fields
        date_gmt = entry.get("date_gmt", "")
        modified_gmt = entry.get("modified_gmt", "")
        link = entry.get("link", "")
        titles = entry.get("title", {})
        text_title = titles.get("text", "")
        # Extract the content HTML and look for the last relevant publication line
        content_html = entry.get("content", {}).get("html", "")
        last_publication_line = ""
        html_array = []
        # Search for lines in the HTML that mention "published in"
        for line in content_html.splitlines():
            line.split("</p>")
            html_array.append(line)



            external_links = entry.get("links", {}).get("external", [])
        my_str = ' '.join(html_array)
        html_array = my_str.split(" ")
        html_array = html_array[-15:]
        my_str = ' '.join(html_array)

        last_external_link = external_links[-1] if external_links else {}
        clean_text = re.sub(r'<.*?>', '', my_str)
        title = entry.get("title", {}).get("rendered", "")
        last_publication_line = extract_sentence(clean_text,"<p>","<a href=")
        if modified_gmt == date_gmt:
            modified_gmt = "not modified"
        else :
            modified_gmt = f'the article was modified on {modified_gmt}'

        # Structure the extracted information
        result = {
            "index": counter,
            "title": text_title,
            "date_gmt": date_gmt,
            "modified_gmt": modified_gmt,
            "url": link,
            "publication_line": last_publication_line,
            "publication_url": last_external_link.get("href", ""),
            "external_links": external_links,
        }

        # Add the result to the extracted data list
        extracted_data.append(result)
        counter += 1
    return extracted_data

import json
import re

# Load JSON data from file
with open('posts.json', 'r') as file:
    data = json.load(file)

# Define a regular expression pattern to match DOIs
doi_pattern = r"10\.\d{4,9}/[-._;()/:A-Z0-9]+"

# Extract DOIs
dois = []
for entry in data:
    if "publication_url" in entry:
        match = re.search(doi_pattern, entry["publication_url"], re.IGNORECASE)
        if match:
            dois.append(match.group())

# Print the extracted DOIs
print(dois)


def extract_sentence(text, start_str, end_str):
    # Use a regular expression to find "publish" or "republish" within words
    match = re.search(r'\b(publish|republish)\b', text, re.IGNORECASE)
    if match:
        index = match.start()
        publish_sentence = text[index:]
    else:
        publish_sentence = text

    return publish_sentence

# Save the extracted information to a file

ouput_file = "urls_with_info.json"
# Example usage
json_file_path = "posts.json"
extracted_info = load_and_extract(json_file_path)
with open("urls_with_info.json", "w", encoding="utf-8") as output_file:
    json.dump(extracted_info, output_file, indent=4)
# Process or display the extracted information as needed
for info in extracted_info:
    print(info)
