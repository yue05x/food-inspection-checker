import requests
import json

API_KEY = "ragflow-7YHyApNlkk3W9PvJzeovev0DC3FDQmrRm4W953ztkxI"
BASE_URL = "http://47.110.141.115/api/v1"
KB_ID = "4793322ff5f611f0a2d30242ac120006"

def test_retrieval():
    url = f"{BASE_URL}/retrieval"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "question": "test",
        "dataset_ids": [KB_ID]
    }
    
    print(f"Testing retrieval at {url}...")
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Retrieval test failed: {e}")

def list_datasets(endpoint):
    url = f"http://47.110.141.115{endpoint}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"Testing list datasets at {url}...")
    try:
        # Disable proxies
        session = requests.Session()
        session.trust_env = False
        
        response = session.get(url, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                print("Success! Datasets found:")
                for ds in data.get('data', [])[:20]: 
                    print(f"ID: {ds.get('id')}, Name: {ds.get('name')}, Created: {ds.get('create_time')}")
            else:
                print(f"API Error: {data.get('message')}")
        else:
             print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"List datasets test failed: {e}")

def check_socket(host, port):
    import socket
    print(f"Checking socket connection to {host}:{port}...")
    try:
        sock = socket.create_connection((host, port), timeout=5)
        print("Socket connection successful!")
        sock.close()
    except Exception as e:
        print(f"Socket connection failed: {e}")


def check_url(url, description):
    print(f"Testing {description} at {url}...")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        # Disable proxies
        session = requests.Session()
        session.trust_env = False
        
        response = session.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        if response.status_code == 200:
            if 'dataset' in url:
                data = response.json()
                if data.get('code') == 0:
                    print("Success! Datasets found:")
                    for ds in data.get('data', [])[:20]: 
                        print(f"ID: {ds.get('id')}, Name: {ds.get('name')}, Created: {ds.get('create_time')}")
                else:
                    print(f"API Error: {data.get('message')}")
            else:
                 print(f"Response: {response.text[:200]}")
        else:
             print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    # Disable proxies globally 
    import os
    os.environ['NO_PROXY'] = '*'
    
    check_socket("47.110.141.115", 80)
    print("-" * 30)
    check_url("http://47.110.141.115/api/v1/dataset/list", "Dataset List (Target IP)")
    print("-" * 30)
    check_url("http://47.110.141.115/", "Root (Target IP)")
    print("-" * 30)
    check_url("http://118.31.79.26/api/v1/dataset/list", "Dataset List (Old IP)")


