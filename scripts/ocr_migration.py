
import shutil
from pathlib import Path

def migrate_ocr_module():
    base_dir = Path(__file__).resolve().parent.parent
    
    # Hedef
    ocr_module = base_dir / "app/modules/ocr"
    ocr_module.mkdir(parents=True, exist_ok=True)
    
    # Kaynak
    backend_dir = base_dir / "app/backend"
    database_dir = base_dir / "app/database" # Bazı dosyalar burada olabilir
    
    files_to_move = [
        "SuryaOCR_backend.py",
        "GazeteOCRProcessor.py",
        "ProcessingProgressTracker.py",
        "DocumentMetadata.py",
        "database_integration.py",
        "on_isleme_main.py"
    ]
    
    for filename in files_to_move:
        # Önce backend'de ara, sonra database'de
        src = backend_dir / filename
        if not src.exists():
            src = database_dir / filename
            
        if src.exists():
            dst = ocr_module / filename
            shutil.copy2(src, dst)
            print(f"Copied {src} -> {dst}")
        else:
            print(f"Warning: File not found {filename}")

    # Init file create
    init_file = ocr_module / "__init__.py"
    if not init_file.exists():
        with open(init_file, 'w') as f:
            f.write("from flask import Blueprint\n\nocr_bp = Blueprint('ocr', __name__)\n\nfrom . import SuryaOCR_backend\n")
            # SuryaOCR_backend artık routes içerecek veya init olacak
            
if __name__ == "__main__":
    migrate_ocr_module()
