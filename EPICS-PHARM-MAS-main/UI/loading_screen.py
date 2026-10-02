import tkinter as tk
from tkinter import messagebox, simpledialog
import tkinter.ttk as ttk
import json
from typing import Tuple
from tkinter import Entry
from tkinter import Scrollbar
from tkinter import *
from image_new import download_image
import cv2
import textwrap
from pyzbar.pyzbar import decode
from client_api import open_drawer
import time
import threading
from clear_frame import clear_frame
from screen_controller import switch_to_dispensing_screen
from global_db import prods

def load_products(filename):
    with open(filename, 'r') as file:
        return json.load(file)

def query_upc(upc, data):
    for product in data:
        if 'upc' in product.get('openfda') and upc in product['openfda']['upc']:
            packagings = []
            for packaging in product.get('packaging'):
                packagings.append({"ndc": packaging.get("package_ndc"), "description": packaging.get("description")})
            return {"generic_name": product.get("generic_name"), "labeler_name": product.get("labeler_name"), "brand_name": product.get("brand_name"), "expiry_date": product.get("listing_expiration_date"), "packaging": packagings}
    return None

def brute_ndc(ndc, data):
    for product in data:
        for packaging in product.get('packaging'):
            if (packaging.get('package_ndc').replace('-','') in ndc): 
                return {"generic_name": product.get("generic_name"), "labeler_name": product.get("labeler_name"), "brand_name": product.get("brand_name"), "expiry_date": product.get("listing_expiration_date"), "ndc": packaging.get("package_ndc"), "description": packaging.get("description")}
    return None

def load(window, name, label, brand, exp, ndc, desc, selected_cabinet):
    # Get string values from Text widgets

    loading_count = simpledialog.askinteger(
        "Loading count",
        f"Enter the quantity of {name} loading", initialvalue=1
    )

    name_str = name.get()
    label_str = label.get()
    brand_str = brand.get()
    exp_str = exp.get()
    ndc_str = ndc.get()
    desc_str = desc.get()

    current_stored_medecine = {}
    current_stored_medecine["generic_name"] = name_str
    current_stored_medecine["labeler_name"] = label_str
    current_stored_medecine["brand_name"] = brand_str
    current_stored_medecine["expiry_date"] = exp_str
    current_stored_medecine["ndc"] = ndc_str
    current_stored_medecine["description"] = desc_str 

    with open("medecine_data.json", "r") as f:
        data = json.load(f)

    data[selected_cabinet['number']-1]["current_stored_medecine"] = current_stored_medecine
    data[selected_cabinet['number']-1]["fill_status"] = True
    data[selected_cabinet['number']-1]["quantity"] += loading_count

    with open("medecine_data.json", "w") as f:
        json.dump(data, f, indent=4)

    # Clear all input fields
    for widget in (name, label, brand, exp, ndc, desc):
        widget.delete(0, tk.END)

    # Destroy old frame if it exists
    if hasattr(window, 'scroll_frame'):
        window.scroll_frame.destroy()

    # Open the selected cabinet to load 
    open_drawer(selected_cabinet['number'])

    # Download image associated with ndc code
    download_image(current_stored_medecine["ndc"])

    #Wrap text if needed
    wrap_list = textwrap.wrap(current_stored_medecine['generic_name'], width = 22)
    wrap_label = ""
    for a in wrap_list:
        wrap_label += "-\n" + a 
    wrap_label = wrap_label.replace("-\n","", 1)

    # Create new status display
    display_drawer_status(window, selected_cabinet, name, label, brand, exp, ndc, desc, 0)    

def search(window, data, name, label, brand, exp, ndc, desc, selected_cabinet):
    product = None
    if data:
        product = brute_ndc(data, prods) 
        if not product:
            product = query_upc(data, prods) 
    if product:
        name.delete(0, tk.END)
        name.insert(0, product["generic_name"])
        label.delete(0, tk.END)
        label.insert(0, product["labeler_name"])
        brand.delete(0, tk.END)
        brand.insert(0, product["brand_name"])
        exp.delete(0, tk.END)
        exp.insert(0, product["expiry_date"])
        ndc.delete(0, tk.END)
        # ndc.insert(0, product["ndc"])
        ndc.insert(0, int(data)) # the scanned ndc
        desc.delete(0, tk.END)
        desc.insert(0, product["description"])

        # loading_count = simpledialog.askinteger(
        #     "Loading count",
        #     f"Enter the number of {product['generic_name']} loading", initialvalue=1
        # )
        load(window, name, label, brand, exp, ndc, desc, selected_cabinet)



def select_cabinet(cabinet_frame, cabinet_number, selected_cabinet, name, label, brand, exp, ndc, desc):
    try:
        # Remove highlight from previously selected cabinet if it exists
        if selected_cabinet['frame'] is not None:
            try:
                selected_cabinet['frame'].configure(
                    highlightbackground='black',
                    highlightthickness=1
                )
            except tk.TclError:
                # Previous frame no longer exists, ignore the error
                pass

        # Highlight the newly selected cabinet
        cabinet_frame.configure(
            highlightbackground='red',
            highlightthickness=3
        )
        selected_cabinet['frame'] = cabinet_frame
        selected_cabinet['number'] = cabinet_number
    except tk.TclError as e:
        # Handle any Tkinter errors gracefully
        print(f"Error updating cabinet selection: {e}")
        # Reset selection if there's an error
        selected_cabinet['frame'] = None
        selected_cabinet['number'] = None


    #Find the cabinet using the cabinet number

    with open("medecine_data.json", "r") as f:
        cabinets = json.load(f)
        cabinet = cabinets[cabinet_number-1]
        #Show data from cabinet in the text boxes
        if cabinet["fill_status"]: 
            data = cabinet['current_stored_medecine']
            name.delete(0, tk.END)
            name.insert(0, data['generic_name'])
            label.delete(0, tk.END)
            label.insert(0, data['labeler_name'])
            brand.delete(0, tk.END)
            brand.insert(0, data['brand_name'])
            exp.delete(0, tk.END)
            exp.insert(0, data['expiry_date'])
            ndc.delete(0, tk.END)
            ndc.insert(0, data['ndc'])
            desc.delete(0, tk.END)
            desc.insert(0, data['description'])
        #if it isn't filled delete any info in the text boxes

        else:
            name.delete(0, tk.END)
            label.delete(0, tk.END)
            brand.delete(0, tk.END)
            exp.delete(0, tk.END)
            ndc.delete(0, tk.END)
            desc.delete(0, tk.END)

def display_drawer_status(window, selected_cabinet, name, label, brand, exp, ndc, desc, preselect):
    # Create custom styles for selected and unselected frames
    style = ttk.Style()
    style.configure('selected.TFrame', 
                   relief="solid",
                   borderwidth=3,  # Increased border width
                   background='white',  # Background color
                   highlightbackground='red',  # Border color
                   highlightcolor='red',
                   highlightthickness=3)  # Border thickness

    style.configure('unselected.TFrame', 
                   relief="solid",
                   borderwidth=1,
                   background='white',
                   highlightbackground='black',
                   highlightcolor='black',
                   highlightthickness=1)

    # Create a simple frame without scrollbar - it will extend as needed
    status_frame = ttk.Frame(window)
    status_frame.grid(row=0, column=1, rowspan=16, padx=20, pady=10, sticky="nsew")

    # Add header
    ttk.Label(status_frame, text="Selected Cabinet", font=('Times New Roman', 16, 'bold')).pack(pady=5)

    # Load and display cabinet data
    with open("medecine_data.json", "r") as f:
        cabinets = json.load(f)
        first_cabinet_frame = None
        first_empty_cabinet = None
        first_empty_number = None
        preselect_cabinet = None
        i = 1
        for cabinet in cabinets:
            # Create frame for each cabinet
            cabinet_frame = tk.Frame(status_frame, 
                        relief="solid", 
                        highlightbackground='black',
                        highlightcolor='black',
                        highlightthickness=1,
                        background='white')
            cabinet_frame.pack(pady=5, padx=5, fill="x")

            # Store first cabinet reference
            if first_cabinet_frame is None:
                first_cabinet_frame = cabinet_frame
                first_cabinet_number = cabinet['cabinet_number']

            # Store first empty cabinet reference
            if not cabinet["fill_status"] and first_empty_cabinet is None:
                first_empty_cabinet = cabinet_frame
                first_empty_number = cabinet['cabinet_number']

            # Make the frame clickable
            cabinet_frame.bind('<Button-1>', 
                lambda e, cf=cabinet_frame, cn=cabinet['cabinet_number']: 
                select_cabinet(cf, cn, selected_cabinet, name, label, brand, exp, ndc, desc))

            # Cabinet number and status
            status_text = "FILLED" if cabinet["fill_status"] else "EMPTY"
            status_label = ttk.Label(cabinet_frame, 
                text=f"Cabinet {cabinet['cabinet_number']} - {status_text}",
                font=('Times New Roman', 12, 'bold'))
            status_label.pack(pady=2)

            # Make the label clickable too
            status_label.bind('<Button-1>', 
                lambda e, cf=cabinet_frame, cn=cabinet['cabinet_number']: 
                select_cabinet(cf, cn, selected_cabinet, name, label, brand, exp, ndc, desc))

            # If cabinet has medicine, display its details
            if cabinet["fill_status"]:
                med = cabinet["current_stored_medecine"]
                details = [
                    f"Name: {med['generic_name']}",
                    f"NDC: {med['ndc']}",
                    f"Manufacturer: {med['brand_name']}",
                    f"Expires: {med['expiry_date'].split('T')[0]}",
                    f"Description: {med['description']}"
                ]

                for detail in details:
                    detail_label = ttk.Label(cabinet_frame, text=detail, wraplength=300)
                    detail_label.pack()

                    # Make all labels in the frame clickable
                    detail_label.bind('<Button-1>', 
                        lambda e, cf=cabinet_frame, cn=cabinet['cabinet_number']: 
                        select_cabinet(cf, cn, selected_cabinet, name, label, brand, exp, ndc, desc))

            #Check if preselected
            if(i == preselect):
                preselect_cabinet = cabinet_frame
            i = i + 1

        # Auto-select first empty cabinet or first cabinet if all are filled
        if(preselect):
            select_cabinet(preselect_cabinet, preselect, selected_cabinet, name, label, brand, exp, ndc, desc)
        else:
            if first_empty_cabinet is not None:
                select_cabinet(first_empty_cabinet, first_empty_number, selected_cabinet, name, label, brand, exp, ndc, desc)
            elif first_cabinet_frame is not None:
                select_cabinet(first_cabinet_frame, first_cabinet_number, selected_cabinet, name, label, brand, exp, ndc, desc)

def cleanup(window):
    if hasattr(window, 'scanner_thread') and window.scanner_thread.is_alive():
        window.scanning_active.clear() 
        window.scanner_thread.join()    
    
    cv2.destroyAllWindows()

def loading_screen(window, preselect):
    clear_frame(window)
    selected_cabinet = {'frame': None, 'number': None}

    search_label = ttk.Label(window, text="Scan NDC Code", foreground = 'black',
                             font=('Times New Roman', 20, 'bold')).grid(row=0, column=0, padx= 50, pady=5)

    search_entry = tk.Entry(window, width = 20)
    search_entry.grid(row=1, column=0)
    search_entry.focus_set()

    # Make the search entry the default entry
    def handle_window_click(event):
        try:
            clicked_widget = event.widget
            if not isinstance(clicked_widget, tk.Entry):
                search_entry.focus_set()
        except TclError:
            print("No entry pin")
    
    window.bind("<Button-1>", handle_window_click)

    button_frame = ttk.Frame(window)
    button_frame.grid(row=2, column=0, pady=10)
    search_button = ttk.Button(button_frame, text="Search", 
                               command=lambda: search(window, search_entry.get(), name_in, label_in, brand_in, exp_in, ndc_in, desc_in, selected_cabinet))
    search_button.grid(row=0, column=0, padx=2)

    search_entry.bind("<Return>", lambda event: search(window, search_entry.get(), name_in, label_in, brand_in, exp_in, ndc_in, desc_in, selected_cabinet))

    header = ttk.Label(window, text = 'Medication Information', foreground = 'black',
                       font = ('Times New Roman', 20, 'bold')).grid(row=3, column=0, padx= 50, pady=10)

    generic_name = ttk.Label(window, text= 'Generic Name').grid(row=4, column = 0)
    labeler_name = ttk.Label(window, text= 'Labeler Name').grid(row=6, column = 0)
    brand_name = ttk.Label(window, text= 'Brand Name').grid(row=8, column = 0)
    expire_date = ttk.Label(window, text= 'Expiration Date').grid(row=10, column = 0)
    ndc_code = ttk.Label(window, text= 'NDC Code').grid(row=12, column = 0)
    desc = ttk.Label(window, text= 'Description').grid(row=14, column = 0)
    name_in = tk.Entry(window, width = 20)
    name_in.grid(row=5, column=0)
    label_in = tk.Entry(window, width = 20)
    label_in.grid(row=7, column=0)
    brand_in = tk.Entry(window, width = 20)
    brand_in.grid(row=9, column=0)
    exp_in = tk.Entry(window, width = 20)
    exp_in.grid(row=11, column=0)
    ndc_in = tk.Entry(window, width = 20)
    ndc_in.grid(row=13, column=0)
    desc_in = tk.Entry(window, width = 20)
    desc_in.grid(row=15, column=0)
    # style = ttk.Style()
    # style.configure("Button.TButton", foreground = 'black', background = 'black')

    button = ttk.Button(window, text="Enter", style="Button.TButton", 
        command=lambda: load(window, name_in, label_in, brand_in, exp_in, 
                            ndc_in, desc_in, selected_cabinet))
    button.grid(row=16, column=0, ipadx = 1, pady = 25)

    # Add the dispensing screen button on the right side
    dispensing_button = ttk.Button(window, 
                                  text="Go to\nDispensing\nScreen", 
                                  style="Button.TButton",
                                  command=lambda: switch_to_dispensing_screen(window))
    dispensing_button.grid(row=0, column=2, rowspan=3, padx=20, pady=20, 
                          ipadx=30, ipady=50, sticky="ns")

    display_drawer_status(window, selected_cabinet, name_in, label_in, brand_in, exp_in, ndc_in, desc_in, preselect)