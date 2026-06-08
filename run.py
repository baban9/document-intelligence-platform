"""Run the document intelligence API locally."""

from docintel.app import create_app
from docintel.config import Config

app = create_app()


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
