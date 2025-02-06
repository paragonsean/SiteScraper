import aiohttp
import asyncio
import logging
from typing import Any, List, Optional, Tuple, Union,Set
from tqdm import tqdm
import json
from urllib.parse import urlsplit, urlunsplit
import math
import aiofiles
from bs4 import BeautifulSoup
import csv
from aiohttp_client_cache import CachedSession, SQLiteBackend

# Utility functions
async def get_total_pages(session, base_url):
    """Get total pages available from WordPress API."""
    url = url_path_join(base_url, "wp-json/wp/v2/posts?_embed&per_page=100&page=1")
    async with session.get(url) as response:
        if response.status != 200:
            logging.error(f"Failed to retrieve the total number of pages: {response.status}")
            return 0

        total_pages = response.headers.get('X-WP-TotalPages')
        return int(total_pages) if total_pages else 0

def url_path_join(*parts: str) -> str:
    """Joins URL path components intelligently."""
    schemes, netlocs, paths, queries, fragments = zip(*(urlsplit(part) for part in parts))
    scheme = first(schemes)
    netloc = first(netlocs)
    path = "/".join(x.strip("/") for x in paths if x)
    query = first(queries)
    fragment = first(fragments)
    return urlunsplit((scheme, netloc, path, query, fragment))

def first(sequence: Union[List[str], Tuple[str]], default: str = "") -> str:
    """Returns the first non-empty item in a sequence or a default value if none is found."""
    return next((x for x in sequence if x), default)

async def get_content_as_json(response_obj) -> Any:
    """Parses the response content as JSON."""
    content = await response_obj.read()
    if content[:3] == b"\xef\xbb\xbf":  # UTF-8 BOM
        content = content.decode("utf-8-sig")
    else:
        content = content.decode("utf-8")
    return json.loads(content)

def clean_html_content(html_content: str) -> str:
    """Cleans the HTML content by removing ads, scripts, and unnecessary tags."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove ad divs, script tags, and other unwanted elements
    for ad_div in soup.find_all("div", class_="ad-slot--container"):
        ad_div.decompose()
    for script in soup.find_all("script"):
        script.decompose()

    # Return cleaned text
    return soup.get_text(separator=" ", strip=True)

def extract_links(html_content: str, base_url: str) -> List[str]:
    """Extracts all external links from the HTML content, ignoring Facebook and non-https links."""
    soup = BeautifulSoup(html_content, "html.parser")
    links = set
    links_arr = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith("https://") and "facebook" not in href and not href.startswith(base_url) and "sciencealert" not in href and "twitter" not in href and "instagram" not in href and "pinterest" not in href and "linkedin" not in href and ".jpeg" not in href and ".jpg" not in href and ".png" not in href and ".gif" not in href:
            links_arr.append(href)

    link = links_arr[-1]
    links = set(links_arr)

    links_arr = []
    for link in links:
        links_arr.append(link)
    return links_arr,link

# Core functionality
async def get_basic_info(session, target: str, api_path: str = "wp-json/") -> dict:
    """Collects basic information about the WordPress API target."""
    rest_url = url_path_join(target, api_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    try:
        async with session.get(rest_url, headers=headers) as req:
            req.raise_for_status()
            basic_info = await get_content_as_json(req)
            if "wp/v2" in basic_info.get("namespaces", []):
                logging.info("WordPress API v2 is supported.")
            else:
                logging.warning("WordPress API v2 is not supported.")
            return basic_info
    except Exception as e:
        logging.error(f"Error fetching basic info: {e}")
        raise

async def crawl_pages(
    session,
    base_url: str,
    api_path: str,
    start: Optional[int] = None,
    num: Optional[int] = None,
    display_progress: bool = True,
) -> Tuple[List[Any], int]:
    """Crawls pages from a given endpoint, retrieving entries."""
    page = 1
    total_entries = 0
    entries: List[Any] = []
    per_page = 50  # Optimized to scrape 50 posts at a time
    entries_left = num if num is not None else 1

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    if start is not None:
        page = math.floor(start / per_page) + 1

    more_entries = True

    with tqdm(total=num if num else float('inf'), desc="Scraping Posts", unit="post") as pbar:
        while more_entries and entries_left > 0:
            rest_url = url_path_join(base_url, f"wp-json/{api_path}?page={page}&per_page={per_page}")

            try:
                async with session.get(rest_url, headers=headers) as req:
                    req.raise_for_status()

                    if page == 1 and "X-WP-Total" in req.headers:
                        total_entries = int(req.headers["X-WP-Total"])
                        logging.info(f"Total number of entries: {total_entries}")
                        num = total_entries if num is None else min(num, total_entries)
                    json_content = await get_content_as_json(req)
                    if isinstance(json_content, list) and json_content:
                        entries += json_content
                        entries_left -= len(json_content)
                        pbar.update(len(json_content))
                    else:
                        more_entries = False

            except aiohttp.ClientResponseError as e:
                logging.error(f"HTTP error on page {page}: {e}")
                break
            except Exception as e:
                logging.error(f"Error on page {page}: {e}")
                break

            page += 1

    return entries, total_entries

async def crawl_single_page(session, base_url: str, api_path: str) -> Any:
    """Crawls a single page of the WordPress API."""
    rest_url = url_path_join(base_url, f"wp-json/{api_path}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    try:
        async with session.get(rest_url, headers=headers) as req:
            req.raise_for_status()
            return await get_content_as_json(req)
    except aiohttp.ClientResponseError as e:
        logging.error(f"HTTP error: {e}")
        return None
    except Exception as e:
        logging.error(f"Error: {e}")
        return None

# Functions to retrieve different types of entries
async def get_comments(session, base_url: str, start: Optional[int] = None, num: Optional[int] = None) -> Tuple[List[Any], int]:
    """Retrieves all comments from the WordPress API."""
    return await crawl_pages(session, base_url, "wp/v2/comments", start, num)

async def get_posts(session, base_url: str, start: Optional[int] = None, num: Optional[int] = None) -> Tuple[List[Any], int]:
    """Retrieves all posts from the WordPress API."""
    queue = asyncio.Queue()
    posts = []
    total_posts = 0
    batch_size = 50  # Set batch size to 50 to scrape incrementally

    async def worker():
        while True:
            page = await queue.get()
            if page is None:
                break
            try:
                batch_posts, total_posts = await crawl_pages(session, base_url, "wp/v2/posts", start=(page - 1) * batch_size, num=batch_size, display_progress=False)
                posts.extend(batch_posts)
            except Exception as e:
                logging.error(f"Error while scraping page {page}: {e}")
            finally:
                queue.task_done()

    for i in range(start // batch_size + 1 if start is not None else 1, (num // batch_size) + 2 if num else total_posts // batch_size + 2):
        await queue.put(i)

    # Start worker tasks
    workers = [asyncio.create_task(worker()) for _ in range(5)]  # Use 5 workers for concurrency
    await queue.join()

    # Stop workers
    for _ in workers:
        await queue.put(None)
    await asyncio.gather(*workers)

    return posts[:num] if num else posts, total_posts

async def save_posts_to_json(posts: List[Any], file_path: str):
    """Saves posts to a JSON file."""
    # Extract only required fields for each post
    filtered_posts = [
        {
            "index": idx + 1,
            "title": post.get("title", {}).get("rendered") if include_title else None,
            "url": post.get("link"),
            "date_gmt": post.get("date_gmt") if include_date else None,
            "content": clean_html_content(post.get("content", {}).get("rendered", "")) if include_content else None,
            "links": extract_links(post.get("content", {}).get("rendered", ""), base_url=post.get("link")) if include_links else None
        }
        for idx, post in enumerate(posts)
    ]

    async with aiofiles.open(file_path, mode='w', encoding='utf-8') as file:
        await file.write(json.dumps(filtered_posts, indent=4))
    logging.info(f"Data saved to {file_path}")

async def save_posts_to_csv(posts: List[Any], file_path: str):
    """Saves posts to a CSV file."""
    # Extract only required fields for each post
    fieldnames = ["index"]
    if include_title:
        fieldnames.append("title")
    if include_date:
        fieldnames.append("date_gmt")
    if include_content:
        fieldnames.append("content")
    fieldnames.append("link")

    filtered_posts = [
        {
            "index": idx + 1,
            "title": post.get("title", {}).get("rendered") if include_title else None,
            "link": post.get("link"),
            "date_gmt": post.get("date_gmt") if include_date else None,
            "content": clean_html_content(post.get("content", {}).get("rendered", "")) if include_content else None
        }
        for idx, post in enumerate(posts)
    ]

    async with aiofiles.open(file_path, mode='w', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        await file.write(",".join(fieldnames) + "\n")
        for post in filtered_posts:
            await file.write(",".join(f'"{str(post[field])}"' for field in fieldnames if post[field] is not None) + "\n")
    logging.info(f"Data saved to {file_path}")

# Example usage of the script
async def main():
    logging.basicConfig(level=logging.INFO)

    base_url = input("Enter the base URL of the WordPress site: ").strip()
    if not base_url:
        print("Base URL cannot be empty.")
        return

    num_posts = input("Enter the number of posts to scrape (press enter for all): ").strip()
    num_posts = int(num_posts) if num_posts.isdigit() else None

    global include_title, include_date, include_content, include_links
    include_title = input("Do you want to scrape the title? (y/n): ").strip().lower() == 'y'
    include_date = input("Do you want to scrape the date? (y/n): ").strip().lower() == 'y'
    include_content = input("Do you want to scrape the content? (y/n): ").strip().lower() == 'y'
    include_links = input("Do you want to scrape the links? (y/n): ").strip().lower() == 'y'

    async with CachedSession(cache=SQLiteBackend(), expire_after=180) as session:
        posts, total_posts = await get_posts(session, base_url, start=0, num=num_posts)
        print(f"Retrieved {len(posts)} posts out of {total_posts} available.")
        # Save posts to a JSON file
        await save_posts_to_json(posts, "wordpress_posts.json")
        # Save posts to a CSV file
        await save_posts_to_csv(posts, "wordpress_posts.csv")

if __name__ == "__main__":
    asyncio.run(main())