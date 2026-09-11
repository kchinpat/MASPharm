import tkinter as tk
from tkinter import messagebox, simpledialog
import tkinter.ttk as ttk
import json
# import manual_load2
import edit_func
from typing import Tuple
from PIL import Image, ImageTk
from image_new import load_medicine_image
import textwrap
# from tkinter import Scrollbar
from client_api import open_drawer
from clear_frame import clear_frame

from screen_controller import switch_to_loading_screen

def dispense_with_verification(compartment_num: int):
    with open("medecine_data.json", "r") as f:
        data = json.load(f)

    medication = next((m for m in data if m['cabinet_number'] == compartment_num), None)
    print(medication)

    if medication and medication['fill_status']:
        expected_ndc =  medication['current_stored_medecine'].get('ndc', '')
        expected_ndc = (''.join(c for c in expected_ndc if c.isdigit()))
    else:
        messagebox.showerror("Error", "There is no ndc code associated with this compartment")
        return

    num_medications_dispensing = simpledialog.askinteger(
        "Number of medications dispensing",
        f"Please indicate the number of {medication['current_stored_medecine']['generic_name']} you are dispensing",
        initialvalue=1
    )

    if type(num_medications_dispensing) != int or num_medications_dispensing <= 0:
        messagebox.showerror("Error", "Did not indicate a vaild number")
        return

    if num_medications_dispensing > medication['quantity']:
        messagebox.showerror("Error", "Attempting to dispensing more medications then are in the compartment")
        return

    open_drawer(compartment_num)

    failed_dispensing = False
    for i in range(num_medications_dispensing):
        scanned_ndc = simpledialog.askstring(
            "NDC Verification",
            f"Please scan medication number {i + 1} out of {num_medications_dispensing} you are dispensing. Expecting {expected_ndc}."
        )

        # Do this for now. TODO change the ndc input into the loading screen
        try:
            is_valid_entry = int(scanned_ndc) == int(expected_ndc)
        except:
            is_valid_entry = False

        if not is_valid_entry:
            messagebox.showinfo("NDC Verification",f"INCORRECT NDC.\nExpecting {expected_ndc}.\nGot {scanned_ndc}.")
            failed_dispensing = True
            break
        # else:
        #     messagebox.showinfo("NDC Verification",f"Verified dispensed {medication['generic_name']}")
    if not failed_dispensing:
        messagebox.showinfo("NDC Verification",f"Verified dispensed {medication['current_stored_medecine']['generic_name']}")
        medication['quantity'] -= num_medications_dispensing
        if medication['quantity'] <= 0:
            messagebox.showinfo("Please verify that compartment is now empty")
        data[compartment_num - 1] = medication
        with open("medecine_data.json", "w") as f:
            json.dump(data, f, indent=4)

def load(filename):
    with open(filename, "r") as file:
        data = json.load(file)
    return data


def delete_medicine(tuple_of_buttons: Tuple[ttk.Button], 
                    tuple_of_img_labels: Tuple[ttk.Label], 
                    tuple_of_parent_frames: Tuple[ttk.Frame], 
                    cabinet_number: int):
    confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to unload the medication in Compartment {cabinet_number}?")
    
    if confirm:
        with open("medecine_data.json", "r") as f:
            data = json.load(f)

        # Update data for the selected cabinet
        for m in data:
            if m['cabinet_number'] == cabinet_number:
                m['fill_status'] = False
                m['current_stored_medecine'] = {}
                m['quantity'] = 0

        # Save updated data
        with open("medecine_data.json", "w") as f:
            json.dump(data, f, indent=4)

        # Update UI: label and image
        idx = cabinet_number - 1
        button = tuple_of_buttons[idx]
        button.config(text=f"Compartment {cabinet_number}\n[EMPTY]\n\nCLICK TO DISPENSE")

        # Remove image from frame
        for widget in tuple_of_parent_frames[idx].winfo_children():
            widget.destroy()

        ask = messagebox.askyesno("Confirm Open", f"Would you like to open to retrieve medicine in Compartment {cabinet_number}?")
        if ask:
            open_drawer(cabinet_number)

def add_medicine(main_ui_root, number):
    # Import here to avoid circular import
    # import manual_load2
    # manual_load2.main(main_ui_root, tuple_of_buttons, tuple_of_img_labels, tuple_of_parent_frames, number)
    switch_to_loading_screen(main_ui_root, number)


def dispensing_screen(window):
    clear_frame(window)

    medicine_data = load("medecine_data.json")

    # Style configuration
    # style = ttk.Style()
    # style.configure("Button.TButton", foreground='black', background='black', font=('Arial', 12))
    # style.configure("Edit.TButton", foreground='black', background='black')

    buttons_container = ttk.Frame(window)
    buttons_container.pack(fill='x', padx=10, pady=10)

    # Header section
    search_header = ttk.Label(buttons_container, text="EPICS-PHARM-MAS", foreground="black", font=('', 18, 'underline'))
    search_header.grid(row=0, column=0, columnspan=2)
 
    sub_header = ttk.Label(buttons_container, text="Dispensing Menu", foreground="black", font=('', 15, 'underline'))
    sub_header.grid(row=1, column=0, columnspan=2)

    # Configure grid weights
    buttons_container.grid_columnconfigure(0, weight=1)
    buttons_container.grid_columnconfigure(1, weight=0)

    # Top right frame for control buttons
    top_right_frame = ttk.Frame(buttons_container)
    top_right_frame.grid(row=0, column=1, sticky="ne", padx=10, pady=10)

    manual_open = ttk.Button(top_right_frame, text="Manual Unlock", style="Button.TButton", 
                           command=lambda: open_drawer(1))
    manual_open.grid(row=0, column=0, padx=5, pady=5, ipadx=20, ipady=20)

    # Main drawers container
    drawers_frame = ttk.Frame(buttons_container)
    drawers_frame.grid(row=2, column=0, columnspan=2, pady=20)

    # Initialize lists to store references
    drawer_buttons = []
    img_labels = []
    parent_frames = []
    drawer_frames = []
    quantity_labels = []

    # Create compartments using a loop
    num_compartments = 4
    for i in range(num_compartments):
        cabinet_number = i + 1
        
        # Find medicine data for this cabinet
        comp_label = ""
        comp_ndc = None
        for m in medicine_data:
            if m['cabinet_number'] == cabinet_number:
                if m['fill_status']:
                    comp_label_list = textwrap.wrap(m['current_stored_medecine']['generic_name'], width=22)
                    for a in comp_label_list:
                        comp_label += "-\n" + a
                    comp_label = comp_label.replace("-\n", "", 1)
                    comp_ndc = m['current_stored_medecine']['ndc']
                else:
                    comp_label = 'EMPTY'
                    comp_ndc = None

        row = 0
        col = i

        # Create drawer frame
        drawer_frame = ttk.Frame(drawers_frame)
        drawer_frame.grid(row=row, column=col, padx=50)
        drawer_frames.append(drawer_frame)

        # Create image frame (above button)
        img_frame = ttk.Frame(drawer_frame, relief="solid", borderwidth=2)
        img_frame.grid(row=0, column=0, padx=10, pady=10, ipady=100, ipadx=100, sticky="nsew")
        img_frame.grid_propagate(False)
        parent_frames.append(img_frame)

        # Load medicine image
        img_label = load_medicine_image(img_frame, comp_ndc)
        img_labels.append(img_label)

        # Create dispense button (below image)
        drawer_button = ttk.Button(
            drawer_frame,
            text=f"Compartment {cabinet_number}\n[{comp_label}]\n\nCLICK TO DISPENSE",
            style="Button.TButton",
            width=15,
            # command=lambda num=cabinet_number: open_drawer(num),
            command=lambda num=cabinet_number: dispense_with_verification(num),
        )
        drawer_button.grid(row=1, column=0, padx=10, pady=10, ipady=30, ipadx=50)
        drawer_buttons.append(drawer_button)

        quantity_label = ttk.Label(drawer_frame, text=f"Quantity: {medicine_data[i]['quantity']}")
        quantity_label.grid(row=2, column=0, columnspan=2, pady=10)
        quantity_labels.append(quantity_label)

        # Create edit button
        edit_button = ttk.Button(
            drawer_frame, 
            text='Edit', 
            style='Edit.TButton', 
            command=lambda num=cabinet_number: add_medicine(window, num)
        )
        edit_button.grid(row=3, column=0, columnspan=2, pady=10)

        # Create unload button
        unload_button = ttk.Button(
            drawer_frame, 
            text='Unload', 
            style='Edit.TButton',
            command=lambda num=cabinet_number: delete_medicine(tuple(drawer_buttons), tuple(img_labels), tuple(parent_frames), num)
        )
        unload_button.grid(row=4, column=0, columnspan=2, pady=5)

    # Add "Load Medication" button to top right frame
    add_button = ttk.Button(
        top_right_frame, 
        text="Load Medication", 
        style="Button.TButton", 
        command=lambda: add_medicine(window, 0)
    )
    add_button.grid(row=1, column=0, padx=5, pady=5, ipadx=20, ipady=20)
