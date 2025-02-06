import json
import re

# Load JSON data from file
with open('updated_urls_with_dois.json', 'r') as file:
    data = json.load(file)

# Define regular expression patterns to match DOIs and PMIDs
doi_pattern = r"10\.\d{4,9}/[^/]+"
pmid_pattern = r"pmid=(\d+)"
pubmed_url_pattern = r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/"


# Function to extract DOI or PMID from a URL
def extract_doi_or_pmid(url):
    doi_match = re.search(doi_pattern, url, re.IGNORECASE)
    pmid_match = re.search(pmid_pattern, url, re.IGNORECASE)
    pubmed_match = re.search(pubmed_url_pattern, url, re.IGNORECASE)

    if doi_match:
        return {'doi': doi_match.group()}
    elif pmid_match:
        return {'pubmedID': pmid_match.group(1)}
    elif pubmed_match:
        return {'pubmedID': pubmed_match.group(1)}
    return None


# Iterate over each entry in the data
for entry in data:
    # Extract DOI and PMID from 'publication_url'
    publication_url = entry.get("publication_url")
    if publication_url and isinstance(publication_url, str):
        doi_match = re.search(doi_pattern, publication_url, re.IGNORECASE)
        if doi_match:
            entry['doi'] = doi_match.group()
        pmid_match = re.search(pmid_pattern, publication_url, re.IGNORECASE)
        if pmid_match:
            entry['pmid:'] = pmid_match.group(1)

    # Iterate over external links to extract DOI or PMID from 'href' field
    external_links = entry.get("external_links", [])
    for link in external_links:
        href = link.get("href")
        if href and isinstance(href, str):
            extracted_info = extract_doi_or_pmid(href)
            if extracted_info:
                # Add the extracted DOI or PMID under the link dictionary
                link.update(extracted_info)

# Write the updated JSON data back to a file
with open('wordpress_filtered.json', 'w') as outfile:
    json.dump(data, outfile, indent=4)

# Optionally, print the updated data to check the results
for entry in data:
    print(entry)
