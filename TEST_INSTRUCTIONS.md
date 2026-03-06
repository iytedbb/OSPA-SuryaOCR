# OSPA SuryaOCR Testing Instructions

This document provides guidelines for testing and verifying the SuryaOCR framework components.

## 1. Environment Verification

Check if all AI models are correctly loaded and GPU is accessible.

```bash
# Run the verification script
python scripts/verify_gpu.py
```

## 2. API Endpoint Testing

### OCR Processing
You can test the main processing endpoint using `curl`:

```bash
curl -X POST http://localhost:5000/api/process \
     -H "Content-Type: application/json" \
     -d '{"file_path": "data/veriler/pdf/test_sample.pdf", "process_mode": "ocr"}'
```

### Layout Detection
```bash
curl -X POST http://localhost:5000/api/layout-detection \
     -H "Content-Type: application/json" \
     -d '{"file_path": "data/veriler/pdf/test_sample.pdf", "page_number": 1}'
```

## 3. Web Interface Testing

1. **Dashboard**: Navigate to `http://localhost:5000/admin` and verify that system statistics (CPU/VRAM) are updating.
2. **Uploading**: Upload a multi-page PDF and verify that "Page Splitting" correctly handles dual-page scans.
3. **Execution**: Start an OCR job and ensure the progress bar reaches 100% without errors.
4. **Export**: Verify that Markdown and XML files are correctly generated in the `data/veriler/outputs` directory.

## 4. Performance Benchmarking

To test the throughput of the system:

```bash
python scripts/benchmark_ocr.py --input test_folder/ --batch_size 16
```

## 5. Troubleshooting

- **Memory Error**: If you encounter `OutOfMemoryError`, reduce the `optimal_batch_size` in `config.py`.
- **Database Connection**: Ensure the `ocr_db` container is running using `docker ps`.
- **ImportError**: Verify that you have activated the virtual environment or are running within the Docker container.
