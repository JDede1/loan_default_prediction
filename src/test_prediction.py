import requests
import json

url = "http://localhost:5001/invocations"
headers = {"Content-Type": "application/json"}

with open("sample_input.json") as f:
    data = json.load(f)

response = requests.post(url, headers=headers, json=data)
print("Status Code:", response.status_code)
print("Response:", response.text)
