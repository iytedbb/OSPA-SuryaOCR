import os
from flask import render_template, send_from_directory, current_app
from . import frontend_bp

@frontend_bp.route('/')
def landing_page():
    return render_template('landing.html')

@frontend_bp.route('/ocr')
def index():
    # Serve the modernized React app from the dist directory
    dist_dir = os.path.join(current_app.root_path, 'static', 'dist')
    return send_from_directory(dist_dir, 'index.html')

@frontend_bp.route('/preprocessing-info')
def preprocessing_info_page():
    return render_template('preprocessing_info.html')

@frontend_bp.route('/ocr-info')
def ocr_info_page():
    return render_template('ocr_info.html')

@frontend_bp.route('/about')
def about_page():
    # Fallback if about.html doesn't exist, though it should be handled by templates
    return render_template('about.html')

@frontend_bp.route('/contact')
def contact_page():
    return render_template('contact.html')
