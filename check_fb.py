import os
import requests
from dotenv import load_dotenv

load_dotenv()

page_token = os.getenv("FB_PAGE_TOKEN")
page_id = os.getenv("FB_PAGE_ID")

if not page_token:
    print("No FB_PAGE_TOKEN found in .env")
else:
    url = f"https://graph.facebook.com/v20.0/{page_id}?access_token={page_token}"
    res = requests.get(url)
    print("Status Code:", res.status_code)
    print("Response:", res.text)
