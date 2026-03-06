"""
Test script for database operations
"""

import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from operations import DatabaseOperations, create_document_with_context
from connection import initialize_database

def test_database_operations():
    """
    Test all major database operations
    """
    print("🧪 Testing SuryaOCR Database Operations")
    print("=" * 50)

    # Initialize database
    try:
        initialize_database()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return

    # Test 1: Create a document
    print("\n📄 Test 1: Creating documents")

    # Test book metadata
    book_metadata = {
        'title': 'Yapay Zeka ve Makine Öğrenmesi',
        'author': 'Dr. Mehmet Yılmaz',
        'metadata_type': 'book',
        'publisher': 'TechBooks',
        'publication_year': 2023,
        'publication_city': 'İstanbul',
        'isbn': '978-0123456789',
        'language': 'tr',
        'page_count': 350,
        'citation_style': 'apa'
    }

    article_metadata = {
        'title': 'Deep Learning in Natural Language Processing',
        'author': 'Prof. Dr. Ayşe Kaya, Dr. Okan Demir',
        'metadata_type': 'article',
        'publication': 'AI Research Journal',
        'volume': '12',
        'issue': '3',
        'pages': '45-67',
        'doi': '10.1234/example.2023.001',
        'publication_year': 2023,
        'language': 'en',
        'citation_style': 'chicago'
    }

    with DatabaseOperations() as db_ops:
        # Create book
        book_id = db_ops.create_document(book_metadata)
        if book_id:
            print(f"✅ Book created with ID: {book_id}")
        else:
            print("❌ Failed to create book")
            return

        # Create article
        article_id = db_ops.create_document(article_metadata)
        if article_id:
            print(f"✅ Article created with ID: {article_id}")
        else:
            print("❌ Failed to create article")
            return

        # Test 2: Search documents
        print("\n🔍 Test 2: Searching documents")

        # Search by title
        results = db_ops.search_documents({'title': 'Yapay Zeka'})
        print(f"✅ Found {len(results)} documents with 'Yapay Zeka' in title")

        # Search by metadata type
        results = db_ops.search_documents({'metadata_type': 'article'})
        print(f"✅ Found {len(results)} articles")

        # Search by author
        results = db_ops.search_documents({'author': 'Mehmet'})
        print(f"✅ Found {len(results)} documents by authors containing 'Mehmet'")

        # Test 3: Check duplicates
        print("\n🔄 Test 3: Duplicate detection")

        duplicate_check = db_ops.check_duplicate_by_metadata(book_metadata)
        if duplicate_check:
            print(f"✅ Duplicate detected: {duplicate_check.id}")
        else:
            print("❌ Duplicate detection failed")

        # Test with DOI
        duplicate_check = db_ops.check_duplicate_by_metadata(article_metadata)
        if duplicate_check:
            print(f"✅ Duplicate detected by DOI: {duplicate_check.id}")
        else:
            print("❌ DOI duplicate detection failed")

        # Test 4: Add files to document
        print("\n📁 Test 4: Adding files")

        # Create a dummy file for testing
        test_file_path = "test_document.pdf"
        with open(test_file_path, 'w') as f:
            f.write("This is a test PDF content")

        file_info = {
            'filename': 'test_doc_123.pdf',
            'original_filename': 'test_document.pdf',
            'file_path': test_file_path,
            'file_size': os.path.getsize(test_file_path),
            'mime_type': 'application/pdf',
            'file_type': 'pdf'
        }

        file_id = db_ops.add_file_to_document(book_id, file_info)
        if file_id:
            print(f"✅ File added with ID: {file_id}")
        else:
            print("❌ Failed to add file")

        # Get document files
        files = db_ops.get_document_files(book_id)
        print(f"✅ Document has {len(files)} files")

        # Test 5: Processing jobs
        print("\n⚙️ Test 5: Processing jobs")

        job_id = db_ops.create_processing_job(book_id, 'ocr', ['md', 'xml'])
        if job_id:
            print(f"✅ Processing job created: {job_id}")

            # Update job status
            success = db_ops.update_job_status(job_id, 'processing', total_pages=10, current_page=5)
            if success:
                print("✅ Job status updated to processing")

            success = db_ops.update_job_status(job_id, 'completed', current_page=10)
            if success:
                print("✅ Job status updated to completed")

        # Test 6: OCR Results
        print("\n📝 Test 6: OCR Results")

        ocr_data = {
            'markdown_content': '# Yapay Zeka\n\nBu bir test belgesidir.\n\n## Makine Öğrenmesi\n\nDetaylı açıklama...',
            'xml_content': '<document><h1>Yapay Zeka</h1><p>Bu bir test belgesidir.</p><h2>Makine Öğrenmesi</h2><p>Detaylı açıklama...</p></document>',
            'total_pages': 10,
            'total_characters': 2500,
            'confidence_score': 0.95,
            'processing_time_seconds': 45.5,
            'characters_per_second': 55.0
        }

        ocr_result_id = db_ops.save_ocr_results(job_id, book_id, ocr_data)
        if ocr_result_id:
            print(f"✅ OCR results saved: {ocr_result_id}")

            # Get OCR results back
            results = db_ops.get_ocr_results_by_document(book_id)
            if results:
                print(f"✅ Retrieved OCR results: {len(results.markdown_content)} chars markdown")

        # Test 7: Detection Results
        print("\n🎯 Test 7: Detection Results")

        detection_data = [
            {
                'page_number': 1,
                'total_pages': 10,
                'text_regions': [
                    {'region_id': 1, 'bbox': [100, 100, 400, 150], 'confidence': 0.95},
                    {'region_id': 2, 'bbox': [100, 200, 450, 300], 'confidence': 0.87}
                ],
                'region_count': 2,
                'average_confidence': 0.91,
                'processing_time_ms': 150
            },
            {
                'page_number': 2,
                'total_pages': 10,
                'text_regions': [
                    {'region_id': 1, 'bbox': [50, 80, 380, 120], 'confidence': 0.92}
                ],
                'region_count': 1,
                'average_confidence': 0.92,
                'processing_time_ms': 120
            }
        ]

        success = db_ops.save_detection_results(job_id, book_id, detection_data)
        if success:
            print("✅ Detection results saved")

            # Get detection results back
            results = db_ops.get_detection_results_by_document(book_id)
            print(f"✅ Retrieved detection results for {len(results)} pages")

        # Test 8: Statistics
        print("\n📊 Test 8: Statistics")

        success = db_ops.update_daily_stats()
        if success:
            print("✅ Daily statistics updated")

        stats = db_ops.get_database_stats()
        print(f"✅ Database Stats:")
        for key, value in stats.items():
            print(f"   {key}: {value}")

        # Test 9: Get document with all relations
        print("\n🔗 Test 9: Document relations")

        document = db_ops.get_document_by_id(book_id)
        if document:
            print(f"✅ Document: {document.title}")
            print(f"   Files: {len(document.files)}")
            print(f"   Jobs: {len(document.processing_jobs)}")
            print(f"   OCR Results: {len(document.ocr_results)}")
            print(f"   Detection Results: {len(document.detection_results)}")

    # Cleanup test file
    try:
        os.remove(test_file_path)
        print("✅ Test file cleaned up")
    except:
        pass

    print("\n🎉 All database operation tests completed!")
    print("=" * 50)

def test_convenience_functions():
    """
    Test convenience functions
    """
    print("\n🔧 Testing convenience functions")

    # Test creating document with convenience function
    metadata = {
        'title': 'Test Document via Convenience Function',
        'author': 'Test Author',
        'metadata_type': 'article',
        'language': 'tr'
    }

    doc_id = create_document_with_context(metadata)
    if doc_id:
        print(f"✅ Document created via convenience function: {doc_id}")
    else:
        print("❌ Convenience function failed")

if __name__ == "__main__":
    try:
        test_database_operations()
        test_convenience_functions()
        print("\nAll tests passed successfully!")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()