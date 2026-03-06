/**
 * Preprocessing Integration Module for SuryaOCR
 * This module adds preprocessing workflow to the existing OCR interface
 */

(function () {
    'use strict';

    // Configuration
    const PREPROCESSING_API_URL = '/preprocessing/api';
    const OCR_API_URL = '';

    // State
    let preprocessingEnabled = false;
    let currentFileForPreprocessing = null;
    let preprocessingJobId = null;

    /**
     * Initialize preprocessing integration
     */
    function initPreprocessingIntegration() {
        // Add preprocessing choice modal HTML
        addPreprocessingModal();

        // Override file upload handler
        interceptFileUpload();

        // Add event listeners
        setupEventListeners();

        console.log('✅ Preprocessing integration initialized');
    }

    /**
     * Add preprocessing choice modal to the DOM
     */
    function addPreprocessingModal() {
        const modalHTML = `
            <div id="preprocessingChoiceModal" class="preprocessing-modal" style="display: none;">
                <div class="preprocessing-modal-overlay"></div>
                <div class="preprocessing-modal-content">
                    <div class="preprocessing-modal-header">
                        <h2>İşleme Yöntemi Seçin</h2>
                        <p>Belgenizi nasıl işlemek istersiniz?</p>
                    </div>
                    
                    <div class="preprocessing-modal-body">
                        <div class="preprocessing-options">
                            <div class="preprocessing-option" id="directOCROption">
                                <div class="option-icon">
                                    <i class="fas fa-forward"></i>
                                </div>
                                <h3>Direkt OCR</h3>
                                <p>Belgeyi olduğu gibi OCR işlemine sok</p>
                                <ul>
                                    <li>✓ Hızlı işlem</li>
                                    <li>✓ Kaliteli belgeler için ideal</li>
                                </ul>
                                <button class="btn-option" onclick="PreprocessingIntegration.selectDirectOCR()">
                                    Direkt OCR ile Devam
                                </button>
                            </div>
                            
                            <div class="preprocessing-option recommended" id="preprocessingOption">
                                <div class="option-badge">Önerilen</div>
                                <div class="option-icon">
                                    <i class="fas fa-magic"></i>
                                </div>
                                <h3>Ön İşleme ile OCR</h3>
                                <p>Görüntü kalitesini iyileştir, sonra OCR uygula</p>
                                <ul>
                                    <li>✓ Daha yüksek doğruluk</li>
                                    <li>✓ Otomatik düzeltmeler</li>
                                    <li>✓ Gürültü temizleme</li>
                                </ul>
                                <button class="btn-option btn-recommended" onclick="PreprocessingIntegration.selectPreprocessing()">
                                    Ön İşleme ile İlerle
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="preprocessing-modal-footer">
                        <button class="btn-cancel" onclick="PreprocessingIntegration.cancelPreprocessing()">
                            İptal
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Add modal styles
        const modalStyles = `
            <style>
                .preprocessing-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    z-index: 10000;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }

                .preprocessing-modal-overlay {
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.8);
                    backdrop-filter: blur(5px);
                }

                .preprocessing-modal-content {
                    position: relative;
                    background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                    border: 1px solid rgba(220, 20, 60, 0.3);
                    border-radius: 20px;
                    padding: 2rem;
                    max-width: 800px;
                    width: 90%;
                    max-height: 90vh;
                    overflow-y: auto;
                    box-shadow: 0 20px 60px rgba(220, 20, 60, 0.3);
                    animation: modalSlideIn 0.3s ease-out;
                }

                @keyframes modalSlideIn {
                    from {
                        opacity: 0;
                        transform: translateY(-20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }

                .preprocessing-modal-header {
                    text-align: center;
                    margin-bottom: 2rem;
                }

                .preprocessing-modal-header h2 {
                    font-family: 'Space Grotesk', sans-serif;
                    font-size: 2rem;
                    color: #ffffff;
                    margin-bottom: 0.5rem;
                }

                .preprocessing-modal-header p {
                    color: #9CA3AF;
                    font-size: 1.1rem;
                }

                .preprocessing-options {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 2rem;
                    margin-bottom: 2rem;
                }

                .preprocessing-option {
                    background: rgba(255, 255, 255, 0.03);
                    border: 2px solid rgba(255, 255, 255, 0.1);
                    border-radius: 15px;
                    padding: 2rem;
                    text-align: center;
                    position: relative;
                    transition: all 0.3s ease;
                }

                .preprocessing-option:hover {
                    background: rgba(255, 255, 255, 0.05);
                    border-color: rgba(220, 20, 60, 0.5);
                    transform: translateY(-5px);
                    box-shadow: 0 10px 30px rgba(220, 20, 60, 0.2);
                }

                .preprocessing-option.recommended {
                    border-color: rgba(220, 20, 60, 0.5);
                    background: rgba(220, 20, 60, 0.05);
                }

                .option-badge {
                    position: absolute;
                    top: -10px;
                    right: 20px;
                    background: linear-gradient(135deg, #DC143C, #B91C1C);
                    color: white;
                    padding: 0.25rem 1rem;
                    border-radius: 20px;
                    font-size: 0.85rem;
                    font-weight: 600;
                    box-shadow: 0 4px 10px rgba(220, 20, 60, 0.3);
                }

                .option-icon {
                    width: 80px;
                    height: 80px;
                    background: rgba(220, 20, 60, 0.1);
                    border: 2px solid rgba(220, 20, 60, 0.3);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 1.5rem;
                    font-size: 2rem;
                    color: #DC143C;
                }

                .preprocessing-option h3 {
                    font-family: 'Space Grotesk', sans-serif;
                    font-size: 1.5rem;
                    color: #ffffff;
                    margin-bottom: 0.5rem;
                }

                .preprocessing-option p {
                    color: #9CA3AF;
                    margin-bottom: 1rem;
                    line-height: 1.5;
                }

                .preprocessing-option ul {
                    list-style: none;
                    padding: 0;
                    margin: 1rem 0;
                    text-align: left;
                }

                .preprocessing-option li {
                    color: #D1D5DB;
                    padding: 0.25rem 0;
                    font-size: 0.95rem;
                }

                .btn-option {
                    width: 100%;
                    padding: 1rem;
                    background: rgba(255, 255, 255, 0.1);
                    color: white;
                    border: 2px solid rgba(255, 255, 255, 0.2);
                    border-radius: 10px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    margin-top: 1rem;
                }

                .btn-option:hover {
                    background: rgba(255, 255, 255, 0.15);
                    border-color: rgba(255, 255, 255, 0.3);
                    transform: translateY(-2px);
                }

                .btn-recommended {
                    background: linear-gradient(135deg, #DC143C, #B91C1C);
                    border-color: #DC143C;
                }

                .btn-recommended:hover {
                    background: linear-gradient(135deg, #EF4444, #DC143C);
                    box-shadow: 0 4px 15px rgba(220, 20, 60, 0.4);
                }

                .preprocessing-modal-footer {
                    text-align: center;
                    padding-top: 1rem;
                    border-top: 1px solid rgba(255, 255, 255, 0.1);
                }

                .btn-cancel {
                    padding: 0.75rem 2rem;
                    background: transparent;
                    color: #9CA3AF;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 8px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }

                .btn-cancel:hover {
                    color: white;
                    border-color: rgba(255, 255, 255, 0.3);
                }

                /* Scanning animation overlay */
                .scanning-overlay {
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    pointer-events: none;
                    overflow: hidden;
                    border-radius: 10px;
                }

                .scan-line {
                    position: absolute;
                    width: 100%;
                    height: 3px;
                    background: linear-gradient(90deg, 
                        transparent 0%,
                        rgba(220, 20, 60, 0.3) 10%,
                        rgba(220, 20, 60, 0.8) 50%,
                        rgba(220, 20, 60, 0.3) 90%,
                        transparent 100%);
                    box-shadow: 
                        0 0 20px rgba(220, 20, 60, 0.8),
                        0 0 40px rgba(220, 20, 60, 0.4);
                    animation: scanAnimation 3s linear infinite;
                }

                @keyframes scanAnimation {
                    0% {
                        top: -3px;
                    }
                    100% {
                        top: 100%;
                    }
                }

                .scan-glow {
                    position: absolute;
                    width: 100%;
                    height: 50px;
                    background: radial-gradient(ellipse at center,
                        rgba(220, 20, 60, 0.2) 0%,
                        transparent 70%);
                    animation: scanAnimation 3s linear infinite;
                }
            </style>
        `;

        // Add to page
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        document.head.insertAdjacentHTML('beforeend', modalStyles);
    }

    /**
     * Intercept file upload to show preprocessing choice
     */
    function interceptFileUpload() {
        // Wait for React component to be ready
        setTimeout(() => {
            // Find the original file input handler
            const originalHandleFileSelect = window.handleFileSelect;

            if (originalHandleFileSelect) {
                // Override the file select handler
                window.handleFileSelect = function (files) {
                    if (files && files.length > 0) {
                        currentFileForPreprocessing = files[0];
                        showPreprocessingChoice();
                    }
                };
            }

            // Also intercept drop zone
            const dropZone = document.querySelector('.upload-area');
            if (dropZone) {
                dropZone.addEventListener('drop', (e) => {
                    e.preventDefault();
                    e.stopPropagation();

                    const files = e.dataTransfer.files;
                    if (files && files.length > 0) {
                        currentFileForPreprocessing = files[0];
                        showPreprocessingChoice();
                    }
                }, true);
            }
        }, 1000);
    }

    /**
     * Setup event listeners
     */
    function setupEventListeners() {
        // Listen for OCR completion to add scanning animation
        document.addEventListener('ocrProcessing', (e) => {
            if (e.detail && e.detail.pageImage) {
                addScanningAnimation(e.detail.pageImage);
            }
        });
    }

    /**
     * Show preprocessing choice modal
     */
    function showPreprocessingChoice() {
        const modal = document.getElementById('preprocessingChoiceModal');
        if (modal) {
            modal.style.display = 'flex';
        }
    }

    /**
     * Hide preprocessing choice modal
     */
    function hidePreprocessingChoice() {
        const modal = document.getElementById('preprocessingChoiceModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    /**
     * Select direct OCR (no preprocessing)
     */
    function selectDirectOCR() {
        hidePreprocessingChoice();
        preprocessingEnabled = false;

        // Continue with normal OCR flow
        if (currentFileForPreprocessing) {
            // Call original OCR function
            if (window.processFile) {
                window.processFile(currentFileForPreprocessing);
            } else {
                // Fallback: trigger file upload event
                const event = new CustomEvent('fileSelected', {
                    detail: { file: currentFileForPreprocessing }
                });
                document.dispatchEvent(event);
            }
        }
    }

    /**
     * Select preprocessing workflow
     */
    function selectPreprocessing() {
        hidePreprocessingChoice();
        preprocessingEnabled = true;

        if (currentFileForPreprocessing) {
            // Redirect to preprocessing tool
            uploadFileForPreprocessing(currentFileForPreprocessing);
        }
    }

    /**
     * Cancel preprocessing choice
     */
    function cancelPreprocessing() {
        hidePreprocessingChoice();
        currentFileForPreprocessing = null;
    }

    /**
     * Upload file and redirect to preprocessing tool
     */
    async function uploadFileForPreprocessing(file) {
        try {
            // Show loading indicator
            showNotification('Dosya yükleniyor...', 'info');

            // Upload file to get an ID
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`${OCR_API_URL}/api/upload-temp`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.file_id) {
                // Redirect to preprocessing tool with file ID
                window.location.href = `/preprocessing?file=${data.file_id}`;
            } else {
                throw new Error('Dosya yüklenemedi');
            }
        } catch (error) {
            showNotification('Hata: ' + error.message, 'error');
        }
    }

    /**
     * Add scanning animation to OCR page
     */
    function addScanningAnimation(pageElement) {
        if (!pageElement) return;

        // Create scanning overlay
        const scanningOverlay = document.createElement('div');
        scanningOverlay.className = 'scanning-overlay';
        scanningOverlay.innerHTML = `
            <div class="scan-line"></div>
            <div class="scan-glow"></div>
        `;

        // Add to page element
        pageElement.style.position = 'relative';
        pageElement.appendChild(scanningOverlay);

        // Remove after animation completes
        setTimeout(() => {
            scanningOverlay.remove();
        }, 3000);
    }

    /**
     * Show notification (utility function)
     */
    function showNotification(message, type = 'info') {
        // Check if there's an existing notification system
        if (window.showNotification) {
            window.showNotification(message, type);
        } else {
            // Fallback to console
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    // Export functions to global scope
    window.PreprocessingIntegration = {
        init: initPreprocessingIntegration,
        selectDirectOCR: selectDirectOCR,
        selectPreprocessing: selectPreprocessing,
        cancelPreprocessing: cancelPreprocessing
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPreprocessingIntegration);
    } else {
        initPreprocessingIntegration();
    }

})();
