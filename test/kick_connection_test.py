import requests

url = "https://kick.com/api/v1/oauth2/token"

headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0"  # Cloudflare'in bot filtresine karşı
}

data = {
    "grant_type": "client_credentials",
    "client_id": "01JT604CPR0G0B926AY2P6KCGX",
    "client_secret": "d9a5f314f32a5421b4235459af4d96acdfbdacb94eed7388b45ed4f9c47cc977"
}

response = requests.post(url, headers=headers, data=data)

print(response.status_code)
print(response.text)
