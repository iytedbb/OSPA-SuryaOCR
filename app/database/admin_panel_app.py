"""
OCR Database Admin Panel - Flask Backend
Port: 5847
"""

import os
import sys
import json
import uuid
import shutil
import mimetypes
import hashlib
import zipfile
import unicodedata
import openpyxl # Excel için gerekli

from openpyxl.styles import Font # Başlıkları kalın yapmak için
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, jsonify, send_file, Response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

# .env dosyasını yükle
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Flask uygulaması
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
CORS(app)

# Database bağlantı bilgileri
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'ospa_suryaocr')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def extract_year_smart(date_obj):
    """
    Verilen objeden (datetime, string veya int) akıllıca YIL bilgisini çeker.
    """
    if not date_obj:
        return None
        
    # Eğer gelen veri veritabanı tarih objesiyse (datetime veya date)
    if hasattr(date_obj, 'year'):
        return date_obj.year
        
    # Eğer string ise ve parse edilebiliyorsa
    s_val = str(date_obj).strip()
    if s_val.isdigit() and len(s_val) == 4:
        return int(s_val)
        
    try:
        # Basit ISO format denemesi (YYYY-MM-DD)
        return datetime.strptime(s_val[:10], "%Y-%m-%d").year
    except:
        return None

# SQLAlchemy engine
engine = None
Session = None

def secure_filename_tr(filename):
    """Türkçe karakterleri güvenli ASCII karakterlere çevirir"""
    if not filename:
        return "document"
    
    # Türkçe karakter değişimi
    replacements = {
        'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G', 'ü': 'u', 'Ü': 'U',
        'ş': 's', 'Ş': 'S', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
    }
    for search, replace in replacements.items():
        filename = filename.replace(search, replace)
        
    # Unicode normalize ve güvenli dosya adı
    filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
    return secure_filename(filename)

def generate_detailed_filename(record):
    """
    Kayıt bilgilerinden detaylı dosya adı oluşturur.
    Format: [Yazar] - [Başlık] - [Hazırlayan] - [Yayın Evi] - [Cilt] - [Yıl]
    """
    parts = []
    
    # 1. Yazar
    author = record.get('author')
    if author:
        parts.append(author.strip())
        
    # 2. Eser Adı (Başlık)
    title = record.get('title')
    if title:
        parts.append(title.strip())
    else:
        parts.append("Basliksiz")
        
    # 3. Hazırlayan (Editor)
    editor = record.get('editor')
    if editor and str(editor).lower() != 'none':
        parts.append(f"Haz. {str(editor).strip()}")
        
    # 4. Yayın Evi (Publisher)
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

    # 6. Yayın Yılı
    year = record.get('publication_year')
    if year:
        parts.append(str(year))
        
    # Parçaları birleştir
    filename_base = " - ".join(parts)
    
    # Türkçe karakterleri temizle ve güvenli hale getir
    return secure_filename_tr(filename_base)

def resolve_file_path(db_path):
    """
    Veritabanındaki mutlak yolu yoksayar, dosya ismini alıp
    projenin 'veriler' klasöründe dinamik olarak arar.
    """
    if not db_path:
        return None
        
    # 1. Dosya ismini güvenli bir şekilde ayıkla
    # Windows yolları (\) Linux'ta sorun çıkarabilir, onları / ile değiştirip ayırıyoruz
    clean_path = str(db_path).replace('\\', '/')
    filename = os.path.basename(clean_path)
    
    # 2. Şu anki scriptin (admin_panel_app.py) bulunduğu klasörü al
    # Senin durumunda: /home/gkdb/Desktop/emre/suryaocr/app/database
    current_dir = Path(__file__).parent.resolve()
    
    # 3. Olası yolları oluştur (Dinamik Arama)
    possible_paths = [
        # Öncelik 1: app/database/veriler/pdf/dosya.pdf
        current_dir / 'veriler' / 'pdf' / filename,
        
        # Öncelik 2: app/database/veriler/images/dosya.jpg
        current_dir / 'veriler' / 'images' / filename,
        
        # Öncelik 3: Belki doğrudan veriler klasöründedir
        current_dir / 'veriler' / filename,
        
        # Öncelik 4: Orijinal yol (Eğer aynı makinedeyse çalışır)
        Path(db_path)
    ]
    
    # 4. Yolları kontrol et
    for path in possible_paths:
        if path.exists():
            return str(path)
            
    # Hiçbiri bulunamazsa debug için konsola yaz (PyCharm terminalinde görünür)
    print(f"❌ Dosya bulunamadı! Aranan dosya ismi: {filename}")
    print(f"   Kontrol edilen yollar:")
    for p in possible_paths:
        print(f"   - {p}")
        
    return None

def init_database():
    """Veritabanı bağlantısını başlat"""
    global engine, Session
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
        Session = scoped_session(sessionmaker(bind=engine))
        return True
    except Exception as e:
        print(f"Database bağlantı hatası: {e}")
        return False


def get_db():
    """Database session döndür"""
    if Session is None:
        init_database()
    return Session()


def close_db(session):
    """Database session kapat"""
    try:
        session.close()
    except:
        pass


# ==========================================
# API ENDPOINTS
# ==========================================

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('admin_panel_index.html')

@app.route('/favicon.ico')
def favicon():
    # Mevcut logonuzu favicon olarak kullanıyoruz
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'gemini_ospa_ocr_db_logo.png', mimetype='image/vnd.microsoft.icon')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Sistem sağlık kontrolü"""
    db = get_db()
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    finally:
        close_db(db)
    
    return jsonify({
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    })


# ==========================================
# STATISTICS
# ==========================================

@app.route('/api/stats', methods=['GET'])
def get_statistics():
    """Dashboard istatistiklerini döndür"""
    db = get_db()
    try:
        stats = {}
        
        # Toplam yazar sayısı
        result = db.execute(text(
            "SELECT COUNT(DISTINCT author) FROM documents WHERE author IS NOT NULL AND author != ''"
        ))
        stats['total_authors'] = result.scalar() or 0
        
        # Toplam eser sayısı
        result = db.execute(text("SELECT COUNT(*) FROM documents"))
        stats['total_documents'] = result.scalar() or 0
        
        # OCR tamamlanan
        result = db.execute(text("SELECT COUNT(*) FROM ocr_results"))
        stats['ocr_completed'] = result.scalar() or 0
        
        # Toplam sayfa
        result = db.execute(text("SELECT COALESCE(SUM(total_pages), 0) FROM ocr_results"))
        stats['total_pages'] = result.scalar() or 0
        
        # Toplam dosya boyutu (MB)
        result = db.execute(text("SELECT COALESCE(SUM(file_size), 0) FROM document_files"))
        total_bytes = result.scalar() or 0
        stats['total_size_mb'] = round(total_bytes / 1024 / 1024, 2)
        
        # Son 7 günde eklenen
        result = db.execute(text("""
            SELECT COUNT(*) FROM documents 
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """))
        stats['recent_documents'] = result.scalar() or 0
        
        # En çok eser sahibi yazarlar (top 5)
        result = db.execute(text("""
            SELECT author, COUNT(*) as count
            FROM documents
            WHERE author IS NOT NULL AND author != ''
            GROUP BY author
            ORDER BY count DESC
            LIMIT 5
        """))
        stats['top_authors'] = [
            {"name": row[0], "count": row[1]} 
            for row in result.fetchall()
        ]
        
        # Metadata türlerine göre dağılım
        result = db.execute(text("""
            SELECT COALESCE(metadata_type, 'unknown') as type, COUNT(*) as count
            FROM documents
            GROUP BY metadata_type
            ORDER BY count DESC
        """))
        stats['type_distribution'] = [
            {"type": row[0], "count": row[1]} 
            for row in result.fetchall()
        ]
        
        # Son eklenen 5 eser
        result = db.execute(text("""
            SELECT id, title, author, created_at
            FROM documents
            ORDER BY created_at DESC
            LIMIT 5
        """))
        stats['recent_additions'] = [
            {
                "id": str(row[0]),
                "title": row[1],
                "author": row[2],
                "created_at": row[3].isoformat() if row[3] else None
            }
            for row in result.fetchall()
        ]
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


# ==========================================
# AUTHORS
# ==========================================

@app.route('/api/authors', methods=['GET'])
def get_authors():
    """Yazarları listele"""
    db = get_db()
    try:
        sort = request.args.get('sort', 'a_z')
        search = request.args.get('search', '').strip()
        
        # Sıralama
        order_clause = "author ASC"
        if sort == 'z_a':
            order_clause = "author DESC"
        elif sort == 'doc_count':
            order_clause = "doc_count DESC"
        elif sort == 'recent':
            order_clause = "last_updated DESC"
        
        # Arama filtresi
        where_clause = "WHERE author IS NOT NULL AND author != ''"
        params = {}
        
        if search:
            where_clause += " AND LOWER(author) LIKE :search"
            params['search'] = f"%{search.lower()}%"
        
        query = f"""
            SELECT 
                author,
                COUNT(*) as doc_count,
                MAX(created_at) as last_updated
            FROM documents
            {where_clause}
            GROUP BY author
            ORDER BY {order_clause}
        """
        
        result = db.execute(text(query), params)
        authors = [
            {
                "name": row[0],
                "doc_count": row[1],
                "last_updated": row[2].isoformat() if row[2] else None
            }
            for row in result.fetchall()
        ]
        
        return jsonify(authors)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/authors/<author_name>', methods=['PUT'])
def update_author(author_name):
    """Yazar adını güncelle (tüm belgelerinde)"""
    db = get_db()
    try:
        data = request.get_json()
        new_name = data.get('new_name', '').strip()
        
        if not new_name:
            return jsonify({"error": "Yeni isim boş olamaz"}), 400
        
        result = db.execute(text("""
            UPDATE documents
            SET author = :new_name, updated_at = NOW()
            WHERE author = :old_name
        """), {"old_name": author_name, "new_name": new_name})
        
        db.commit()
        
        return jsonify({
            "success": True,
            "updated_count": result.rowcount,
            "message": f"'{author_name}' -> '{new_name}' olarak güncellendi"
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


# ==========================================
# DOCUMENTS (RECORDS)
# ==========================================

@app.route('/api/records', methods=['GET'])
def get_records():
    """Kayıtları listele - Güncellenmiş Filtreleme ve Tarih Mantığı ile"""
    db = get_db()
    try:
        # Parametreler
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 25))
        sort = request.args.get('sort', 'a_z')
        author = request.args.get('author', '').strip()
        search = request.args.get('search', '').strip()
        doc_type = request.args.get('type', '').strip()
        year_from = request.args.get('year_from', '')
        year_to = request.args.get('year_to', '')

        offset = (page - 1) * per_page

        # Sıralama
        order_clause = "d.title ASC"
        if sort == 'z_a':
            order_clause = "d.title DESC"
        elif sort == 'old_to_new':
            order_clause = "d.created_at ASC"
        elif sort == 'new_to_old':
            order_clause = "d.created_at DESC"
        elif sort == 'year_asc':
            order_clause = "d.publication_year ASC NULLS LAST"
        elif sort == 'year_desc':
            order_clause = "d.publication_year DESC NULLS LAST"

        # WHERE koşulları
        conditions = ["1=1"]
        params = {"limit": per_page, "offset": offset}

        if author:
            conditions.append("d.author = :author")
            params['author'] = author

        if search:
            conditions.append("""
                (d.title ILIKE :search 
                OR d.author ILIKE :search)
            """)
            params['search'] = f"%{search}%"

        if doc_type:
            # GÜNCELLEME: ILIKE kullanılarak büyük/küçük harf toleransı sağlandı
            conditions.append("d.metadata_type ILIKE :doc_type")
            params['doc_type'] = doc_type

        if year_from:
            conditions.append("d.publication_year >= :year_from")
            params['year_from'] = int(year_from)

        if year_to:
            conditions.append("d.publication_year <= :year_to")
            params['year_to'] = int(year_to)

        where_clause = " AND ".join(conditions)

        # Toplam kayıt sayısı
        count_query = f"""
            SELECT COUNT(*) FROM documents d WHERE {where_clause}
        """
        total = db.execute(text(count_query), params).scalar() or 0

        # Kayıtlar
        query = f"""
            SELECT 
                d.id,
                d.title,
                d.author,
                d.metadata_type,
                d.publication_year,
                d.date,
                d.page_count,
                d.volume,
                d.publisher,
                d.edition,
                d.editor,
                d.newspaper_name,
                d.section,
                d.column_name,
                d.publication,
                d.issue,
                d.created_at,
                d.updated_at,
                (SELECT file_path FROM document_files WHERE document_id = d.id AND file_type = 'pdf' LIMIT 1) as pdf_path,
                (SELECT CASE WHEN markdown_content IS NOT NULL AND markdown_content != '' THEN true ELSE false END 
                 FROM ocr_results WHERE document_id = d.id LIMIT 1) as has_markdown,
                (SELECT CASE WHEN xml_content IS NOT NULL AND xml_content != '' THEN true ELSE false END 
                 FROM ocr_results WHERE document_id = d.id LIMIT 1) as has_xml,
                (SELECT total_pages FROM ocr_results WHERE document_id = d.id ORDER BY created_at DESC LIMIT 1) as ocr_page_count
            FROM documents d
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT :limit OFFSET :offset
        """

        result = db.execute(text(query), params)
        records = []

        for row in result.fetchall():
            # Akıllı yıl hesaplama (Önceki çözümümüz)
            display_year = row[4]
            if not display_year and row[5]:
                # extract_year_smart fonksiyonu dosyanın başında tanımlı olmalıdır
                display_year = extract_year_smart(row[5])
            
            record = {
                "id": str(row[0]),
                "title": row[1] or "Başlıksız",
                "author": row[2],
                "metadata_type": row[3] or "book",
                "publication_year": display_year,
                "date": row[5].isoformat() if row[5] else None,
                "page_count": row[6],
                "volume": row[7],
                "publisher": row[8],
                "edition": row[9],
                "editor": row[10],
                "description": "", 
                "newspaper_name": row[11],
                "section": row[12],
                "column_name": row[13],
                "journal_name": row[14], 
                "issue_number": row[15], 
                "created_at": row[16].isoformat() if row[16] else None,
                "updated_at": row[17].isoformat() if row[17] else None,
                "pdf_path": row[18],
                "has_markdown": row[19] or False,
                "has_xml": row[20] or False,
                "ocr_page_count": row[21]
            }
            records.append(record)

        return jsonify({
            "records": records,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        })

    except Exception as e:
        print(f"Hata detayı: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/records/<record_id>', methods=['GET'])
def get_record(record_id):
    """Tek kayıt detayı - Tablodaki TÜM Sütunlar"""
    db = get_db()
    try:
        # Tablodaki tüm sütunları açıkça çağırıyoruz
        query = """
            SELECT 
                -- Temel Alanlar
                d.id, d.title, d.author, d.metadata_type, 
                d.language, d.country, d.citation_style, d.url,
                
                -- Tarih ve Zaman
                d.publication_year, d.date, d.access_date, 
                d.created_at, d.updated_at,
                
                -- Kitap/Seri Alanları
                d.publisher, d.publication_city, d.country, 
                d.edition, d.volume, d.page_count, d.pages, d.isbn, 
                d.series, d.series_title, d.series_text, d.editor,
                
                -- Makale Alanları
                d.publication, d.issue, d.doi, d.issn, d.journal_abbreviation,
                
                -- Gazete Alanları
                d.newspaper_name, d.publication_place, d.section, 
                d.column_name, d.page_range,
                
                -- Ansiklopedi Alanları
                d.encyclopedia_title, d.short_title,
                
                -- Arşiv/Kütüphane Alanları
                d.archive, d.archive_location, d.library_catalog, 
                d.call_number, d.rights,
                
                -- İlişkili Dosya Yolları (Alt sorgular)
                (SELECT file_path FROM document_files WHERE document_id = d.id AND file_type = 'pdf' LIMIT 1) as pdf_path,
                (SELECT markdown_content FROM ocr_results WHERE document_id = d.id LIMIT 1) as markdown_content,
                (SELECT xml_content FROM ocr_results WHERE document_id = d.id LIMIT 1) as xml_content,
                (SELECT total_pages FROM ocr_results WHERE document_id = d.id LIMIT 1) as ocr_page_count
            FROM documents d
            WHERE d.id = :record_id
        """
        
        result = db.execute(text(query), {"record_id": record_id})
        row = result.fetchone()
        
        if not row:
            return jsonify({"error": "Kayıt bulunamadı"}), 404
        
        # Row -> Dict Dönüşümü
        try:
            record = dict(row._mapping)
        except AttributeError:
            record = dict(row)
            
        # Tarih formatlarını düzelt (Date objelerini string yap)
        date_fields = ['date', 'access_date', 'created_at', 'updated_at']
        for field in date_fields:
            if record.get(field):
                record[field] = record[field].isoformat()
        
        # Frontend uyumluluğu (Eski kodlarla çakışmaması için aliaslar)
        record['journal_name'] = record.get('publication')
        record['issue_number'] = record.get('issue')
        
        return jsonify(record)
        
    except Exception as e:
        print(f"Get Record Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/records', methods=['POST'])
def create_record():
    """Yeni kayıt oluştur"""
    db = get_db()
    try:
        data = request.get_json()
        new_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Tarih işleme
        record_date = data.get('date') or None
        access_date = data.get('access_date') or None
        pub_year = data.get('publication_year') or None
        
        # Otomatik yıl çıkarma
        if record_date and not pub_year:
            try:
                dt = datetime.strptime(record_date, '%Y-%m-%d')
                pub_year = dt.year
            except:
                pass

        query = """
            INSERT INTO documents (
                id, title, author, metadata_type, language, citation_style, url,
                publication_year, date, access_date,
                publisher, publication_city, country, edition, volume, 
                page_count, pages, isbn, series, series_title, series_text, editor,
                publication, issue, doi, issn, journal_abbreviation,
                newspaper_name, publication_place, section, column_name, page_range,
                encyclopedia_title, short_title,
                archive, archive_location, library_catalog, call_number, rights,
                created_at, updated_at
            ) VALUES (
                :id, :title, :author, :metadata_type, :language, :citation_style, :url,
                :publication_year, :date, :access_date,
                :publisher, :publication_city, :country, :edition, :volume, 
                :page_count, :pages, :isbn, :series, :series_title, :series_text, :editor,
                :publication, :issue, :doi, :issn, :journal_abbreviation,
                :newspaper_name, :publication_place, :section, :column_name, :page_range,
                :encyclopedia_title, :short_title,
                :archive, :archive_location, :library_catalog, :call_number, :rights,
                :created_at, :updated_at
            )
        """
        
        params = {
            # Temel
            "id": new_id,
            "title": data.get('title', 'Başlıksız'),
            "author": data.get('author'),
            "metadata_type": data.get('metadata_type', 'book'),
            "language": data.get('language'),
            "citation_style": data.get('citation_style'),
            "url": data.get('url'),
            
            # Tarih
            "publication_year": pub_year,
            "date": record_date,
            "access_date": access_date,
            
            # Kitap
            "publisher": data.get('publisher'),
            "publication_city": data.get('publication_city'),
            "country": data.get('country'),
            "edition": data.get('edition'),
            "volume": data.get('volume'),
            "page_count": data.get('page_count'),
            "pages": data.get('page_count'), # 'pages' kolonuna da aynı sayıyı yazıyoruz
            "isbn": data.get('isbn'),
            "series": data.get('series'),
            "series_title": data.get('series_title'),
            "series_text": data.get('series_text'),
            "editor": data.get('editor'),
            
            # Makale
            "publication": data.get('publication'),
            "issue": data.get('issue'),
            "doi": data.get('doi'),
            "issn": data.get('issn'),
            "journal_abbreviation": data.get('journal_abbreviation'),
            
            # Gazete
            "newspaper_name": data.get('newspaper_name'),
            "publication_place": data.get('publication_place'),
            "section": data.get('section'),
            "column_name": data.get('column_name'),
            "page_range": data.get('page_range'),
            
            # Ansiklopedi
            "encyclopedia_title": data.get('encyclopedia_title'),
            "short_title": data.get('short_title'),
            
            # Arşiv
            "archive": data.get('archive'),
            "archive_location": data.get('archive_location'),
            "library_catalog": data.get('library_catalog'),
            "call_number": data.get('call_number'),
            "rights": data.get('rights'),
            
            "created_at": now,
            "updated_at": now
        }
        
        db.execute(text(query), params)
        db.commit()
        
        return jsonify({"success": True, "id": new_id, "message": "Kayıt başarıyla oluşturuldu"}), 201
        
    except Exception as e:
        db.rollback()
        print(f"Create Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/records/<record_id>', methods=['PUT'])
def update_record(record_id):
    """Kayıt güncelle"""
    db = get_db()
    try:
        data = request.get_json()
        
        # Güncellenebilir alanlar listesi (DB şemasına uygun)
        updatable_fields = [
            'title', 'author', 'metadata_type', 'language', 'country', 'citation_style', 'url',
            'publication_year', 'date', 'access_date',
            'publisher', 'publication_city', 'edition', 'volume', 
            'page_count', 'pages', 'isbn', 'series', 'series_title', 'series_text', 'editor',
            'publication', 'issue', 'doi', 'issn', 'journal_abbreviation',
            'newspaper_name', 'publication_place', 'section', 'column_name', 'page_range',
            'encyclopedia_title', 'short_title',
            'archive', 'archive_location', 'library_catalog', 'call_number', 'rights'
        ]
        
        set_clauses = ["updated_at = NOW()"]
        params = {"record_id": record_id}
        
        for field in updatable_fields:
            val = None
            # Özel eşleştirmeler (Frontend -> DB)
            if field == 'publication_city' and 'city' in data: val = data.get('city')
            elif field == 'pages' and 'page_count' in data: val = data.get('page_count') # pages ile page_count'u eşitle
            elif field in data:
                val = data[field]
            
            # Boş string -> NULL
            if val == '': val = None
                
            if field in data or val is not None:
                set_clauses.append(f"{field} = :{field}")
                params[field] = val
        
        query = f"""
            UPDATE documents
            SET {', '.join(set_clauses)}
            WHERE id = :record_id
        """
        
        result = db.execute(text(query), params)
        db.commit()
        
        return jsonify({"success": True, "message": "Kayıt başarıyla güncellendi"})
        
    except Exception as e:
        db.rollback()
        print(f"Update Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/records/<record_id>', methods=['DELETE'])
def delete_record(record_id):
    """Kayıt sil"""
    db = get_db()
    try:
        # Önce ilişkili dosya yollarını al
        file_result = db.execute(text("""
            SELECT file_path FROM document_files WHERE document_id = :record_id
        """), {"record_id": record_id})
        file_paths = [row[0] for row in file_result.fetchall()]
        
        # İlişkili kayıtları sil
        db.execute(text("DELETE FROM ocr_results WHERE document_id = :record_id"), 
                   {"record_id": record_id})
        db.execute(text("DELETE FROM document_files WHERE document_id = :record_id"), 
                   {"record_id": record_id})
        
        # Ana kaydı sil
        result = db.execute(text("DELETE FROM documents WHERE id = :record_id"), 
                            {"record_id": record_id})
        
        db.commit()
        
        if result.rowcount == 0:
            return jsonify({"error": "Kayıt bulunamadı"}), 404
        
        # Dosyaları fiziksel olarak sil
        deleted_files = []
        for file_path in file_paths:
            try:
                if file_path and Path(file_path).exists():
                    Path(file_path).unlink()
                    deleted_files.append(file_path)
            except Exception as fe:
                print(f"Dosya silinemedi: {file_path} - {fe}")
        
        return jsonify({
            "success": True,
            "message": "Kayıt ve ilişkili dosyalar silindi",
            "deleted_files": len(deleted_files)
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


# ==========================================
# SEARCH
# ==========================================

@app.route('/api/search', methods=['GET'])
def search_records():
    """Gelişmiş arama (Eser, Yazar, Yıl)"""
    db = get_db()
    try:
        query_text = request.args.get('q', '').strip()
        search_field = request.args.get('field', 'all')  # all, title, author, year
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 25))
        
        if not query_text:
            return jsonify({"records": [], "total": 0})
        
        offset = (page - 1) * per_page
        conditions = []
        params = {"limit": per_page, "offset": offset}
        
        if search_field == 'title':
            conditions.append("d.title ILIKE :search") # LOWER ve LIKE yerine ILIKE
            params['search'] = f"%{query_text}%"       # lower() yok
        elif search_field == 'author':
            conditions.append("d.author ILIKE :search") # ILIKE
            params['search'] = f"%{query_text}%"
        elif search_field == 'year':
            try:
                year = int(query_text)
                conditions.append("d.publication_year = :year")
                params['year'] = year
            except ValueError:
                return jsonify({"error": "Geçersiz yıl formatı"}), 400
        else:
            # Tümünde ara
            conditions.append("""
                (d.title ILIKE :search 
                OR d.author ILIKE :search
                OR CAST(d.publication_year AS TEXT) LIKE :search)
            """)
            params['search'] = f"%{query_text}%"
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Toplam
        count_query = f"SELECT COUNT(*) FROM documents d WHERE {where_clause}"
        total = db.execute(text(count_query), params).scalar() or 0
        
        # Sonuçlar
        query = f"""
            SELECT 
                d.id, d.title, d.author, d.metadata_type,
                d.publication_year, d.created_at,
                (SELECT file_path FROM document_files WHERE document_id = d.id AND file_type = 'pdf' LIMIT 1) as pdf_path
            FROM documents d
            WHERE {where_clause}
            ORDER BY d.title ASC
            LIMIT :limit OFFSET :offset
        """
        
        result = db.execute(text(query), params)
        records = [
            {
                "id": str(row[0]),
                "title": row[1],
                "author": row[2],
                "metadata_type": row[3],
                "publication_year": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "pdf_path": row[6]
            }
            for row in result.fetchall()
        ]
        
        return jsonify({
            "records": records,
            "total": total,
            "page": page,
            "per_page": per_page
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


# ==========================================
# CONTENT (Markdown, XML)
# ==========================================

@app.route('/api/records/<record_id>/markdown', methods=['GET'])
def get_markdown(record_id):
    """Markdown içeriğini getir"""
    db = get_db()
    try:
        result = db.execute(text("""
            SELECT markdown_content FROM ocr_results 
            WHERE document_id = :record_id
        """), {"record_id": record_id})
        
        row = result.fetchone()
        content = row[0] if row else ""
        
        return jsonify({"content": content or ""})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/records/<record_id>/markdown', methods=['PUT'])
def save_markdown(record_id):
    """Markdown içeriğini kaydet"""
    db = get_db()
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        # UPSERT
        query = """
            INSERT INTO ocr_results (id, document_id, markdown_content, created_at, total_pages)
            VALUES (:id, :doc_id, :content, NOW(), 0)
            ON CONFLICT (document_id) 
            DO UPDATE SET markdown_content = :content
        """
        
        db.execute(text(query), {
            "id": str(uuid.uuid4()),
            "doc_id": record_id,
            "content": content
        })
        db.commit()
        
        return jsonify({"success": True, "message": "Markdown kaydedildi"})
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/records/<record_id>/xml', methods=['GET'])
def get_xml(record_id):
    """XML içeriğini getir"""
    db = get_db()
    try:
        result = db.execute(text("""
            SELECT xml_content FROM ocr_results 
            WHERE document_id = :record_id
        """), {"record_id": record_id})
        
        row = result.fetchone()
        content = row[0] if row else ""
        
        return jsonify({"content": content or ""})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/records/<record_id>/xml', methods=['PUT'])
def save_xml(record_id):
    """XML içeriğini kaydet"""
    db = get_db()
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        query = """
            INSERT INTO ocr_results (id, document_id, xml_content, created_at, total_pages)
            VALUES (:id, :doc_id, :content, NOW(), 0)
            ON CONFLICT (document_id) 
            DO UPDATE SET xml_content = :content
        """
        
        db.execute(text(query), {
            "id": str(uuid.uuid4()),
            "doc_id": record_id,
            "content": content
        })
        db.commit()
        
        return jsonify({"success": True, "message": "XML kaydedildi"})
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


# ==========================================
# EXPORT
# ==========================================

@app.route('/api/export/json', methods=['GET'])
def export_json():
    """Tüm veritabanını JSON olarak dışa aktar"""
    db = get_db()
    try:
        author = request.args.get('author', '').strip()
        
        where_clause = ""
        params = {}
        
        if author:
            where_clause = "WHERE d.author = :author"
            params['author'] = author
        
        # SORGUNA d.date EKLENDİ
        query = f"""
            SELECT 
                d.id, d.title, d.author, d.metadata_type,
                d.publication_year, d.page_count, d.volume,
                d.publisher, d.edition, d.editor,
                d.created_at,
                (SELECT markdown_content FROM ocr_results WHERE document_id = d.id LIMIT 1) as markdown,
                (SELECT xml_content FROM ocr_results WHERE document_id = d.id LIMIT 1) as xml,
                d.date
            FROM documents d
            {where_clause}
            ORDER BY d.author, d.title
        """
        
        result = db.execute(text(query), params)
        
        export_data = {
            "export_date": datetime.now().isoformat(),
            "total_records": 0,
            "records": []
        }
        
        for row in result.fetchall():
            record = {
                "id": str(row[0]),
                "title": row[1],
                "author": row[2],
                "metadata_type": row[3],
                "publication_year": row[4],
                "page_count": row[5],
                "volume": row[6],
                "publisher": row[7],
                "edition": row[8],
                "editor": row[9],
                "created_at": row[10].isoformat() if row[10] else None,
                "markdown_content": row[11],
                "xml_content": row[12],
                # YENİ EKLENEN ALAN
                "date": row[13].isoformat() if row[13] else None 
            }
            export_data["records"].append(record)
        
        export_data["total_records"] = len(export_data["records"])
        
        # JSON dosyası olarak indir
        response = Response(
            json.dumps(export_data, ensure_ascii=False, indent=2),
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename=database_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            }
        )
        
        return response
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Veritabanını CSV olarak dışa aktar"""
    db = get_db()
    try:
        import csv
        from io import StringIO
        
        # SORGUNA d.date EKLENDİ
        query = """
            SELECT 
                d.id, d.title, d.author, d.metadata_type,
                d.publication_year, d.page_count, d.volume,
                d.publisher, d.edition, d.editor, d.description,
                d.created_at,
                d.date
            FROM documents d
            ORDER BY d.author, d.title
        """
        
        result = db.execute(text(query))
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'ID', 'Başlık', 'Yazar', 'Tür', 'Tarih / Yıl',
            'Sayfa Sayısı', 'Cilt', 'Yayınevi', 'Baskı',
            'Editör', 'Açıklama', 'Oluşturma Tarihi'
        ])
        
        # Data
        for row in result.fetchall():
            # Tarih Mantığı
            pub_year = row[4]
            full_date = row[12]
            
            display_date = ""
            if full_date:
                display_date = full_date.isoformat()
            elif pub_year:
                display_date = str(pub_year)

            writer.writerow([
                str(row[0]),
                row[1],
                row[2],
                row[3],
                display_date, # GÜNCELLENDİ
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
                row[10],
                row[11].isoformat() if row[11] else ''
            ])
        
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=database_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )
        
        return response
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)

@app.route('/api/export/excel', methods=['GET'])
def export_excel():
    """Veritabanını Excel (.xlsx) olarak dışa aktar"""
    db = get_db()
    try:
        # SORGUNA d.date EKLENDİ (En sona)
        query = """
            SELECT 
                d.id, d.title, d.author, d.metadata_type,
                d.publication_year, d.page_count, d.volume,
                d.publisher, d.edition, d.editor, d.description,
                d.created_at,
                d.date
            FROM documents d
            ORDER BY d.author, d.title
        """
        
        result = db.execute(text(query))
        
        # Workbook oluştur
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Kayıtlar"
        
        # Başlıklar ("Yayın Yılı" -> "Tarih / Yıl" olarak güncellendi)
        headers = [
            'ID', 'Başlık', 'Yazar', 'Tür', 'Tarih / Yıl',
            'Sayfa Sayısı', 'Cilt', 'Yayınevi', 'Baskı',
            'Editör', 'Açıklama', 'Oluşturma Tarihi'
        ]
        ws.append(headers)
        
        # Başlıkları Kalın Yap
        for cell in ws[1]:
            cell.font = Font(bold=True)
            
        # Verileri Ekle
        for row in result.fetchall():
            # Tarih Mantığı: Eğer tam tarih (d.date) varsa onu kullan, yoksa yılı kullan
            pub_year = row[4]
            full_date = row[12] # SQL sorgusunun sonuna eklediğimiz d.date
            
            display_date = ""
            if full_date:
                display_date = full_date.isoformat() # YYYY-MM-DD formatı
            elif pub_year:
                display_date = str(pub_year)
            
            row_data = [
                str(row[0]),      # ID
                row[1],           # Başlık
                row[2],           # Yazar
                row[3],           # Tür
                display_date,     # Tarih / Yıl (GÜNCELLENDİ)
                row[5],           # Sayfa
                row[6],           # Cilt
                row[7],           # Yayınevi
                row[8],           # Baskı
                row[9],           # Editör
                row[10],          # Açıklama
                row[11].isoformat() if row[11] else '' # Oluşturma Tarihi
            ]
            ws.append(row_data)
            
        # Dosyayı belleğe kaydet
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        filename = f'database_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
    except Exception as e:
        print(f"Excel Export Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


# ==========================================
# IMPORT
# ==========================================

@app.route('/api/import', methods=['POST'])
def import_data():
    """JSON dosyasından veri içe aktar"""
    db = get_db()
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Dosya seçilmedi"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "Dosya seçilmedi"}), 400
        
        if not file.filename.endswith('.json'):
            return jsonify({"error": "Sadece JSON dosyaları desteklenir"}), 400
        
        import_data = json.load(file)
        records = import_data.get('records', [])
        
        imported = 0
        skipped = 0
        errors = []
        
        for record in records:
            try:
                # ID kontrolü - varsa atla
                existing = db.execute(text(
                    "SELECT id FROM documents WHERE id = :id"
                ), {"id": record.get('id')}).fetchone()
                
                if existing:
                    skipped += 1
                    continue
                
                new_id = record.get('id') or str(uuid.uuid4())
                now = datetime.now()
                
                db.execute(text("""
                    INSERT INTO documents (
                        id, title, author, metadata_type, publication_year,
                        page_count, volume, publisher, edition, editor,
                        description, created_at, updated_at
                    ) VALUES (
                        :id, :title, :author, :metadata_type, :publication_year,
                        :page_count, :volume, :publisher, :edition, :editor,
                        :description, :created_at, :updated_at
                    )
                """), {
                    "id": new_id,
                    "title": record.get('title', 'Başlıksız'),
                    "author": record.get('author'),
                    "metadata_type": record.get('metadata_type', 'book'),
                    "publication_year": record.get('publication_year'),
                    "page_count": record.get('page_count'),
                    "volume": record.get('volume'),
                    "publisher": record.get('publisher'),
                    "edition": record.get('edition'),
                    "editor": record.get('editor'),
                    "description": record.get('description'),
                    "created_at": now,
                    "updated_at": now
                })
                
                # Markdown/XML varsa ekle
                md_content = record.get('markdown_content')
                xml_content = record.get('xml_content')
                
                if md_content or xml_content:
                    db.execute(text("""
                        INSERT INTO ocr_results (id, document_id, markdown_content, xml_content, created_at, total_pages)
                        VALUES (:id, :doc_id, :md, :xml, NOW(), 0)
                    """), {
                        "id": str(uuid.uuid4()),
                        "doc_id": new_id,
                        "md": md_content,
                        "xml": xml_content
                    })
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Kayıt hatası: {str(e)}")
        
        db.commit()
        
        return jsonify({
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10]  # İlk 10 hata
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


# ==========================================
# TOOLS (Backup, Vacuum, Duplicates)
# ==========================================

@app.route('/api/backup', methods=['POST'])
def create_backup():
    """Veritabanı yedeği oluştur"""
    db = get_db()
    try:
        backup_dir = Path('/app/database/backups')
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"backup_{timestamp}.json"
        
        # Tüm verileri çek
        result = db.execute(text("""
            SELECT 
                d.*,
                (SELECT markdown_content FROM ocr_results WHERE document_id = d.id LIMIT 1) as markdown,
                (SELECT xml_content FROM ocr_results WHERE document_id = d.id LIMIT 1) as xml
            FROM documents d
        """))
        
        backup_data = {
            "backup_date": datetime.now().isoformat(),
            "records": []
        }
        
        columns = result.keys()
        for row in result.fetchall():
            record = dict(zip(columns, row))
            # Serialize
            for key, value in record.items():
                if hasattr(value, 'isoformat'):
                    record[key] = value.isoformat()
                elif isinstance(value, uuid.UUID):
                    record[key] = str(value)
            backup_data["records"].append(record)
        
        backup_data["total_records"] = len(backup_data["records"])
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            "success": True,
            "message": f"Yedekleme tamamlandı",
            "file": str(backup_file),
            "records": backup_data["total_records"]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/vacuum', methods=['POST'])
def vacuum_database():
    """Veritabanını optimize et"""
    db = get_db()
    try:
        # PostgreSQL'de VACUUM için autocommit gerekli
        connection = engine.raw_connection()
        connection.set_isolation_level(0)  # AUTOCOMMIT
        cursor = connection.cursor()
        cursor.execute("VACUUM ANALYZE")
        cursor.close()
        connection.close()
        
        return jsonify({
            "success": True,
            "message": "Veritabanı optimize edildi (VACUUM ANALYZE)"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/duplicates', methods=['GET'])
def find_duplicates():
    """Tekrar eden kayıtları bul"""
    db = get_db()
    try:
        # Aynı başlık + yazar kombinasyonuna sahip kayıtları bul
        query = """
            SELECT 
                title, author, COUNT(*) as count,
                ARRAY_AGG(id) as ids
            FROM documents
            WHERE title IS NOT NULL AND title != ''
            GROUP BY title, author
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 100
        """
        
        result = db.execute(text(query))
        duplicates = []
        
        for row in result.fetchall():
            duplicates.append({
                "title": row[0],
                "author": row[1],
                "count": row[2],
                "ids": [str(id) for id in row[3]]
            })
        
        return jsonify({
            "duplicates": duplicates,
            "total_groups": len(duplicates)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


@app.route('/api/duplicates', methods=['DELETE'])
def remove_duplicates():
    """Tekrar eden kayıtları sil (her gruptan birini tut)"""
    db = get_db()
    try:
        data = request.get_json()
        ids_to_delete = data.get('ids', [])
        
        if not ids_to_delete:
            return jsonify({"error": "Silinecek kayıt belirtilmedi"}), 400
        
        deleted = 0
        
        for record_id in ids_to_delete:
            # İlişkili kayıtları sil
            db.execute(text("DELETE FROM ocr_results WHERE document_id = :id"), {"id": record_id})
            db.execute(text("DELETE FROM document_files WHERE document_id = :id"), {"id": record_id})
            result = db.execute(text("DELETE FROM documents WHERE id = :id"), {"id": record_id})
            deleted += result.rowcount
        
        db.commit()
        
        return jsonify({
            "success": True,
            "deleted": deleted,
            "message": f"{deleted} tekrar eden kayıt silindi"
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


# ==========================================
# NEWSPAPERS (Gazeteler)
# ==========================================

@app.route('/api/newspapers', methods=['GET'])
def get_newspapers():
    """Gazete listesini getir"""
    db = get_db()
    try:
        query = """
            SELECT 
                COALESCE(newspaper_name, 'İsimsiz') as name,
                COUNT(*) as article_count
            FROM documents
            WHERE metadata_type = 'newspaper'
            GROUP BY newspaper_name
            ORDER BY article_count DESC
        """
        
        result = db.execute(text(query))
        newspapers = [
            {"name": row[0], "article_count": row[1]}
            for row in result.fetchall()
        ]
        
        return jsonify(newspapers)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)


# ==========================================
# FILE SERVING & DOWNLOAD
# ==========================================

@app.route('/api/files/view/<record_id>')
def view_source_file(record_id):
    """Kaynağa ait PDF veya Resmi tarayıcıda göster"""
    db = get_db()
    try:
        # Dosya yolunu veritabanından çek
        query = text("""
            SELECT file_path 
            FROM document_files 
            WHERE document_id = :record_id 
            LIMIT 1
        """)
        result = db.execute(query, {"record_id": record_id}).fetchone()
        
        if not result or not result[0]:
            return "Dosya kaydı bulunamadı", 404
            
        # Akıllı yol bulucuyu kullan
        file_path = resolve_file_path(result[0])
        
        if not file_path:
            # Hata ayıklama için veritabanındaki yolu da yazdıralım
            return f"Fiziksel dosya bulunamadı. DB Yolu: {result[0]}", 404

        # MIME türünü belirle
        mime_type, _ = mimetypes.guess_type(file_path)
        
        return send_file(file_path, mimetype=mime_type, as_attachment=False)
        
    except Exception as e:
        return f"Hata: {str(e)}", 500
    finally:
        close_db(db)

@app.route('/api/files/download/<record_id>')
def download_source_file(record_id):
    """Kaynak dosyayı (PDF/JPG) indir - Düzenli isimlendirme ile"""
    db = get_db()
    try:
        # 1. Dosya yolunu bul
        file_query = text("SELECT file_path FROM document_files WHERE document_id = :record_id LIMIT 1")
        file_res = db.execute(file_query, {"record_id": record_id}).fetchone()
        
        if not file_res or not file_res[0]:
            return jsonify({"error": "Dosya bulunamadı"}), 404
            
        file_path = resolve_file_path(file_res[0])
        if not file_path:
            return jsonify({"error": "Fiziksel dosya diskte yok"}), 404

        # 2. Güzel isim oluşturmak için kayıt bilgilerini çek (YENİ KISIM)
        doc_query = text("SELECT * FROM documents WHERE id = :id")
        doc_row = db.execute(doc_query, {"id": record_id}).fetchone()
        
        download_name = None
        if doc_row:
            try:
                record = dict(doc_row._mapping)
            except AttributeError:
                record = dict(doc_row)
            
            ext = os.path.splitext(file_path)[1]
            # Fonksiyonu kullanarak ismi oluştur
            safe_title = generate_detailed_filename(record)
            download_name = f"{safe_title}{ext}"

        # 3. İndir (download_name parametresi ile)
        return send_file(
            file_path, 
            as_attachment=True,
            download_name=download_name # Eğer None ise orijinal ismi kullanır
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)

@app.route('/api/content/download/<record_id>/<content_type>')
def download_generated_content(record_id, content_type):
    """Markdown veya XML içeriğini dosya olarak indir"""
    db = get_db()
    try:
        # Tüm alanları çekiyoruz ki generate_detailed_filename çalışabilsin
        query = text("SELECT * FROM documents WHERE id = :id")
        row = db.execute(query, {"id": record_id}).fetchone()
        
        if not row:
            return jsonify({"error": "Kayıt bulunamadı"}), 404

        try:
            record = dict(row._mapping)
        except AttributeError:
            record = dict(row)

        # --- YENİ İSİMLENDİRME ---
        safe_title = generate_detailed_filename(record)
        # -------------------------

        col_name = "markdown_content" if content_type == "markdown" else "xml_content"
        ext = "md" if content_type == "markdown" else "xml"
        
        query = text(f"SELECT {col_name} FROM ocr_results WHERE document_id = :id")
        result = db.execute(query, {"id": record_id}).fetchone()
        
        content = result[0] if result else ""
        
        if not content:
            return jsonify({"error": "İçerik bulunamadı"}), 404

        content_bytes = content.encode('utf-8')
        
        return Response(
            content_bytes,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename="{safe_title}.{ext}"',
                'Content-Length': str(len(content_bytes))
            }
        )
        
    except Exception as e:
        print(f"Content Download Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)

# ==========================================
# FILE UPLOAD & REPLACEMENT
# ==========================================

def get_storage_path(subfolder):
    """Veriler klasörü altındaki hedef klasör yolunu döndürür"""
    base_dir = Path(__file__).parent / 'veriler'
    target_dir = base_dir / subfolder
    target_dir.mkdir(parents=True, exist_ok=True) # Klasör yoksa oluştur
    return target_dir

def calculate_file_hash(file_path):
    """Dosyanın SHA256 hash'ini hesaplar"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

@app.route('/api/files/upload/source/<record_id>', methods=['POST'])
def upload_source_file(record_id):
    """Ana dosyayı (PDF/Resim) yükle ve eskisiyle değiştir"""
    db = get_db()
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Dosya gönderilmedi"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Dosya seçilmedi"}), 400

        # Orijinal dosya adı ve uzantısı
        original_filename = secure_filename(file.filename)
        ext = os.path.splitext(original_filename)[1].lower()
        
        # Dosya türü belirle
        file_type = 'pdf' if ext == '.pdf' else 'image'
        subfolder = 'pdf' if file_type == 'pdf' else 'images'
        
        # MIME Type belirle
        mime_type = mimetypes.guess_type(original_filename)[0]
        if not mime_type:
            mime_type = 'application/pdf' if file_type == 'pdf' else 'image/jpeg'
        
        # 1. Eski dosyayı bul ve sil
        old_file_query = text("SELECT id, file_path FROM document_files WHERE document_id = :record_id")
        old_files = db.execute(old_file_query, {"record_id": record_id}).fetchall()
        
        for old_rec in old_files:
            # Fiziksel silme
            old_path = resolve_file_path(old_rec[1])
            if old_path and os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception as e:
                    print(f"Eski dosya silinemedi: {e}")
            
            # DB kaydını sil
            db.execute(text("DELETE FROM document_files WHERE id = :id"), {"id": old_rec[0]})

        # 2. Yeni dosyayı kaydet
        safe_name = f"{record_id}{ext}" # Çakışmayı önlemek için ID kullan
        save_dir = get_storage_path(subfolder)
        file_path = save_dir / safe_name
        
        file.save(str(file_path))
        
        # Dosya boyutu ve Hash hesapla
        file_size = os.path.getsize(file_path)
        
        # Hash hesaplama (Eğer calculate_file_hash fonksiyonu tanımlıysa kullan, yoksa boş geçme hatası almamak için dummy değer ver)
        try:
            file_hash = calculate_file_hash(str(file_path))
        except NameError:
            # calculate_file_hash fonksiyonu eklenmemişse import hashlib yapıp burada hesaplayalım
            import hashlib
            sha256_hash = hashlib.sha256()
            with open(str(file_path), "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            file_hash = sha256_hash.hexdigest()

        # 3. Yeni DB kaydı oluştur (TÜM KOLONLARLA)
        new_file_id = str(uuid.uuid4())
        insert_query = text("""
            INSERT INTO document_files (
                id, document_id, file_path, filename, 
                original_filename, mime_type, file_hash,
                file_type, file_size, created_at
            ) VALUES (
                :id, :doc_id, :path, :filename,
                :original_filename, :mime_type, :file_hash,
                :type, :size, NOW()
            )
        """)
        
        db.execute(insert_query, {
            "id": new_file_id,
            "doc_id": record_id,
            "path": str(file_path),
            "filename": safe_name,       # Sistemdeki adı (UUID)
            "original_filename": original_filename, # Kullanıcının yüklediği ad (ZORUNLU ALAN)
            "mime_type": mime_type,      # ZORUNLU ALAN
            "file_hash": file_hash,      # ZORUNLU ALAN
            "type": file_type,
            "size": file_size
        })
        
        db.commit()
        return jsonify({"success": True, "message": "Dosya başarıyla güncellendi"})

    except Exception as e:
        db.rollback()
        print(f"UPLOAD ERROR: {str(e)}") # Hatayı terminale yaz
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)

@app.route('/api/files/upload/content/<record_id>/<content_type>', methods=['POST'])
def upload_content_file(record_id, content_type):
    """Markdown veya XML dosyasını yükle ve veritabanı içeriğini güncelle"""
    db = get_db()
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Dosya gönderilmedi"}), 400
            
        file = request.files['file']
        
        # Dosya içeriğini oku
        content = file.read().decode('utf-8', errors='ignore')
        
        col_name = "markdown_content" if content_type == "markdown" else "xml_content"
        
        # UPSERT işlemi (Varsa güncelle, yoksa ekle)
        query = text(f"""
            INSERT INTO ocr_results (id, document_id, {col_name}, created_at, total_pages)
            VALUES (:id, :doc_id, :content, NOW(), 0)
            ON CONFLICT (document_id) 
            DO UPDATE SET {col_name} = :content
        """)
        
        db.execute(query, {
            "id": str(uuid.uuid4()),
            "doc_id": record_id,
            "content": content
        })
        
        db.commit()
        return jsonify({"success": True, "message": f"{content_type.upper()} içeriği güncellendi", "content": content})

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)

# ==========================================
# ADVANCED EXPORT (ZIP & AUTHOR)
# ==========================================

@app.route('/api/export/record/<record_id>/zip', methods=['GET'])
def export_record_zip(record_id):
    """Bir esere ait her şeyi (PDF, MD, XML, JSON) ZIP olarak indir"""
    db = get_db()
    try:
        query = text("""
            SELECT 
                d.*,
                (SELECT file_path FROM document_files WHERE document_id = d.id LIMIT 1) as file_path,
                (SELECT markdown_content FROM ocr_results WHERE document_id = d.id LIMIT 1) as markdown,
                (SELECT xml_content FROM ocr_results WHERE document_id = d.id LIMIT 1) as xml
            FROM documents d
            WHERE d.id = :id
        """)
        
        row = db.execute(query, {"id": record_id}).fetchone()
        
        if not row:
            return jsonify({"error": "Kayıt bulunamadı"}), 404

        # Row'u Dict'e çevirme
        try:
            record = dict(row._mapping)
        except AttributeError:
            record = dict(row)
        
        # --- YENİ İSİMLENDİRME ---
        safe_title = generate_detailed_filename(record)
        # -------------------------
        
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            
            # A. Metadata JSON
            metadata = {k: v for k, v in record.items() if k not in ['markdown', 'xml', 'file_path']}
            for k, v in metadata.items():
                if isinstance(v, uuid.UUID):
                    metadata[k] = str(v)
                elif hasattr(v, 'isoformat'): 
                    metadata[k] = v.isoformat()
            
            zf.writestr(f"{safe_title}_metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
            
            # B. Markdown
            if record.get('markdown'):
                zf.writestr(f"{safe_title}.md", record.get('markdown'))
                
            # C. XML
            if record.get('xml'):
                zf.writestr(f"{safe_title}.xml", record.get('xml'))
                
            # D. Kaynak Dosya
            if record.get('file_path'):
                real_path = resolve_file_path(record['file_path'])
                if real_path and os.path.exists(real_path):
                    ext = os.path.splitext(real_path)[1]
                    # Dosya adını da standart formatta yapıyoruz
                    zf.write(real_path, arcname=f"{safe_title}{ext}")

        memory_file.seek(0)
        zip_content = memory_file.getvalue()
        
        return Response(
            zip_content,
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename="{safe_title}.zip"', # ZIP adı güncellendi
                'Content-Length': str(len(zip_content))
            }
        )

    except Exception as e:
        print(f"ZIP Export Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)

@app.route('/api/export/author/<author_name>/json', methods=['GET'])
def export_author_data(author_name):
    """Seçili yazara ait TÜM detaylı verileri JSON olarak indir"""
    db = get_db()
    try:
        # Yazarın tüm eserlerini ve detaylarını çek
        # d.* diyerek tablodaki her şeyi alıyoruz
        query = text("""
            SELECT 
                d.*,
                (SELECT COUNT(*) FROM ocr_results WHERE document_id = d.id) as has_ocr,
                (SELECT markdown_content FROM ocr_results WHERE document_id = d.id LIMIT 1) as markdown_preview
            FROM documents d
            WHERE d.author = :author
            ORDER BY d.publication_year
        """)
        
        result = db.execute(query, {"author": author_name})
        
        export_data = {
            "author": author_name,
            "export_date": datetime.now().isoformat(),
            "total_works": 0,
            "works": []
        }
        
        # Sütun isimlerini al
        columns = result.keys()
        
        for row in result.fetchall():
            # Satırı dictionary'e çevir
            work = dict(zip(columns, row))
            
            # Veri tiplerini JSON uyumlu hale getir (Tarih, UUID vb.)
            for key, value in work.items():
                if isinstance(value, uuid.UUID):
                    work[key] = str(value)
                elif hasattr(value, 'isoformat'):
                    work[key] = value.isoformat()
            
            export_data["works"].append(work)
            
        export_data["total_works"] = len(export_data["works"])
        
        # Dosya adı için güvenli isim (Türkçe karakter destekli)
        safe_name = secure_filename_tr(author_name)
        
        return Response(
            json.dumps(export_data, ensure_ascii=False, indent=2),
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename={safe_name}_tum_eserleri.json'
            }
        )

    except Exception as e:
        print(f"Author Export Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)

@app.route('/api/export/author/<author_name>/zip', methods=['GET'])
def export_author_zip(author_name):
    """
    Seçili yazara ait TÜM verileri (PDF, MD, XML, JSON) klasörlenmiş bir ZIP olarak indir.
    Yapı:
    Yazar_Adi_Arsiv.zip
      └── Eser_Adi_Yil/
           ├── Eser_Adi.pdf
           ├── Eser_Adi.md
           ├── Eser_Adi.xml
           └── metadata.json
    """
    db = get_db()
    try:
        # 1. Yazarın tüm belgelerini çek
        query = text("""
            SELECT d.* FROM documents d WHERE d.author = :author
        """)
        documents = db.execute(query, {"author": author_name}).fetchall()
        
        if not documents:
            return jsonify({"error": "Bu yazara ait kayıt bulunamadı"}), 404

        # Bellekte ZIP oluştur
        memory_file = BytesIO()
        
        # Türkçe karakter sorunu olmaması için zip dosya adını güvenli hale getir
        safe_author_name = secure_filename_tr(author_name)

        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            
            for doc_row in documents:
                # Row -> Dict dönüşümü
                try:
                    record = dict(doc_row._mapping)
                except AttributeError:
                    record = dict(doc_row)
                
                # Dosya adını oluştur (Uzantısız)
                base_name = generate_detailed_filename(record)
                
                # Her eser için bir klasör adı oluştur
                folder_name = base_name 
                
                # --- A. Metadata (JSON) ---
                metadata = {k: v for k, v in record.items()}
                for k, v in metadata.items():
                    if isinstance(v, uuid.UUID): metadata[k] = str(v)
                    elif hasattr(v, 'isoformat'): metadata[k] = v.isoformat()
                
                zf.writestr(
                    f"{folder_name}/{base_name}_metadata.json", 
                    json.dumps(metadata, ensure_ascii=False, indent=2)
                )

                # --- B. Kaynak Dosya (PDF/Resim) ---
                file_query = text("SELECT file_path FROM document_files WHERE document_id = :id LIMIT 1")
                file_res = db.execute(file_query, {"id": record['id']}).fetchone()
                
                if file_res and file_res[0]:
                    real_path = resolve_file_path(file_res[0])
                    if real_path and os.path.exists(real_path):
                        # Orijinal uzantıyı al (.pdf, .jpg vs)
                        ext = os.path.splitext(real_path)[1]
                        # ZIP içine ekle
                        zf.write(real_path, arcname=f"{folder_name}/{base_name}{ext}")

                # --- C. OCR İçerikleri (MD / XML) ---
                ocr_query = text("SELECT markdown_content, xml_content FROM ocr_results WHERE document_id = :id LIMIT 1")
                ocr_res = db.execute(ocr_query, {"id": record['id']}).fetchone()
                
                if ocr_res:
                    md_content, xml_content = ocr_res
                    
                    if md_content:
                        zf.writestr(f"{folder_name}/{base_name}.md", md_content)
                    
                    if xml_content:
                        zf.writestr(f"{folder_name}/{base_name}.xml", xml_content)

        # ZIP dosyasını sonlandır ve gönder
        memory_file.seek(0)
        return Response(
            memory_file.getvalue(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename="{safe_author_name}_Tum_Eserler.zip"'
            }
        )

    except Exception as e:
        print(f"Author ZIP Export Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        close_db(db)

# ==========================================
# STARTUP
# ==========================================

if __name__ == '__main__':
    print("="*50)
    print("OCR Database Admin Panel")
    print("="*50)
    print(f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Starting server on port 5847...")
    print("="*50)
    
    if init_database():
        print("Database connection successful!")
    else:
        print("WARNING: Database connection failed!")
    
    app.run(
        host='0.0.0.0',
        port=5847,
        debug=True
    )