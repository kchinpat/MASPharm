import tkinter as tk
from tkinter import messagebox
import tkinter.ttk as ttk
import json

# should have parameter to only show info from that drawer

def load(root, name, label, brand, exp, ndc, desc, selected_cabinet):
    #idk what to do with the data is there a file or smth
    # Get string values from Text widgets
    name_str = name.get("1.0", "end-1c")
    label_str = label.get("1.0", "end-1c")
    brand_str = brand.get("1.0", "end-1c")
    exp_str = exp.get("1.0", "end-1c")
    ndc_str = ndc.get("1.0", "end-1c")
    desc_str = desc.get("1.0", "end-1c")

    current_stored_medecine = {}
    current_stored_medecine["generic_name"] = name_str
    current_stored_medecine["labeler_name"] = label_str
    current_stored_medecine["brand_name"] = brand_str
    current_stored_medecine["expiry_date"] = exp_str
    current_stored_medecine["ndc"] = ndc_str
    current_stored_medecine["description"] = desc_str 

    with open("medecine_data.json", "r") as f:
        data = json.load(f)
    
    data[selected_cabinet['cabinet_number'] - 1]["current_stored_medecine"] = current_stored_medecine
    data[selected_cabinet['cabinet_number'] - 1]["fill_status"] = True


    # print(data)
    with open("medecine_data.json", "w") as f:
        json.dump(data, f, indent=4)
    # Clear all input fields
    for widget in (name, label, brand, exp, ndc, desc):
        widget.delete("1.0", "end")
   
    # Find and destroy the old status frame
    for widget in root.winfo_children():
        if isinstance(widget, ttk.Frame):
            widget.destroy()
    
     


def display_drawer_status(root, selected_cabinet):
  
    if selected_cabinet['cabinet_number'] is None:
        return
    for widget in root.winfo_children():
        if isinstance(widget, ttk.Frame) and widget.winfo_name() == "status_frame":
            widget.destroy()
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

    # Create a frame for the cabinet status display
    status_frame = ttk.Frame(root)
    status_frame.grid(row=0, column=1, rowspan=14, padx=20, sticky="n")
    ttk.Label(status_frame, text="Cabinet Status", font=('Times New Roman', 16, 'bold')).pack(pady=5)
   
    try:
        with open("medecine_data.json", "r") as f:
            cabinets = json.load(f)
    except FileNotFoundError:
        ttk.Label(status_frame, text="Data file not found", font=('Times New Roman', 12, 'bold')).pack(pady=5)
        return


    cabinet_number = selected_cabinet['cabinet_number']
    cabinet_data = next((cab for cab in cabinets if cab["cabinet_number"] == cabinet_number), None)
    if not cabinet_data:
        ttk.Label(status_frame, text="Cabinet not found", font=('Times New Roman', 12, 'bold')).pack(pady=5)
        return  

    # Create frame for the selected cabinet
    cabinet_frame = tk.Frame(status_frame, 
                             relief="solid", 
                             highlightbackground='black',
                             highlightcolor='black',
                             highlightthickness=1,
                             background='white')
    cabinet_frame.pack(pady=5, padx=5, fill="x")

    # Cabinet number and status
    status_text = "FILLED" if cabinet_data["fill_status"] else "EMPTY"
    status_label = ttk.Label(cabinet_frame, 
                             text=f"Cabinet {cabinet_number} - {status_text}",
                             font=('Times New Roman', 12, 'bold'))
    status_label.pack(pady=2)

    # If the cabinet has medicine, display details
    if cabinet_data["fill_status"]:
        med = cabinet_data["current_stored_medecine"]
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


    return

def delete_medicine(cabinet, root):
    # Confirm deletion
    if not messagebox.askyesno("Action", "Are you sure you want to delete this medicine? This action cannot be undone."):
        return
    
    try:
        with open("medecine_data.json", "r") as f:
            data = json.load(f)   
        # Find the correct cabinet
        for x in data:
            if x["cabinet_number"] == cabinet['cabinet_number']:
                x["current_stored_medecine"] = {
                    "generic_name": "",
                    "labeler_name": "",
                    "brand_name": "",
                    "expiry_date": "",
                    "ndc": "",
                    "description": ""
                }
                x["fill_status"] = False  # Mark as empty
                break
        
        # Save updated data
        with open("medecine_data.json", "w") as f:
            json.dump(data, f, indent=4)
        messagebox.showinfo("Success", "Medicine deleted successfully.")
        
        # Refresh the UI
        display_drawer_status(root, cabinet)

    except FileNotFoundError:
        messagebox.showerror("Error", "Data file not found.")

    # MAKE SURE IT ACCEPTS THE RIGHT CABINET INFO 
    

    return

def main(drawer):

    root = tk.Tk()
    root.title('Manual Load')
    selected_cabinet = {'cabinet_number': drawer}
    ttk.Label(root, text='Edit Medicine Info', font=('Times New Roman', 20, 'bold')).grid(row=0, column=0, padx=50, pady=10)
    
    fields = [("Generic Name", 1), ("Labeler Name", 3), ("Brand Name", 5),("Expiration Date", 7), ("NDC Code", 9), ("Description", 11)]
    inputs = {}
    
    for label, row in fields:
        ttk.Label(root, text=label).grid(row=row, column=0)
        entry = tk.Text(root, height=1, width=20)
        entry.grid(row=row+1, column=0)
        inputs[label] = entry

    ttk.Button(root, text="Enter", style="Button.TButton", 
               command=lambda: load(root, inputs["Generic Name"], inputs["Labeler Name"], inputs["Brand Name"],
                                    inputs["Expiration Date"], inputs["NDC Code"], inputs["Description"], selected_cabinet)
               ).grid(row=13, column=0, ipadx=1, pady=25)
    ttk.Button(root, text="Delete", style="Button.TButton", command=lambda:delete_medicine(selected_cabinet, root)).grid(row=14,column=0,ipadx=1,pady=10)

    selected_cabinet['cabinet_number'] = drawer
    display_drawer_status(root, selected_cabinet)

    root.mainloop()

    return



    #MIGHT CAUSE AN ISUE LATER BC I WANT IT TO BE CALLED BASED ON WHATEVRER IS IN THE MAIN