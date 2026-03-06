# DocumentMetadata.py - Enhanced document metadata management for SuryaOCR
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional, Literal
import json
import xml.etree.ElementTree as ET

MetadataType = Literal['book', 'article', 'encyclopedia', 'newspaper']


@dataclass
class DocumentMetadata:
    """
    Enhanced document metadata structure supporting different document types.
    Supports book, article, encyclopedia, and newspaper metadata with type-specific fields.
    """
    # Core metadata type
    metadata_type: MetadataType = 'book'

    # 🆕 Doküman tipi (gazete detection için)
    document_type: str = 'auto'  # 'auto' | 'newspaper' | 'normal'

    # Common fields for all types
    title: str = ""
    author: str = ""
    language: str = "tr"

    # Book-specific fields
    publisher: str = ""
    publication_year: Optional[int] = None
    publication_city: str = ""
    country: str = ""
    edition: str = ""
    volume: str = ""
    series: str = ""
    page_count: Optional[int] = None
    isbn: str = ""
    url: str = ""
    archive: str = ""
    archive_location: str = ""
    library_catalog: str = ""
    call_number: str = ""
    editor: str = ""

    # Article-specific fields
    publication: str = ""
    issue: str = ""
    pages: str = ""
    date: str = ""
    series_title: str = ""
    series_text: str = ""
    journal_abbreviation: str = ""
    doi: str = ""
    issn: str = ""
    rights: str = ""

    # Encyclopedia-specific fields
    encyclopedia_title: str = ""
    short_title: str = ""
    access_date: str = ""

    # 🆕 Newspaper-specific fields (Gazete için ek alanlar)
    section: str = ""  # Bölüm
    extra: str = ""  # İlave

    # Legacy fields
    subject: str = ""
    description: str = ""
    keywords: str = ""
    category: str = ""
    page_range: str = ""

    # Processing information
    processed_by: str = "SuryaOCR Pro"
    processing_date: str = ""
    ocr_confidence: float = 0.0

    # Source file information
    source_filename: str = ""
    source_format: str = ""

    # Citation style preference
    citation_style: str = "apa"

    def __post_init__(self):
        """Initialize processing date if not provided"""
        if not self.processing_date:
            self.processing_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentMetadata':
        """Create DocumentMetadata from dictionary with type validation"""
        # Filter out unknown fields
        valid_fields = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        # Ensure metadata_type is valid
        metadata_type = filtered_data.get('metadata_type', 'book')
        if metadata_type not in ['book', 'article', 'encyclopedia']:
            metadata_type = 'book'
        filtered_data['metadata_type'] = metadata_type

        return cls(**filtered_data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def is_empty(self) -> bool:
        """Check if metadata contains meaningful information"""
        core_fields = [self.title, self.author]

        if self.metadata_type == 'book':
            core_fields.extend([self.publisher, self.isbn])
        elif self.metadata_type == 'article':
            core_fields.extend([self.publication, self.doi])
        elif self.metadata_type == 'encyclopedia':
            core_fields.extend([self.encyclopedia_title])

        return not any(field.strip() for field in core_fields if field)

    def get_type_specific_fields(self) -> Dict[str, str]:
        """Get fields specific to the metadata type"""
        if self.metadata_type == 'book':
            return {
                'Publisher': self.publisher,
                'Publication Year': str(self.publication_year) if self.publication_year else '',
                'Publication City': self.publication_city,
                'Country': self.country,
                'Edition': self.edition,
                'Volume': self.volume,
                'Series': self.series,
                'Editor': self.editor,
                'ISBN': self.isbn,
                'Archive': self.archive,
                'Archive Location': self.archive_location,
                'Library Catalog': self.library_catalog,
                'Call Number': self.call_number,
            }

        elif self.metadata_type == 'article':
            return {
                'Publication': self.publication,
                'Volume': self.volume,
                'Issue': self.issue,
                'Pages': self.pages,
                'Date': self.date,
                'Series': self.series,
                'Series Title': self.series_title,
                'Series Text': self.series_text,
                'Journal Abbreviation': self.journal_abbreviation,
                'DOI': self.doi,
                'ISSN': self.issn,
                'Rights': self.rights,
                'Archive': self.archive,
                'Archive Location': self.archive_location,
                'Library Catalog': self.library_catalog,
                'Call Number': self.call_number,
            }

        elif self.metadata_type == 'encyclopedia':
            return {
                'Encyclopedia Title': self.encyclopedia_title,
                'Publisher': self.publisher,
                'Publication Year': str(self.publication_year) if self.publication_year else '',
                'Publication City': self.publication_city,
                'Volume': self.volume,
                'Edition': self.edition,
                'Series': self.series,
                'Date': self.date,
                'Pages': self.pages,
                'ISBN': self.isbn,
                'Short Title': self.short_title,
                'Access Date': self.access_date,
                'Archive': self.archive,
                'Archive Location': self.archive_location,
                'Library Catalog': self.library_catalog,
                'Call Number': self.call_number,
                'Rights': self.rights,
            }

        elif self.metadata_type == 'newspaper':
            # 🆕 GAZETE ALANLARI (Zotero uyumlu)
            return {
                'Yayın': self.publication,
                'Yazar': self.author,
                'Yayın Yeri': self.publication_city,
                'Baskı': self.edition,
                'Tarih': self.date,
                'Bölüm': self.section,
                'Sayfa': self.pages,
                'Dil': self.language.upper() if self.language else '',
                'Kısa Başlık': self.short_title,
                'ISSN': self.issn,
                'URL': self.url,
                'Son Erişim': self.access_date,
                'Arşiv': self.archive,
                'Arşivdeki Yeri': self.archive_location,
                'Kütüphane Kataloğu': self.library_catalog,
                'Yer Numarası': self.call_number,
                'Telif': self.rights,
                'İlave': self.extra,
            }

        return {}

    def get_citation_apa(self) -> str:
        """Generate APA style citation based on metadata type"""
        parts = []

        # Author (common for all types)
        if self.author:
            parts.append(f"{self.author}")

        if self.metadata_type == 'book':
            # Year
            if self.publication_year:
                parts.append(f"({self.publication_year})")

            # Title
            if self.title:
                parts.append(f"*{self.title}*")

            # Edition
            if self.edition:
                parts.append(f"({self.edition})")

            # Publisher info
            publisher_info = []
            if self.publication_city:
                publisher_info.append(self.publication_city)
            if self.publisher:
                publisher_info.append(self.publisher)
            if publisher_info:
                parts.append(": ".join(publisher_info))

        elif self.metadata_type == 'article':
            # Date - flexible format
            date_part = ""
            if self.date:
                date_str = self.date.strip()
                if len(date_str) == 4 and date_str.isdigit():
                    date_part = f"({date_str})"
                elif len(date_str) == 7 and '-' in date_str:
                    year, month = date_str.split('-')
                    date_part = f"({year}, {month})"
                elif len(date_str) == 10 and date_str.count('-') == 2:
                    year, month, day = date_str.split('-')
                    date_part = f"({year}, {month}-{day})"
                else:
                    date_part = f"({date_str})"

            if date_part:
                parts.append(date_part)

            # Title
            if self.title:
                parts.append(f"{self.title}")

            # Publication info
            if self.publication:
                pub_info = f"*{self.publication}*"
                volume_issue = []
                if self.volume:
                    volume_issue.append(f"{self.volume}")
                if self.issue:
                    volume_issue.append(f"({self.issue})")
                if volume_issue:
                    pub_info += f", {''.join(volume_issue)}"
                if self.pages:
                    pub_info += f", {self.pages}"
                parts.append(pub_info)

            # DOI
            if self.doi:
                parts.append(f"https://doi.org/{self.doi}")

        elif self.metadata_type == 'encyclopedia':
            # Date - flexible format for encyclopedia too
            date_part = ""
            if self.date:
                date_str = self.date.strip()
                if len(date_str) == 4 and date_str.isdigit():
                    date_part = f"({date_str})"
                else:
                    date_part = f"({date_str})"
            elif self.publication_year:
                date_part = f"({self.publication_year})"

            if date_part:
                parts.append(date_part)

            # Title
            if self.title:
                parts.append(f"{self.title}")

            # Encyclopedia info
            if self.encyclopedia_title:
                enc_info = f"*{self.encyclopedia_title}*"
                if self.volume:
                    enc_info += f" (Cilt {self.volume})"
                if self.pages:
                    enc_info += f", {self.pages}"
                parts.append(enc_info)

            # Publisher info
            publisher_info = []
            if self.publication_city:
                publisher_info.append(self.publication_city)
            if self.publisher:
                publisher_info.append(self.publisher)
            if publisher_info:
                parts.append(": ".join(publisher_info))

        elif self.metadata_type == 'newspaper':
            # Author
            if self.author:
                parts.append(f"{self.author}")

            # Date
            if self.date:
                date_str = self.date.strip()
                if len(date_str) == 4 and date_str.isdigit():
                    date_part = f"({date_str})"
                elif len(date_str) == 10 and date_str.count('-') == 2:
                    year, month, day = date_str.split('-')
                    date_part = f"({year}, {month}-{day})"
                else:
                    date_part = f"({date_str})"
                parts.append(date_part)

            # Title
            if self.title:
                parts.append(f"{self.title}")

            # Publication info
            if self.publication:
                pub_info = f"*{self.publication}*"
                if self.section:
                    pub_info += f", {self.section}"
                if self.pages:
                    pub_info += f", {self.pages}"
                parts.append(pub_info)

            # URL and access date
            if self.url:
                url_part = self.url
                if self.access_date:
                    url_part += f" (Erişim tarihi: {self.access_date})"
                parts.append(url_part)

        # URL and access date (for all other types)
        if self.metadata_type not in ['newspaper']:
            if self.url:
                url_part = self.url
                if self.access_date:
                    access_str = self.access_date.strip()
                    if len(access_str) == 4 and access_str.isdigit():
                        url_part += f" (Erişim tarihi: {access_str})"
                    else:
                        url_part += f" (Erişim tarihi: {access_str})"
                parts.append(url_part)

        citation = ". ".join(filter(None, parts))
        return citation if citation else "Yazar bilgisi bulunamadı."

        # DocumentMetadata.py - Gerekli olan _month_name metodu eklendi
        # ... (önceki metodlar ve __post_init__, from_dict, to_dict, to_json, is_empty, get_type_specific_fields)

    def _month_name(self, month_num: str) -> str:
        """
        Convert month number, modern month name, Rumi, or Hijri month name
        to Turkish month name for Chicago style.
        """
        if not month_num:
            return ""

        # Gelen metni küçük harfe çevirip boşlukları temizle
        clean_month = month_num.strip().lower().replace('.', '')

        # Ay numarası ve isimlerini içeren standart sözlük
        months = {
            '01': 'Ocak', '02': 'Şubat', '03': 'Mart', '04': 'Nisan',
            '05': 'Mayıs', '06': 'Haziran', '07': 'Temmuz', '08': 'Ağustos',
            '09': 'Eylül', '10': 'Ekim', '11': 'Kasım', '12': 'Aralık'
        }

        # --- AY ADI/NUMARASI ARAMA SÖZLÜĞÜ (TÜM GİRİŞLER) ---
        name_to_num = {
            # 1. Sayısal Karşılıklar (Zaten int() ile deneniyor, burada yedek)
            '01': '01', '02': '02', '03': '03', '04': '04', '05': '05',
            '06': '06', '07': '07', '08': '08', '09': '09', '10': '10',
            '11': '11', '12': '12',

            # 2. Modern Türkçe ve İngilizce İsimler/Kısaltmalar
            'ocak': '01', 'şubat': '02', 'mart': '03', 'nisan': '04',
            'mayıs': '05', 'haziran': '06', 'temmuz': '07', 'ağustos': '08',
            'eylül': '09', 'ekim': '10', 'kasım': '11', 'aralık': '12',
            'oca': '01', 'şub': '02', 'mar': '03', 'nis': '04',
            'haz': '06', 'tem': '07', 'ağu': '08', 'eyl': '09', 'eki': '10',
            'kas': '11', 'ara': '12',
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',

            # 3. Hicri Aylar (Ay adını bulup 'Hicri' olduğunu varsayarak Gregorian ay adı yerine geçirme)
            'muharrem': '01', 'safer': '02', 'rebiülevvel': '03', 'rebiülahir': '04',
            'cemaziyelevvel': '05', 'cemaziyelahir': '06', 'receb': '07', 'şaban': '08',
            'ramazan': '09', 'şevval': '10', 'zilkade': '11', 'zilhicce': '12',

            # 4. Rumi/Maliye Aylar (Gregoryen'e yakın olanlar)
            'kânunusani': '01', 'şubat': '02', 'mart': '03', 'nisan': '04',
            'mayıs': '05', 'haziran': '06', 'temmuz': '07', 'ağustos': '08',
            'eylül': '09', 'teşrinievvel': '10', 'teşrinisani': '11', 'kânunuevvel': '12',

            # 4b. Yeni Rumi İsimler (1945'ten sonra)
            'ocak': '01', 'şubat': '02', 'mart': '03', 'nisan': '04',
            'mayıs': '05', 'haziran': '06', 'temmuz': '07', 'ağustos': '08',
            'eylül': '09', 'ekim': '10', 'kasım': '11', 'aralık': '12',
        }

        # 1. Sayısal kontrol
        try:
            num = int(clean_month)
            if 1 <= num <= 12:
                month_key = f"{num:02d}"
                return months.get(month_key, month_num)
        except ValueError:
            pass  # Sayısal değilse metinsel kontrolle devam et

        # 2. Metinsel kontrol
        if clean_month in name_to_num:
            month_key = name_to_num[clean_month]
            return months.get(month_key, month_num)

        # 3. Kısaltma ve Özel Durumlar için Regex
        # Yıl kısımlarını temizle (Sadece ayın adı kalsın)
        import re
        if re.search(r'[a-zğışöçü]{3,}', clean_month):  # En az 3 harfli bir kelime varsa

            # Özel Osmanlıca (Rumi/Hicri) kısaltmaları
            osmanlica_karsiliklar = {
                'kanunusani': '01', 'sanisani': '01', 'kssani': '01',
                'teşrinievvel': '10', 'teşriniyevel': '10', 'teşriniev': '10', 'teşev': '10',
                'teşrinisani': '11', 'teşrinis': '11', 'tesev': '11',
                'kanunuevvel': '12', 'kanevvel': '12', 'kuevvel': '12',
                'cemaziyelahir': '06', 'cemahir': '06',
                'rebiülahir': '04', 'rebahir': '04'
            }

            for osmanlica, key in osmanlica_karsiliklar.items():
                if osmanlica.startswith(clean_month):
                    return months.get(key, month_num)

            # Başka bir kütüphane kullanmadan, genel bir kural:
            # Eğer temizlenmiş ay adı, bir Hicri/Rumi ay adına benziyorsa
            # ama tam eşleşmiyorsa ve modern ay adı değilse, orijinali döndür.
            pass

        # Ne sayısal ne de bilinen bir metin ay adı/kısaltması ise orijinal değeri döndür
        return month_num

    def get_citation_chicago(self) -> str:
        """Generate Chicago style citation based on metadata type"""
        parts = []

        if self.metadata_type == 'book':
            # Author - Chicago style: Surname, First Name (only for first author)
            if self.author:
                author_names = [a.strip() for a in self.author.split(',')]
                if author_names:
                    # First author: reverse name order
                    first_author = author_names[0].strip()
                    name_parts = first_author.rsplit(' ', 1)  # Split from right to get last word as surname
                    if len(name_parts) == 2:
                        formatted_first = f"{name_parts[1]}, {name_parts[0]}"
                    else:
                        formatted_first = first_author

                    # Other authors: keep normal order
                    if len(author_names) > 1:
                        other_authors = ', '.join(author_names[1:])
                        parts.append(f"{formatted_first}, {other_authors}")
                    else:
                        parts.append(formatted_first)
                else:
                    parts.append(self.author)
            elif self.editor:
                # If no author, editor becomes primary
                editor_names = [e.strip() for e in self.editor.split(',')]
                if editor_names:
                    first_editor = editor_names[0].strip()
                    name_parts = first_editor.rsplit(' ', 1)
                    if len(name_parts) == 2:
                        formatted_first = f"{name_parts[1]}, {name_parts[0]}"
                    else:
                        formatted_first = first_editor

                    if len(editor_names) > 1:
                        other_editors = ', '.join(editor_names[1:])
                        parts.append(f"{formatted_first}, {other_editors}, ed.")
                    else:
                        parts.append(f"{formatted_first}, ed.")

            # Title - italicized
            if self.title:
                parts.append(f"*{self.title}*")

            # Editor info (if author exists)
            if self.author and self.editor:
                parts.append(f"Hazırlayan {self.editor}")

            # Volume
            if self.volume:
                parts.append(f"C. {self.volume}")

            # Publication info: City: Publisher, Year
            pub_parts = []
            if self.publication_city:
                pub_parts.append(self.publication_city)

            if self.publisher:
                if pub_parts:
                    pub_parts.append(f": {self.publisher}")
                else:
                    pub_parts.append(self.publisher)

            if self.publication_year:
                if pub_parts:
                    pub_parts.append(f", {self.publication_year}")
                else:
                    pub_parts.append(str(self.publication_year))

            if pub_parts:
                parts.append(''.join(pub_parts))

        elif self.metadata_type == 'article':
            # Author - Chicago style for articles
            if self.author:
                author_names = [a.strip() for a in self.author.split(',')]
                if author_names:
                    first_author = author_names[0].strip()
                    name_parts = first_author.rsplit(' ', 1)
                    if len(name_parts) == 2:
                        formatted_first = f"{name_parts[1]}, {name_parts[0]}"
                    else:
                        formatted_first = first_author

                    if len(author_names) > 1:
                        other_authors = ', '.join(author_names[1:])
                        parts.append(f"{formatted_first}, {other_authors}")
                    else:
                        parts.append(formatted_first)

            # Title in quotes
            if self.title:
                parts.append(f'"{self.title}"')

            # Journal name (italicized)
            if self.publication:
                journal_part = f"*{self.publication}*"

                # Volume and issue
                if self.volume:
                    journal_part += f" {self.volume}"
                    if self.issue:
                        journal_part += f", no. {self.issue}"
                elif self.issue:
                    journal_part += f", no. {self.issue}"

                # Date
                if self.date:
                    date_str = self.date.strip()
                    if len(date_str) == 4 and date_str.isdigit():
                        journal_part += f" ({date_str})"
                    else:
                        journal_part += f" ({date_str})"

                parts.append(journal_part)

            # Pages
            if self.pages:
                parts.append(self.pages)

        elif self.metadata_type == 'encyclopedia':
            # Author
            if self.author:
                author_names = [a.strip() for a in self.author.split(',')]
                if author_names:
                    first_author = author_names[0].strip()
                    name_parts = first_author.rsplit(' ', 1)
                    if len(name_parts) == 2:
                        formatted_first = f"{name_parts[1]}, {name_parts[0]}"
                    else:
                        formatted_first = first_author

                    if len(author_names) > 1:
                        other_authors = ', '.join(author_names[1:])
                        parts.append(f"{formatted_first}, {other_authors}")
                    else:
                        parts.append(formatted_first)

            # Title in quotes
            if self.title:
                parts.append(f'"{self.title}"')

            # Encyclopedia title (italicized)
            if self.encyclopedia_title:
                enc_part = f"*{self.encyclopedia_title}*"
                if self.volume:
                    enc_part += f", C. {self.volume}"
                parts.append(enc_part)

            # Publication info
            pub_parts = []
            if self.publication_city:
                pub_parts.append(self.publication_city)

            if self.publisher:
                if pub_parts:
                    pub_parts.append(f": {self.publisher}")
                else:
                    pub_parts.append(self.publisher)

            # Date
            date_val = None
            if self.date:
                date_str = self.date.strip()
                if len(date_str) == 4 and date_str.isdigit():
                    date_val = date_str
                else:
                    date_val = date_str
            elif self.publication_year:
                date_val = str(self.publication_year)

            if date_val:
                if pub_parts:
                    pub_parts.append(f", {date_val}")
                else:
                    pub_parts.append(date_val)

            if pub_parts:
                parts.append(''.join(pub_parts))

            # Pages
            if self.pages:
                parts.append(self.pages)

        # Join parts with appropriate separators
        citation = ". ".join(filter(None, parts))
        if citation and not citation.endswith('.'):
            citation += "."

        elif self.metadata_type == 'newspaper':
            # Author - Chicago style
            if self.author:
                author_names = [a.strip() for a in self.author.split(',')]
                if author_names:
                    first_author = author_names[0].strip()
                    name_parts = first_author.rsplit(' ', 1)
                    if len(name_parts) == 2:
                        formatted_first = f"{name_parts[1]}, {name_parts[0]}"
                    else:
                        formatted_first = first_author

                    if len(author_names) > 1:
                        other_authors = ', '.join(author_names[1:])
                        parts.append(f"{formatted_first}, {other_authors}")
                    else:
                        parts.append(formatted_first)

            # Title in quotes
            if self.title:
                parts.append(f'"{self.title}"')

            # Publication name (italicized)
            if self.publication:
                pub_part = f"*{self.publication}*"

                # Date
                if self.date:
                    date_str = self.date.strip()
                    if len(date_str) == 10 and date_str.count('-') == 2:
                        year, month, day = date_str.split('-')
                        # 👇 KOD DÜZELTİLDİ: self. ile çağır
                        pub_part += f", {day} {self._month_name(month)} {year}"
                    elif len(date_str) == 4 and date_str.isdigit():
                        pub_part += f", {date_str}"
                    else:
                        pub_part += f", {date_str}"

                # Section
                if self.section:
                    pub_part += f", {self.section}"

                # Edition
                if self.edition:
                    pub_part += f", {self.edition}"

                parts.append(pub_part)

            # Pages
            if self.pages:
                parts.append(self.pages)

        return citation if citation else "Yazar bilgisi bulunamadı."

    def get_citation(self, style: str = None) -> str:
        """Generate citation in specified style"""
        style = style or self.citation_style or "apa"

        if style.lower() == "chicago":
            return self.get_citation_chicago()
        else:
            return self.get_citation_apa()

    def get_type_display_name(self) -> str:
        """Get display name for metadata type"""
        type_names = {
            'book': 'Kitap',
            'article': 'Makale',
            'encyclopedia': 'Ansiklopedi',
            'newspaper': 'Gazete'
        }
        return type_names.get(self.metadata_type, 'Bilinmeyen')

    def generate_markdown_header(self) -> str:
        """Generate comprehensive markdown header with type-specific metadata"""
        header_lines = []

        # Title section
        if self.title:
            header_lines.append(f"# {self.title}")
        else:
            header_lines.append("# Dijital Metin Çıktısı")

        header_lines.append("")

        # Document type and metadata table
        header_lines.append(f"## Doküman Bilgileri ({self.get_type_display_name()})")
        header_lines.append("")
        header_lines.append("| Alan | Değer |")
        header_lines.append("|------|-------|")

        # Common fields
        header_lines.append(f"| **Tür** | {self.get_type_display_name()} |")
        if self.author:
            header_lines.append(f"| **Yazar** | {self.author} |")
        if self.language:
            header_lines.append(f"| **Dil** | {self.language.upper()} |")

        # Type-specific fields
        type_fields = self.get_type_specific_fields()
        for label, value in type_fields.items():
            if value and value.strip():
                header_lines.append(f"| **{label}** | {value} |")

        # URL section if exists
        if self.url:
            header_lines.append(f"| **URL** | [{self.url}]({self.url}) |")

        header_lines.append("")

        # Description section
        if self.description:
            header_lines.append("## Açıklama")
            header_lines.append("")
            header_lines.append(self.description)
            header_lines.append("")

        # Keywords section
        if self.keywords:
            header_lines.append("## Anahtar Kelimeler")
            header_lines.append("")
            keywords_list = [kw.strip() for kw in self.keywords.split(',') if kw.strip()]
            header_lines.append(", ".join(f"`{kw}`" for kw in keywords_list))
            header_lines.append("")

        # Processing information
        header_lines.append("## İşlem Bilgileri")
        header_lines.append("")
        header_lines.append("| Alan | Değer |")
        header_lines.append("|------|-------|")
        header_lines.append(f"| **İşleyici** | {self.processed_by} |")
        header_lines.append(f"| **İşlem Tarihi** | {self.processing_date} |")

        if self.page_count:
            header_lines.append(f"| **Sayfa Sayısı** | {self.page_count} |")

        if self.ocr_confidence > 0:
            header_lines.append(f"| **Ortalama Güven** | {self.ocr_confidence:.1%} |")

        if self.source_filename:
            header_lines.append(f"| **Kaynak Dosya** | `{self.source_filename}` |")

        header_lines.append("")

        # Citation
        citation_apa = self.get_citation_apa()
        citation_chicago = self.get_citation_chicago()

        header_lines.append("## Kaynak Gösterimi")
        header_lines.append("")
        header_lines.append("### APA Formatı")
        header_lines.append("")
        header_lines.append(f"> {citation_apa}")
        header_lines.append("")
        header_lines.append("### Chicago Formatı")
        header_lines.append("")
        header_lines.append(f"> {citation_chicago}")
        header_lines.append("")

        # Separator
        header_lines.append("---")
        header_lines.append("")

        return "\n".join(header_lines)

    def generate_xml_metadata(self, root_element: ET.Element) -> None:
        """Add enhanced metadata to XML root element as the FIRST child"""
        # Create metadata section as the first element
        metadata_elem = ET.Element('metadata')
        metadata_elem.set('type', self.metadata_type)

        # Document information
        doc_info = ET.SubElement(metadata_elem, 'document_info')

        # Common fields
        common_fields = [
            ('title', self.title),
            ('author', self.author),
            ('language', self.language),
        ]

        for field_name, field_value in common_fields:
            if field_value:
                field_elem = ET.SubElement(doc_info, field_name)
                field_elem.text = field_value

        # Type-specific fields
        type_specific = ET.SubElement(doc_info, f'{self.metadata_type}_fields')

        if self.metadata_type == 'book':
            book_fields = [
                ('publisher', self.publisher),
                ('publication_year', str(self.publication_year) if self.publication_year else ''),
                ('publication_city', self.publication_city),
                ('country', self.country),
                ('edition', self.edition),
                ('volume', self.volume),
                ('series', self.series),
                ('isbn', self.isbn),
                ('archive', self.archive),
                ('archive_location', self.archive_location),
                ('library_catalog', self.library_catalog),
                ('call_number', self.call_number),
            ]

            for field_name, field_value in book_fields:
                if field_value:
                    field_elem = ET.SubElement(type_specific, field_name)
                    field_elem.text = field_value

        elif self.metadata_type == 'article':
            article_fields = [
                ('publication', self.publication),
                ('volume', self.volume),
                ('issue', self.issue),
                ('pages', self.pages),
                ('date', self.date),
                ('series', self.series),
                ('series_title', self.series_title),
                ('series_text', self.series_text),
                ('journal_abbreviation', self.journal_abbreviation),
                ('doi', self.doi),
                ('issn', self.issn),
                ('rights', self.rights),
                ('archive', self.archive),
                ('archive_location', self.archive_location),
                ('library_catalog', self.library_catalog),
                ('call_number', self.call_number),
            ]

            for field_name, field_value in article_fields:
                if field_value:
                    field_elem = ET.SubElement(type_specific, field_name)
                    field_elem.text = field_value

        elif self.metadata_type == 'encyclopedia':
            encyclopedia_fields = [
                ('encyclopedia_title', self.encyclopedia_title),
                ('publisher', self.publisher),
                ('publication_year', str(self.publication_year) if self.publication_year else ''),
                ('publication_city', self.publication_city),
                ('volume', self.volume),
                ('edition', self.edition),
                ('series', self.series),
                ('date', self.date),
                ('pages', self.pages),
                ('isbn', self.isbn),
                ('short_title', self.short_title),
                ('access_date', self.access_date),
                ('rights', self.rights),
                ('archive', self.archive),
                ('archive_location', self.archive_location),
                ('library_catalog', self.library_catalog),
                ('call_number', self.call_number),
            ]

            for field_name, field_value in encyclopedia_fields:
                if field_value:
                    field_elem = ET.SubElement(type_specific, field_name)
                    field_elem.text = field_value

        # Common optional fields
        if self.url:
            url_elem = ET.SubElement(doc_info, 'url')
            url_elem.text = self.url

        if self.description:
            desc_elem = ET.SubElement(doc_info, 'description')
            desc_elem.text = self.description

        if self.keywords:
            keywords_elem = ET.SubElement(doc_info, 'keywords')
            keywords_elem.text = self.keywords

        if self.subject:
            subject_elem = ET.SubElement(doc_info, 'subject')
            subject_elem.text = self.subject

        if self.category:
            category_elem = ET.SubElement(doc_info, 'category')
            category_elem.text = self.category

        # Processing information
        processing_info = ET.SubElement(metadata_elem, 'processing_info')

        processing_fields = [
            ('processed_by', self.processed_by),
            ('processing_date', self.processing_date),
            ('ocr_confidence', f"{self.ocr_confidence:.4f}" if self.ocr_confidence > 0 else ''),
            ('page_count', str(self.page_count) if self.page_count else ''),
            ('source_filename', self.source_filename),
            ('source_format', self.source_format),
        ]

        for field_name, field_value in processing_fields:
            if field_value:
                field_elem = ET.SubElement(processing_info, field_name)
                field_elem.text = field_value

        # Citation
        citation_elem = ET.SubElement(metadata_elem, 'citation')
        citation_elem.set('style', 'APA')
        citation_elem.text = self.get_citation_apa()

        # Insert metadata as the FIRST child element
        root_element.insert(0, metadata_elem)


class MetadataManager:
    """
    Enhanced manager class for handling document metadata in OCR processing.
    Now supports type-specific metadata management.
    """

    def __init__(self):
        self.current_metadata: Optional[DocumentMetadata] = None

    def set_metadata(self, metadata: DocumentMetadata) -> None:
        """Set current document metadata"""
        self.current_metadata = metadata

    def clear_metadata(self) -> None:
        """Clear current metadata"""
        self.current_metadata = None

    def has_metadata(self) -> bool:
        """Check if metadata is available"""
        return self.current_metadata is not None and not self.current_metadata.is_empty()

    def get_metadata_type(self) -> Optional[MetadataType]:
        """Get the current metadata type"""
        return self.current_metadata.metadata_type if self.current_metadata else None

    def update_processing_info(self,
                               page_count: int,
                               confidence: float = 0.0,
                               source_filename: str = "",
                               source_format: str = "") -> None:
        """Update processing-related metadata"""
        if self.current_metadata:
            self.current_metadata.page_count = page_count
            self.current_metadata.ocr_confidence = confidence
            self.current_metadata.source_filename = source_filename
            self.current_metadata.source_format = source_format

    def generate_enhanced_markdown(self,
                                   original_content: str,
                                   filename: str = "") -> str:
        """Generate markdown with metadata header"""
        if not self.has_metadata():
            return original_content

        # Update filename if provided
        if filename and not self.current_metadata.source_filename:
            self.current_metadata.source_filename = filename

        header = self.current_metadata.generate_markdown_header()

        # Combine header with original content
        lines = original_content.split('\n')
        content_start = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Stop at first "## Sayfa" - this is where real content begins
            if stripped.startswith('## Sayfa'):
                content_start = i
                break
            # Also stop if we've gone past 10 lines (safety limit)
            if i > 10:
                content_start = 0
                break

        enhanced_content = header + '\n'.join(lines[content_start:])
        return enhanced_content

    def generate_enhanced_xml(self,
                              original_xml: str,
                              filename: str = "") -> str:
        """Generate XML with metadata section"""
        if not self.has_metadata():
            return original_xml

        # Update filename if provided
        if filename and not self.current_metadata.source_filename:
            self.current_metadata.source_filename = filename

        try:
            # Clean and prepare the XML string for parsing
            cleaned_xml = original_xml.strip()

            # Remove XML declaration if present (we'll add our own)
            if cleaned_xml.startswith('<?xml'):
                declaration_end = cleaned_xml.find('?>') + 2
                cleaned_xml = cleaned_xml[declaration_end:].strip()

            # Remove any BOM or invisible characters at the beginning
            cleaned_xml = cleaned_xml.lstrip('\ufeff\ufffe\x00\x01\x02\x03')

            # Ensure we have actual XML content
            if not cleaned_xml.startswith('<'):
                print(f"⚠️ XML doesn't start with '<': {cleaned_xml[:50]}...")
                return original_xml

            # Parse the cleaned XML
            try:
                root = ET.fromstring(cleaned_xml)
            except ET.ParseError as e:
                print(f"⚠️ First parse attempt failed: {e}")
                try:
                    parser = ET.XMLParser(encoding='utf-8')
                    root = ET.fromstring(cleaned_xml.encode('utf-8'), parser=parser)
                except Exception as e2:
                    print(f"⚠️ Second parse attempt failed: {e2}")
                    return original_xml

            # Add metadata to root
            self.current_metadata.generate_xml_metadata(root)

            # Convert back to string
            xml_str = ET.tostring(root, encoding='unicode', method='xml')

            # Add XML declaration
            final_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

            # Pretty format using manual approach
            try:
                import xml.dom.minidom
                dom = xml.dom.minidom.parseString(final_xml)
                pretty_xml = dom.toprettyxml(indent="  ", encoding=None)

                # Clean up empty lines and extra whitespace
                lines = []
                for line in pretty_xml.split('\n'):
                    stripped = line.strip()
                    if stripped:
                        lines.append(line.rstrip())

                result = '\n'.join(lines)

                # Remove duplicate XML declarations if any
                if result.count('<?xml') > 1:
                    lines = result.split('\n')
                    xml_decl_count = 0
                    final_lines = []
                    for line in lines:
                        if line.strip().startswith('<?xml'):
                            xml_decl_count += 1
                            if xml_decl_count == 1:
                                final_lines.append(line)
                        else:
                            final_lines.append(line)
                    result = '\n'.join(final_lines)

                return result

            except Exception as pretty_error:
                print(f"⚠️ Pretty formatting failed: {pretty_error}")
                return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

        except Exception as e:
            print(f"⚠️ XML metadata enhancement failed: {e}")
            return original_xml

    def export_metadata_json(self) -> str:
        """Export metadata as JSON"""
        if not self.current_metadata:
            return "{}"

        return self.current_metadata.to_json()


def create_metadata_from_form(form_data: Dict[str, Any]) -> DocumentMetadata:
    """
    Enhanced helper function to create DocumentMetadata from web form data.
    Now handles type-specific field mapping and document type detection.
    """
    # Get metadata type
    metadata_type = form_data.get('metadata_type', 'book')
    if metadata_type not in ['book', 'article', 'encyclopedia', 'newspaper']:
        metadata_type = 'book'

    # 🆕 Document type (gazete/normal) al
    document_type = str(form_data.get('document_type', 'auto')).strip().lower()
    if document_type not in ['auto', 'newspaper', 'normal']:
        document_type = 'auto'

    # Convert publication year to int if provided
    pub_year = form_data.get('publication_year', '')
    if pub_year:
        try:
            pub_year = int(pub_year)
        except (ValueError, TypeError):
            pub_year = None
    else:
        pub_year = None

    # Convert page_count to int if provided
    page_count_val = form_data.get('page_count', '')
    if page_count_val:
        try:
            page_count_val = int(page_count_val)
        except (ValueError, TypeError):
            page_count_val = None
    else:
        page_count_val = None

    # Create metadata object with all possible fields
    metadata = DocumentMetadata(
        metadata_type=metadata_type,
        document_type=document_type,  # 🆕 YENI ALAN

        # Common fields
        title=str(form_data.get('title', '')).strip(),
        author=str(form_data.get('author', '')).strip(),
        language=str(form_data.get('language', 'tr')).strip().lower(),

        # Book fields
        publisher=str(form_data.get('publisher', '')).strip(),
        publication_year=pub_year,
        publication_city=str(form_data.get('publication_city', '')).strip(),
        country=str(form_data.get('country', '')).strip(),
        edition=str(form_data.get('edition', '')).strip(),
        volume=str(form_data.get('volume', '')).strip(),
        series=str(form_data.get('series', '')).strip(),
        page_count=page_count_val,
        isbn=str(form_data.get('isbn', '')).strip(),
        archive=str(form_data.get('archive', '')).strip(),
        archive_location=str(form_data.get('archive_location', '')).strip(),
        library_catalog=str(form_data.get('library_catalog', '')).strip(),
        call_number=str(form_data.get('call_number', '')).strip(),
        editor=str(form_data.get('editor', '')).strip(),  # YENİ ALAN

        # Article fields
        publication=str(form_data.get('publication', '')).strip(),
        issue=str(form_data.get('issue', '')).strip(),
        pages=str(form_data.get('pages', '')).strip(),
        date=str(form_data.get('date', '')).strip(),
        series_title=str(form_data.get('series_title', '')).strip(),
        series_text=str(form_data.get('series_text', '')).strip(),
        journal_abbreviation=str(form_data.get('journal_abbreviation', '')).strip(),
        doi=str(form_data.get('doi', '')).strip(),
        issn=str(form_data.get('issn', '')).strip(),
        rights=str(form_data.get('rights', '')).strip(),

        # Encyclopedia fields
        encyclopedia_title=str(form_data.get('encyclopedia_title', '')).strip(),
        short_title=str(form_data.get('short_title', '')).strip(),
        access_date=str(form_data.get('access_date', '')).strip(),

        # 🆕 Newspaper fields
        section=str(form_data.get('section', '')).strip(),
        extra=str(form_data.get('extra', '')).strip(),

        # Common optional fields
        url=str(form_data.get('url', '')).strip(),
        subject=str(form_data.get('subject', '')).strip(),
        description=str(form_data.get('description', '')).strip(),
        keywords=str(form_data.get('keywords', '')).strip(),
        category=str(form_data.get('category', '')).strip(),

        # Legacy field
        page_range=str(form_data.get('page_range', '')).strip(),

        # Citation style
        citation_style=str(form_data.get('citation_style', 'apa')).strip().lower(),
    )

    return metadata

def get_metadata_schema() -> Dict[MetadataType, Dict[str, Dict[str, Any]]]:
    """
    Return the metadata schema for frontend validation.
    This matches the schema defined in the HTML.
    """
    return {
        'book': {
            'title': {'label': 'Başlık', 'required': True},
            'author': {'label': 'Yazar', 'required': False},
            'editor': {'label': 'Hazırlayan/Derleyen/Editör', 'required': False},  # YENİ
            'publisher': {'label': 'Yayınevi', 'required': False},
            'publication_year': {'label': 'Yayın Yılı', 'required': False, 'type': 'number'},
            'publication_city': {'label': 'Yayın Yeri', 'required': False},
            'country': {'label': 'Yayınlandığı Ülke', 'required': False},
            'edition': {'label': 'Baskı', 'required': False},
            'volume': {'label': 'Cilt', 'required': False},
            'series': {'label': 'Dizi', 'required': False},
            'page_count': {'label': 'Sayfa Sayısı', 'required': False, 'type': 'number'},
            'language': {'label': 'Dil', 'required': False, 'type': 'select'},
            'isbn': {'label': 'ISBN', 'required': False},
            'url': {'label': 'URL', 'required': False, 'type': 'url'},
            'archive': {'label': 'Arşiv', 'required': False},
            'archive_location': {'label': 'Arşivdeki Yeri', 'required': False},
            'library_catalog': {'label': 'Kütüphane Kataloğu', 'required': False},
            'call_number': {'label': 'Yer Numarası', 'required': False}
        },
        'article': {
            'title': {'label': 'Başlık', 'required': True},
            'author': {'label': 'Yazar', 'required': False},
            'publication': {'label': 'Yayın', 'required': False},
            'volume': {'label': 'Cilt', 'required': False},
            'issue': {'label': 'Sayı', 'required': False},
            'pages': {'label': 'Sayfa', 'required': False},
            'date': {'label': 'Tarih', 'required': False, 'type': 'date'},
            'series': {'label': 'Dizi', 'required': False},
            'series_title': {'label': 'Dizi Başlığı', 'required': False},
            'series_text': {'label': 'Dizi Metni', 'required': False},
            'journal_abbreviation': {'label': 'Dergi Kısaltması', 'required': False},
            'language': {'label': 'Dil', 'required': False, 'type': 'select'},
            'doi': {'label': 'DOI', 'required': False},
            'issn': {'label': 'ISSN', 'required': False},
            'url': {'label': 'URL', 'required': False, 'type': 'url'},
            'archive': {'label': 'Arşiv', 'required': False},
            'archive_location': {'label': 'Arşivdeki Yeri', 'required': False},
            'library_catalog': {'label': 'Kütüphane Kataloğu', 'required': False},
            'call_number': {'label': 'Yer Numarası', 'required': False},
            'rights': {'label': 'Telif', 'required': False}
        },
        'encyclopedia': {
            'title': {'label': 'Başlık', 'required': True},
            'author': {'label': 'Yazar', 'required': False},
            'encyclopedia_title': {'label': 'Ansiklopedi Başlığı', 'required': False},
            'publisher': {'label': 'Yayınevi', 'required': False},
            'publication_year': {'label': 'Yayın Yılı', 'required': False, 'type': 'number'},
            'publication_city': {'label': 'Yayın Yeri', 'required': False},
            'volume': {'label': 'Cilt', 'required': False},
            'edition': {'label': 'Baskı', 'required': False},
            'series': {'label': 'Dizi', 'required': False},
            'date': {'label': 'Tarih', 'required': False, 'type': 'date'},
            'pages': {'label': 'Sayfa', 'required': False},
            'isbn': {'label': 'ISBN', 'required': False},
            'short_title': {'label': 'Kısa Başlık', 'required': False},
            'url': {'label': 'URL', 'required': False, 'type': 'url'},
            'access_date': {'label': 'Son Erişim', 'required': False, 'type': 'date'},
            'language': {'label': 'Dil', 'required': False, 'type': 'select'},
            'archive': {'label': 'Arşiv', 'required': False},
            'archive_location': {'label': 'Arşivdeki Yeri', 'required': False},
            'library_catalog': {'label': 'Kütüphane Kataloğu', 'required': False},
            'call_number': {'label': 'Yer Numarası', 'required': False},
            'rights': {'label': 'Telif', 'required': False}
        },
        'newspaper': {
            'title': {'label': 'Başlık', 'required': True},
            'author': {'label': 'Yazar', 'required': False},
            'publication': {'label': 'Yayın', 'required': False},
            'publication_city': {'label': 'Yayın Yeri', 'required': False},
            'edition': {'label': 'Baskı', 'required': False},
            'date': {'label': 'Tarih', 'required': False, 'type': 'date'},
            'section': {'label': 'Bölüm', 'required': False},
            'pages': {'label': 'Sayfa', 'required': False},
            'language': {'label': 'Dil', 'required': False, 'type': 'select'},
            'short_title': {'label': 'Kısa Başlık', 'required': False},
            'issn': {'label': 'ISSN', 'required': False},
            'url': {'label': 'URL', 'required': False, 'type': 'url'},
            'access_date': {'label': 'Son Erişim', 'required': False, 'type': 'date'},
            'archive': {'label': 'Arşiv', 'required': False},
            'archive_location': {'label': 'Arşivdeki Yeri', 'required': False},
            'library_catalog': {'label': 'Kütüphane Kataloğu', 'required': False},
            'call_number': {'label': 'Yer Numarası', 'required': False},
            'rights': {'label': 'Telif', 'required': False},
            'extra': {'label': 'İlave', 'required': False, 'type': 'textarea'}
        }
    }


# External API integration functions for metadata fetching
async def fetch_metadata_from_doi(doi: str) -> Optional[Dict[str, Any]]:
    """
    Fetch metadata from DOI using CrossRef API.
    Returns article metadata if found.
    """
    import aiohttp
    import asyncio

    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {
            'User-Agent': 'SuryaOCR-Pro/1.0 (https://github.com/your-repo; mailto:your-email@domain.com)'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    work = data.get('message', {})

                    # Extract metadata
                    authors = work.get('author', [])
                    author_names = []
                    for author in authors:
                        given = author.get('given', '')
                        family = author.get('family', '')
                        if given and family:
                            author_names.append(f"{given} {family}")
                        elif family:
                            author_names.append(family)

                    # Get publication date
                    pub_date = work.get('published-print') or work.get('published-online')
                    date_str = ""
                    if pub_date and 'date-parts' in pub_date:
                        date_parts = pub_date['date-parts'][0]
                        if len(date_parts) >= 3:
                            date_str = f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
                        elif len(date_parts) >= 1:
                            date_str = str(date_parts[0])

                    # Extract journal info
                    container_title = work.get('container-title', [])
                    journal_name = container_title[0] if container_title else ""

                    # Extract page info
                    page = work.get('page', '')

                    # Extract volume and issue
                    volume = work.get('volume', '')
                    issue = work.get('issue', '')

                    return {
                        'metadata_type': 'article',
                        'title': work.get('title', [''])[0] if work.get('title') else '',
                        'author': ', '.join(author_names),
                        'publication': journal_name,
                        'volume': volume,
                        'issue': issue,
                        'pages': page,
                        'date': date_str,
                        'doi': doi,
                        'issn': work.get('ISSN', [''])[0] if work.get('ISSN') else '',
                        'language': 'en'  # Default, could be improved with language detection
                    }

    except Exception as e:
        print(f"Error fetching DOI metadata: {e}")

    return None


async def fetch_metadata_from_pmid(pmid: str) -> Optional[Dict[str, Any]]:
    """
    Fetch metadata from PMID using NCBI E-utilities.
    Returns article metadata if found.
    """
    import aiohttp
    import xml.etree.ElementTree as ET

    try:
        # First get the detailed record
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            'db': 'pubmed',
            'id': pmid,
            'retmode': 'xml'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    xml_content = await response.text()
                    root = ET.fromstring(xml_content)

                    article = root.find('.//Article')
                    if article is None:
                        return None

                    # Extract title
                    title_elem = article.find('.//ArticleTitle')
                    title = title_elem.text if title_elem is not None else ""

                    # Extract authors
                    authors = []
                    author_list = article.find('.//AuthorList')
                    if author_list is not None:
                        for author in author_list.findall('.//Author'):
                            last_name = author.find('LastName')
                            first_name = author.find('ForeName')
                            if last_name is not None and first_name is not None:
                                authors.append(f"{first_name.text} {last_name.text}")
                            elif last_name is not None:
                                authors.append(last_name.text)

                    # Extract journal info
                    journal_elem = article.find('.//Journal/Title')
                    journal = journal_elem.text if journal_elem is not None else ""

                    # Extract publication date
                    pub_date = article.find('.//PubDate')
                    date_str = ""
                    if pub_date is not None:
                        year = pub_date.find('Year')
                        month = pub_date.find('Month')
                        day = pub_date.find('Day')

                        date_parts = []
                        if year is not None:
                            date_parts.append(year.text)
                        if month is not None:
                            # Convert month name to number if needed
                            month_map = {
                                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                                'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                                'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                            }
                            month_text = month.text
                            if month_text in month_map:
                                date_parts.append(month_map[month_text])
                            elif month_text.isdigit():
                                date_parts.append(f"{int(month_text):02d}")
                            else:
                                date_parts.append(month_text)
                        if day is not None:
                            date_parts.append(f"{int(day.text):02d}")

                        date_str = "-".join(date_parts)

                    # Extract volume and issue
                    volume_elem = article.find('.//Volume')
                    volume = volume_elem.text if volume_elem is not None else ""

                    issue_elem = article.find('.//Issue')
                    issue = issue_elem.text if issue_elem is not None else ""

                    # Extract pages
                    pagination = article.find('.//Pagination/MedlinePgn')
                    pages = pagination.text if pagination is not None else ""

                    # Try to get DOI
                    doi = ""
                    article_ids = root.find('.//ArticleIdList')
                    if article_ids is not None:
                        for article_id in article_ids.findall('.//ArticleId'):
                            if article_id.get('IdType') == 'doi':
                                doi = article_id.text
                                break

                    return {
                        'metadata_type': 'article',
                        'title': title,
                        'author': ', '.join(authors),
                        'publication': journal,
                        'volume': volume,
                        'issue': issue,
                        'pages': pages,
                        'date': date_str,
                        'doi': doi,
                        'language': 'en'
                    }

    except Exception as e:
        print(f"Error fetching PMID metadata: {e}")

    return None


async def fetch_metadata_from_arxiv(arxiv_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch metadata from arXiv ID using arXiv API.
    Returns article metadata if found.
    """
    import aiohttp
    import xml.etree.ElementTree as ET
    from datetime import datetime

    try:
        # Clean up arXiv ID format
        if not arxiv_id.startswith('http'):
            if '/' in arxiv_id:
                # Old format like cs.AI/0601001
                arxiv_id = arxiv_id
            elif arxiv_id.count('.') == 1:
                # New format like 1234.5678
                arxiv_id = arxiv_id

        url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    xml_content = await response.text()
                    root = ET.fromstring(xml_content)

                    # Define namespace
                    ns = {'atom': 'http://www.w3.org/2005/Atom'}

                    entry = root.find('.//atom:entry', ns)
                    if entry is None:
                        return None

                    # Extract title
                    title_elem = entry.find('atom:title', ns)
                    title = title_elem.text.strip() if title_elem is not None else ""

                    # Extract authors
                    authors = []
                    for author in entry.findall('.//atom:author', ns):
                        name_elem = author.find('atom:name', ns)
                        if name_elem is not None:
                            authors.append(name_elem.text)

                    # Extract date
                    published = entry.find('atom:published', ns)
                    date_str = ""
                    if published is not None:
                        # Parse ISO date format
                        date_obj = datetime.fromisoformat(published.text.replace('Z', '+00:00'))
                        date_str = date_obj.strftime('%Y-%m-%d')

                    # Extract summary
                    summary_elem = entry.find('atom:summary', ns)
                    summary = summary_elem.text.strip() if summary_elem is not None else ""

                    # Extract categories/subjects
                    categories = []
                    for category in entry.findall('.//atom:category', ns):
                        term = category.get('term')
                        if term:
                            categories.append(term)

                    return {
                        'metadata_type': 'article',
                        'title': title,
                        'author': ', '.join(authors),
                        'publication': 'arXiv preprint',
                        'date': date_str,
                        'description': summary[:500] + '...' if len(summary) > 500 else summary,
                        'subject': ', '.join(categories),
                        'url': f"https://arxiv.org/abs/{arxiv_id}",
                        'language': 'en'
                    }

    except Exception as e:
        print(f"Error fetching arXiv metadata: {e}")

    return None


async def fetch_metadata_from_ads(ads_bibcode: str) -> Optional[Dict[str, Any]]:
    """
    Fetch metadata from ADS Bibcode using NASA ADS API.
    Note: Requires API key for production use.
    Returns article metadata if found.
    """
    # This is a placeholder implementation
    # In production, you would need to register for ADS API key
    # and implement the actual API call

    return {
        'metadata_type': 'article',
        'title': f'Sample Article for {ads_bibcode}',
        'author': 'Sample Author',
        'publication': 'Astrophysical Journal',
        'volume': '123',
        'pages': '456-789',
        'date': '2023',
        'language': 'en',
        'description': 'This is a placeholder for ADS API integration. Please implement with actual ADS API key.'
    }


async def fetch_metadata_by_identifier(identifier_type: str, identifier: str) -> Optional[Dict[str, Any]]:
    """
    Main function to fetch metadata based on identifier type.
    """
    identifier = identifier.strip()

    if identifier_type == 'doi':
        return await fetch_metadata_from_doi(identifier)
    elif identifier_type == 'pmid':
        return await fetch_metadata_from_pmid(identifier)
    elif identifier_type == 'arxiv':
        return await fetch_metadata_from_arxiv(identifier)
    elif identifier_type == 'ads':
        return await fetch_metadata_from_ads(identifier)
    else:
        return None