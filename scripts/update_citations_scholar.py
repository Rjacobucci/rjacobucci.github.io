#!/usr/bin/env python3
"""
Improved Google Scholar citation fetcher with better reliability
"""
import requests
from bs4 import BeautifulSoup
import re
import os
import time
import random
from datetime import datetime

def get_citations_from_scholar(scholar_id, max_retries=3):
    """
    Fetch citation count from Google Scholar with improved reliability
    """
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    
    # Rotate through different user agents
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14.2.1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
    ]
    
    session = requests.Session()
    
    for attempt in range(max_retries):
        # Random user agent for each attempt
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        try:
            # Random delay between 3-7 seconds to avoid rate limiting
            delay = random.uniform(3, 7)
            print(f"Attempt {attempt + 1}: Waiting {delay:.1f} seconds...")
            time.sleep(delay)
            
            response = session.get(url, headers=headers, timeout=30)
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 429:
                print("Rate limited. Waiting longer...")
                time.sleep(30)
                continue
                
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Method 1: Look for citation count in the stats table
            stats_table = soup.find('table', {'id': 'gsc_rsb_st'})
            if stats_table:
                # The first cell in the stats table is typically the total citations
                cells = stats_table.find_all('td', {'class': 'gsc_rsb_std'})
                if cells and len(cells) > 0:
                    citation_text = cells[0].text.strip()
                    if citation_text.replace(',', '').isdigit():
                        citations = int(citation_text.replace(',', ''))
                        print(f"Found {citations:,} citations (method 1)")
                        return citations
            
            # Method 2: Look for citation row specifically
            citation_row = soup.find('td', string=re.compile(r'Citations', re.I))
            if citation_row:
                next_cell = citation_row.find_next_sibling('td')
                if next_cell:
                    citation_text = next_cell.text.strip()
                    if citation_text.replace(',', '').isdigit():
                        citations = int(citation_text.replace(',', ''))
                        print(f"Found {citations:,} citations (method 2)")
                        return citations
            
            # Method 3: Search for any element with gsc_rsb_std class containing a large number
            all_stats = soup.find_all(['td', 'div'], {'class': re.compile('gsc_rsb_std')})
            for stat in all_stats:
                text = stat.text.strip()
                if text.replace(',', '').isdigit():
                    num = int(text.replace(',', ''))
                    # Assume citations are the largest number
                    if num > 100:  # Reasonable threshold
                        print(f"Found potential citation count: {num:,} (method 3)")
                        # Don't return immediately, keep looking for larger numbers
            
            # If we couldn't find citations, save debug info
            if attempt == max_retries - 1:
                with open('scholar_debug.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print("Saved debug HTML to scholar_debug.html")
                
        except requests.exceptions.RequestException as e:
            print(f"Request error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        except Exception as e:
            print(f"Unexpected error on attempt {attempt + 1}: {e}")
            
    return None

def update_config_file(citation_count):
    """
    Update the _config.yml file with new citation count
    """
    config_path = '_config.yml'
    
    # Read the current config
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract current citation count for comparison
    current_match = re.search(r'bio\s*:\s*"[^"]*?(\d+,?\d*)\+? citations', content)
    current_count = 0
    if current_match:
        current_count = int(current_match.group(1).replace(',', ''))
    
    # Only update if new count is significantly higher (to avoid Semantic Scholar updates)
    if citation_count > current_count * 1.1:  # 10% threshold
        # Update the bio line with new citation count
        old_pattern = r'(\s*bio\s*:\s*"[^"]*?)(\d+,?\d*)\+? citations'
        new_bio = rf'\g<1>{citation_count:,}+ citations'
        
        updated_content = re.sub(old_pattern, new_bio, content)
        
        # Write back to file
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"Updated citation count from {current_count:,} to {citation_count:,}")
        return True
    else:
        print(f"Citation count {citation_count:,} not significantly higher than current {current_count:,}. Skipping update.")
        return False

def main():
    # Your Google Scholar ID
    scholar_id = "K7_cclwAAAAJ"
    
    print(f"Fetching Google Scholar citations for ID: {scholar_id}")
    print(f"Time: {datetime.now()}")
    
    citation_count = get_citations_from_scholar(scholar_id)
    
    if citation_count and citation_count > 0:
        print(f"\nSuccessfully retrieved {citation_count:,} citations from Google Scholar")
        if update_config_file(citation_count):
            print("Config file updated successfully")
        else:
            print("Config file not updated (count not significantly higher)")
    else:
        print("\nFailed to retrieve citation count from Google Scholar")
        print("This might be due to:")
        print("1. Google Scholar blocking automated requests")
        print("2. Changes in the page structure")
        print("3. Network issues")
        print("\nConsider using the manual update approach or a dedicated API service")
        exit(1)

if __name__ == "__main__":
    main()