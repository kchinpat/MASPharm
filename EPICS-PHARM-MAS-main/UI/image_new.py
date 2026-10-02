import requests
from bs4 import BeautifulSoup
import urllib.request
from PIL import Image, ImageTk
import tkinter as tk

def download_image(ndc):
    search_url = f'https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query={ndc}'
    
    response = requests.get(search_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    drug_photos_section = soup.find('div', class_='mod drug-photos')
    if drug_photos_section:
        first_image_tag = drug_photos_section.find('li', class_='img package-photo').find('img')
        if first_image_tag:
            image_url = first_image_tag['src']
            
            if not image_url.startswith('http'):
                image_url = 'https://dailymed.nlm.nih.gov' + image_url
            
            urllib.request.urlretrieve(image_url, f'images/{ndc}.jpg')
        else:
            print("No image found in drug photos.")
    else:
        print("No drug photos section found.")

# ndc_code = '01000-3107-30'
# download_image(ndc_code)

def load_medicine_image(parent_frame, ndc, width=300):
    """
    Loads and displays a medicine image in the given frame.
    
    Args:
        parent_frame: The tkinter frame to display the image in
        ndc: The NDC number for the image filename
        width: Desired width of the image (height will be scaled proportionally)
    
    Returns:
        The image label reference or None if there was an error
    """
    try:
        if ndc:
            img = Image.open(f"images/{ndc}.jpg")
            orig_width, orig_height = img.size
            new_width = width
            new_height = int((new_width / orig_width) * orig_height)
            img = img.resize((new_width, new_height))
            photo = ImageTk.PhotoImage(img)
            img_label = tk.Label(parent_frame, image=photo)
            img_label.image = photo  # Keep a reference to prevent garbage collection
            img_label.place(relx=0.5, rely=0.5, anchor='center')
            return img_label
    except Exception as e:
        print(f"Error loading image: {e}")
        return None

def update_medicine_image(img_label, parent_frame, new_ndc, width=200):
    """
    Updates an existing image label with a new medicine image.
    
    Args:
        img_label: The existing image label to update
        parent_frame: The parent frame containing the image label
        new_ndc: The new NDC number for the image filename
        width: Desired width of the image (height will be scaled proportionally)
    
    Returns:
        The updated image label or a new one if needed
    """
    # First clear the existing image if there is one
    if img_label:
        img_label.destroy()
    
    # Then load the new image
    return load_medicine_image(parent_frame, new_ndc, width)