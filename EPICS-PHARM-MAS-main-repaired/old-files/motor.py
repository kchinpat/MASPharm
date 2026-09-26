# start, stop and reverse direction

import tkinter as tk
import tkinter
from tkinter import Toplevel
import tkinter.ttk as ttk
from tkinter import messagebox
from tkinter import simpledialog
import os

import StepperMotorSerialInput


def start(button, root):
    StepperMotorSerialInput.setSpeed(100)
    return messagebox.showinfo("Action", "Starting Motor")


def stop(button, root):
    StepperMotorSerialInput.setSpeed(0)
    return messagebox.showinfo("Action", "Stopping Motor")
   

def reverse_direction(button, root):
    StepperMotorSerialInput.reverse()
    return messagebox.showinfo("Action", "Reversing Direction")



def change_speed(event=None):
    try:
        speed_val = float(speed_entry.get())
        if speed_val < 0:
            return messagebox.showwarning("Invalid Input", "Error: Please enter a valid numerical value.")
        elif speed_val == 0:
            return messagebox.showwarning("Invalid Input", "Error: Please enter a valid numerical value. \nIf you wish to stop the motor, use the STOP MOTOR button.")

        else:
            current_speed_label.config(text = f"Current Steps Per Rotation: {speed_val}")
            print(f"Speed applied: {speed_val}")
            StepperMotorSerialInput.setSpeed(speed_val)
    except ValueError:
        messagebox.showwarning("Invalid Input", "Error: Please enter a valid numerical value.")
    return 0



def main():
    global speed_entry, current_speed_label
    root = tk.Tk()
    root.title('Stepper Motor Control')
   # root.state('zoomed')

    header = ttk.Label(root, text = 'Motor Control', foreground = 'black',
                       font = ('Times New Roman', 20, 'bold')).grid(row=0, column=0, padx= 50, pady=50)

    style = ttk.Style()
    style.configure("Button.TButton", foreground = 'black', background = 'black',
                    font = ('arial', 12) )
    


    # speed entry
    speed_entry = ttk.Entry(root)
    speed_entry.grid(row=2, column=1, padx = 20, pady=20)


    speed_label = ttk.Label(root, text='Enter speed below:', foreground = 'black',
    font = ('Arial', 12))
    speed_label.grid(row=1, column=1)


    current_speed_label = ttk.Label(root, text="Current Steps Per Rotation (speed): N/A", foreground='black',
                                    font=('arial', 10))
    current_speed_label.grid(row=3, column=1, pady=20, padx=25)


    #buttons 

    start_button = ttk.Button(root, text = 'Start Motor', style= 'Button.TButton', command=lambda: start(start_button, root))
    start_button.grid(row=1, column=0,padx=20, pady=20, ipadx=20, ipady=20)

    stop_button = ttk.Button(root, text = 'Stop Motor', style= 'Button.TButton', command=lambda: stop(stop_button, root))
    stop_button.grid(row=2, column=0,padx=20, pady=20, ipadx=20, ipady=20)


    reverse_button = ttk.Button(root, text = 'Reverse Motor', style= 'Button.TButton', command=lambda: reverse_direction(reverse_button, root))
    reverse_button.grid(row=3, column=0,padx=20, pady=20, ipadx=20, ipady=20)

    """ if you want a button for speed:"""

    #speed = ttk.Button(root, text = 'Change Speed', command=change_speed)
    #speed.grid(row=3, column=1, padx=20, pady=20, ipadx=20, ipady=20)
     # button that ACTUALLY applies it
    

    speed_entry.bind("<Return>", change_speed)

   
    root.mainloop()
if __name__ == "__main__":
    
    main()
