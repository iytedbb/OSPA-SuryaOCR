# OSPA SuryaOCR - Advanced Document Processing Framework
by The OSPA Project

![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![PyTorch](https://img.shields.io/badge/pytorch-2.0+-orange)
![TUBITAK](https://img.shields.io/badge/TUBITAK-323K372-red)

A comprehensive OCR and document analysis framework designed for high-accuracy text extraction from historical documents, newspapers, and academic texts using state-of-the-art AI models including Surya and DocLayout-YOLO.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Models](#models)
- [Quick Start](#quick-start)
- [Admin Dashboard](#admin-dashboard)
- [Project Structure](#project-structure)
- [Acknowledgments](#acknowledgments)
- [License](#license)
- [Support](#support)

## Overview

OSPA SuryaOCR is an **End-to-End Orchestrated Pipeline** designed for the complete digitization of complex historical documents. Rather than providing standalone models, this framework provides a sophisticated orchestration of multiple state-of-the-art AI engines specialized for:

1. **Preprocessing & Recovery**: Automated dewarping ([UVDoc](https://github.com/tanguymagne/UVDoc)), deskewing, and binarization to handle curved book pages and low-quality scans.
2. **Structural Intelligence**: Using **[Surya Layout](https://github.com/datalab-to/surya)** and **[DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)** to identify page types (Newspapers, Books, Documents) and segment them into logical regions.
3. **Advanced OCR Orchestration**: Leveraging the **Surya 0.17 engine** for high-precision multilingual text recognition, applied specifically to the segmented columns and lines.
4. **Structured Output Generation**: Converting raw visual data into structured **Markdown** and **XML** formats, preserving headings, **paragraphs**, and hierarchical metadata.

> *"We don't just scan archives; we transform 'Visual Data' into 'Machine-Readable Data'."* — **The OSPA Vision**

### From "Archive Digitization" to "Document Digitization"

As outlined in our project philosophy, there is a critical distinction:

- **Archive Digitization (Visual)**: Scanning a physical document into PDF/JPG. To a machine, this is still just pixels.
- **Document Digitization (Data)**: Converting that image into character-level data. Our pipeline bridges this gap, turning "Visuals" into "Queryable Data Objects".

While SuryaOCR provides powerful base models, our pipeline significantly boosts the final quality by solving real-world digitization challenges:

- **Layout-Aware OCR**: By using **Surya Layout Engine** to segment columns *before* OCR, we prevent the "text bleeding" common in multi-column newspaper scans, ensuring a natural reading order.
- **Warp-Resistant Accuracy**: Historical books often have curved pages. Our **[UVDoc](https://github.com/tanguymagne/UVDoc)** integration flattens these surfaces, increasing character recognition accuracy by up to 30% compared to raw scans.

## The Orchestration Journey: Step-by-Step

Following the technical workflow outlined in our documentation, the pipeline follows five critical stages to ensure data integrity:

### 1. Preprocessing & Page Topology (PyReform & UVDoc)

The journey begins by preparing the document. We tackle common historical challenges: **aged pages**, **faded ink**, and **curved scans**.

- **Page Structure Analysis**: The system first determines whether the input is a single page, a double page, or rotated. Using intelligent detection, we allow for automated splitting of double-page scans.
- **Image Enhancement**: **[py-reform](https://pypi.org/project/py-reform/)** and **OpenCV** (Bilateral Filter, CLAHE) are used to dewarp curved pages and enhance contrast, making the text clearer for the AI.

### 2. Layout Analysis (Selectable Engines)

Before reading a single letter, the system understands the page arrangement. The pipeline offers two high-performance options, with **[Surya 0.17 Layout Engine](https://github.com/datalab-to/surya)** being the default preferred choice for historical text precision. Users can manually switch to **[DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)**, which remains highly effective for complex, multi-column newspaper structures.

### 3. Text Detection (DetectionPredictor)

Once the layout is understood, the **Surya Detection** engine identifies text regions at the pixel level. It draws bounding boxes around every line, ensuring no text is missed, even in the margins.

### 4. Character Recognition (RecognitionPredictor)

This is where the core processing happens. Using the **Vision Transformer (ViT)** architecture, the system reads text contextually. It solves common historical "bleeds" (like 'h' vs 'n' confusion) by analyzing the visual pattern of the entire word.

### 5. Final Formatting (Structured Export)

The processed data is exported into dual formats to serve both quantitative and qualitative research needs.

#### Output Example: Markdown (MD)

*Designed for "Readable and Verifiable Representation".*
Clear, tag-free text optimized for human reading and quick control.

```markdown
## Page 117
### House of Lords
**4 July 1881**
Earl de la-Warr: - Regarding the trial of Midhat Pasha taking place in Istanbul...
Lord Granville: - Your Excellency, the whole of Europe...
```

#### Output Example: XML

*Designed for "Structural and Analytic Representation".*
Preserves the hierarchy (Page > Paragraph > Sentence > Word) and location data for machine analysis.

```xml
<page number="117" paragraph_count="8">
  <paragraph number="1" type="heading">House of Lords</paragraph>
  <paragraph number="2" type="paragraph">4 July 1881</paragraph>
  <paragraph number="3" type="paragraph">Earl de la-Warr: - Regarding the trial...</paragraph>
  <paragraph number="4" type="paragraph">Lord Granville: - Your Excellency...</paragraph>
</page>
```

## Performance Benchmarks

In extensive testing with the OSPA historical document collection (1900-1940 period), this framework consistently outperformed both legacy and modern alternatives:

| OCR System | Modern Documents | Historical Documents | Processing Time | GPU Usage | Cost |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **SuryaOCR (Proposed)** | **90-95%** | **80-88%** | **5-10s** | **3-5 GB** | **Free** |
| Tesseract + Hybrid | 85-90% | 25-45% | 40-60s | Low | Free |
| EasyOCR | 78-85% | 5-25% | 15-25s | 6-8 GB | Free |
| Nanonets API | 90%+ | 85-90% | 8-12s | Cloud | Paid |
| Ollama / LLM OCR | 70% | 55-60% | 45-60s | 90%+ | Free |

### Why It Works

- **Tesseract/EasyOCR Issues**: Failed on **historical fonts** ('h' vs 'n' confusion) and complex layouts.
- **LLM Issues**: While promising, LLMs suffered from the **"Loop Problem"** (hallucinating repetitions in long texts) and lacked specific historical context.
- **SuryaOCR Advantage**: Uses **Vision Transformers (ViT)** to perceive words as complete visual patterns within a context, dramatically reducing "character bleeding" in faded historical ink.

## Core Philosophy: From Pixels to Data Objects

Our approach goes beyond simple optical character recognition. As defined in our vision:

- **The Digitization Gap**: Computer systems initially perceive a scanned archive only as a collection of pixels. Our pipeline bridges the gap between a "digital image" and a "digital document".
- **Structural Integrity**: By using **XML for machines** and **Markdown for researchers**, we ensure that the document's layout, hierarchy, and metadata are preserved as a queryable data object.
- **Data over Image**: We transform historical noise (faded ink, yellowed paper) into a verifiable and analyzable digital asset, opening the doors for advanced NLP, socio-political network analysis, and text mining.

> *"We are not just moving documents to a digital environment; we are making them machine-readable, discoverable, and reinterpretable for the modern scholar."*

## Features

- **Surya v0.17 Integration**: Uses the latest Foundation, Detection, and Recognition predictors.
- **DocLayout-YOLO**: Advanced layout detection for complex document structures.
- **Dockerized Environment**: One-command setup with PostgreSQL and model preloading.
- **Dual Database Support**: Automatic fallback to SQLite for local development, PostgreSQL for production.
- **Modern Web UI**: React-based frontend with real-time progress tracking via Server-Sent Events (SSE).
- **Extensive Admin Panel**: Manage books, track OCR progress, and export results in multiple formats.
- **Hardware Optimized**: Fully supports CUDA (RTX 5000 Ada/Blackwell) with high-performance memory management.

## Installation

### Requirements

- Python 3.11+
- Docker & Docker Compose (optional but recommended)
- NVIDIA GPU with 8GB+ VRAM (recommended for OCR performance)

### Option 1: Docker (Recommended)

The easiest way to get started. It handles the database, Python environment, and models automatically.

```bash
# Clone the repository
git clone https://github.com/iytedbb/OSPA-SuryaOCR.git
cd OSPA-SuryaOCR

# Start the application
docker-compose up --build
```

Wait for the "SuryaOCR Processor READY!" message. The web interface will be available at `http://localhost:5000`.

### Option 2: Local Installation (uv)

```bash
# Install uv if not already installed
# See: https://docs.astral.sh/uv/getting-started/installation/

# Clone and enter the project
git clone https://github.com/iytedbb/OSPA-SuryaOCR.git
cd OSPA-SuryaOCR

# Sync dependencies
uv sync

# Run the application
uv run python run.py
```

This will use SQLite by default and require manual model downloads upon first run.

## Models

SuryaOCR integrates several state-of-the-art AI models to handle different stages of the document digitization pipeline:

| Model | Task | Source |
|-------|------|--------|
| **Surya Detection** | Text line & column detection | [datalab-to/surya](https://github.com/datalab-to/surya) |
| **Surya Recognition** | Multilingual Text OCR | [datalab-to/surya](https://github.com/datalab-to/surya) |
| **Surya Layout** | Structural analysis (Headings, Tables) | [datalab-to/surya](https://github.com/datalab-to/surya) |
| **DocLayout-YOLO** | Page type & segment detection | [opendatalab/DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO) |
| **UVDoc** | Document dewarping & straightening | [tanguymagne/UVDoc](https://github.com/tanguymagne/UVDoc) via [py-reform](https://pypi.org/project/py-reform/) |
| **Deskew** | Automated skew correction | [deskew (PyPI)](https://pypi.org/project/deskew/) |

### Preprocessing Pipeline

The preprocessing module uses **[UVDoc](https://github.com/tanguymagne/UVDoc)** for complex document dewarping, ensuring that curved book pages are flattened before OCR. **[DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)** acts as the primary classifier to determine if a document is a standard book, a multi-column newspaper, or a biography card, enabling specialized processing logic for each type.

## Quick Start

1. **Access UI**: Open `http://localhost:5000` in your browser.
2. **Upload**: Drag and drop a PDF file to the upload area.
3. **Configure**: Select "Newspaper Mode" for multi-column layouts or "Standard OCR" for books.
4. **Process**: Click "Start Processing" and monitor the real-time progress bar.
5. **Download**: Once finished, download your results as **Markdown**, **XML**, or a **ZIP** archive.

## Admin Dashboard

Manage your entire digital library at `http://localhost:5000/admin`.

- **Statistics**: View processing counts, VRAM usage, and throughput.
- **Records**: Search, edit metadata (Author, Year, etc.), or delete existing records.
- **Verification**: Preview OCR output side-by-side with original images.

## Project Structure

```
ospa_suryaocr_git/
├── app/                            # Backend (Flask application)
│   ├── database/                   # Database layer
│   │   ├── fonts/                  # Font files for PDF export
│   │   ├── models/                 # DocLayout-YOLO weights (.pt)
│   │   ├── static/                 # Admin panel static assets
│   │   ├── templates/              # Admin panel HTML templates
│   │   ├── veriler/                # Data storage (images, PDFs, preprocessed)
│   │   ├── connection.py           # DB connection handler
│   │   ├── database_service.py     # Core database service
│   │   ├── models.py               # ORM models
│   │   ├── operations.py           # CRUD operations
│   │   └── name_variants.py        # Name normalization logic
│   ├── models/                     # Application-level model definitions
│   │   └── __init__.py             # ORM Model Definitions
│   ├── modules/
│   │   ├── admin/                  # Admin panel routes
│   │   ├── common/                 # Shared utilities
│   │   └── ocr/                    # Core OCR logic
│   │       ├── SuryaOCR_backend.py         # Surya engine integration
│   │       ├── GazeteOCRProcessor.py       # Newspaper-specific OCR
│   │       ├── on_isleme_main.py           # Preprocessing pipeline
│   │       ├── DocumentMetadata.py         # Metadata extraction
│   │       ├── ProcessingProgressTracker.py # Real-time progress (SSE)
│   │       ├── database_integration.py     # OCR-to-DB bridge
│   │       └── routes.py                   # OCR API endpoints
│   ├── static/                     # Frontend assets & example images
│   │   ├── dist/                   # Compiled React build
│   │   ├── admin/                  # Admin panel assets
│   │   ├── comparison/             # Before/after comparison images
│   │   └── ornekler/               # Sample document images
│   └── templates/                  # HTML templates (landing, info pages)
├── frontend/                       # React frontend source
│   ├── src/
│   │   ├── components/             # UI components
│   │   │   ├── FileUploader.jsx
│   │   │   ├── LayoutViewer.jsx
│   │   │   ├── MetadataForm.jsx
│   │   │   ├── ProcessingView.jsx
│   │   │   ├── ResultsView.jsx
│   │   │   ├── SettingsPanel.jsx
│   │   │   └── StepProgressBar.jsx
│   │   └── hooks/
│   │       └── useOCR.js           # OCR state management hook
│   ├── package.json
│   └── vite.config.js
├── scripts/                        # Utility & migration scripts
│   ├── migration.py
│   └── ocr_migration.py
├── .dockerignore
├── .gitignore
├── .python-version
├── CITATION.bib                    # Citation information (BibTeX)
├── config.py                       # Application & model configurations
├── Dockerfile
├── docker-compose.yml              # Service orchestration (App + Postgres)
├── main.py                         # Alternative entry point
├── preload_models.py               # Script to pre-cache AI models
├── pyproject.toml                  # Project metadata and dependencies
├── README.md
├── requirements.txt                # Legacy/Compatibility dependency list
├── run.py                          # Main entry point
├── setup.py                        # Package installation script
├── TEST_INSTRUCTIONS.md            # Testing & verification guide
└── uv.lock                         # Deterministic dependency lock file
```

## Acknowledgments

This work is supported by:

**TUBITAK (The Scientific and Technological Research Council of Turkey)**
Project No: 323K372

### Contributors

- Dr. Mustafa İLTER - Izmir Institute of Technology 
- Emre ONUÇ - Pamukkale University

## Citation

If you use this framework in your research, please cite:

```bibtex
@software{OSPA-SuryaOCR-2026,
  title     = {OSPA SuryaOCR - Advanced Document Processing Framework},
  author    = {İlter, Mustafa and Onuç, Emre},
  year      = {2026},
  publisher = {GitHub},
  url       = {https://github.com/iytedbb/OSPA-SuryaOCR},
  note      = {Supported by TUBITAK Project No: 323K372. Built on Surya OCR 0.17 and DocLayout-YOLO},
  license   = {CC-BY-NC-4.0}
}
```

## License

This project is licensed under **CC BY-NC 4.0** (Creative Commons Attribution-NonCommercial 4.0 International).

## Support

For issues, bug reports, or feature requests:

- **Email**: mustafailter@iyte.edu.tr
- **GitHub**: [github.com/iytedbb/OSPA-SuryaOCR](https://github.com/iytedbb/OSPA-SuryaOCR)
- **Hugging Face Models**: [huggingface.co/dbbiyte](https://huggingface.co/dbbiyte)
