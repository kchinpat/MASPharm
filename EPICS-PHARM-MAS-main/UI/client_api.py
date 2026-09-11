import os
from dotenv import load_dotenv
import requests
import requests
import json

load_dotenv()


RPI_ADDRESS = os.getenv("RPI_ADDRESS")
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("No API_KEY found in .env file")

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def open_drawer(drawer_num):
    # try:
    #     response = requests.post(
    #         f"http://{RPI_ADDRESS}/open_drawer",
    #         json={"drawer": drawer_num},
    #         headers=headers
    #     )
    #     if response.status_code == 200:
    #         return True, response.json().get("message", "Success")
    #     else:
    #         return False, response.json().get("error", "Unknown error")
    # except Exception as e:
    #     return False, f"Connection error: {str(e)}"
    pass

def lock_drawer(drawer_num):
    # try:
    #     response = requests.post(
    #         f"http://{RPI_ADDRESS}/lock_drawer",
    #         json={"drawer": drawer_num},
    #         headers=headers
    #     )
    #     if response.status_code == 200:
    #         return True, response.json().get("message", "Success")
    #     else:
    #         return False, response.json().get("error", "Unknown error")
    # except Exception as e:
    #     return False, f"Connection error: {str(e)}"
    pass

def emergency_unlock():
    # try:
    #     response = requests.post(
    #         f"http://{RPI_ADDRESS}/unlock",
    #         headers=headers,
    #         json={}
    #     )
    #     return response.status_code == 200, response.json().get("message", "Error")
    # except Exception as e:
    #     return False, f"Connection error: {str(e)}"
    pass

def control_light(box_num):
    # try:
    #     response = requests.post(
    #         f"http://{RPI_ADDRESS}/light",
    #         headers=headers,
    #         json={"box": box_num}
    #     )
    #     return response.status_code == 200, response.json().get("message", "Error")
    # except Exception as e:
    #     return False, f"Connection error: {str(e)}"
    pass

def unlock_cabinet_lock(box_num):
    # try:
    #     response = requests.post(
    #         f"http://{RPI_ADDRESS}/unlock_cabinet_lock",
    #         headers=headers,
    #         json={"box": box_num}
    #     )
    #     return response.status_code == 200, response.json().get("message", "Error")
    # except Exception as e:
    #     return False, f"Connection error: {str(e)}"
    pass

def lock_cabinet_lock(box_num):
    # try:
    #     response = requests.post(
    #         f"http://{RPI_ADDRESS}/lock_cabinet_lock",
    #         headers=headers,
    #         json={"box": box_num}
    #     )
    #     return response.status_code == 200, response.json().get("message", "Error")
    # except Exception as e:
    #     return False, f"Connection error: {str(e)}"
    pass

def check_api_status():
    # try:
    #     response = requests.get(
    #         f"http://{RPI_ADDRESS}/status",
    #         headers=headers
    #     )
    #     return response.status_code == 200
    # except:
    #     return False
    pass
