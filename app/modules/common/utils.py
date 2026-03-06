
import os
import unicodedata
from datetime import datetime
from werkzeug.utils import secure_filename
from pathlib import Path

def secure_filename_tr(filename):
    """
    Turkce karakterleri guvenli ASCII karakterlere cevirir.
    """
    if not filename:
        return "document"
    
    replacements = {
        'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G', 'ü': 'u', 'Ü': 'U',
        'ş': 's', 'Ş': 'S', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
    }
    for search, replace in replacements.items():
        filename = filename.replace(search, replace)
        
    filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
    return secure_filename(filename)

def generate_detailed_filename(record):
    """
    Kayit bilgilerinden detayli dosya adi olusturur.
    Format: [Yazar] - [Baslik] - [Hazirlayan] - [Yayin Evi] - [Cilt] - [Yil]
    """
    parts = []
    
    # 1. Yazar
    author = record.get('author')
    if author:
        parts.append(author.strip())
        
    # 2. Eser Adi (Baslik)
    title = record.get('title')
    if title:
        parts.append(title.strip())
    else:
        parts.append("Basliksiz")
        
    # 3. Hazirlayan (Editor)
    editor = record.get('editor')
    if editor and str(editor).lower() != 'none':
        parts.append(f"Haz. {str(editor).strip()}")
        
    # 4. Yayin Evi (Publisher)
    publisher = record.get('publisher')
    if publisher and str(publisher).lower() != 'none':
        parts.append(str(publisher).strip())

    # 5. Cilt (Volume) - Varsa
    volume = record.get('volume')
    if volume and str(volume).lower() != 'none':
        vol_str = str(volume).strip()
        if not vol_str.lower().startswith(('cilt', 'volume')):
            parts.append(f"Cilt {vol_str}")
        else:
            parts.append(vol_str)

    # 6. Yayin Yili
    year = record.get('publication_year')
    if year:
        parts.append(str(year))
        
    # Parcalari birlestir
    filename_base = " - ".join(parts)
    
    return secure_filename_tr(filename_base)

def extract_year_smart(date_obj):
    """
    Verilen objeden (datetime, string veya int) akillica YIL bilgisini ceker.
    """
    if not date_obj:
        return None
        
    if hasattr(date_obj, 'year'):
        return date_obj.year
        
    s_val = str(date_obj).strip()
    if s_val.isdigit() and len(s_val) == 4:
        return int(s_val)
        
    try:
        return datetime.strptime(s_val[:10], "%Y-%m-%d").year
    except:
        return None

def resolve_file_path(db_path, base_dirs=None):
    """
    Veritabanindaki mutlak yolu yoksayar, dosya ismini alip
    verilen 'base_dirs' listesindeki klasorlerde dinamik olarak arar.
    
    Args:
        db_path (str): DB kayitli yol
        base_dirs (list[Path]): Aranacak kok dizinler listesi
    """
    if not db_path:
        return None
        
    clean_path = str(db_path).replace('\\', '/')
    filename = os.path.basename(clean_path)
    
    if not base_dirs:
        # Varsayilan olarak mevcut scriptin parent'i (Fallback)
        # Ancak normal kullanimda base_dirs verilmeli
        return str(Path(db_path))
    
    for base_dir in base_dirs:
        # Olasiliklar:
        # 1. base_dir/filename
        # 2. base_dir/pdf/filename
        # 3. base_dir/images/filename
        
        possible_subdirs = [
            base_dir,
            base_dir / 'pdf',
            base_dir / 'images'
        ]
        
        for p_dir in possible_subdirs:
            candidate = p_dir / filename
            if candidate.exists():
                return str(candidate)
            
    return None
