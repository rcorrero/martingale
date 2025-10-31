"""
Simple backup strategy for JSON files on Heroku.
This creates backups in external storage services.
"""
import json
import os
import requests
from datetime import datetime

def backup_to_github_gist():
    """Backup data to GitHub Gist (free, simple)."""
    # You'll need to set GITHUB_TOKEN in Heroku config
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        return
    
    # Read all data files
    data = {}
    for filename in ['users.json', 'portfolios.json', 'price_data.json']:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data[filename] = f.read()
    
    # Create gist
    gist_data = {
        "description": f"Martingale backup {datetime.now().isoformat()}",
        "public": False,
        "files": {filename: {"content": content} for filename, content in data.items()}
    }
    
    response = requests.post(
        'https://api.github.com/gists',
        headers={'Authorization': f'token {token}'},
        json=gist_data
    )
    
    if response.status_code == 201:
        print(f"Backup created: {response.json()['html_url']}")

# Add this to your app to run periodic backups