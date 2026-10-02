import requests
import json
import os

BASE_URL = "https://dailymed.nlm.nih.gov/dailymed/services"
def download_images(ndc):
    url = f"{BASE_URL}/v1/ndc/{ndc}/spls.json"
    response = requests.get(url)
    print(response)
    print(response.json())
    set_id = response.json()["DATA"][0][0]
    print(set_id)

    url = f"{BASE_URL}/v2/spls/{set_id}/media.json"
    response = requests.get(url)
    print(json.dumps(response.json(), indent=4))
    with open("html_response.json", "w") as f:
        f.write(json.dumps(response.json(), indent=4))

    response_dict = dict(response.json())
    media = response_dict["data"]["media"]
    os.mkdir(ndc)
    os.chdir(ndc)
    for item in media:
        url = item["url"]
        name = item["name"]
        response = requests.get(url)
        if response.status_code == 200:
            with open(name, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded {name}")
        else:
            print(f"Failed to download {name}")
    os.chdir("..")

if __name__ == "__main__":
    ndc = "59762-3719-1"
    download_images(ndc) 