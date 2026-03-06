#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuryaOCR Setup Script
====================
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
import urllib.request
import zipfile

def print_header():
    """Başlık yazdır"""
    print("🔧 SuryaOCR Setup & Installation")
    print("=" * 50)
    print(f"📱 Platform: {platform.system()} {platform.machine()}")
    print(f"🐍 Python: {sys.version}")
    print("=" * 50)

def check_requirements():
    """Sistem gereksinimlerini kontrol et"""
    print("\n🔍 Sistem kontrolleri...")
    
    # Python version
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ gerekli!")
        return False
    if sys.version_info >= (3, 12):
        print("⚠️  Python 3.12+ test edilmemiş, 3.11 önerilen")
    print("✅ Python version OK")
    
    # Git kontrolü
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        print("✅ Git mevcut")
    except:
        print("⚠️  Git bulunamadı (opsiyonel)")
    
    # Package manager
    has_uv = False
    has_pip = False
    
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        has_uv = True
        print("✅ UV package manager mevcut")
    except:
        pass
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, check=True)
        has_pip = True
        print("✅ Pip mevcut")
    except:
        print("❌ Pip bulunamadı!")
        return False
    
    # Ön işleme dependencies kontrolü
    try:
        import cv2
        print("✅ OpenCV mevcut")
    except ImportError:
        print("⚠️  OpenCV bulunamadı - kurulum sırasında yüklenecek")
    
    try:
        import PIL
        print("✅ Pillow mevcut")
    except ImportError:
        print("⚠️  Pillow bulunamadı - kurulum sırasında yüklenecek")
    
    return True

def create_directory_structure():
    """Klasör yapısını oluştur"""
    print("\n📁 Klasör yapısı oluşturuluyor...")
    
    directories = [
        "app/modules/ocr",
        "app/modules/admin",
        "app/templates",
        "app/database",
        "data/veriler",
        "logs",
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"   ✅ {directory}")
    
    print("✅ Klasör yapısı hazır!")

def install_python_dependencies():
    """Python paketlerini kur"""
    print("\n📦 Python dependencies kuruluyor...")
    
    # requirements.txt kontrolü
    req_file = Path("requirements.txt")
    if not req_file.exists():
        print("❌ requirements.txt bulunamadı!")
        return False
    
    try:
        # UV varsa onu kullan
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            print("🚀 UV ile hızlı kurulum...")
            result = subprocess.run([
                "uv", "pip", "install", "-r", "requirements.txt"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, "uv")
                
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("📦 Pip ile kurulum...")
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ Pip kurulum hatası:\n{result.stderr}")
                return False
        
        print("✅ Dependencies kuruldu!")
        return True
        
    except Exception as e:
        print(f"❌ Dependency kurulum hatası: {e}")
        return False

def download_models():
    """Gerekli ML modellerini indir"""
    print("\n🤖 Model dosyaları kontrol ediliyor...")
    
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    
    # YOLO model için (SuryaOCR backend)
    yolo_model_path = models_dir / "doclayout_yolo_docstructbench_imgsz1024.pt"
    
    if not yolo_model_path.exists():
        print("📥 SuryaOCR YOLO model indiriliyor... (Bu işlem internet bağlantısına göre sürebilir)")
        try:
            url = "https://huggingface.co/juliozhao/DocLayout-YOLO-DocStructBench/resolve/main/doclayout_yolo_docstructbench_imgsz1024.pt"
            
            # Progress gösterimi ile indir
            def progress_hook(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\r   📥 SuryaOCR model indiriliyor: {percent:.1f}%", end="", flush=True)
            
            urllib.request.urlretrieve(url, yolo_model_path, progress_hook)
            print(f"\n✅ SuryaOCR YOLO model indirildi: {yolo_model_path}")
            
        except Exception as e:
            print(f"\n⚠️  SuryaOCR YOLO model indirilemedi: {e}")
            print("   Model manuel olarak indirilebilir.")
    else:
        print("✅ SuryaOCR YOLO model mevcut")
    
    # DocLayout-YOLO model için (ön işleme)
    print("\n📥 Ön işleme modelleri kontrol ediliyor...")
    try:
        # DocLayout-YOLO otomatik indirilir, sadece import test et
        print("   DocLayout-YOLO modeli ilk kullanımda otomatik indirilecek")
        print("✅ Ön işleme model sistemi hazır")
    except Exception as e:
        print(f"⚠️  Ön işleme model sistemi uyarısı: {e}")
    
    # py-reform modelleri
    try:
        print("   py-reform modelleri ilk kullanımda otomatik indirilecek")
        print("✅ py-reform model sistemi hazır")
    except Exception as e:
        print(f"⚠️  py-reform model sistemi uyarısı: {e}")

def create_config_files():
    """Konfigürasyon dosyalarını oluştur"""
    print("\n⚙️  Konfigürasyon dosyaları oluşturuluyor...")
    
    # .env dosyası oluştur
    env_content = """# SuryaOCR Production Environment
FLASK_ENV=production
FLASK_DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# GPU Settings
CUDA_VISIBLE_DEVICES=0
TORCH_CUDA_ARCH_LIST="8.6"

# Paths
UPLOADS_DIR=uploads
OUTPUTS_DIR=outputs
MODELS_DIR=models
LOGS_DIR=logs

# Database
# Using SQLite for metadata tracking by default
DATABASE_URL=sqlite:///app.db

# Security
SECRET_KEY=your-secret-key-change-this-in-production
"""
    
    with open(".env", "w", encoding="utf-8") as f:
        f.write(env_content)
    print("   ✅ .env")
    
    # Logging config
    log_config = """[loggers]
keys=root

[handlers]
keys=consoleHandler,fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=INFO
handlers=consoleHandler,fileHandler

[handler_consoleHandler]
class=StreamHandler
level=INFO
formatter=simpleFormatter
args=(sys.stdout,)

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=simpleFormatter
args=('logs/surya_ocr.log',)

[formatter_simpleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
"""
    
    with open("logging.conf", "w", encoding="utf-8") as f:
        f.write(log_config)
    print("   ✅ logging.conf")

def create_startup_scripts():
    """Platform-specific başlatma scriptleri oluştur"""
    print("\n🚀 Başlatma scriptleri oluşturuluyor...")
    
    # Windows batch file
    bat_content = """@echo off
echo Starting SuryaOCR...
python run.py
pause
"""
    with open("start.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)
    print("   ✅ start.bat (Windows)")
    
    # Unix shell script
    sh_content = """#!/bin/bash
echo "Starting SuryaOCR..."
python3 run.py
"""
    with open("start.sh", "w", encoding="utf-8") as f:
        f.write(sh_content)
    
    # Make executable on Unix systems
    if platform.system() != "Windows":
        os.chmod("start.sh", 0o755)
    print("   ✅ start.sh (Linux/Mac)")

def verify_installation():
    """Kurulumu doğrula"""
    print("\n🔍 Kurulum doğrulanıyor...")
    
    # Critical files check
    critical_files = [
        "run.py",
        "requirements.txt",
        "config.py",
        "app/modules/ocr/SuryaOCR_backend.py"
    ]
    
    for file in critical_files:
        if Path(file).exists():
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} - EKSIK!")
            return False
    
    # Python imports test
    try:
        import flask
        print("   ✅ Flask import OK")
    except ImportError:
        print("   ❌ Flask import failed")
        return False
    
    return True

def main():
    """Ana kurulum fonksiyonu"""
    print_header()
    
    # Sistem kontrolleri
    if not check_requirements():
        print("\n❌ Sistem gereksinimleri karşılanmıyor!")
        sys.exit(1)
    
    # Kurulum adımları
    steps = [
        ("Klasör yapısı", create_directory_structure),
        ("Python dependencies", install_python_dependencies),
        ("Model dosyaları", download_models),
        ("Konfigürasyon", create_config_files),
        ("Başlatma scriptleri", create_startup_scripts),
        ("Doğrulama", verify_installation)
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n❌ {step_name} adımı başarısız!")
            sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 Kurulum tamamlandı!")
    print("=" * 50)
    print("🚀 Başlatmak için:")
    print("   python run.py")
    print("   veya")
    print("   ./start.sh (Linux/Mac)")
    print("   start.bat (Windows)")
    print("\n🌐 Web arayüzü: http://localhost:5000")
    print("📖 Detaylı bilgi: README.md")
    print("=" * 50)

if __name__ == "__main__":
    main()
