from dispensing_screen import dispensing_screen
import tkinter as tk
import json
from global_db import prods # in order to load the db into ram on bootup of application

if __name__ == "__main__":

    window = tk.Tk()
    window.title("Home")
    window.wm_state('normal')

    window.attributes('-fullscreen', True)
    window.bind('<Escape>', lambda e: window.attributes('-fullscreen', False))
    print(type(prods))


    dispensing_screen(window)
    window.mainloop()