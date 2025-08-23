#!/usr/bin/env python3
"""
Alternative script to fetch citation count using Semantic Scholar API
"""
import requests
import re
import os
from datetime import datetime

def get_citations_from_semantic_scholar(author_name):
    """
    Fetch citation count from Semantic Scholar API
    """
    # Search for author
    search_url = "https://api.semanticscholar.org/graph/v1/author/search"
    params = {"query": author_name, "limit": 5}
    
    try:
        response = requests.get(search_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('data'):
            print(f"No authors found for: {author_name}")
            return None
            
        # Get the first matching author
        author_id = data['data'][0]['authorId']
        print(f"Found author ID: {author_id}")
        
        # Get author details including citations
        author_url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}"
        params = {"fields": "name,citationCount,hIndex"}
        
        response = requests.get(author_url, params=params, timeout=30)
        response.raise_for_status()
        author_data = response.json()
        
        citation_count = author_data.get('citationCount', 0)
        h_index = author_data.get('hIndex', 0)
        
        print(f"Author: {author_data.get('name')}")
        print(f"Citations: {citation_count}")
        print(f"h-index: {h_index}")
        
        return citation_count
        
    except Exception as e:
        print(f"Error fetching from Semantic Scholar: {e}")
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
    # Author name to search for
    author_name = "Ross Jacobucci"
    
    print(f"Fetching citations for: {author_name}")
    print(f"Time: {datetime.now()}")
    
    citation_count = get_citations_from_semantic_scholar(author_name)
    
    if citation_count and citation_count > 0:
        print(f"Found {citation_count:,} citations")
        update_config_file(citation_count)
    else:
        print("Could not fetch citation count or count is 0")
        # Try Google Scholar as fallback
        print("Falling back to manual update...")
        exit(1)

if __name__ == "__main__":
    main()