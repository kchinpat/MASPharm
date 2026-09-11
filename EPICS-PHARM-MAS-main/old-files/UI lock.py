import tkinter as tk
import tkinter
from tkinter import Toplevel
import tkinter.ttk as ttk
from tkinter import messagebox
from tkinter import simpledialog
from PIL import Image, ImageTk
import os

import Serial_Input_Final

# write a function that actually does the "opening" that takes the drawer# as a parameter and will open that drawer


def popup(drawer):
    win = tk.Toplevel()
    win.wm_title("Drawer Action")
    sc_w = win.winfo_screenwidth()
    sc_h = win.winfo_screenheight()

    x = (sc_w // 2) - (200 // 2)
    y = (sc_h // 2) - (100 // 2)
    
    win.geometry(f'200x150+{x}+{y}')
    label = tk.Label(win, text= f"Opening Drawer {drawer}", font=('Segoe UI', '10')).grid(row=1, column=1, padx= 50, pady=50, sticky="nsew")
    
    
def open_compartment(drawer, root): 
    # fx goes HERE
    popup(drawer)

    return Serial_Input_Final.rgbOn(drawer)


def unlock_drawer(button, root):

   # if button['text'] == 'Drawer Locked':
    #    button.config(text = 'Drawer Unlocked', style='UnlockButton.TButton')
    #elif button['text'] == 'Drawer Unlocked':
     #   button.config(text='Drawer Locked', style='LockButton.Tbutton')

    
    return Serial_Input_Final.emUnlock()

## make either a separate button to lock it again, or some how be able to clikc it again to reverse it. 
#cus right now it doesnt change back. i think the issue is that its not actually setting the text name to unlocked permanently or something
# also, make it so that it doesnt expand the other drawers/affect the other columns as well. this probably has to do with the text formatting

 
def main():
    root = tk.Tk()
    root.title("MAS Drawer Test 1")
    root.state('zoomed') #automatically zooms in
  

    header= ttk.Label(root, text = "Drawer Test 1", foreground ='white', background = 'gray', 
              font =('Segoe UI', '40', 'bold'),
              relief = 'raised').grid(row=0, column=0, padx= 50, pady=50)


    style = ttk.Style() #set style for drawer buttons
    style.configure('Type1Button.TButton', foreground = 'black', borderwidth =4,
                    font= ('Arial', 24, ''), relief='raised',cursor ='hand2')
    


    ## TOGGLE APPEARANCE FOR THE OTHER THING FOR THE UNLOCK 

    temp_style = ttk.Style()
    temp_style.configure('Temp.TButton', foreground = 'black', background='black', font=('Arial', 15, 'bold'), relief='raised', padding=20)
   # lock_style = ttk.Style()
   # lock_style.configure('LockButton.TButton', foreground = 'red', background= 'red', font=('Arial', 15, 'bold'), relief='raised', padding=20)
   # unlock_style = ttk.Style()
   # unlock_style.configure('UnlockButton.TButton', foreground='green' ,background='green',font=('Arial', 15, 'bold'), relief='raised', padding=20)
    ####

    frame = tk.Frame(root, bg='lightgray', width=500, height=500)
    frame.grid(row=1, column=0, padx=50, pady=50, sticky='nsew')

    root.rowconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)

# kinda fucks it up and makes it like not totally right, i want the button to be on the right but it doesnt sean 

    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(0, weight=1)
    frame.rowconfigure(1, weight=1)
      


    #=========
    # BUTTONS 
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    neosporin_path = os.path.join(current_dir, 'neosporin.jpg')
    toothpaste_path = os.path.join(current_dir, 'toothpaste.jpg')
    sunscreen_path = os.path.join(current_dir, 'sunscreen.jpg')
    soap_path = os.path.join(current_dir, 'soap.jpg')
   
    neosporin_img = Image.open(neosporin_path)
    neosporin_img = neosporin_img.resize((300, 200), Image.LANCZOS)
    neosporin_photo = ImageTk.PhotoImage(neosporin_img)

    toothpaste_img = Image.open(toothpaste_path)
    toothpaste_img = toothpaste_img.resize((300, 100), Image.LANCZOS)
    toothpaste_photo = ImageTk.PhotoImage(toothpaste_img)

    sunscreen_img = Image.open(sunscreen_path)
    sunscreen_img = sunscreen_img.resize((300, 200), Image.LANCZOS)
    sunscreen_photo = ImageTk.PhotoImage(sunscreen_img)

    soap_img = Image.open(soap_path)
    soap_img = soap_img.resize((300, 200), Image.LANCZOS)
    soap_photo = ImageTk.PhotoImage(soap_img)

    
  ## UNLOCK DRAWER BUTTON

    unlock = ttk.Button(root, text="Unlock Drawer", style = 'Temp.TButton',command=lambda: unlock_drawer(unlock,root))
    unlock.grid(row=0, column=1, ipadx=50, ipady=50)


    ## MAYBE ADD SOME KIND OF INPUT BELOW IT

    
  
    comp1 = ttk.Button(frame, text = 'Compartment 1', compound='bottom', style ='Type1Button.TButton', command=lambda: open_compartment(1,root))
    comp1.grid(row=0,column=0,ipadx=100, ipady=100)
                      
  
    comp2 = ttk.Button(frame, text = 'Compartment 2', compound='bottom', style ='Type1Button.TButton', command=lambda: open_compartment(2,root))
    comp2.grid(row=0, column=1,ipadx=100, ipady=100)


    comp3 = ttk.Button(frame, text = 'Compartment 3', compound='bottom', style ='Type1Button.TButton', command=lambda: open_compartment(3,root))
    comp3.grid(row=1,column=0,ipadx=100, ipady=100)

    comp4 = ttk.Button(frame, text = 'Compartment 4', compound='bottom', style ='Type1Button.TButton', command=lambda: open_compartment(4,root))
    comp4.grid(row=1, column=1,ipadx=100, ipady=100)

   

    root.mainloop()



if __name__ == "__main__":
    
    main()
