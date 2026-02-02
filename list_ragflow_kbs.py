import requests
import json
from datetime import datetime

API_KEY = "ragflow-7YHyApNlkk3W9PvJzeovev0DC3FDQmrRm4W953ztkxI"
BASE_URL = "http://47.110.141.115/api/v1"

def list_datasets():
    url = f"{BASE_URL}/dataset/list"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 0:
            datasets = data.get('data', [])
            print(f"Found {len(datasets)} datasets:")
            
            # Sort by create_time if available, otherwise just list
            # Assuming 'create_time' or similar field exists. 
            # If not, will just print as is.
            
            for ds in datasets:
                # Convert timestamp to readable format if possible
                create_time = ds.get('create_time')
                if create_time:
                    try:
                        # Attempt to parse if it's a timestamp or string
                        if isinstance(create_time, (int, float)):
                            create_time_str = datetime.fromtimestamp(create_time/1000).strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            create_time_str = str(create_time)
                    except:
                        create_time_str = str(create_time)
                else:
                    create_time_str = "N/A"
                
                print(f"ID: {ds.get('id')}")
                print(f"Name: {ds.get('name')}")
                print(f"Created: {create_time_str}")
                print("-" * 30)
        else:
            print(f"Error listing datasets: {data.get('message')}")
            
    except Exception as e:
        print(f"Request failed: {e}")
        # Try without /list just in case
        try:
            print("Retrying with /dataset...")
            url = f"{BASE_URL}/dataset"
            response = requests.get(url, headers=headers)
            print(response.text)
        except Exception as e2:
            print(f"Retry failed: {e2}")

if __name__ == "__main__":
    list_datasets()
