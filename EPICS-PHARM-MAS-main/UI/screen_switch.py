import tkinter as tk
from tkinter import Button,Label


def clear_frame():
    for widget in window.winfo_children():
        widget.destroy()


def screen_two():
    clear_frame()
    button_2 = Button(window, text="Go to  screen one", command=lambda: screen_one())
    button_2.pack(pady=10)
    label_2 = Label(window, text="Label on window two")
    label_2.pack(pady=10)


def screen_one():
    clear_frame()
    button_1 = Button(window, text="Go to screen two", command=lambda: screen_two())
    button_1.pack(pady=10)
    label_1 = Label(window, text="Label on window one")
    label_1.pack(pady=10)


window = tk.Tk()
window.title("Test")
window.geometry('250x100')

screen_one()
window.mainloop()