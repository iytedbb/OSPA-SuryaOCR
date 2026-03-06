
import shutil
import os
from pathlib import Path

def setup_directories():
    base_dir = Path(__file__).resolve().parent.parent
    
    # Hedef Diziler
    app_admin_tpl = base_dir / "app/templates/admin"
    app_admin_static = base_dir / "app/static/admin"
    
    app_admin_tpl.mkdir(parents=True, exist_ok=True)
    app_admin_static.mkdir(parents=True, exist_ok=True)
    
    # Kaynak Dosyalar
    db_templates = base_dir / "app/database/templates"
    db_static = base_dir / "app/database/static"
    
    # Copy Template
    source_tpl = db_templates / "admin_panel_index.html"
    dest_tpl = app_admin_tpl / "index.html"
    
    if source_tpl.exists():
        shutil.copy2(source_tpl, dest_tpl)
        print(f"Copied {source_tpl} -> {dest_tpl}")
    else:
        print(f"Source template not found: {source_tpl}")

    # Copy Static Files
    if db_static.exists():
        if app_admin_static.exists():
            shutil.rmtree(app_admin_static) # Clean existing
        shutil.copytree(db_static, app_admin_static)
        print(f"Copied {db_static} -> {app_admin_static}")

    # Update Template Content (Adjust static paths if needed)
    with open(dest_tpl, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace static url paths if hardcoded
    # Although Flask url_for is preferred, existing code might use plain paths
    # We will assume admin blueprint serves static from /static/admin
    # But usually Flask static folder is global. With blueprints, it can be tricky.
    # The safest is to serve from global /static/admin
    
    # Simple replacement for demonstration, might need refinement
    # content = content.replace("static/", "static/admin/")
    # Since we use url_for usually, let's see. If not, we fix it later.
    
    # For now, let's just make sure files are there. We will tackle path issues in routes.py
    
if __name__ == "__main__":
    setup_directories()
