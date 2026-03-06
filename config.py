#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuryaOCR Production Configuration
================================
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
load_dotenv(dotenv_path=BASE_DIR / ".env")
APP_DIR = BASE_DIR / "app"
BACKEND_DIR = APP_DIR / "modules" / "ocr"
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
DATABASE_DIR = APP_DIR / "database"

class Config:
    """Base configuration class"""
    
    # Application
    APP_NAME = "SuryaOCR Production"
    APP_VERSION = "1.0.0"
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    
    # Flask
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    TESTING = False
    
    # Server
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', 5000))
    THREADED = True
    
    # Paths
    UPLOADS_DIR = BASE_DIR / os.environ.get('UPLOADS_DIR', 'uploads')
    OUTPUTS_DIR = BASE_DIR / os.environ.get('OUTPUTS_DIR', 'outputs')
    MODELS_DIR = BASE_DIR / os.environ.get('MODELS_DIR', 'models')
    LOGS_DIR = BASE_DIR / os.environ.get('LOGS_DIR', 'logs')
    CACHE_DIR = BASE_DIR / 'cache'
    
    # Preprocessing paths
    PREPROCESSING_OUTPUTS_DIR = BASE_DIR / 'preprocessing_outputs'
    PREPROCESSING_CACHE_DIR = BASE_DIR / 'preprocessing_cache'
    
    # File Upload
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    UPLOAD_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp'}
    
    # Database
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME', 'ospa_suryaocr')

    if DB_PASSWORD and DB_NAME:
        DATABASE_URL = os.environ.get('DATABASE_URL', f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    else:
        DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR}/app.db')
        
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # GPU & Processing
    CUDA_VISIBLE_DEVICES = os.environ.get('CUDA_VISIBLE_DEVICES', '0')
    TORCH_CUDA_ARCH_LIST = os.environ.get('TORCH_CUDA_ARCH_LIST', '8.6')
    PROCESSING_TIMEOUT = 3600  # 1 hour
    MAX_CONCURRENT_JOBS = 3
    
    # Preprocessing settings
    PREPROCESSING_ENABLED = True
    PREPROCESSING_MAX_CONCURRENT_JOBS = 2
    PREPROCESSING_TIMEOUT = 1800  # 30 minutes
    PREPROCESSING_CLEANUP_HOURS = 24  # Auto cleanup after 24 hours
    
    # Security
    CORS_ORIGINS = ['http://localhost:3000', 'http://localhost:5000', 'http://127.0.0.1:5000']
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = LOGS_DIR / 'surya_ocr.log'
    
    @classmethod
    def init_app(cls, app):
        """Initialize Flask app with configuration"""
        # Create necessary directories
        cls.create_directories()
        
        # Set up logging
        cls.setup_logging()
        
        # Configure GPU if available
        cls.setup_gpu()

    @classmethod
    def create_directories(cls):
        """Create necessary directories"""
        directories = [
            cls.UPLOADS_DIR,
            cls.OUTPUTS_DIR, 
            cls.MODELS_DIR,
            cls.LOGS_DIR,
            cls.CACHE_DIR,
            cls.PREPROCESSING_OUTPUTS_DIR,
            cls.PREPROCESSING_CACHE_DIR,
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def setup_logging(cls):
        """Setup application logging"""
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Create logs directory
        cls.LOGS_DIR.mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL),
            format=cls.LOG_FORMAT,
            handlers=[
                logging.StreamHandler(sys.stdout),
                RotatingFileHandler(
                    cls.LOG_FILE,
                    maxBytes=10*1024*1024,  # 10MB
                    backupCount=5
                )
            ]
        )

    @classmethod
    def setup_gpu(cls):
        """Setup GPU configuration"""
        try:
            import torch
            if torch.cuda.is_available():
                # Set CUDA device
                if cls.CUDA_VISIBLE_DEVICES:
                    os.environ['CUDA_VISIBLE_DEVICES'] = cls.CUDA_VISIBLE_DEVICES
                
                # Set CUDA architecture
                if cls.TORCH_CUDA_ARCH_LIST:
                    os.environ['TORCH_CUDA_ARCH_LIST'] = cls.TORCH_CUDA_ARCH_LIST
                
                print(f"🎮 GPU configured: {torch.cuda.get_device_name(0)}")
            else:
                print("⚠️  No GPU available, using CPU")
                
        except ImportError:
            print("⚠️  PyTorch not available for GPU configuration")

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'
    CORS_ORIGINS = ['*']  # Allow all origins in development
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'
    
    # Enhanced security for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Production optimizations
    JSONIFY_PRETTYPRINT_REGULAR = False
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DATABASE_URL = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class UniversityConfig(ProductionConfig):
    """University-specific production configuration"""
    
    # University-specific settings
    UNIVERSITY_NAME = os.environ.get('UNIVERSITY_NAME', 'University Name')
    DEPARTMENT = os.environ.get('DEPARTMENT', 'Computer Science')
    CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'support@university.edu')
    
    # Network settings for university environment
    PROXY_FIX = True  # Enable if behind university proxy
    
    # Enhanced monitoring for university IT
    MONITORING_ENABLED = True
    HEALTH_CHECK_ENDPOINT = '/health'
    METRICS_ENDPOINT = '/metrics'
    
    # University compliance
    DATA_RETENTION_DAYS = 30  # Automatic cleanup after 30 days
    PRIVACY_COMPLIANCE = True
    AUDIT_LOGGING = True

# Configuration mapping
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'university': UniversityConfig,
    'default': UniversityConfig
}

config = config_by_name # Alias for app/__init__.py

def get_config() -> Config:
    """Get configuration based on environment"""
    config_name = os.environ.get('FLASK_ENV', 'university')
    return config_by_name.get(config_name, UniversityConfig)

# System information
def get_system_info() -> Dict[str, Any]:
    """Get system information for diagnostics"""
    import platform
    import psutil
    
    info = {
        'platform': {
            'system': platform.system(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
        },
        'memory': {
            'total': psutil.virtual_memory().total,
            'available': psutil.virtual_memory().available,
            'used_percent': psutil.virtual_memory().percent,
        },
        'disk': {
            'total': psutil.disk_usage('.').total,
            'free': psutil.disk_usage('.').free,
            'used_percent': (psutil.disk_usage('.').used / psutil.disk_usage('.').total) * 100,
        },
        'cpu': {
            'count': psutil.cpu_count(),
            'usage_percent': psutil.cpu_percent(interval=1),
        }
    }
    
    # GPU information
    try:
        import torch
        if torch.cuda.is_available():
            info['gpu'] = {
                'available': True,
                'device_count': torch.cuda.device_count(),
                'current_device': torch.cuda.current_device(),
                'device_name': torch.cuda.get_device_name(0),
                'memory_allocated': torch.cuda.memory_allocated(0),
                'memory_reserved': torch.cuda.memory_reserved(0),
            }
        else:
            info['gpu'] = {'available': False}
    except ImportError:
        info['gpu'] = {'available': False, 'error': 'PyTorch not installed'}
    
    return info

def validate_configuration() -> bool:
    """Validate configuration and environment"""
    config = get_config()
    
    # Check required directories
    required_dirs = [
        BACKEND_DIR,
        TEMPLATES_DIR,
    ]
    
    for directory in required_dirs:
        if not directory.exists():
            print(f"❌ Required directory missing: {directory}")
            return False
    
    # Check required files
    required_files = [
        BACKEND_DIR / "SuryaOCR_backend.py",
        TEMPLATES_DIR / "index.html",
    ]
    
    for file_path in required_files:
        if not file_path.exists():
            print(f"❌ Required file missing: {file_path}")
            return False
    
    # Check Python version
    if sys.version_info < (3, 11):
        print(f"❌ Python 3.11+ required, found {sys.version}")
        return False
    if sys.version_info >= (3, 12):
        print(f"⚠️  Python 3.12+ not tested, 3.11 recommended. Found {sys.version}")
    
    print("✅ Configuration validation passed")
    return True

# Export main configuration
__all__ = ['Config', 'get_config', 'get_system_info', 'validate_configuration']
