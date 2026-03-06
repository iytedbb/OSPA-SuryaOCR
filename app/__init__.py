
from flask import Flask
from config import config
from app.extensions import db, cors, migrate

def create_app(config_name='default'):
    """Application factory function."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Enable template auto-reloading and disable caching for development
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
    # Initialize extensions
    db.init_app(app)
    cors.init_app(app, resources={r"/*": {"origins": "*"}})
    migrate.init_app(app, db)
    
    # Import models to register them with SQLAlchemy
    with app.app_context():
        from app import models
        db.create_all()
    
    # Register Blueprints
    from app.modules.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app.modules.ocr import api_bp, frontend_bp, preprocess_bp
    app.register_blueprint(api_bp) # /api prefix is defined in blueprint
    app.register_blueprint(frontend_bp)
    app.register_blueprint(preprocess_bp, url_prefix='/preprocessing')
    
    @app.route('/health')
    def health_check():
        return {"status": "ok", "app": "OSPASuryaOCR"}
        
    return app
