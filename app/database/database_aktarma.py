"""
Modern SuryaOCR Bulk Import Tool
Advanced PySide6 application for batch importing processed documents
"""

import sys
import os
import json
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging
from datetime import datetime
import re

# PySide6 imports
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
        QWidget, QLabel, QPushButton, QFileDialog, QTextEdit,
        QTableWidget, QTableWidgetItem, QProgressBar, QMessageBox,
        QGroupBox, QFormLayout, QLineEdit, QComboBox, QCheckBox,
        QSplitter, QScrollArea, QFrame, QGridLayout, QSpacerItem,
        QSizePolicy, QHeaderView, QAbstractItemView, QTreeWidget,
        QTreeWidgetItem, QTabWidget
    )
    from PySide6.QtCore import Qt, QThread, QTimer, Signal, QSize
    from PySide6.QtGui import QFont, QPixmap, QIcon, QPalette, QColor
except ImportError:
    print("PySide6 not found. Install with: uv add PySide6")
    sys.exit(1)

# Database imports
try:
    current_dir = Path(__file__).parent
    database_dir = current_dir / 'database'
    if database_dir.exists():
        sys.path.insert(0, str(database_dir))

    from database_service import get_database_service, initialize_database_service
    import connection
    DATABASE_AVAILABLE = True
except ImportError as e:
    print(f"Database service not available: {e}")
    DATABASE_AVAILABLE = False


class MetadataExtractor:
    """Enhanced metadata extraction with better error handling"""

    @staticmethod
    def extract_from_xml(xml_path: str) -> Optional[Dict[str, Any]]:
        """Extract metadata from XML file with robust parsing"""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            metadata = {}

            # Find metadata section - try multiple approaches
            metadata_elem = (
                root.find('.//metadata') or
                root.find('.//document_info') or
                (root if root.tag in ['metadata', 'document'] else None)
            )

            if metadata_elem is None:
                # Fallback: extract from any structured content
                return MetadataExtractor._extract_fallback_metadata(root)

            # Extract all text content from metadata
            for elem in metadata_elem.iter():
                if elem.text and elem.text.strip() and elem.tag != metadata_elem.tag:
                    key = elem.tag.replace('_', ' ').title()
                    metadata[elem.tag] = elem.text.strip()

            # Extract attributes
            for key, value in metadata_elem.attrib.items():
                if value and value.strip():
                    metadata[key] = value.strip()

            # Ensure required fields
            if 'metadata_type' not in metadata:
                metadata['metadata_type'] = 'article'
            if 'language' not in metadata:
                metadata['language'] = 'tr'

            return metadata

        except Exception as e:
            print(f"XML parsing error: {e}")
            return None

    @staticmethod
    def _extract_fallback_metadata(root) -> Dict[str, Any]:
        """Fallback metadata extraction"""
        metadata = {
            'metadata_type': 'article',
            'language': 'tr',
            'title': 'Imported Document',
            'source': 'bulk_import'
        }

        # Try to find any text content
        all_text = []
        for elem in root.iter():
            if elem.text and len(elem.text.strip()) > 10:
                all_text.append(elem.text.strip())

        if all_text:
            # Use first substantial text as title
            metadata['title'] = all_text[0][:100]

        return metadata


class DocumentMatcher:
    """Intelligent document matching between PDF and XML/MD folders"""

    def __init__(self, pdf_folder: str, content_folder: str):
        self.pdf_folder = Path(pdf_folder)
        self.content_folder = Path(content_folder)

    def find_matches(self) -> List[Dict[str, str]]:
        """Find matching document sets"""
        matches = []

        # Get all PDF files
        pdf_files = list(self.pdf_folder.glob("*.pdf"))

        for pdf_file in pdf_files:
            # Look for matching XML and MD files
            xml_file, md_file = self._find_content_files(pdf_file.name)

            if xml_file:
                match = {
                    'pdf_path': str(pdf_file),
                    'xml_path': str(xml_file),
                    'md_path': str(md_file) if md_file else None,
                    'base_name': pdf_file.stem,
                    'status': 'ready'
                }
                matches.append(match)
            else:
                # No matching XML found
                match = {
                    'pdf_path': str(pdf_file),
                    'xml_path': None,
                    'md_path': None,
                    'base_name': pdf_file.stem,
                    'status': 'no_xml'
                }
                matches.append(match)

        return matches

    def _find_content_files(self, pdf_name: str) -> Tuple[Optional[Path], Optional[Path]]:
        """Find matching XML and MD files for a PDF"""
        # Direct match: PDF_NAME.xml, PDF_NAME.md
        xml_direct = self.content_folder / f"{pdf_name}.xml"
        md_direct = self.content_folder / f"{pdf_name}.md"

        if xml_direct.exists():
            return xml_direct, md_direct if md_direct.exists() else None

        # Try without extension and re-add
        base_name = Path(pdf_name).stem
        xml_alt = self.content_folder / f"{base_name}.xml"
        md_alt = self.content_folder / f"{base_name}.md"

        if xml_alt.exists():
            return xml_alt, md_alt if md_alt.exists() else None

        # Try fuzzy matching for similar names
        xml_files = list(self.content_folder.glob("*.xml"))
        for xml_file in xml_files:
            if self._names_match(base_name, xml_file.stem):
                md_match = self.content_folder / f"{xml_file.stem}.md"
                return xml_file, md_match if md_match.exists() else None

        return None, None

    def _names_match(self, name1: str, name2: str, threshold: float = 0.8) -> bool:
        """Simple fuzzy name matching"""
        # Remove common suffixes and prefixes
        clean1 = re.sub(r'(_processed|_split|_result|_output).*', '', name1.lower())
        clean2 = re.sub(r'(_processed|_split|_result|_output).*', '', name2.lower())

        if clean1 == clean2:
            return True

        # Check if one contains the other
        return clean1 in clean2 or clean2 in clean1


class ImportWorker(QThread):
    """Background worker for import operations with progress tracking"""

    progress_updated = Signal(int, str, dict)
    import_completed = Signal(dict)
    item_completed = Signal(int, dict)

    def __init__(self, matches: List[Dict[str, str]]):
        super().__init__()
        self.matches = matches
        self.should_stop = False

    def run(self):
        try:
            # Initialize database
            initialize_database_service()
            db_service = get_database_service()

            if not db_service or not db_service.is_ready():
                self.import_completed.emit({
                    'success': False,
                    'message': 'Database connection failed',
                    'results': []
                })
                return

            results = []
            total = len([m for m in self.matches if m['status'] == 'ready'])
            processed = 0

            for i, match in enumerate(self.matches):
                if self.should_stop:
                    break

                if match['status'] != 'ready':
                    continue

                self.progress_updated.emit(
                    int((processed / total) * 100),
                    f"Processing: {match['base_name']}",
                    {'current': processed + 1, 'total': total}
                )

                # Import single document
                result = self._import_single_document(match, db_service)
                results.append(result)

                # Emit item completion
                self.item_completed.emit(i, result)

                processed += 1

            self.progress_updated.emit(100, "Import completed", {'current': total, 'total': total})

            # Calculate summary
            successful = sum(1 for r in results if r['success'])
            failed = len(results) - successful

            self.import_completed.emit({
                'success': True,
                'message': f'Completed: {successful} successful, {failed} failed',
                'results': results,
                'summary': {'successful': successful, 'failed': failed, 'total': len(results)}
            })

        except Exception as e:
            self.import_completed.emit({
                'success': False,
                'message': f'Import process failed: {str(e)}',
                'results': []
            })

    def _import_single_document(self, match: Dict[str, str], db_service) -> Dict[str, Any]:
        """Import a single document"""
        try:
            # Extract metadata from XML
            metadata = MetadataExtractor.extract_from_xml(match['xml_path'])
            if not metadata:
                return {
                    'success': False,
                    'file': match['base_name'],
                    'error': 'Could not parse XML metadata'
                }

            # Prepare file info
            file_info = self._prepare_file_info(match['pdf_path'])

            # Clean metadata for database
            clean_metadata = self._clean_metadata(metadata)

            # Save document and file
            document_id = db_service.save_document_and_file(clean_metadata, file_info)
            if not document_id:
                return {
                    'success': False,
                    'file': match['base_name'],
                    'error': 'Failed to save document to database'
                }

            # Save OCR results if we have content files
            if match['xml_path']:
                self._save_content_results(document_id, match, db_service, metadata)

            return {
                'success': True,
                'file': match['base_name'],
                'document_id': document_id,
                'message': 'Successfully imported'
            }

        except Exception as e:
            return {
                'success': False,
                'file': match['base_name'],
                'error': str(e)
            }

    def _prepare_file_info(self, pdf_path: str) -> Dict[str, Any]:
        """Prepare file information"""
        path = Path(pdf_path)

        return {
            'filename': path.name,
            'original_filename': path.name,
            'file_path': str(path.absolute()),
            'file_size': path.stat().st_size,
            'mime_type': 'application/pdf',
            'file_type': 'pdf'
        }

    def _normalize_date_value(self, raw: str) -> tuple[dict, bool]:
        """
        Metadaki 'date' benzeri alanları normalize eder.
        - Sadece yıl (YYYY) ise: {'publication_year': int(YYYY)} döner, date kullanılmaz.
        - Yıl-ay (YYYY-MM veya YYYY/MM) ise: date=YYYY-MM-01 yapılır.
        - Tam tarih (YYYY-MM-DD gibi) ise doğrudan date olarak döner.
        Dönüş: ( {'date': 'YYYY-MM-DD'} veya {'publication_year': 1956} , handled_flag )
        """
        s = str(raw).strip()
        if not s:
            return ({}, False)

        import re
        # 1) Sadece yıl: 1956
        m_year = re.fullmatch(r'(\d{4})', s)
        if m_year:
            return ({'publication_year': int(m_year.group(1))}, True)

        # 2) Yıl-Ay: 1956-03 veya 1956/3
        m_year_month = re.fullmatch(r'(\d{4})[-/](\d{1,2})', s)
        if m_year_month:
            y = int(m_year_month.group(1))
            m = int(m_year_month.group(2))
            if 1 <= m <= 12:
                return ({'date': f'{y:04d}-{m:02d}-01'}, True)

        # 3) Tam tarih: 1956-3-5, 1956/03/05, 1956.03.05, 1956 03 05
        m_full = re.fullmatch(r'(\d{4})[-/.\s](\d{1,2})[-/.\s](\d{1,2})', s)
        if m_full:
            y = int(m_full.group(1))
            m = max(1, min(12, int(m_full.group(2))))
            d = max(1, min(31, int(m_full.group(3))))
            return ({'date': f'{y:04d}-{m:02d}-{d:02d}'}, True)

        # 4) Parse edemediysek
        return ({}, False)

    def _clean_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Clean metadata for database"""
        # Veritabanında olmayan veya sistemsel alanları dışla
        excluded_fields = [
            'ocr_confidence', 'processing_time', 'characters_per_second',
            'total_characters', 'processed_by', 'processing_date',
            'source_filename', 'source_format',
            'citation'  # Modelde yoksa gönderme
        ]

        clean: Dict[str, Any] = {}

        for key, value in metadata.items():
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue

            # 1) 'type' -> 'metadata_type' dönüşümü
            if key == 'type':
                if 'metadata_type' not in clean and 'metadata_type' not in metadata:
                    clean['metadata_type'] = text
                continue

            # 2) Tarih normalizasyonu (sadece 'date' ve muhtemel varyantları yakala)
            if key.lower() in ('date', 'publication_date', 'pub_date'):
                norm, handled = self._normalize_date_value(text)
                if handled:
                    # norm {'publication_year': 1956} veya {'date': 'YYYY-MM-DD'} dönebilir
                    clean.update(norm)
                else:
                    # Parse edemediysek 'date'i göndermemek daha güvenli
                    # (istersen burada 'short_title' vb. başka yere yazabilirsin)
                    pass
                continue

            # 3) Hariç tutulanlar
            if key in excluded_fields:
                continue

            # 4) Normal anahtarlar
            clean[key] = text

        # Zorunlu alanları garanti et
        clean.setdefault('metadata_type', 'article')
        clean.setdefault('language', 'tr')
        clean.setdefault('citation_style', 'apa')

        # 5) Ek güvence: publication_year bazı yerlerde "1956" string gelebilir → int'e çevir
        if 'publication_year' in clean:
            try:
                clean['publication_year'] = int(str(clean['publication_year']).strip())
            except Exception:
                # Çevrilemezse kaldır (veritabanı int bekliyorsa sorun olmasın)
                clean.pop('publication_year', None)

        return clean

    def _save_content_results(self, document_id: str, match: Dict[str, str],
                             db_service, metadata: Dict[str, Any]):
        """Save OCR content results"""
        try:
            # Read file contents
            xml_content = self._read_file(match['xml_path'])
            md_content = self._read_file(match['md_path']) if match['md_path'] else ""

            # Create processing job
            job_id = db_service.create_processing_job(document_id, 'ocr', ['xml', 'md'])
            if not job_id:
                return

            # Prepare OCR data
            ocr_data = {
                'outputs': {
                    'xml': xml_content,
                    'md': md_content
                },
                'page_count': metadata.get('page_count', 1),
                'processing_time': 0.1,  # Imported content
                'confidence_score': float(metadata.get('ocr_confidence', 0.95)),
                'from_import': True
            }

            # Save OCR results
            db_service.save_ocr_results(job_id, document_id, ocr_data)
            db_service.complete_job(job_id, success=True)

        except Exception as e:
            print(f"Error saving content results: {e}")

    def _read_file(self, file_path: str) -> str:
        """Read file content"""
        try:
            if not file_path or not os.path.exists(file_path):
                return ""
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ""

    def stop(self):
        """Stop the import process"""
        self.should_stop = True


class ModernBulkImportTool(QMainWindow):
    """Modern, user-friendly bulk import application"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SuryaOCR Advanced Bulk Import Tool")
        self.setGeometry(100, 100, 1400, 900)

        # Data for both import modes
        self.pdf_folder = ""
        self.content_folder = ""
        self.matches = []
        self.import_worker = None

        # Single import data
        self.single_files = {'pdf': '', 'xml': '', 'md': ''}
        self.single_metadata = {}

        # Setup
        self.setup_modern_ui()
        self.setup_styles()
        self.check_database_status()

    def setup_modern_ui(self):
        """Create modern, intuitive UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header
        self.create_header(main_layout)

        # Tab widget for different import modes
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create tabs
        self.create_single_import_tab()
        self.create_bulk_import_tab()

        # Status bar
        self.statusBar().showMessage("Ready - Choose import mode")

    def create_single_import_tab(self):
        """Create single file import tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)

        # File selection group
        files_group = QGroupBox("Select Files for Single Import")
        files_layout = QFormLayout(files_group)

        # PDF file
        pdf_layout = QHBoxLayout()
        self.single_pdf_edit = QLineEdit()
        self.single_pdf_edit.setReadOnly(True)
        self.single_pdf_edit.setPlaceholderText("Select PDF file...")

        pdf_browse_btn = QPushButton("Browse PDF")
        pdf_browse_btn.setObjectName("browseBtn")
        pdf_browse_btn.clicked.connect(self.browse_single_pdf)

        pdf_layout.addWidget(self.single_pdf_edit, 1)
        pdf_layout.addWidget(pdf_browse_btn)
        files_layout.addRow("PDF File:", pdf_layout)

        # XML file
        xml_layout = QHBoxLayout()
        self.single_xml_edit = QLineEdit()
        self.single_xml_edit.setReadOnly(True)
        self.single_xml_edit.setPlaceholderText("Select XML file...")

        xml_browse_btn = QPushButton("Browse XML")
        xml_browse_btn.setObjectName("browseBtn")
        xml_browse_btn.clicked.connect(self.browse_single_xml)

        xml_layout.addWidget(self.single_xml_edit, 1)
        xml_layout.addWidget(xml_browse_btn)
        files_layout.addRow("XML File:", xml_layout)

        # MD file (optional)
        md_layout = QHBoxLayout()
        self.single_md_edit = QLineEdit()
        self.single_md_edit.setReadOnly(True)
        self.single_md_edit.setPlaceholderText("Select MD file (optional)...")

        md_browse_btn = QPushButton("Browse MD")
        md_browse_btn.setObjectName("browseBtn")
        md_browse_btn.clicked.connect(self.browse_single_md)

        md_clear_btn = QPushButton("Clear")
        md_clear_btn.setObjectName("clearBtn")
        md_clear_btn.clicked.connect(lambda: self.single_md_edit.clear())

        md_layout.addWidget(self.single_md_edit, 1)
        md_layout.addWidget(md_browse_btn)
        md_layout.addWidget(md_clear_btn)
        files_layout.addRow("MD File:", md_layout)

        layout.addWidget(files_group)

        # Preview metadata
        preview_group = QGroupBox("Metadata Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.single_metadata_table = QTableWidget()
        self.single_metadata_table.setColumnCount(2)
        self.single_metadata_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.single_metadata_table.horizontalHeader().setStretchLastSection(True)
        self.single_metadata_table.setMaximumHeight(200)
        preview_layout.addWidget(self.single_metadata_table)

        # Parse button
        parse_btn = QPushButton("Parse Metadata from XML")
        parse_btn.setObjectName("parseBtn")
        parse_btn.clicked.connect(self.parse_single_metadata)
        preview_layout.addWidget(parse_btn)

        layout.addWidget(preview_group)

        # Import controls
        single_controls_layout = QHBoxLayout()

        self.single_import_btn = QPushButton("Import Single Document")
        self.single_import_btn.setObjectName("importBtn")
        self.single_import_btn.clicked.connect(self.import_single_document)
        self.single_import_btn.setEnabled(False)

        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.setObjectName("clearBtn")
        clear_all_btn.clicked.connect(self.clear_single_files)

        single_controls_layout.addWidget(self.single_import_btn)
        single_controls_layout.addWidget(clear_all_btn)
        single_controls_layout.addStretch()

        layout.addLayout(single_controls_layout)
        layout.addStretch()

        self.tab_widget.addTab(tab, "Single Import")

    def create_bulk_import_tab(self):
        """Create bulk import tab"""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # Main content area
        content_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(content_splitter)

        # Left panel - Configuration
        left_panel = self.create_configuration_panel()
        content_splitter.addWidget(left_panel)

        # Right panel - Results and progress
        right_panel = self.create_results_panel()
        content_splitter.addWidget(right_panel)

        # Set splitter proportions
        content_splitter.setSizes([600, 800])

        self.tab_widget.addTab(tab, "Bulk Import")

    def create_header(self, parent_layout):
        """Create application header"""
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header_frame)

        # Title and description
        title_layout = QVBoxLayout()

        title_label = QLabel("SuryaOCR Bulk Import")
        title_label.setObjectName("titleLabel")

        desc_label = QLabel("Import processed documents from separate PDF and content folders")
        desc_label.setObjectName("descLabel")

        title_layout.addWidget(title_label)
        title_layout.addWidget(desc_label)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Database status indicator
        self.db_status_widget = self.create_db_status_widget()
        header_layout.addWidget(self.db_status_widget)

        parent_layout.addWidget(header_frame)

    def create_db_status_widget(self) -> QWidget:
        """Create database status indicator"""
        widget = QFrame()
        widget.setObjectName("dbStatusFrame")
        layout = QHBoxLayout(widget)

        self.db_status_label = QLabel("Checking...")
        self.db_status_label.setObjectName("dbStatusLabel")

        self.db_test_btn = QPushButton("Test")
        self.db_test_btn.setObjectName("dbTestBtn")
        self.db_test_btn.clicked.connect(self.check_database_status)

        layout.addWidget(QLabel("Database:"))
        layout.addWidget(self.db_status_label)
        layout.addWidget(self.db_test_btn)

        return widget

    def create_configuration_panel(self) -> QWidget:
        """Create left configuration panel"""
        panel = QFrame()
        panel.setObjectName("configPanel")
        layout = QVBoxLayout(panel)

        # Folder selection
        folders_group = QGroupBox("Folder Selection")
        folders_group.setObjectName("foldersGroup")
        folders_layout = QFormLayout(folders_group)

        # PDF folder
        pdf_layout = QHBoxLayout()
        self.pdf_folder_edit = QLineEdit()
        self.pdf_folder_edit.setReadOnly(True)
        self.pdf_folder_edit.setPlaceholderText("Select folder containing PDF files...")

        pdf_browse_btn = QPushButton("Browse")
        pdf_browse_btn.setObjectName("browseBtn")
        pdf_browse_btn.clicked.connect(self.browse_pdf_folder)

        pdf_layout.addWidget(self.pdf_folder_edit, 1)
        pdf_layout.addWidget(pdf_browse_btn)
        folders_layout.addRow("PDF Folder:", pdf_layout)

        # Content folder (XML/MD)
        content_layout = QHBoxLayout()
        self.content_folder_edit = QLineEdit()
        self.content_folder_edit.setReadOnly(True)
        self.content_folder_edit.setPlaceholderText("Select folder containing XML and MD files...")

        content_browse_btn = QPushButton("Browse")
        content_browse_btn.setObjectName("browseBtn")
        content_browse_btn.clicked.connect(self.browse_content_folder)

        content_layout.addWidget(self.content_folder_edit, 1)
        content_layout.addWidget(content_browse_btn)
        folders_layout.addRow("Content Folder:", content_layout)

        layout.addWidget(folders_group)

        # Scan button
        self.scan_btn = QPushButton("Scan for Matches")
        self.scan_btn.setObjectName("scanBtn")
        self.scan_btn.clicked.connect(self.scan_folders)
        self.scan_btn.setEnabled(False)
        layout.addWidget(self.scan_btn)

        # Matches preview
        matches_group = QGroupBox("Found Matches")
        matches_layout = QVBoxLayout(matches_group)

        self.matches_tree = QTreeWidget()
        self.matches_tree.setHeaderLabels(["Document", "Status", "Files"])
        self.matches_tree.setObjectName("matchesTree")
        matches_layout.addWidget(self.matches_tree)

        # Match stats
        self.matches_stats = QLabel("No matches found")
        self.matches_stats.setObjectName("statsLabel")
        matches_layout.addWidget(self.matches_stats)

        layout.addWidget(matches_group, 1)

        # Import controls
        import_group = QGroupBox("Import Controls")
        import_layout = QVBoxLayout(import_group)

        self.import_btn = QPushButton("Start Import")
        self.import_btn.setObjectName("importBtn")
        self.import_btn.clicked.connect(self.start_import)
        self.import_btn.setEnabled(False)

        self.stop_btn = QPushButton("Stop Import")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.clicked.connect(self.stop_import)
        self.stop_btn.setEnabled(False)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.stop_btn)
        import_layout.addLayout(button_layout)

        layout.addWidget(import_group)

        return panel

    def create_results_panel(self) -> QWidget:
        """Create right results panel"""
        panel = QFrame()
        panel.setObjectName("resultsPanel")
        layout = QVBoxLayout(panel)

        # Progress section
        progress_group = QGroupBox("Import Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")

        self.progress_label = QLabel("Ready to import")
        self.progress_label.setObjectName("progressLabel")

        self.progress_details = QLabel("")
        self.progress_details.setObjectName("progressDetails")

        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_details)

        layout.addWidget(progress_group)

        # Results table
        results_group = QGroupBox("Import Results")
        results_layout = QVBoxLayout(results_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Document", "Status", "Document ID", "Message"])
        self.results_table.setObjectName("resultsTable")
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        # Make table responsive
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        results_layout.addWidget(self.results_table)

        layout.addWidget(results_group, 1)

        # Summary section
        summary_group = QGroupBox("Import Summary")
        summary_layout = QVBoxLayout(summary_group)

        self.summary_label = QLabel("No imports completed yet")
        self.summary_label.setObjectName("summaryLabel")
        summary_layout.addWidget(self.summary_label)

        layout.addWidget(summary_group)

        return panel

    def setup_styles(self):
        """Apply modern stylesheet"""
        style = """
        QMainWindow {
            background-color: #f5f5f5;
        }
        
        #headerFrame {
            background-color: #2c3e50;
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        
        #titleLabel {
            font-size: 24px;
            font-weight: bold;
            color: white;
        }
        
        #descLabel {
            font-size: 12px;
            color: #bdc3c7;
            margin-top: 5px;
        }
        
        #dbStatusFrame {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
            padding: 8px;
        }
        
        #dbStatusLabel {
            color: white;
            font-weight: bold;
        }
        
        #dbTestBtn {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
        }
        
        #dbTestBtn:hover {
            background-color: #2980b9;
        }
        
        QGroupBox {
            font-weight: bold;
            font-size: 14px;
            border: 2px solid #bdc3c7;
            border-radius: 8px;
            margin: 10px 0;
            padding-top: 15px;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 8px 0 8px;
            color: #2c3e50;
        }
        
        #configPanel, #resultsPanel {
            background-color: white;
            border-radius: 8px;
            padding: 15px;
        }
        
        QLineEdit {
            padding: 8px;
            border: 2px solid #ecf0f1;
            border-radius: 5px;
            font-size: 12px;
        }
        
        QLineEdit:focus {
            border-color: #3498db;
        }
        
        #browseBtn {
            background-color: #95a5a6;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            font-weight: bold;
        }
        
        #browseBtn:hover {
            background-color: #7f8c8d;
        }
        
        #scanBtn {
            background-color: #f39c12;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
        }
        
        #scanBtn:hover {
            background-color: #e67e22;
        }
        
        #scanBtn:disabled {
            background-color: #bdc3c7;
        }
        
        #importBtn {
            background-color: #27ae60;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
        }
        
        #importBtn:hover {
            background-color: #229954;
        }
        
        #importBtn:disabled {
            background-color: #bdc3c7;
        }
        
        #stopBtn {
            background-color: #e74c3c;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
        }
        
        #stopBtn:hover {
            background-color: #c0392b;
        }
        
        #stopBtn:disabled {
            background-color: #bdc3c7;
        }
        
        #matchesTree {
            background-color: #fafafa;
            border: 1px solid #ecf0f1;
            border-radius: 5px;
            alternate-background-color: #f8f9fa;
        }
        
        #progressBar {
            border: 2px solid #ecf0f1;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }
        
        #progressBar::chunk {
            background-color: #3498db;
            border-radius: 3px;
        }
        
        #resultsTable {
            background-color: #fafafa;
            border: 1px solid #ecf0f1;
            border-radius: 5px;
            gridline-color: #ecf0f1;
        }
        
        #resultsTable::item {
            padding: 8px;
        }
        
        #statsLabel, #progressLabel, #progressDetails,         #clearBtn {
            background-color: #95a5a6;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
        }
        
        #clearBtn:hover {
            background-color: #7f8c8d;
        }
        
        #parseBtn {
            background-color: #9b59b6;
            color: white;
            border: none;
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
        }
        
        #parseBtn:hover {
            background-color: #8e44ad;
        }
        """

        self.setStyleSheet(style)

    def browse_pdf_folder(self):
        """Browse for PDF folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select PDF Folder")
        if folder:
            self.pdf_folder = folder
            self.pdf_folder_edit.setText(folder)
            self.update_scan_button()

    def browse_content_folder(self):
        """Browse for content (XML/MD) folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Content Folder (XML/MD)")
        if folder:
            self.content_folder = folder
            self.content_folder_edit.setText(folder)
            self.update_scan_button()

    def update_scan_button(self):
        """Enable scan button if both folders are selected"""
        self.scan_btn.setEnabled(bool(self.pdf_folder and self.content_folder))

    def scan_folders(self):
        """Scan folders for matching documents"""
        if not self.pdf_folder or not self.content_folder:
            return

        self.statusBar().showMessage("Scanning folders...")

        try:
            matcher = DocumentMatcher(self.pdf_folder, self.content_folder)
            self.matches = matcher.find_matches()

            self.update_matches_display()
            self.update_import_button()

            ready_count = len([m for m in self.matches if m['status'] == 'ready'])
            self.statusBar().showMessage(f"Scan complete: {ready_count} documents ready for import")

        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Error scanning folders: {str(e)}")
            self.statusBar().showMessage("Scan failed")

    def update_matches_display(self):
        """Update matches tree widget"""
        self.matches_tree.clear()

        ready_count = 0
        missing_xml_count = 0

        for match in self.matches:
            item = QTreeWidgetItem()

            # Document name
            item.setText(0, match['base_name'])

            # Status
            if match['status'] == 'ready':
                item.setText(1, "Ready")
                item.setBackground(1, QColor("#d5f4e6"))  # Light green
                ready_count += 1

                # Files info
                files_info = "PDF + XML"
                if match['md_path']:
                    files_info += " + MD"
                item.setText(2, files_info)

            else:
                item.setText(1, "Missing XML")
                item.setBackground(1, QColor("#fadbd8"))  # Light red
                item.setText(2, "PDF only")
                missing_xml_count += 1

            self.matches_tree.addTopLevelItem(item)

        # Update stats
        total_count = len(self.matches)
        stats_text = f"Total: {total_count} | Ready: {ready_count} | Missing XML: {missing_xml_count}"
        self.matches_stats.setText(stats_text)

        # Auto-resize columns
        for i in range(3):
            self.matches_tree.resizeColumnToContents(i)

    def update_import_button(self):
        """Enable import button if there are ready matches"""
        ready_count = len([m for m in self.matches if m['status'] == 'ready'])
        self.import_btn.setEnabled(ready_count > 0)

    def check_database_status(self):
        """Check and update database connection status"""
        if not DATABASE_AVAILABLE:
            self.db_status_label.setText("Not Available")
            self.db_status_label.setStyleSheet("color: #e74c3c;")
            return False

        try:
            initialize_database_service()
            db_service = get_database_service()

            if db_service and db_service.is_ready():
                self.db_status_label.setText("Connected")
                self.db_status_label.setStyleSheet("color: #27ae60;")
                return True
            else:
                self.db_status_label.setText("Failed")
                self.db_status_label.setStyleSheet("color: #e74c3c;")
                return False

        except Exception as e:
            self.db_status_label.setText("Error")
            self.db_status_label.setStyleSheet("color: #e74c3c;")
            print(f"Database connection error: {e}")
            return False

    def start_import(self):
        """Start the import process"""
        if not self.check_database_status():
            QMessageBox.critical(
                self,
                "Database Error",
                "Database connection failed. Please check your database configuration."
            )
            return

        ready_matches = [m for m in self.matches if m['status'] == 'ready']
        if not ready_matches:
            QMessageBox.warning(self, "No Documents", "No documents ready for import")
            return

        # Confirm import
        reply = QMessageBox.question(
            self,
            "Confirm Import",
            f"Import {len(ready_matches)} documents to database?\n\n"
            "This operation cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Prepare UI for import
        self.import_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.scan_btn.setEnabled(False)

        # Clear previous results
        self.results_table.setRowCount(0)
        self.progress_bar.setValue(0)

        # Start import worker
        self.import_worker = ImportWorker(ready_matches)
        self.import_worker.progress_updated.connect(self.on_progress_updated)
        self.import_worker.item_completed.connect(self.on_item_completed)
        self.import_worker.import_completed.connect(self.on_import_completed)
        self.import_worker.start()

        self.statusBar().showMessage("Import started...")

    def stop_import(self):
        """Stop the import process"""
        if self.import_worker and self.import_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Stop Import",
                "Are you sure you want to stop the import process?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.import_worker.stop()
                self.statusBar().showMessage("Stopping import...")

    def on_progress_updated(self, progress: int, message: str, details: Dict[str, Any]):
        """Handle progress updates"""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

        if 'current' in details and 'total' in details:
            self.progress_details.setText(f"{details['current']} / {details['total']} documents")

        self.statusBar().showMessage(message)

    def on_item_completed(self, index: int, result: Dict[str, Any]):
        """Handle individual item completion"""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        # Document name
        self.results_table.setItem(row, 0, QTableWidgetItem(result['file']))

        # Status
        status_item = QTableWidgetItem("Success" if result['success'] else "Failed")
        if result['success']:
            status_item.setBackground(QColor("#d5f4e6"))  # Light green
        else:
            status_item.setBackground(QColor("#fadbd8"))  # Light red
        self.results_table.setItem(row, 1, status_item)

        # Document ID
        doc_id = result.get('document_id', '')
        self.results_table.setItem(row, 2, QTableWidgetItem(str(doc_id) if doc_id else ''))

        # Message
        message = result.get('message', result.get('error', ''))
        self.results_table.setItem(row, 3, QTableWidgetItem(message))

        # Scroll to latest
        self.results_table.scrollToBottom()

    def on_import_completed(self, result: Dict[str, Any]):
        """Handle import completion"""
        self.progress_bar.setValue(100)

        if result['success']:
            summary = result.get('summary', {})
            summary_text = (
                f"Import Complete!\n"
                f"Total: {summary.get('total', 0)} | "
                f"Successful: {summary.get('successful', 0)} | "
                f"Failed: {summary.get('failed', 0)}"
            )

            self.summary_label.setText(summary_text)
            self.progress_label.setText("Import completed successfully")
            self.statusBar().showMessage("Import completed")

            # Show completion message
            QMessageBox.information(
                self,
                "Import Complete",
                f"Import completed successfully!\n\n"
                f"Processed: {summary.get('total', 0)} documents\n"
                f"Successful: {summary.get('successful', 0)}\n"
                f"Failed: {summary.get('failed', 0)}"
            )

        else:
            self.summary_label.setText("Import failed")
            self.progress_label.setText("Import failed")
            self.statusBar().showMessage("Import failed")

            QMessageBox.critical(
                self,
                "Import Failed",
                f"Import process failed:\n{result['message']}"
            )

        # Re-enable controls
        self.import_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.scan_btn.setEnabled(True)
        self.update_import_button()

    # Single Import Methods
    def browse_single_pdf(self):
        """Browse for single PDF file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select PDF File", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.single_pdf_edit.setText(file_path)
            self.single_files['pdf'] = file_path
            self.update_single_import_button()

    def browse_single_xml(self):
        """Browse for single XML file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select XML File", "", "XML Files (*.xml)"
        )
        if file_path:
            self.single_xml_edit.setText(file_path)
            self.single_files['xml'] = file_path
            self.update_single_import_button()

    def browse_single_md(self):
        """Browse for single MD file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Markdown File", "", "Markdown Files (*.md)"
        )
        if file_path:
            self.single_md_edit.setText(file_path)
            self.single_files['md'] = file_path

    def clear_single_files(self):
        """Clear all single file selections"""
        self.single_pdf_edit.clear()
        self.single_xml_edit.clear()
        self.single_md_edit.clear()
        self.single_files = {'pdf': '', 'xml': '', 'md': ''}
        self.single_metadata = {}
        self.single_metadata_table.setRowCount(0)
        self.update_single_import_button()

    def update_single_import_button(self):
        """Enable single import button if PDF and XML are selected"""
        has_required = bool(self.single_files['pdf'] and self.single_files['xml'])
        self.single_import_btn.setEnabled(has_required)

    def parse_single_metadata(self):
        """Parse metadata from selected XML file"""
        if not self.single_files['xml']:
            QMessageBox.warning(self, "Warning", "Please select an XML file first")
            return

        self.single_metadata = MetadataExtractor.extract_from_xml(self.single_files['xml'])

        if not self.single_metadata:
            QMessageBox.critical(self, "Error", "Could not parse metadata from XML file")
            return

        self.update_single_metadata_table()
        QMessageBox.information(self, "Success", "Metadata parsed successfully")

    def update_single_metadata_table(self):
        """Update single metadata table"""
        self.single_metadata_table.setRowCount(len(self.single_metadata))

        for row, (key, value) in enumerate(self.single_metadata.items()):
            key_item = QTableWidgetItem(str(key))
            value_item = QTableWidgetItem(str(value))

            self.single_metadata_table.setItem(row, 0, key_item)
            self.single_metadata_table.setItem(row, 1, value_item)

        self.single_metadata_table.resizeColumnsToContents()

    def import_single_document(self):
        """Import single selected document"""
        if not self.single_files['pdf'] or not self.single_files['xml']:
            QMessageBox.warning(self, "Warning", "PDF and XML files are required")
            return

        if not self.check_database_status():
            QMessageBox.critical(
                self,
                "Database Error",
                "Database connection failed. Please check your database configuration."
            )
            return

        # Parse metadata if not already done
        if not self.single_metadata:
            self.single_metadata = MetadataExtractor.extract_from_xml(self.single_files['xml'])
            if not self.single_metadata:
                QMessageBox.critical(self, "Error", "Could not parse metadata from XML")
                return

        # Confirm import
        reply = QMessageBox.question(
            self,
            "Confirm Import",
            f"Import document to database?\n\nTitle: {self.single_metadata.get('title', 'Unknown')}\n\n"
            "This operation cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Create match object for single import
        match = {
            'pdf_path': self.single_files['pdf'],
            'xml_path': self.single_files['xml'],
            'md_path': self.single_files['md'] if self.single_files['md'] else None,
            'base_name': Path(self.single_files['pdf']).stem,
            'status': 'ready'
        }

        # UI hazırlığı
        self.single_import_btn.setEnabled(False)
        self.statusBar().showMessage("Single import started...")
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Processing: {match['base_name']}")
        self.progress_details.setText("1 / 1 documents")

        try:
            # Initialize database
            initialize_database_service()
            db_service = get_database_service()

            if not db_service or not db_service.is_ready():
                QMessageBox.critical(self, "Error", "Database service not available")
                self.single_import_btn.setEnabled(True)
                return

            # Thread referansını KORU: yerel değişken yerine öznitelik
            self.import_worker = ImportWorker([match])

            # İlerleme ve tamamlanma sinyallerini mevcut UI’ye bağla
            self.import_worker.progress_updated.connect(self.on_progress_updated)
            self.import_worker.item_completed.connect(self.on_item_completed)

            def on_single_import_complete(result):
                # Thread bitti; butonları aç
                self.single_import_btn.setEnabled(True)
                self.statusBar().showMessage("Single import finished")

                if result['success'] and result['results']:
                    doc_result = result['results'][0]
                    if doc_result['success']:
                        QMessageBox.information(
                            self,
                            "Import Successful",
                            (
                                f"Document imported successfully!\n\n"
                                f"Document ID: {doc_result.get('document_id', 'Unknown')}\n"
                                f"Title: {self.single_metadata.get('title', 'Unknown')}"
                            )
                        )
                        # Başarılıysa seçimleri temizle
                        self.clear_single_files()
                    else:
                        QMessageBox.critical(
                            self,
                            "Import Failed",
                            f"Import failed: {doc_result.get('error', 'Unknown error')}"
                        )
                else:
                    QMessageBox.critical(
                        self,
                        "Import Failed",
                        f"Import failed: {result.get('message', 'Unknown error')}"
                    )

                # Thread referansını bırak (iş bittiğinde)
                self.import_worker = None

            self.import_worker.import_completed.connect(on_single_import_complete)

            # Thread’i başlat
            self.import_worker.start()

        except Exception as e:
            self.single_import_btn.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Import error: {str(e)}")

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("SuryaOCR Advanced Bulk Import")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("SuryaOCR")

    # Set application icon (if available)
    try:
        app.setWindowIcon(QIcon("icon.png"))
    except:
        pass

    # Create and show main window
    window = ModernBulkImportTool()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()