"""Compatibility entry point. All routes live in secure_api.py."""
try:
    from .secure_api import create_app, main
except ImportError:
    from secure_api import create_app, main
if __name__ == "__main__":
    main()
