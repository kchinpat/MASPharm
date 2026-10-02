def switch_to_loading_screen(window, preselect=None):
    from loading_screen import loading_screen
    loading_screen(window, preselect)

def switch_to_dispensing_screen(window):
    from dispensing_screen import dispensing_screen
    dispensing_screen(window)