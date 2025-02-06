import json
import logging
import requests_cache
from tqdm import tqdm

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize cache
requests_cache.install_cache('openalex_cache', expire_after=3600)  # Cache expires after 1 hour

def get_paper_metadata(client, doi=None, url=None):
    """
    Fetch metadata of a paper from OpenAlex API using DOI or URL.
    It handles retries if a 429 error is encountered and caches responses to avoid redundant API calls.
    """
    if not any([doi, url]):
        raise ValueError("At least one of 'doi' or 'url' must be provided.")
    
    # Build the API URL
    if doi:
        doi = doi.replace("https://doi.org/", "")
        api_url = f"https://api.openalex.org/works/doi:{doi}"
    elif url:
        api_url = f"https://api.openalex.org/works/doi:{url}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0"
    }
    logger.info(api_url)
    
    try:
        response = client.get(api_url, headers=headers)
        # Check if the response was retrieved from cache
        if response.from_cache:
            logger.info("Response retrieved from cache.")
        else:
            logger.info("Response retrieved from the API.")
        
        if response.status_code == 200:
            metadata = response.json()
            doi = metadata.get("doi", None)
            if doi:
                doi = doi[len("https://doi.org/"):]
            
            # Return metadata, including cited_by_api_url, counts_by_year, updated_date, created_date
            return {
                "openalex_id": metadata.get("id","No Id"),
                "title": metadata.get("display_name", "No Title Available"),
                "first_author": metadata["authorships"][0]["author"]["display_name"] if metadata.get("authorships") else "No Author",
                "authors": ", ".join([author["author"]["display_name"] for author in metadata.get("authorships", [])]),
                "year": metadata.get("publication_year", "Unknown Year"),
                "doi": doi,
                "journal": metadata.get("host_venue", {}).get("display_name", "Unknown Journal"),
                "pages": f"{metadata['biblio'].get('first_page', '')}-{metadata['biblio'].get('last_page', '')}",
                "volume": metadata["biblio"].get("volume", ""),
                "number": metadata["biblio"].get("issue", ""),
                "referenced_works_count": metadata.get("referenced_works_count", 0),  # Get referenced works count
                "referenced_works": metadata.get("referenced_works", []),  # Get list of referenced works
                "cited_by_api_url": metadata.get("cited_by_api_url", ""),  # Get cited_by_api_url
                "counts_by_year": metadata.get("counts_by_year", []),  # Get counts by year
                "updated_date": metadata.get("updated_date", ""),  # Get updated date
                "created_date": metadata.get("created_date", ""),  # Get created date
                "queried_indexes": []  # This will store the indices of articles querying the same DOI or author
            }
        elif response.status_code == 429:
            logger.warning(f"Rate limit exceeded for {doi or url}. Retrying after a brief delay...")
            return None
        else:
            logger.error(f"Error: Received status code {response.status_code} for {doi or url}")
            logger.info(response)
            return None
    except Exception as e:
        logger.error(f"Error fetching metadata for {doi or url}: {str(e)}")
        return None

def process_article_batch(client, article_batch, processed_papers, no_match_articles, key, subkey, doi_key, doi_subkey):
    """
    Process a batch of articles and fetch metadata for each paperlink.
    If a paper is already processed, we don't add it again but append the index to 'queried_indexes'.
    """
    first_response_printed = False

    for article in article_batch:
        try:
            index = article.get('index')  # Get the index from the input JSON
            if index is None:
                logger.warning(f"Article missing 'index' field: {article}")
                continue

            # Check if the key points to a list
            data_value = article.get(key)
            if isinstance(data_value, list):
                # Process each element in the list
                for element in data_value:
                    if isinstance(element, dict) and doi_subkey in element:
                        doi_key_or_url = element[doi_subkey]
                        
                        # Check if the paper is already in processed_papers
                        if doi_key_or_url in processed_papers:
                            # Append the index to 'queried_indexes' if already exists
                            processed_papers[doi_key_or_url]['queried_indexes'].append(index)
                        else:
                            paper_data = get_paper_metadata(client, url=doi_key_or_url)
                            if paper_data:
                                if not first_response_printed:
                                    logger.info("First response:")
                                    logger.info(paper_data)
                                    first_response_printed = True
                                
                                # Add paper metadata and the index
                                processed_papers[doi_key_or_url] = paper_data
                                processed_papers[doi_key_or_url].setdefault('queried_indexes', []).append(index)
                            else:
                                no_match_articles.append({'index': index, 'url': doi_key_or_url})
            else:
                # If the key points to a dict, process it
                doi = article.get(doi_key)
                if isinstance(doi, dict) and doi_subkey in doi:
                    doi_key_or_url = doi[doi_subkey]
                    
                    # Check if the paper is already in processed_papers
                    if doi_key_or_url in processed_papers:
                        # Append the index to 'queried_indexes' if already exists
                        processed_papers[doi_key_or_url]['queried_indexes'].append(index)
                    else:
                        paper_data = get_paper_metadata(client, doi=doi_key_or_url)
                        if paper_data:
                            if not first_response_printed:
                                logger.info("First response:")
                                logger.info(paper_data)
                                first_response_printed = True
                            
                            # Add paper metadata and the index
                            processed_papers[doi_key_or_url] = paper_data
                            processed_papers[doi_key_or_url].setdefault('queried_indexes', []).append(index)
                        else:
                            no_match_articles.append({'index': index, 'doi': doi_key_or_url})
        except Exception as e:
            logger.error(f"Error processing article with index {article.get('index')}: {e}")


def run_openalex_process():
    """
    Process the articles from a JSON file, fetch metadata, and save results.
    """
    articleinfos_path = input("Enter the input JSON file name (e.g., 'updated_urls_with_dois_and_pmids.json'): ") or "updated_urls_with_dois_and_pmids.json"
    output_path = input("Enter the output JSON file name (e.g., 'processed_papers.json'): ") or "updated_urls_with_dois_and_pmids_metadata.json"
    key = input("Enter the key to look for (e.g., 'external_links'): ") or "external_links"
    subkey = input("Enter the subkey to look for (e.g., 'href'): ") or "href"
    doi_key = input("Enter the DOI key to look for (e.g., 'doi'): ") or "doi"
    doi_subkey = input("Enter the DOI subkey to look for (e.g., 'doi'): ") or "doi"
    
    # Ask how many articles to scrape
    num_articles = input("How many articles would you like to scrape? (Enter a number or 'all' for all articles): ").strip()
    
    with open(articleinfos_path, 'r') as f:
        articles = json.load(f)
    
    if num_articles.lower() != 'all':
        try:
            num_articles = int(num_articles)
            articles = articles[:num_articles]  # Slice the list to the number of articles requested
        except ValueError:
            print("Invalid input. Please enter a valid number or 'all'.")
            return
    
    processed_papers = {}  # Initialize dict to store processed papers
    no_match_articles = []  # List to store articles with no match

    batch_size = 50  # Process 50 articles per batch
    
    # Use tqdm to show progress
    with requests_cache.CachedSession() as client:  # Use a CachedSession
        i = 0
        for i in tqdm(range(0, len(articles), batch_size), desc="Processing batches"):
            article_batch = articles[i:i + batch_size]
            logger.info(f"Processing batch {i + 1} to {i + batch_size}")

            try:
                process_article_batch(client, article_batch, processed_papers, no_match_articles, key, subkey, doi_key, doi_subkey)
            except Exception as e:
                logger.error(f"Error processing batch: {e}")

    # Save the final processed papers to the output file
    with open(output_path, 'w') as f:
        json.dump(list(processed_papers.values()), f, indent=4)

    # Save the no match articles to a separate file
    with open('no_match_articles.json', 'w') as f:
        json.dump(no_match_articles, f, indent=4)

    logger.info(f"Paper metadata saved to {output_path}")
    logger.info(f"No match articles saved to no_match_articles.json")


if __name__ == "__main__":
    run_openalex_process()
