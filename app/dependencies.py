from fastapi.templating import Jinja2Templates
from .config import TEMPLATE_DIRS

# Shared template loader
templates = Jinja2Templates(directory=[str(p) for p in TEMPLATE_DIRS])


def get_templates():
    return templates
