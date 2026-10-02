import tkinter as tk
import tkinter
from tkinter import Toplevel
import tkinter.ttk as ttk
from tkinter import messagebox
from tkinter import simpledialog
from PIL import Image, ImageTk
import os
import Serial_Input_Final


def popup(drawer):
     messagebox.showinfo("Action", f"Opening Compartment {drawer}")

     return
    
    
def open_compartment(drawer, root): 
    # fx goes HERE
    popup(drawer)
    Serial_Input_Final.rgbOn(drawer)
    # other_drawers = [1, 2, 3, 4]
    # other_drawers.remove(drawer)

    # for other in other_drawers:  
    #     Serial_Input_Final.rgbOff(other)

    return


def control_lock(button,root): 

    if button['text'] == 'Drawer Locked':
          button.config(text = 'Drawer Unlocked', style='Unlocked_Button.TButton')
          messagebox.showinfo("Action", f'Drawer is now unlocked.')
    
    Serial_Input_Final.emUnlock()    

    return 0 


def main():
    root = tk.Tk()
    root.title("MAS Drawer Test 1")
    root.state('zoomed') 
    
    

    header= ttk.Label(root, text = "Drawer Management", foreground ='black', background = 'lightgray', 
              font =('Segoe UI', '40', ''),
              relief = 'raised').grid(row=0, column=0, padx= 50, pady=50, sticky='n')
    
    style = ttk.Style() #drawer buttons style
    style.configure('Type1Button.TButton', foreground = 'black',borderwidth =2,
                    font= ('Arial', 24, ''), relief='raised',cursor ='hand2')

   
    lock_style = ttk.Style()
    lock_style.configure('Lock_Button.TButton', foreground = 'red', background='black', 
                         font=('Arial', 15, 'bold'), relief='raised', padding=20)

    unlock_style = ttk.Style()
    unlock_style.configure('Unlocked_Button.TButton', foreground = 'green', background='black',  
                           font=('Arial', 15, 'bold'), relief='raised', padding=20)

    frame = tk.Frame(root, bg='lightgray', width=500, height=500)
    frame.grid(row=1, column=0, padx=50, pady=50, sticky='nsew')


    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=0)
    root.rowconfigure(1, weight=1)
    frame.columnconfigure((0, 1), weight=1)
    frame.rowconfigure((0, 1), weight=1)


    #=========
    # BUTTONS 
    
    unlock = ttk.Button(root, text="Drawer Locked", style = 'Lock_Button.TButton',command=lambda: control_lock(unlock,root))
    unlock.grid(row=0, column=0, padx=(50), pady=50, ipadx=50, ipady= 50, sticky='e')


  
    comp1 = ttk.Button(frame, text = 'Compartment 1', compound='bottom', 
                       style ='Type1Button.TButton', command=lambda: open_compartment(1,root))
    comp1.grid(row=0,column=0,ipadx=100, ipady=100)
                      
  
    comp2 = ttk.Button(frame, text = 'Compartment 2', compound='bottom', 
                       style ='Type1Button.TButton', command=lambda: open_compartment(2,root))
    comp2.grid(row=0, column=1,ipadx=100, ipady=100)


    comp3 = ttk.Button(frame, text = 'Compartment 3', compound='bottom', 
                       style ='Type1Button.TButton', command=lambda: open_compartment(3,root))
    comp3.grid(row=1,column=0,ipadx=100, ipady=100)

    comp4 = ttk.Button(frame, text = 'Compartment 4', compound='bottom', 
                       style ='Type1Button.TButton', command=lambda: open_compartment(4,root))
    comp4.grid(row=1, column=1,ipadx=100, ipady=100)


    root.mainloop()



if __name__ == "__main__":
    
    main()
