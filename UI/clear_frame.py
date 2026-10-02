def clear_frame(window):
    for widget in window.winfo_children():
        widget.destroy()