import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Çevresel değişkenleri yükle
load_dotenv()

# Veritabanı bağlantı bilgilerini al (Varsayılan değerlerle)
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "suryaocr_db")

# Bağlantı cümlesi
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def fix_database():
    print(f"🔧 Veritabanına bağlanılıyor: {DB_NAME}...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            # İşlemi başlat
            trans = connection.begin()
            try:
                # Sütunu ekleme komutu
                print("🔄 'description' sütunu ekleniyor...")
                connection.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS description TEXT;"))
                trans.commit()
                print("✅ Başarılı! 'description' sütunu eklendi.")
            except Exception as e:
                trans.rollback()
                print(f"⚠️ Hata oluştu (Sütun zaten var olabilir veya yetki sorunu): {e}")
                
    except Exception as e:
        print(f"❌ Veritabanına bağlanılamadı: {e}")
        print("💡 Lütfen .env dosyanızdaki şifrelerin doğru olduğundan emin olun.")

if __name__ == "__main__":
    fix_database()