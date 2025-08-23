#!/usr/bin/env python3
"""
Hybrid script to fetch citation count from multiple sources
"""
import requests
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime
import time
import json

def get_citations_from_semantic_scholar(author_name):
    """
    Fetch citation count from Semantic Scholar API
    """
    search_url = "https://api.semanticscholar.org/graph/v1/author/search"
    params = {"query": author_name, "limit": 5}
    
    try:
        response = requests.get(search_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('data'):
            return None
            
        author_id = data['data'][0]['authorId']
        
        # Get author details
        author_url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}"
        params = {"fields": "name,citationCount"}
        
        response = requests.get(author_url, params=params, timeout=30)
        response.raise_for_status()
        author_data = response.json()
        
        return author_data.get('citationCount', 0)
        
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
        return None

def get_citations_from_scholar_api():
    """
    Try to use serpapi or similar service if available
    """
    # This would require an API key
    # For now, return None
    return None

def get_citations_from_scholar_scrape(scholar_id):
    """
    Fallback to scraping Google Scholar with better error handling
    """
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    
    # Try different user agents
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    for ua in user_agents:
        headers = {'User-Agent': ua}
        try:
            # Add delay to avoid rate limiting
            time.sleep(2)
            
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try multiple selectors
                selectors = [
                    ('table#gsc_rsb_st td.gsc_rsb_std', 0),
                    ('div.gsc_rsb_s.gsc_prf_pnl div.gsc_rsb_std', 0),
                    ('td:contains("Citations") + td', None)
                ]
                
                for selector, index in selectors:
                    if index is not None:
                        elements = soup.select(selector)
                        if elements and len(elements) > index:
                            text = elements[index].get_text(strip=True)
                            if text.replace(',', '').isdigit():
                                return int(text.replace(',', ''))
                    else:
                        # Special handling for sibling selector
                        citation_label = soup.find('td', string='Citations')
                        if citation_label:
                            citation_value = citation_label.find_next_sibling('td')
                            if citation_value:
                                text = citation_value.get_text(strip=True)
                                if text.replace(',', '').isdigit():
                                    return int(text.replace(',', ''))
                
        except Exception as e:
            print(f"Error with user agent {ua[:30]}...: {e}")
            continue
    
    return None

def update_config_file(citation_count, source):
    """
    Update the _config.yml file with new citation count
    """
    config_path = '_config.yml'
    
    # Read the current config
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Update the bio line with new citation count
    old_pattern = r'(\s*bio\s*:\s*"[^"]*?)(\d+,?\d*)\+? citations'
    new_bio = rf'\g<1>{citation_count:,}+ citations'
    
    updated_content = re.sub(old_pattern, new_bio, content)
    
    # Write back to file
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"Updated citation count to {citation_count:,} (source: {source})")

def main():
    # Configuration
    author_name = "Ross Jacobucci"
    scholar_id = "K7_cclwAAAAJ"
    
    print(f"Fetching citations for: {author_name}")
    print(f"Time: {datetime.now()}")
    
    # Try multiple sources
    sources = [
        ("Semantic Scholar", lambda: get_citations_from_semantic_scholar(author_name)),
        ("Google Scholar API", lambda: get_citations_from_scholar_api()),
        ("Google Scholar Scrape", lambda: get_citations_from_scholar_scrape(scholar_id))
    ]
    
    citation_count = None
    source_used = None
    
    for source_name, fetch_func in sources:
        print(f"\nTrying {source_name}...")
        try:
            count = fetch_func()
            if count and count > 0:
                citation_count = count
                source_used = source_name
                print(f"Success! Found {count:,} citations")
                break
            else:
                print(f"No results from {source_name}")
        except Exception as e:
            print(f"Error with {source_name}: {e}")
    
    if citation_count and citation_count > 0:
        update_config_file(citation_count, source_used)
    else:
        print("\nCould not fetch citation count from any source")
        print("The Google Scholar page structure may have changed.")
        print("Consider using a dedicated API service or manual updates.")
        exit(1)

if __name__ == "__main__":
    main()