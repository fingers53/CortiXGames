from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.factory import create_app  # once you wire it
from app.security import get_current_user

app = create_app()
