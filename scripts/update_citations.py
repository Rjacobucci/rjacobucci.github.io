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
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the citation count in the stats table
        citation_element = soup.find('td', text='Citations')
        if citation_element:
            citation_count = citation_element.find_next_sibling('td').text
            return int(citation_count)
        
        # Alternative method: look for the citation count in the profile
        stats_table = soup.find('table', {'id': 'gsc_rsb_st'})
        if stats_table:
            cells = stats_table.find_all('td', {'class': 'gsc_rsb_std'})
            if cells and len(cells) > 0:
                return int(cells[0].text)
                
    except Exception as e:
        print(f"Error fetching citations: {e}")
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