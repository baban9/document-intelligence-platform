"""WSGI entry point for production servers."""

from docintel.app import create_app

app = create_app()
