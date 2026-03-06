/**
 * OCR Database Admin Panel - JavaScript
 */

// API Base URL
const API_BASE = '/admin';

// State
let currentPage = 1;
let totalPages = 1;
let currentRecordId = null;

// DOM Elements
const elements = {
    // Navigation
    navItems: document.querySelectorAll('.nav-item'),
    pages: document.querySelectorAll('.page'),
    pageTitle: document.getElementById('pageTitle'),

    // Database Status
    dbStatus: document.getElementById('dbStatus'),

    // Dashboard
    statDocuments: document.getElementById('statDocuments'),
    statAuthors: document.getElementById('statAuthors'),
    statPages: document.getElementById('statPages'),
    recentList: document.getElementById('recentList'),
    topAuthorsList: document.getElementById('topAuthorsList'),
    typeDistList: document.getElementById('typeDistList'),

    // Records
    recordsTableBody: document.getElementById('recordsTableBody'),
    recordsSearch: document.getElementById('recordsSearch'),
    recordsSort: document.getElementById('recordsSort'),
    recordsType: document.getElementById('recordsType'),
    prevPageBtn: document.getElementById('prevPageBtn'),
    nextPageBtn: document.getElementById('nextPageBtn'),
    pageInfo: document.getElementById('pageInfo'),
    addRecordBtn: document.getElementById('addRecordBtn'),

    // Authors
    authorsGrid: document.getElementById('authorsGrid'),
    authorsSearch: document.getElementById('authorsSearch'),
    authorsSort: document.getElementById('authorsSort'),

    // Search
    globalSearch: document.getElementById('globalSearch'),
    searchField: document.getElementById('searchField'),
    searchBtn: document.getElementById('searchBtn'),
    searchResults: document.getElementById('searchResults'),

    // Export/Import
    exportJsonBtn: document.getElementById('exportJsonBtn'),
    exportCsvBtn: document.getElementById('exportCsvBtn'),
    exportExcelBtn: document.getElementById('exportExcelBtn'),
    importFile: document.getElementById('importFile'),
    importBtn: document.getElementById('importBtn'),
    fileName: document.getElementById('fileName'),
    startImportBtn: document.getElementById('startImportBtn'),

    // Tools
    backupBtn: document.getElementById('backupBtn'),
    vacuumBtn: document.getElementById('vacuumBtn'),
    findDuplicatesBtn: document.getElementById('findDuplicatesBtn'),
    duplicatesResult: document.getElementById('duplicatesResult'),

    // Bulk Action Bar Elements
    bulkActionBar: document.getElementById('bulkActionBar'),
    selectedCount: document.getElementById('selectedCount'),
    bulkDeleteBtn: document.getElementById('bulkDeleteBtn'),
    bulkExportBtn: document.getElementById('bulkExportBtn'),
    cancelSelectionBtn: document.getElementById('cancelSelectionBtn'),
    selectAllRecords: document.getElementById('selectAllRecords'),

    // Modal
    recordModal: document.getElementById('recordModal'),
    modalTitle: document.getElementById('modalTitle'),
    closeModalBtn: document.getElementById('closeModalBtn'),
    cancelModalBtn: document.getElementById('cancelModalBtn'),
    saveRecordBtn: document.getElementById('saveRecordBtn'),
    deleteRecordBtn: document.getElementById('deleteRecordBtn'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabContents: document.querySelectorAll('.tab-content'),

    // Form fields
    // Temel
    recordId: document.getElementById('recordId'),
    recordTitle: document.getElementById('recordTitle'),
    recordAuthor: document.getElementById('recordAuthor'),
    recordType: document.getElementById('recordType'),
    recordLanguage: document.getElementById('recordLanguage'),
    recordCountry: document.getElementById('recordCountry'),
    recordCitation: document.getElementById('recordCitation'),

    // Kitap & Seri
    recordPublisher: document.getElementById('recordPublisher'),
    recordCity: document.getElementById('recordCity'),
    recordYear: document.getElementById('recordYear'),
    recordPageCount: document.getElementById('recordPageCount'), // integer olan
    recordVolume: document.getElementById('recordVolume'),
    recordEdition: document.getElementById('recordEdition'),
    recordISBN: document.getElementById('recordISBN'),
    recordEditor: document.getElementById('recordEditor'),
    recordSeries: document.getElementById('recordSeries'),
    recordSeriesTitle: document.getElementById('recordSeriesTitle'),
    recordSeriesText: document.getElementById('recordSeriesText'),

    // Makale
    recordPublication: document.getElementById('recordPublication'), // Dergi Adı
    recordArticleDate: document.getElementById('recordArticleDate'),
    recordIssue: document.getElementById('recordIssue'),
    recordJournalAbbr: document.getElementById('recordJournalAbbr'),
    recordDOI: document.getElementById('recordDOI'),
    recordISSN: document.getElementById('recordISSN'),

    // Gazete
    recordNewspaperName: document.getElementById('recordNewspaperName'),
    recordNewspaperDate: document.getElementById('recordNewspaperDate'),
    recordDate: document.getElementById('recordDate'),
    recordPubPlace: document.getElementById('recordPubPlace'),
    recordSection: document.getElementById('recordSection'),
    recordColumnName: document.getElementById('recordColumnName'),
    recordPageRange: document.getElementById('recordPageRange'),
    recordPagesInt: document.getElementById('recordPagesInt'), // 'pages' kolonu için

    // Ansiklopedi
    recordEncTitle: document.getElementById('recordEncTitle'),
    recordShortTitle: document.getElementById('recordShortTitle'),
    recordEncyclopediaDate: document.getElementById('recordEncyclopediaDate'),

    // Ortak
    recordUrl: document.getElementById('recordUrl'),
    recordAccessDate: document.getElementById('recordAccessDate'),
    recordArchive: document.getElementById('recordArchive'),
    recordArchiveLoc: document.getElementById('recordArchiveLoc'),
    recordLibCatalog: document.getElementById('recordLibCatalog'),
    recordCallNumber: document.getElementById('recordCallNumber'),
    recordRights: document.getElementById('recordRights'),
    recordDescription: document.getElementById('recordDescription'),


    markdownEditor: document.getElementById('markdownEditor'),
    xmlEditor: document.getElementById('xmlEditor'),

    // Toast
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toastMessage'),

    // Refresh
    refreshBtn: document.getElementById('refreshBtn'),

    // Logo Elementi
    brandLogo: document.getElementById('brandLogo'),

    // File Viewer & Downloads
    fileViewerFrame: document.getElementById('fileViewerFrame'),
    downloadSourceBtn: document.getElementById('downloadSourceBtn'),
    downloadMdBtn: document.getElementById('downloadMdBtn'),
    downloadXmlBtn: document.getElementById('downloadXmlBtn'),

    fullScreenBtn: document.getElementById('fullScreenBtn'),
    fileViewerContainer: document.querySelector('.file-viewer-container'),

    // File Upload Elements
    uploadSourceBtn: document.getElementById('uploadSourceBtn'),
    uploadSourceInput: document.getElementById('uploadSourceInput'),

    uploadMdBtn: document.getElementById('uploadMdBtn'),
    uploadMdInput: document.getElementById('uploadMdInput'),

    uploadXmlBtn: document.getElementById('uploadXmlBtn'),
    uploadXmlInput: document.getElementById('uploadXmlInput'),

    // Progress Overlay Elements (YENİ)
    progressOverlay: document.getElementById('progressOverlay'),
    progressTitle: document.getElementById('progressTitle'),
    progressBarFill: document.getElementById('progressBarFill'),
    progressText: document.getElementById('progressText'),
    progressSize: document.getElementById('progressSize'),

    downloadZipBtn: document.getElementById('downloadZipBtn'),

};

// ==========================================
// Initialization
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initEventListeners();
    checkDatabaseStatus();
    loadDashboard();
});

function initNavigation() {
    elements.navItems.forEach(item => {
        if (!item.dataset.page) return;
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            navigateTo(page);
        });
    });
}

function navigateTo(page) {
    // Update nav
    elements.navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });

    // Update pages
    elements.pages.forEach(p => {
        p.classList.toggle('active', p.id === `page-${page}`);
    });

    // Update title
    const titles = {
        dashboard: 'Dashboard',
        records: 'Kayıtlar',
        authors: 'Yazarlar',
        search: 'Arama',
        export: 'Export / Import'
    };
    elements.pageTitle.textContent = titles[page] || page;

    // Load page data
    switch (page) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'records':
            loadRecords();
            break;
        case 'authors':
            loadAuthors();
            break;
    }
}

function initEventListeners() {
    // Refresh button
    elements.refreshBtn.addEventListener('click', () => {
        const activePage = document.querySelector('.page.active');
        if (activePage) {
            const pageId = activePage.id.replace('page-', '');
            navigateTo(pageId);
        }
    });

    // Logo Click -> Dashboard Navigation
    if (elements.brandLogo) {
        elements.brandLogo.addEventListener('click', () => {
            navigateTo('dashboard');
        });
    }

    // Records
    elements.recordsSearch.addEventListener('input', debounce(loadRecords, 300));
    elements.recordsSort.addEventListener('change', loadRecords);
    elements.recordsType.addEventListener('change', loadRecords);
    elements.prevPageBtn.addEventListener('click', () => { currentPage--; loadRecords(); });
    elements.nextPageBtn.addEventListener('click', () => { currentPage++; loadRecords(); });
    // elements.addRecordBtn.addEventListener('click', openNewRecordModal);

    // Authors
    elements.authorsSearch.addEventListener('input', debounce(loadAuthors, 300));
    elements.authorsSort.addEventListener('change', loadAuthors);

    // Search
    elements.searchBtn.addEventListener('click', performSearch);
    elements.globalSearch.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    // Export/Import
    elements.exportJsonBtn.addEventListener('click', exportJson);
    elements.exportCsvBtn.addEventListener('click', exportCsv);
    elements.importBtn.addEventListener('click', () => elements.importFile.click());
    elements.importFile.addEventListener('change', handleFileSelect);
    elements.startImportBtn.addEventListener('click', startImport);

    // Downloads
    elements.downloadSourceBtn.addEventListener('click', () => {
        if (currentRecordId) {
            downloadFileWithProgress(`${API_BASE}/api/files/download/${currentRecordId}`, `kaynak_dosya_${currentRecordId}`);
        }
    });

    elements.downloadMdBtn.addEventListener('click', () => {
        if (currentRecordId) {
            downloadFileWithProgress(`${API_BASE}/api/content/download/${currentRecordId}/markdown`);
        }
    });

    elements.downloadXmlBtn.addEventListener('click', () => {
        if (currentRecordId) {
            downloadFileWithProgress(`${API_BASE}/api/content/download/${currentRecordId}/xml`);
        }
    });

    // Tam Ekran (Full Screen) Eventleri
    if (elements.fullScreenBtn) {
        elements.fullScreenBtn.addEventListener('click', toggleFullScreen);
    }

    if (elements.fileViewerContainer) {
        elements.fileViewerContainer.addEventListener('dblclick', toggleFullScreen);
    }

    // Tools listeners removed

    // Modal
    elements.closeModalBtn.addEventListener('click', closeModal);
    elements.cancelModalBtn.addEventListener('click', closeModal);
    elements.saveRecordBtn.addEventListener('click', saveRecord);
    elements.deleteRecordBtn.addEventListener('click', deleteRecord);

    // ZIP Download Event
    if (elements.downloadZipBtn) {
        elements.downloadZipBtn.addEventListener('click', () => {
            if (currentRecordId) {
                // Sabit ismi SİLDİK. Artık fonksiyon sunucudan gelen ismi kullanacak.
                downloadFileWithProgress(`${API_BASE}/api/export/record/${currentRecordId}/zip`);
            }
        });
    }

    // Modal tabs
    elements.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            elements.tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
            elements.tabContents.forEach(c => c.classList.toggle('active', c.id === `tab-${tab}`));

            // Sekme değişimlerinde yükleme yap
            if (currentRecordId) {
                if (tab === 'markdown') {
                    loadMarkdown(currentRecordId);
                } else if (tab === 'xml') {
                    loadXml(currentRecordId);
                } else if (tab === 'file') {
                    elements.fileViewerFrame.src = `${API_BASE}/api/files/view/${currentRecordId}`;
                }
            }
        });
    });

    // Close modal on outside click
    elements.recordModal.addEventListener('click', (e) => {
        if (e.target === elements.recordModal) closeModal();
    });

    // Arama Temizleme (X) Butonları
    document.querySelectorAll('.clear-btn').forEach(btn => {
        const inputId = btn.dataset.target;
        const input = document.getElementById(inputId);

        if (!input) return;

        input.addEventListener('input', () => {
            btn.style.display = input.value.length > 0 ? 'block' : 'none';
        });

        btn.addEventListener('click', () => {
            input.value = '';
            btn.style.display = 'none';
            input.focus();

            input.dispatchEvent(new Event('input'));

            if (inputId === 'globalSearch') {
                elements.searchResults.innerHTML = '<p class="search-hint">Arama yapmak için yukarıdaki kutuyu kullanın.</p>';
            }
        });

        if (input.value.length > 0) {
            btn.style.display = 'block';
        }
    });

    // Upload Eventleri
    elements.uploadSourceBtn.addEventListener('click', () => elements.uploadSourceInput.click());
    elements.uploadSourceInput.addEventListener('change', (e) => handleFileUpload(e, 'source'));

    elements.uploadMdBtn.addEventListener('click', () => elements.uploadMdInput.click());
    elements.uploadMdInput.addEventListener('change', (e) => handleFileUpload(e, 'markdown'));

    elements.uploadXmlBtn.addEventListener('click', () => elements.uploadXmlInput.click());
    elements.uploadXmlInput.addEventListener('change', (e) => handleFileUpload(e, 'xml'));

    // Tür değiştiğinde form alanlarını güncelle
    elements.recordType.addEventListener('change', updateFormFields);

    // Export/Import bölümü altına:
    elements.exportJsonBtn.addEventListener('click', exportJson);
    elements.exportCsvBtn.addEventListener('click', exportCsv);
    if (elements.exportExcelBtn) {
        elements.exportExcelBtn.addEventListener('click', exportExcel);
    }

}

// ==========================================
// API Functions
// ==========================================

async function apiGet(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API GET Error:', error);
        throw error;
    }
}

async function apiPost(endpoint, data) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API POST Error:', error);
        throw error;
    }
}

async function apiPut(endpoint, data) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API PUT Error:', error);
        throw error;
    }
}

async function apiDelete(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API DELETE Error:', error);
        throw error;
    }
}

// ==========================================
// Database Status
// ==========================================

async function checkDatabaseStatus() {
    try {
        const data = await apiGet('/api/health');
        const statusDot = elements.dbStatus.querySelector('.status-dot');
        const statusText = elements.dbStatus.querySelector('.status-text');

        if (data.database === 'connected') {
            statusDot.className = 'status-dot connected';
            statusText.textContent = 'Bağlı';
        } else {
            statusDot.className = 'status-dot error';
            statusText.textContent = 'Hata';
        }
    } catch (error) {
        const statusDot = elements.dbStatus.querySelector('.status-dot');
        const statusText = elements.dbStatus.querySelector('.status-text');
        statusDot.className = 'status-dot error';
        statusText.textContent = 'Bağlantı yok';
    }
}

// ==========================================
// Dashboard
// ==========================================

async function loadDashboard() {
    try {
        const stats = await apiGet('/api/stats');

        // Stats cards
        elements.statDocuments.textContent = stats.total_documents.toLocaleString();
        elements.statAuthors.textContent = stats.total_authors.toLocaleString();
        elements.statPages.textContent = stats.total_pages.toLocaleString();

        // Recent additions (Son Eklenenler - Tıklanabilir Yapı)
        if (stats.recent_additions && stats.recent_additions.length > 0) {
            elements.recentList.innerHTML = stats.recent_additions.map(item => {
                // Yazar ismi güvenliği (kesme işareti varsa)
                const safeAuthorName = item.author ? item.author.replace(/'/g, "\\'") : '';

                // Başlık Linki
                const titleHtml = `<a href="#" class="table-link title-link" onclick="event.preventDefault(); openRecordModal('${item.id}')" title="Detayları gör">${escapeHtml(item.title)}</a>`;

                // Yazar Linki
                const authorHtml = item.author
                    ? `<a href="#" class="table-link author-link" onclick="event.preventDefault(); filterRecordsByAuthor(decodeURIComponent('${encodeURIComponent(item.author)}'))" title="Yazarın eserlerini gör">${escapeHtml(item.author)}</a>`
                    : '<span class="text-muted">Bilinmeyen</span>';

                return `
                <li>
                    <div class="item-info">
                        <div class="title" style="margin-bottom: 2px;">${titleHtml}</div>
                        <div class="author">${authorHtml}</div>
                    </div>
                    <span class="date">${formatDate(item.created_at)}</span>
                </li>
            `}).join('');
        } else {
            elements.recentList.innerHTML = '<li>Henüz kayıt yok</li>';
        }

        // Top authors
        if (stats.top_authors && stats.top_authors.length > 0) {
            elements.topAuthorsList.innerHTML = stats.top_authors.map(item => {
                const safeName = encodeURIComponent(item.name);

                return `
                <li>
                    <a href="#" class="table-link author-link" style="flex: 1; font-weight: 500;" onclick="event.preventDefault(); filterRecordsByAuthor(decodeURIComponent('${safeName}'))">
                        ${escapeHtml(item.name)}
                    </a>
                    <span class="count">${item.count} eser</span>
                </li>
            `}).join('');
        } else {
            elements.topAuthorsList.innerHTML = '<li>Henüz yazar yok</li>';
        }

        // Type distribution (Tür Dağılımı - Olduğu gibi kalabilir veya filtrelenebilir yapılabilir)
        if (stats.type_distribution && stats.type_distribution.length > 0) {
            const typeLabels = {
                book: 'Kitap',
                article: 'Makale',
                newspaper: 'Gazete',
                encyclopedia: 'Ansiklopedi',
                unknown: 'Belirsiz'
            };
            elements.typeDistList.innerHTML = stats.type_distribution.map(item => `
                <li>
                    <span class="name">${typeLabels[item.type] || item.type}</span>
                    <span class="count">${item.count}</span>
                </li>
            `).join('');
        } else {
            elements.typeDistList.innerHTML = '<li>Veri yok</li>';
        }

    } catch (error) {
        console.error(error);
        showToast('Dashboard yüklenemedi', 'error');
    }
}

// ==========================================
// Records
// ==========================================

async function loadRecords() {
    try {
        const search = elements.recordsSearch.value;
        const sort = elements.recordsSort.value;
        const type = elements.recordsType.value;

        const params = new URLSearchParams({
            page: currentPage,
            per_page: 25,
            sort: sort
        });

        if (search) params.append('search', search);
        if (type) params.append('type', type);

        const data = await apiGet(`/api/records?${params}`);

        totalPages = data.total_pages;

        // Update pagination
        elements.prevPageBtn.disabled = currentPage <= 1;
        elements.nextPageBtn.disabled = currentPage >= totalPages;
        elements.pageInfo.textContent = `Sayfa ${currentPage} / ${totalPages || 1}`;

        // Render table
        if (data.records && data.records.length > 0) {
            elements.recordsTableBody.innerHTML = data.records.map(record => {
                // Yazar isminde tek tırnak varsa escape işlemi
                const safeAuthorName = record.author ? record.author.replace(/'/g, "\\'") : '';

                // Yazar HTML
                const authorHtml = record.author
                    ? `<a href="#" class="table-link author-link" onclick="event.preventDefault(); filterRecordsByAuthor(decodeURIComponent('${encodeURIComponent(record.author)}'))" title="Bu yazarın eserlerini listele">${escapeHtml(record.author)}</a>`
                    : '<span class="text-muted">-</span>';

                // Başlık HTML
                const titleHtml = `<a href="#" class="table-link title-link" onclick="event.preventDefault(); openRecordModal('${record.id}')" title="Düzenlemek için tıkla">${escapeHtml(record.title)}</a>`;

                // --- Mevcut Detay Bilgileri Korunuyor ---
                let detailsParts = [];
                if (record.volume) {
                    const volText = record.volume.toLowerCase().includes('cilt') || record.volume.toLowerCase().includes('vol')
                        ? record.volume
                        : `Cilt ${record.volume}`;
                    detailsParts.push(`<span style="color:var(--text-secondary); font-size:0.85rem;">${escapeHtml(volText)}</span>`);
                }
                if (record.edition) {
                    detailsParts.push(`<span style="color:var(--text-secondary); font-size:0.85rem;">${escapeHtml(record.edition)}. Baskı</span>`);
                }
                if (record.editor) {
                    detailsParts.push(`<span style="color:var(--text-muted); font-size:0.8rem; font-style:italic;">Haz: ${escapeHtml(record.editor)}</span>`);
                }
                const detailsHtml = detailsParts.length > 0 ? detailsParts.join('<br>') : '<span class="text-muted">-</span>';

                // TR içindeki checkbox sütunu ve mevcut diğer tüm sütunlar
                return `
                <tr data-id="${record.id}">
                    <td><input type="checkbox" class="record-checkbox" value="${record.id}"></td>
                    <td>${titleHtml}</td>
                    <td>${authorHtml}</td>
                    <td>${getTypeLabel(record.metadata_type)}</td>
                    <td>${detailsHtml}</td> 
                    <td>${record.publication_year || '-'}</td>
                    <td class="actions">
                        <button class="btn btn-secondary btn-sm" onclick="openRecordModal('${record.id}')">
                            <span class="material-symbols-rounded" style="font-size:16px;">edit</span>
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="confirmDelete('${record.id}')">
                            <span class="material-symbols-rounded" style="font-size:16px;">delete</span>
                        </button>
                    </td>
                </tr>
            `}).join('');

            // Seçim mantığını başlatan yeni fonksiyonu çağırıyoruz
            if (typeof initBulkSelectionEvents === 'function') {
                initBulkSelectionEvents();
            }

        } else {
            // Sütun sayısı 7'ye çıktığı için colspan güncellendi
            elements.recordsTableBody.innerHTML = '<tr><td colspan="7" class="loading">Kayıt bulunamadı</td></tr>';
        }

    } catch (error) {
        console.error(error);
        elements.recordsTableBody.innerHTML = '<tr><td colspan="7" class="loading">Yükleme hatası</td></tr>';
        showToast('Kayıtlar yüklenemedi', 'error');
    }
}

async function openRecordModal(id) {
    currentRecordId = id;
    elements.modalTitle.textContent = 'Kayıt Düzenle';
    elements.deleteRecordBtn.style.display = 'block';

    // 1. Önce iframe'i sıfırla (Eski dosya görünmesin)
    if (elements.fileViewerFrame) elements.fileViewerFrame.src = 'about:blank';

    try {
        // 2. Veriyi veritabanından çek ('record' değişkeni burada oluşuyor)
        const record = await apiGet(`/api/records/${id}`);

        // --- FORM DOLDURMA İŞLEMLERİ ---
        // Temel
        elements.recordId.value = record.id;
        elements.recordTitle.value = record.title || '';
        elements.recordAuthor.value = record.author || '';
        elements.recordType.value = record.metadata_type || 'book';
        elements.recordLanguage.value = record.language || '';
        elements.recordCountry.value = record.country || '';
        elements.recordCitation.value = record.citation_style || '';

        // Kitap & Seri
        elements.recordPublisher.value = record.publisher || '';
        elements.recordCity.value = record.publication_city || '';
        elements.recordYear.value = record.publication_year || '';
        elements.recordPageCount.value = record.page_count || '';
        elements.recordVolume.value = record.volume || '';
        elements.recordEdition.value = record.edition || '';
        elements.recordISBN.value = record.isbn || '';
        elements.recordEditor.value = record.editor || '';
        elements.recordSeries.value = record.series || '';
        elements.recordSeriesTitle.value = record.series_title || '';
        elements.recordSeriesText.value = record.series_text || '';

        // Makale
        elements.recordPublication.value = record.journal_name || record.publication || '';
        elements.recordIssue.value = record.issue_number || record.issue || '';
        elements.recordDOI.value = record.doi || '';
        elements.recordISSN.value = record.issn || '';
        elements.recordJournalAbbr.value = record.journal_abbreviation || '';

        // Gazete
        elements.recordNewspaperName.value = record.newspaper_name || '';
        elements.recordPubPlace.value = record.publication_place || '';
        elements.recordSection.value = record.section || '';
        elements.recordColumnName.value = record.column_name || '';
        elements.recordPageRange.value = record.page_range || '';
        elements.recordPagesInt.value = record.pages || '';

        // Tarih Doldurma
        let dateVal = '';
        if (record.date) {
            dateVal = record.date.split('T')[0];
        }

        if (elements.recordNewspaperDate) elements.recordNewspaperDate.value = dateVal;
        if (elements.recordArticleDate) elements.recordArticleDate.value = dateVal;
        if (elements.recordEncyclopediaDate) elements.recordEncyclopediaDate.value = dateVal;

        // Ansiklopedi
        elements.recordEncTitle.value = record.encyclopedia_title || '';
        elements.recordShortTitle.value = record.short_title || '';

        // Ortak
        elements.recordUrl.value = record.url || '';
        if (record.access_date) {
            elements.recordAccessDate.value = record.access_date.split('T')[0];
        } else {
            elements.recordAccessDate.value = '';
        }

        elements.recordArchive.value = record.archive || '';
        elements.recordArchiveLoc.value = record.archive_location || '';
        elements.recordLibCatalog.value = record.library_catalog || '';
        elements.recordCallNumber.value = record.call_number || '';
        elements.recordRights.value = record.rights || '';
        elements.recordDescription.value = record.description || '';

        // Form alanlarını türe göre ayarla
        updateFormFields();

        // Reset tabs
        elements.tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === 'metadata'));
        elements.tabContents.forEach(c => c.classList.toggle('active', c.id === 'tab-metadata'));
        elements.markdownEditor.value = '';
        elements.xmlEditor.value = '';

        elements.recordModal.classList.add('active');

        // --- 3. DOSYA GÖRÜNTÜLEYİCİ MANTIĞI (DÜZELTİLDİ) ---
        // Bu kod bloğu, 'const record = ...' satırından SONRA gelmelidir.
        if (elements.fileViewerFrame) {
            // pdf_path backend'den gelen veridir.
            if (record.pdf_path) {
                // Cache sorunu olmasın diye timestamp ekleyebiliriz
                const timestamp = new Date().getTime();
                elements.fileViewerFrame.src = `${API_BASE}/api/files/view/${record.id}?t=${timestamp}`;
            } else {
                // Dosya yoksa boş sayfa (404 hatasını engeller)
                elements.fileViewerFrame.src = 'about:blank';
            }
        }

    } catch (error) {
        console.error(error);
        showToast('Kayıt yüklenemedi', 'error');
    }
}

function openNewRecordModal() {
    currentRecordId = null;
    elements.modalTitle.textContent = 'Yeni Kayıt';
    elements.deleteRecordBtn.style.display = 'none';

    // Clear form
    elements.recordId.value = '';
    elements.recordTitle.value = '';
    elements.recordAuthor.value = '';
    elements.recordType.value = 'book';
    elements.recordYear.value = '';
    elements.recordPublisher.value = '';
    if (elements.recordPageCount) elements.recordPageCount.value = '';
    elements.recordVolume.value = '';
    elements.recordEdition.value = '';
    elements.recordEditor.value = '';
    elements.recordDescription.value = '';
    elements.markdownEditor.value = '';
    elements.xmlEditor.value = '';

    // Reset tabs
    elements.tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === 'metadata'));
    elements.tabContents.forEach(c => c.classList.toggle('active', c.id === 'tab-metadata'));

    elements.recordModal.classList.add('active');

    elements.fileViewerFrame.src = '';
}

async function saveRecord() {
    // --- TARİH SEÇİM MANTIĞI (YENİ) ---
    let selectedDate = null;
    const type = elements.recordType.value;

    if (type === 'newspaper') {
        selectedDate = elements.recordNewspaperDate.value;
    } else if (type === 'article') {
        selectedDate = elements.recordArticleDate.value;
    } else if (type === 'encyclopedia') {
        selectedDate = elements.recordEncyclopediaDate.value;
    }

    // Verileri formdan topla
    const data = {
        title: elements.recordTitle.value,
        author: elements.recordAuthor.value,
        metadata_type: elements.recordType.value,
        language: elements.recordLanguage.value,
        country: elements.recordCountry.value,
        citation_style: elements.recordCitation.value,

        // Kitap & Seri
        publisher: elements.recordPublisher.value,
        publication_city: elements.recordCity.value,
        publication_year: elements.recordYear.value ? parseInt(elements.recordYear.value) : null,
        page_count: elements.recordPageCount.value ? parseInt(elements.recordPageCount.value) : null,
        volume: elements.recordVolume.value,
        edition: elements.recordEdition.value,
        isbn: elements.recordISBN.value,
        editor: elements.recordEditor.value,
        series: elements.recordSeries.value,
        series_title: elements.recordSeriesTitle.value,
        series_text: elements.recordSeriesText.value,

        // Makale
        publication: elements.recordPublication.value,
        issue: elements.recordIssue.value,
        doi: elements.recordDOI.value,
        issn: elements.recordISSN.value,
        journal_abbreviation: elements.recordJournalAbbr.value,

        // Gazete
        newspaper_name: elements.recordNewspaperName.value,
        date: selectedDate || null,
        publication_place: elements.recordPubPlace.value,
        section: elements.recordSection.value,
        column_name: elements.recordColumnName.value,
        page_range: elements.recordPageRange.value,
        pages: elements.recordPagesInt.value ? parseInt(elements.recordPagesInt.value) : null,

        // Ansiklopedi
        encyclopedia_title: elements.recordEncTitle.value,
        short_title: elements.recordShortTitle.value,

        // Ortak
        url: elements.recordUrl.value,
        access_date: elements.recordAccessDate.value || null,
        archive: elements.recordArchive.value,
        archive_location: elements.recordArchiveLoc.value,
        library_catalog: elements.recordLibCatalog.value,
        call_number: elements.recordCallNumber.value,
        rights: elements.recordRights.value,
        description: elements.recordDescription.value
    };

    try {
        if (currentRecordId) {
            await apiPut(`/api/records/${currentRecordId}`, data);

            if (elements.markdownEditor.value) {
                await apiPut(`/api/records/${currentRecordId}/markdown`, { content: elements.markdownEditor.value });
            }
            if (elements.xmlEditor.value) {
                await apiPut(`/api/records/${currentRecordId}/xml`, { content: elements.xmlEditor.value });
            }

            showToast('Kayıt güncellendi', 'success');
        } else {
            await apiPost('/api/records', data);
            showToast('Kayıt oluşturuldu', 'success');
        }

        closeModal();
        loadRecords();

    } catch (error) {
        console.error(error);
        showToast('Kaydetme hatası', 'error');
    }
}

async function deleteRecord() {
    if (!currentRecordId) return;

    if (!confirm('Bu kaydi silmek istediginizden emin misiniz?')) return;

    try {
        await apiDelete(`/api/records/${currentRecordId}`);
        showToast('Kayıt silindi', 'success');
        closeModal();
        await loadRecords();
    } catch (error) {
        showToast('Silme hatası', 'error');
    }
}

function confirmDelete(id) {
    if (confirm('Bu kaydi silmek istediginizden emin misiniz?')) {
        apiDelete(`/api/records/${id}`).then(() => {
            showToast('Kayıt silindi', 'success');
            loadRecords();
        }).catch(() => {
            showToast('Silme hatası', 'error');
        });
    }
}

async function loadMarkdown(recordId) {
    try {
        const data = await apiGet(`/api/records/${recordId}/markdown`);
        elements.markdownEditor.value = data.content || '';
    } catch (error) {
        elements.markdownEditor.value = '';
    }
}

async function loadXml(recordId) {
    try {
        const data = await apiGet(`/api/records/${recordId}/xml`);
        elements.xmlEditor.value = data.content || '';
    } catch (error) {
        elements.xmlEditor.value = '';
    }
}

function closeModal() {
    elements.recordModal.classList.remove('active');
    currentRecordId = null;
}

// ==========================================
// Authors
// ==========================================

async function loadAuthors() {
    try {
        const search = elements.authorsSearch.value;
        const sort = elements.authorsSort.value;

        const params = new URLSearchParams({ sort });
        if (search) params.append('search', search);

        const authors = await apiGet(`/api/authors?${params}`);

        if (authors && authors.length > 0) {
            // loadAuthors fonksiyonunun içindeki HTML oluşturma kısmını (map) şöyle değiştir:
            // loadAuthors içindeki map fonksiyonu:
            elements.authorsGrid.innerHTML = authors.map(author => {
                const safeName = encodeURIComponent(author.name);

                return `
                <div class="author-card">
                    <div class="author-header" style="display:flex; justify-content:space-between; align-items:start;">
                        <div class="name" onclick="filterRecordsByAuthor(decodeURIComponent('${safeName}'))" style="flex:1;">
                            ${escapeHtml(author.name)}
                        </div>
                        <button class="btn-icon btn-sm" 
                                style="width:32px; height:32px;" 
                                title="Tüm eserleri ve verileri ZIP olarak indir"
                                onclick="downloadAuthorData(decodeURIComponent('${safeName}'))">
                            <span class="material-symbols-rounded" style="font-size: 18px;">folder_zip</span>
                        </button>
                    </div>
                    <div class="meta" onclick="filterRecordsByAuthor(decodeURIComponent('${safeName}'))">
                        <span>${formatDate(author.last_updated)}</span>
                        <span class="doc-count">${author.doc_count} eser</span>
                    </div>
                </div>
            `}).join('');
        } else {
            elements.authorsGrid.innerHTML = '<div class="loading">Yazar bulunamadı</div>';
        }

    } catch (error) {
        elements.authorsGrid.innerHTML = '<div class="loading">Yükleme hatası</div>';
        showToast('Yazarlar yüklenemedi', 'error');
    }
}

function filterRecordsByAuthor(author) {
    // 1. ÖNCE: Arama kutusuna yazarın adını yaz (Henüz sayfa değişmeden)
    if (elements.recordsSearch) {
        elements.recordsSearch.value = author;
    }

    // 2. Sayfalama ayarını sıfırla
    currentPage = 1;

    // 3. X (Temizleme) Butonunu manuel olarak göster
    const clearBtn = document.querySelector('.clear-btn[data-target="recordsSearch"]');
    if (clearBtn) {
        clearBtn.style.display = 'block';
    }

    // 4. SONRA: Sayfaya git
    navigateTo('records');
}

// ==========================================
// Search
// ==========================================

async function performSearch() {
    const query = elements.globalSearch.value.trim();
    const field = elements.searchField.value;

    if (!query) {
        elements.searchResults.innerHTML = '<p class="search-hint">Arama yapmak icin bir terim girin.</p>';
        return;
    }

    elements.searchResults.innerHTML = '<div class="loading">Araniyor...</div>';

    try {
        const params = new URLSearchParams({ q: query, field });
        const data = await apiGet(`/api/search?${params}`);

        if (data.records && data.records.length > 0) {
            elements.searchResults.innerHTML = data.records.map(record => `
                <div class="search-result-item" onclick="openRecordModal('${record.id}')">
                    <div class="result-title">${escapeHtml(record.title)}</div>
                    <div class="result-meta">
                        ${escapeHtml(record.author || 'Bilinmeyen')} | 
                        ${getTypeLabel(record.metadata_type)} | 
                        ${record.publication_year || '-'}
                    </div>
                </div>
            `).join('');
        } else {
            elements.searchResults.innerHTML = '<p class="search-hint">Sonuc bulunamadı.</p>';
        }

    } catch (error) {
        elements.searchResults.innerHTML = '<p class="search-hint">Arama hatası olustu.</p>';
        showToast('Arama hatası', 'error');
    }
}

// ==========================================
// Export / Import
// ==========================================

function exportJson() {
    window.location.href = `${API_BASE}/api/export/json`;
    showToast('JSON indiriliyor...', 'success');
}

function exportCsv() {
    window.location.href = `${API_BASE}/api/export/csv`;
    showToast('CSV indiriliyor...', 'success');
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        elements.fileName.textContent = file.name;
        elements.startImportBtn.disabled = false;
    } else {
        elements.fileName.textContent = 'Dosya secilmedi';
        elements.startImportBtn.disabled = true;
    }
}

async function startImport() {
    const file = elements.importFile.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/api/import`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast(`${data.imported} kayıt ice aktarildi, ${data.skipped} atlandi`, 'success');
            elements.importFile.value = '';
            elements.fileName.textContent = 'Dosya secilmedi';
            elements.startImportBtn.disabled = true;
        } else {
            showToast(data.error || 'Import hatası', 'error');
        }

    } catch (error) {
        showToast('Import hatası', 'error');
    }
}

// ==========================================
// Tools
// ==========================================

async function createBackup() {
    elements.backupBtn.disabled = true;
    elements.backupBtn.textContent = 'Yedekleniyor...';

    try {
        const data = await apiPost('/api/backup', {});
        showToast(`Yedekleme tamamlandi: ${data.records} kayıt`, 'success');
    } catch (error) {
        showToast('Yedekleme hatası', 'error');
    } finally {
        elements.backupBtn.disabled = false;
        elements.backupBtn.textContent = 'Yedek Olustur';
    }
}

async function vacuumDatabase() {
    elements.vacuumBtn.disabled = true;
    elements.vacuumBtn.textContent = 'Optimize ediliyor...';

    try {
        const data = await apiPost('/api/vacuum', {});
        showToast(data.message, 'success');
    } catch (error) {
        showToast('Optimizasyon hatası', 'error');
    } finally {
        elements.vacuumBtn.disabled = false;
        elements.vacuumBtn.textContent = 'Optimize Et';
    }
}

async function findDuplicates() {
    elements.findDuplicatesBtn.disabled = true;
    elements.duplicatesResult.innerHTML = '<div class="loading">Araniyor...</div>';

    try {
        const data = await apiGet('/api/duplicates');

        if (data.duplicates && data.duplicates.length > 0) {
            elements.duplicatesResult.innerHTML = data.duplicates.map(dup => `
                <div class="duplicate-item">
                    <div class="dup-title">${escapeHtml(dup.title)}</div>
                    <div class="dup-meta">${escapeHtml(dup.author || 'Bilinmeyen')} - ${dup.count} adet</div>
                    <div class="dup-actions">
                        <button class="btn btn-danger" onclick="deleteDuplicates('${dup.ids.slice(1).join(',')}')">
                            Tekrarlari Sil (${dup.count - 1})
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            elements.duplicatesResult.innerHTML = '<p>Tekrar eden kayıt bulunamadı.</p>';
        }

    } catch (error) {
        elements.duplicatesResult.innerHTML = '<p>Arama hatası.</p>';
        showToast('Tekrar arama hatası', 'error');
    } finally {
        elements.findDuplicatesBtn.disabled = false;
    }
}

async function deleteDuplicates(idsString) {
    if (!confirm('Secili tekrar eden kayıtlar silinecek. Emin misiniz?')) return;

    const ids = idsString.split(',');

    try {
        await apiDelete('/api/duplicates', { ids });
        showToast('Tekrar eden kayıtlar silindi', 'success');
        findDuplicates();
    } catch (error) {
        showToast('Silme hatası', 'error');
    }
}

// ==========================================
// Utilities
// ==========================================

function showToast(message, type = 'info') {
    elements.toastMessage.textContent = message;
    elements.toast.className = `toast ${type} show`;

    setTimeout(() => {
        elements.toast.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('tr-TR');
    } catch {
        return dateString;
    }
}

function getTypeLabel(type) {
    const labels = {
        book: 'Kitap',
        article: 'Makale',
        newspaper: 'Gazete',
        encyclopedia: 'Ansiklopedi'
    };
    return labels[type] || type || 'Belirsiz';
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Global functions for onclick handlers
window.openRecordModal = openRecordModal;
window.confirmDelete = confirmDelete;
window.filterRecordsByAuthor = filterRecordsByAuthor;
window.deleteDuplicates = deleteDuplicates;

// ==========================================
// UI Helpers
// ==========================================

function toggleFullScreen() {
    const container = elements.fileViewerContainer;
    if (!container) return;

    if (!document.fullscreenElement) {
        // Tam ekrana geç
        if (container.requestFullscreen) {
            container.requestFullscreen().catch(err => {
                showToast(`Tam ekran hatası: ${err.message}`, 'error');
            });
        } else if (container.webkitRequestFullscreen) { /* Safari */
            container.webkitRequestFullscreen();
        } else if (container.msRequestFullscreen) { /* IE11 */
            container.msRequestFullscreen();
        }
    } else {
        // Tam ekrandan çık
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) { /* Safari */
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) { /* IE11 */
            document.msExitFullscreen();
        }
    }
}

function handleFileUpload(event, type) {
    const file = event.target.files[0];
    if (!file || !currentRecordId) return;

    if (!confirm(`${file.name} dosyasını yüklemek ve eskisini değiştirmek istiyor musunuz?`)) {
        event.target.value = '';
        return;
    }

    let endpoint = '';
    if (type === 'source') {
        endpoint = `${API_BASE}/api/files/upload/source/${currentRecordId}`;
    } else {
        endpoint = `${API_BASE}/api/files/upload/content/${currentRecordId}/${type}`;
    }

    const formData = new FormData();
    formData.append('file', file);

    // Progress barı göster (Eğer fonksiyon tanımlıysa)
    if (typeof showProgress === 'function') {
        showProgress(`${type === 'source' ? 'Dosya' : type.toUpperCase()} Yükleniyor...`);
        if (elements.progressBarFill) elements.progressBarFill.classList.remove('processing');
    }

    const xhr = new XMLHttpRequest();
    xhr.open('POST', endpoint, true);

    // --- Yükleme Takibi ---
    xhr.upload.onprogress = function (e) {
        if (e.lengthComputable && typeof updateProgress === 'function') {
            const percentComplete = (e.loaded / e.total) * 100;
            updateProgress(percentComplete, e.loaded, e.total);

            // %100 olduğunda "İşleniyor" moduna geç
            if (percentComplete >= 99.9 && elements.progressBarFill) {
                if (elements.progressTitle) elements.progressTitle.textContent = "Sunucuya İşleniyor...";
                if (elements.progressText) elements.progressText.textContent = "Lütfen Bekleyin";
                elements.progressBarFill.classList.add('processing');
            }
        }
    };

    // --- İşlem Bittiğinde ---
    xhr.onload = function () {
        if (typeof hideProgress === 'function') hideProgress();
        if (elements.progressBarFill) elements.progressBarFill.classList.remove('processing');

        if (xhr.status === 200) {
            const data = JSON.parse(xhr.responseText);
            showToast('İşlem başarıyla tamamlandı!', 'success');

            // ARAYÜZÜ GÜNCELLEME (Kritik Kısım)
            if (type === 'source') {
                // 1. Iframe'in içinde durduğu kutuyu bul
                const container = document.querySelector('.file-viewer-container');

                // 2. Kutunun içini tamamen boşalt (Eski iframe çöp oldu)
                container.innerHTML = '';

                // 3. Yeni bir iframe yarat
                const newIframe = document.createElement('iframe');
                newIframe.id = 'fileViewerFrame';
                newIframe.style.width = '100%';
                newIframe.style.height = '100%';
                newIframe.style.border = 'none';

                // 4. Yeni linki ver (Timestamp ile cache'i deliyoruz)
                const timestamp = new Date().getTime();
                newIframe.src = `${API_BASE}/api/files/view/${currentRecordId}?t=${timestamp}`;

                // 5. Yeni iframe'i kutuya koy
                container.appendChild(newIframe);

                // 6. Global değişkeni güncelle (Yoksa diğer butonlar bozulur)
                elements.fileViewerFrame = newIframe;

            } else if (type === 'markdown') {
                elements.markdownEditor.value = data.content;
            } else if (type === 'xml') {
                elements.xmlEditor.value = data.content;
            }
        } else {
            try {
                const err = JSON.parse(xhr.responseText);
                showToast(`Hata: ${err.error}`, 'error');
            } catch {
                showToast('Sunucu hatası oluştu', 'error');
            }
        }
        event.target.value = '';
    };

    xhr.onerror = function () {
        if (typeof hideProgress === 'function') hideProgress();
        if (elements.progressBarFill) elements.progressBarFill.classList.remove('processing');
        showToast('Ağ hatası oluştu', 'error');
        event.target.value = '';
    };

    xhr.send(formData);
}

async function downloadFileWithProgress(url, defaultFilename) {
    showProgress('İndiriliyor...');

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        // --- YENİ EKLENEN KISIM: Dosya Adını Sunucudan Alma ---
        let filename = defaultFilename;
        const disposition = response.headers.get('content-disposition');

        // Eğer sunucu bir isim gönderdiyse ve biz manuel bir isim vermediysek (veya üzerine yazmak istersek)
        if (disposition && !defaultFilename) {
            // Regex ile filename="dosya_adi.zip" kısmını ayıkla
            const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
            const matches = filenameRegex.exec(disposition);
            if (matches != null && matches[1]) {
                filename = matches[1].replace(/['"]/g, '');
            }
        }
        // Eğer hala isim yoksa varsayılan bir isim ver
        if (!filename) {
            filename = 'download.zip';
        }
        // -------------------------------------------------------

        const contentLength = response.headers.get('content-length');
        const total = contentLength ? parseInt(contentLength, 10) : 0;
        let loaded = 0;

        const reader = response.body.getReader();
        const chunks = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            chunks.push(value);
            loaded += value.length;

            if (total) {
                const percent = (loaded / total) * 100;
                updateProgress(percent, loaded, total);
            } else {
                updateProgress(100, loaded, 0);
            }
        }

        // Blob oluştur ve indir
        const blob = new Blob(chunks);
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename; // Artık dinamik ismi kullanıyor
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
        document.body.removeChild(a);

        showToast('İndirme tamamlandı', 'success');

    } catch (error) {
        console.error('Download Error:', error);
        showToast('İndirme başarısız', 'error');
    } finally {
        hideProgress();
    }
}

// ==========================================
// Progress Helper Functions
// ==========================================

function showProgress(title) {
    if (elements.progressOverlay) {
        elements.progressTitle.textContent = title;
        elements.progressBarFill.style.width = '0%';
        elements.progressText.textContent = '0%';
        elements.progressSize.textContent = 'Başlatılıyor...';
        elements.progressOverlay.classList.add('active');
    }
}

function updateProgress(percent, loaded, total) {
    if (elements.progressOverlay) {
        elements.progressBarFill.style.width = `${percent}%`;
        elements.progressText.textContent = `${Math.round(percent)}%`;
        if (total) {
            elements.progressSize.textContent = `${formatBytes(loaded)} / ${formatBytes(total)}`;
        } else {
            elements.progressSize.textContent = formatBytes(loaded);
        }
    }
}

function hideProgress() {
    if (elements.progressOverlay) {
        setTimeout(() => {
            elements.progressOverlay.classList.remove('active');
        }, 500);
    }
}

function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function downloadAuthorData(authorName) {
    // Tıklama event'i karta yayılmasın
    event.stopPropagation();
    const safeName = encodeURIComponent(authorName);
    downloadFileWithProgress(
        `${API_BASE}/api/export/author/${safeName}/zip`,
        `${authorName}_Arsiv.zip`
    );
}

// Global scope'a ekle (HTML onclick için gerekli)
window.downloadAuthorData = downloadAuthorData;

function updateFormFields() {
    const type = elements.recordType.value;

    // Tüm grupları gizle
    document.querySelectorAll('.type-group').forEach(el => el.style.display = 'none');

    // Seçili türü göster
    if (type === 'book') {
        document.getElementById('group-book').style.display = 'block';
    } else if (type === 'article') {
        document.getElementById('group-article').style.display = 'block';
    } else if (type === 'newspaper') {
        document.getElementById('group-newspaper').style.display = 'block';
    } else if (type === 'encyclopedia') {
        document.getElementById('group-encyclopedia').style.display = 'block';
    }
}

/// ==========================================
// DASHBOARD TÜR FİLTRELEME ENTEGRASYONU
// ==========================================

function filterRecordsByType(typeName) {
    console.log(`Seçilen Tür: ${typeName}`);

    // 1. Önce "Kayıtlar" sekmesine tıkla (Sayfa değişsin)
    const recordsNavLink = document.querySelector('[data-page="records"]');
    if (recordsNavLink) {
        recordsNavLink.click();
    }

    // 2. Sayfa geçişinin tamamlanması için çok kısa bekle (50ms)
    // Bu, sayfa yüklendiğinde varsayılan filtrelerin bizim seçimimizi ezmesini engeller.
    setTimeout(() => {
        const typeSelect = document.getElementById('recordsType');

        if (typeSelect) {
            // EŞLEŞTİRME HARİTASI (Mapping)
            // Sol taraf Dashboard'da yazan (Text), Sağ taraf Selectbox değeri (Value)
            // Burayı tam olarak HTML'indeki option value değerlerine göre ayarladık.
            const map = {
                'kitap': 'book',
                'makale': 'article',
                'gazete': 'newspaper',
                'ansiklopedi': 'encyclopedia',
                'dergi': 'article'
            };

            // Gelen metni temizle ve küçük harfe çevir
            const cleanName = typeName.trim().toLowerCase();

            // Haritadan değeri bul, yoksa kendisini kullan
            const targetValue = map[cleanName] || cleanName;

            console.log(`Filtreye uygulanan değer: ${targetValue}`); // Konsoldan kontrol edebilirsin

            // Değeri kutuya ata
            typeSelect.value = targetValue;

            // 3. Tabloyu Yenile (Backend'e yeni isteği gönder)
            if (typeof loadRecords === 'function') {
                // Sayfa numarasını 1'e çek ki sonuçlar görünsün
                if (typeof currentPage !== 'undefined') currentPage = 1;
                loadRecords();
            } else {
                // Eğer loadRecords global değilse butonu tetikle
                const searchInput = document.getElementById('recordsSearch');
                if (searchInput) searchInput.dispatchEvent(new Event('input'));
            }
        }
    }, 100); // 100 milisaniye gecikme
}

// Gözlemci (Observer) Kodu - Dashboard yüklendiğinde tıklama özelliği ekler
const typeListObserver = new MutationObserver(function (mutations) {
    const list = document.getElementById('typeDistList');
    if (list && list.children.length > 0 && !list.querySelector('.loading')) {

        Array.from(list.children).forEach(li => {
            // Sadece tür ismini al (Sayıyı temizle)
            // Genelde yapı: <li> Makale <span class="count">5</span> </li>
            // Clone alıp sadece text node'ları birleştiriyoruz
            const clone = li.cloneNode(true);
            const countSpan = clone.querySelector('.count'); // Varsa sayıyı çıkar
            if (countSpan) countSpan.remove();

            const typeName = clone.textContent.trim();

            li.style.cursor = 'pointer';
            li.onclick = function () {
                filterRecordsByType(typeName);
            };
        });
    }
});

// Gözlemciyi başlat
const typeListEl = document.getElementById('typeDistList');
if (typeListEl) {
    typeListObserver.observe(typeListEl, { childList: true });
}

function exportExcel() {
    window.location.href = `${API_BASE}/api/export/excel`;
    showToast('Excel dosyası indiriliyor...', 'success');
}

function initBulkSelectionEvents() {
    const checkboxes = document.querySelectorAll('.record-checkbox');

    // Elementlerin varlığını kontrol et (Hata almamak için)
    if (!elements.selectAllRecords || !elements.bulkActionBar) return;

    // --- SAYAÇ GÜNCELLEME FONKSİYONU ---
    const updateBulkBar = () => {
        const selectedCheckboxes = document.querySelectorAll('.record-checkbox:checked');
        const count = selectedCheckboxes.length;

        // Sayıyı HTML'e yaz
        if (elements.selectedCount) {
            elements.selectedCount.textContent = count;
        }

        // Barı Göster/Gizle (0'dan fazlaysa göster)
        elements.bulkActionBar.style.display = count > 0 ? 'flex' : 'none';

        // "Hepsini Seç" kutusunun durumunu güncelle
        elements.selectAllRecords.checked = (count === checkboxes.length && checkboxes.length > 0);
    };

    // --- EVENTLERİ BAĞLA ---

    // 1. Üstteki "Hepsini Seç" kutusu
    elements.selectAllRecords.onchange = () => {
        checkboxes.forEach(cb => {
            cb.checked = elements.selectAllRecords.checked;
            cb.closest('tr').classList.toggle('selected', elements.selectAllRecords.checked);
        });
        updateBulkBar();
    };

    // 2. Tablodaki tekil kutular
    checkboxes.forEach(cb => {
        cb.onchange = () => {
            cb.closest('tr').classList.toggle('selected', cb.checked);
            updateBulkBar();
        };
    });

    // --- İŞLEMLER (SİLME VE ZIP) ---

    // Toplu Silme Butonu
    elements.bulkDeleteBtn.onclick = async () => {
        const selectedIds = Array.from(document.querySelectorAll('.record-checkbox:checked')).map(cb => cb.value);
        if (confirm(`${selectedIds.length} adet kaydı silmek istediğinize emin misiniz?`)) {
            showProgress('Toplu Silme Yapılıyor...');
            try {
                for (const id of selectedIds) {
                    await apiDelete(`/api/records/${id}`);
                }
                showToast(`${selectedIds.length} kayıt silindi`, 'success');
                loadRecords(); // Tabloyu yenile
            } catch (error) {
                showToast('Hata oluştu', 'error');
            } finally {
                hideProgress();
            }
        }
    };

    // Seçimi İptal Et Butonu (X)
    elements.cancelSelectionBtn.onclick = () => {
        elements.selectAllRecords.checked = false;
        checkboxes.forEach(cb => {
            cb.checked = false;
            cb.closest('tr').classList.remove('selected');
        });
        updateBulkBar();
    };
}