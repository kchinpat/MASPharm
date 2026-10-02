"""Legacy JSON-mutating screen retired. Loading is implemented in pharm.app.App."""
def loading_screen(window, preselect=None):
    raise RuntimeError("Use UI/main.py; loading requires an authenticated inventory session.")
