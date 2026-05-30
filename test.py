import requests
import json

# Use a smaller, more lightweight model
url = "http://localhost:11434/api/generate"
payload = {
    "model": "tinyllama",
    "prompt": "Привет",
    "stream": False
}

try:
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 200:
        result = response.json()
        print("Response:")
        print(result.get('response', 'No response'))
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Connection error: {e}")
    print("\nNote: qwen3.5:2b requires too much CPU memory in this environment.")
    print("Try using tinyllama instead: ollama pull tinyllama")