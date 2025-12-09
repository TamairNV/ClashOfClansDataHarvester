import urllib
from os import environ
import dotenv
import requests
import urllib.parse

dotenv.load_dotenv()
TOKEN = environ.get("TOKEN")


endpoint = "https://api.clashofclans.com/v1/"
headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

encoded_tag = urllib.parse.quote("#8GGPQLPU")

# 2. Build the request URL
URL = f"https://api.clashofclans.com/v1/leaguetiers"



try:
    # 4. Make the GET request
    response = requests.get(URL, headers=headers)

    # 5. Check for successful response
    if response.status_code == 200:
        player_data = response.json()
        print(player_data)
    else:
        print(f"Error fetching data. Status code: {response.status_code}")
        print(response.text) # Shows the error message from the API

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
