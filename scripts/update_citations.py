#!/usr/bin/env python3
"""
Script to fetch citation count from Google Scholar and update Jekyll config
"""
import requests
from bs4 import BeautifulSoup
import re
import yaml
import os
from datetime import datetime

def get_citations_from_scholar(scholar_id):
    """
    Fetch citation count from Google Scholar profile
    """
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Response status: {response.status_code}")
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Debug: save the HTML to see what we're getting
        with open('debug_scholar_response.html', 'w', encoding='utf-8') as f:
            f.write(response.text[:10000])  # First 10k chars for debugging
        
        # Method 1: Find the citation count in the stats table
        citation_element = soup.find('td', text='Citations')
        if citation_element:
            citation_count = citation_element.find_next_sibling('td').text
            print(f"Found citations via method 1: {citation_count}")
            return int(citation_count)
        
        # Method 2: Look for the citation count in the profile stats table
        stats_table = soup.find('table', {'id': 'gsc_rsb_st'})
        if stats_table:
            cells = stats_table.find_all('td', {'class': 'gsc_rsb_std'})
            if cells and len(cells) > 0:
                print(f"Found citations via method 2: {cells[0].text}")
                return int(cells[0].text)
        
        # Method 3: Try to find any element containing citation count
        # Look for divs with class containing 'gsc_rsb_std'
        citation_divs = soup.find_all(['td', 'div'], {'class': re.compile('gsc_rsb_std')})
        print(f"Found {len(citation_divs)} potential citation elements")
        for div in citation_divs[:5]:  # Check first 5
            text = div.get_text(strip=True)
            if text.isdigit() and int(text) > 100:  # Assuming citations > 100
                print(f"Found potential citation count: {text}")
                
        print("Could not find citation count with any method")
                
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except Exception as e:
        print(f"Error fetching citations: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    return None

def update_config_file(citation_count):
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
    
    print(f"Updated citation count to {citation_count:,}")

def main():
    # Your Google Scholar ID from the URL
    scholar_id = "K7_cclwAAAAJ"
    
    print(f"Fetching citations for Scholar ID: {scholar_id}")
    print(f"Time: {datetime.now()}")
    
    citation_count = get_citations_from_scholar(scholar_id)
    
    if citation_count:
        print(f"Found {citation_count:,} citations")
        update_config_file(citation_count)
    else:
        print("Could not fetch citation count")
        exit(1)

if __name__ == "__main__":
    main()