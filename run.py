#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuryaOCR Production Launcher
============================
Eğer port kendini kapatmıyorsa:

Ayarlar → arama kutusuna “forward” yaz:

Remote: Auto Forward Ports → Off

Remote: Restore Forwarded Ports → Never (veya kapat)

source .venv/bin/activate

 python3 run.py

"""

import os
import sys
import subprocess
import platform
import time
from pathlib import Path

def check_python_version():
    """Python 3.11+ kontrolü"""
    if sys.version_info < (3, 11):
        print("❌ Python 3.11 gerekli!")
        print(f"   Mevcut sürüm: {sys.version}")
        # return False # Allow 3.10 for now if needed but user requires 3.11
    if sys.version_info >= (3, 12):
        print(f"⚠️  Python 3.12+ test edilmemiş, 3.11 önerilen. Mevcut: {sys.version}")
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} - OK")
    return True

def check_gpu():
    """GPU durumunu kontrol et"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"🎮 GPU bulundu: {gpu_name}")
            return True
        else:
            print("⚠️  GPU bulunamadı - CPU modu kullanılacak")
            return False
    except ImportError:
        print("⚠️  PyTorch bulunamadı - GPU kontrolü yapılamadı")
        return False

def check_required_files():
    """Gerekli dosyaları kontrol et"""
    print("\n📋 Dosyalar kontrol ediliyor...")
    
    # Mevcut dosya yapısına göre yollar (UPDATED)
    required_files = [
        "app/modules/ocr/SuryaOCR_backend.py",
        "app/modules/ocr/on_isleme_main.py",
        "app/templates/on_isleme_index.html",
        "app/templates/landing.html",
        "app/templates/index.html"
    ]
    
    # YOLO model kontrolü (opsiyonel)
    yolo_model_paths = [
        "app/database/models/doclayout_yolo_docstructbench_imgsz1024.pt",
        "models/doclayout_yolo_docstructbench_imgsz1024.pt",
        "app/modules/ocr/models/doclayout_yolo_docstructbench_imgsz1024.pt" 
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Eksik dosyalar:")
        for file in missing_files:
            print(f"   - {file}")
        print("\n💡 Lütfen README.md dosyasındaki talimatları takip edin.")
        return False
    
    # YOLO model kontrolü
    yolo_found = False
    for yolo_path in yolo_model_paths:
        if Path(yolo_path).exists():
            yolo_found = True
            print(f"✅ YOLO model bulundu: {yolo_path}")
            break
    
    if not yolo_found:
        print("☁️ Yerel YOLO model bulunamadı (Tespiti Hugging Face üzerinden indirecek).")
        print("   Aşağıdaki yerel konumlar boş (buralardan birine konursa HF tetiklenmez):")
        for path in yolo_model_paths:
            print(f"   - {path}")
    
    print("✅ Tüm dosyalar mevcut!")
    print("✅ Ön işleme entegrasyonu hazır!")
    return True

def open_browser(url):
    """Tarayıcıyı açar"""
    import webbrowser
    try:
        webbrowser.open(url)
    except Exception:
        print(f"⚠️  Tarayıcı otomatik açılamadı. Lütfen manuel erişin: {url}")

def start_application():
    """Uygulamayı başlat"""
    # 🎯 Adım 1: Kullanıcı Tercihini En Başta Al (Loglar karışmadan)
    print("\n" + "=" * 50)
    print("🌐 TARAYICI AYARI")
    print("=" * 50)
    print("💡 İPUCU: Uzak sunucuda (iş istasyonu vb.) çalışıyorsanız 'H' demelisiniz.")
    try:
        choice = input("❓ Uygulama hazır olduğunda tarayıcı otomatik açılsın mı? (E/H) [Varsayılan: H]: ").strip().lower()
    except EOFError:
        choice = 'h'
    auto_browser = choice in ['e', 'evet', 'y', 'yes']
    
    print("\n🚀 SuryaOCR modelleri ve sistem servisleri hazırlanıyor...")
    print("=" * 50)

    try:
        # Step 2: Load the app (heavy model loading happens here)
        from app import create_app
        app = create_app()
        
        host = '0.0.0.0'
        port = 5000
        base_url = f"http://{host}:{port}/"
        
        # Step 3: Browser opening logic in a separate thread to wait for port
        if auto_browser:
            def wait_and_open():
                import socket
                # Portun açılmasını bekle (max 60sn)
                ready = False
                for _ in range(60):
                    try:
                        with socket.create_connection((host, port), timeout=0.5):
                            ready = True
                            break
                    except OSError:
                        time.sleep(1)
                if ready:
                    time.sleep(2) # Son loglar için ekstra bekleme
                    print("\n" + "=" * 60)
                    print("🚀 SuryaOCR KULLANIMA HAZIR!")
                    print("=" * 60)
                    print(f"🔗 Adres: {base_url}")
                    print("=" * 60 + "\n")
                    open_browser(base_url)

            import threading
            threading.Thread(target=wait_and_open, daemon=True).start()

        print("\n" + "=" * 50)
        print("🔧 SISTEM SERVISLERI YÜKLENDİ")
        print("=" * 50)
        print(f"🏠 Ana Sayfa:      {base_url}")
        print(f"📋 OCR Paneli:     {base_url}ocr")
        print(f"✨ Ön İşleme:      {base_url}preprocessing")
        print(f"🔑 Admin Paneli:   {base_url}admin")
        print("=" * 50)

        print("\nℹ️  Sunucu logları aşağıda akacaktır. Durdurmak için: Ctrl+C")
        print("-" * 50)
        
        app.run(
            debug=False,
            host=host,
            port=port,
            threaded=True,
            use_reloader=False 
        )

    except Exception as e:
        print(f"❌ Uygulama başlatma hatası: {e}")
        import traceback
        traceback.print_exc()
        return False
    except KeyboardInterrupt:
        print("\n\n⏹️  Uygulama durduruldu.")
        return True

def main():
    """
    Main entry point for the SuryaOCR Launcher.
    Initializes the environment, sets the working directory, and orchestrates the startup sequence.
    """
    print("🎯 SuryaOCR Production Launcher")
    print("=" * 50)

    # Automatically resolve the absolute path of this script and set it as the working directory.
    project_root = Path(__file__).resolve().parent
    os.chdir(project_root)
    print(f"📂 Working Directory set to: {project_root}")

    # System Validation
    if not check_python_version():
        sys.exit(1)

    # Hardware Acceleration Check
    check_gpu()

    # Integrity Check (Files & Models)
    if not check_required_files():
        sys.exit(1)

    print("\n✅ System integrity check passed.")

    # Launch Application
    start_application()

if __name__ == "__main__":
    main()
