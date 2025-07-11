from flask import Flask
from .routes import register_routes

def create_app():
    app = Flask(__name__)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    register_routes(app)
    return app
