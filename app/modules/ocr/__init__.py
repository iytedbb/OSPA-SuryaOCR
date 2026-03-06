from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')
frontend_bp = Blueprint('frontend', __name__)

from . import SuryaOCR_backend
from . import routes
from .on_isleme_main import preprocess_bp
