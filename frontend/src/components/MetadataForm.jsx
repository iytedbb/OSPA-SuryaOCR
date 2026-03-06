import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Book, FileText, Newspaper, Library, Info, Search, Loader2, Zap } from 'lucide-react';

const MetadataForm = ({
    metadataType,
    setMetadataType,
    metadata,
    handleMetadataChange,
    identifierValue,
    setIdentifierValue,
    fetchMetadataFromIdentifier,
    fetchingMetadata,
    completeness
}) => {
    const types = [
        { id: 'book', label: 'Kitap', icon: Book },
        { id: 'article', label: 'Makale', icon: FileText },
        { id: 'newspaper', label: 'Gazete', icon: Newspaper },
        { id: 'encyclopedia', label: 'Ansiklopedi', icon: Library }
    ];

    const schemas = {
        book: [
            { key: 'title', label: 'Başlık', required: true },
            { key: 'author', label: 'Yazar', required: true },
            { key: 'publication_year', label: 'Yayın Yılı', type: 'number', required: true },
            { key: 'publication_city', label: 'Yayın Yeri', required: true },
            { key: 'publisher', label: 'Yayınevi' },
            { key: 'country', label: 'Yayınlandığı Ülke' },
            { key: 'language', label: 'Dil', type: 'select', options: [{ value: 'tr', label: 'Türkçe' }, { value: 'en', label: 'İngilizce' }, { value: 'de', label: 'Almanca' }, { value: 'fr', label: 'Fransızca' }, { value: 'ot', label: 'Osmanlıca' }, { value: 'other', label: 'Diğer' }] },
            { key: 'editor', label: 'Hazırlayan/Derleyen/Editör' },
            { key: 'edition', label: 'Baskı' },
            { key: 'volume', label: 'Cilt' },
            { key: 'series', label: 'Dizi' },
            { key: 'page_count', label: 'Sayfa Sayısı', type: 'number' },
            { key: 'isbn', label: 'ISBN' },
            { key: 'url', label: 'URL', type: 'url' },
            { key: 'archive', label: 'Arşiv' },
            { key: 'archive_location', label: 'Arşivdeki Yeri' },
            { key: 'library_catalog', label: 'Kütüphane Kataloğu' },
            { key: 'call_number', label: 'Yer Numarası' },
            { key: 'rights', label: 'Haklar' }
        ],
        article: [
            { key: 'title', label: 'Başlık', required: true },
            { key: 'author', label: 'Yazar', required: true },
            { key: 'publication', label: 'Yayınlandığı Dergi', required: true },
            { key: 'date', label: 'Tarih', type: 'date', required: true },
            { key: 'publisher', label: 'Yayınevi' },
            { key: 'volume', label: 'Cilt' },
            { key: 'issue', label: 'Sayı' },
            { key: 'pages', label: 'Sayfa' },
            { key: 'publication_city', label: 'Yayın Yeri' },
            { key: 'country', label: 'Yayınlandığı Ülke' },
            { key: 'language', label: 'Dil', type: 'select', options: [{ value: 'tr', label: 'Türkçe' }, { value: 'en', label: 'İngilizce' }, { value: 'de', label: 'Almanca' }, { value: 'fr', label: 'Fransızca' }, { value: 'ot', label: 'Osmanlıca' }, { value: 'other', label: 'Diğer' }] },
            { key: 'doi', label: 'DOI' },
            { key: 'issn', label: 'ISSN' },
            { key: 'journal_abbreviation', label: 'Dergi Kısaltması' },
            { key: 'series_title', label: 'Seri Başlığı' },
            { key: 'url', label: 'URL', type: 'url' },
            { key: 'archive', label: 'Arşiv' },
            { key: 'archive_location', label: 'Arşivdeki Yeri' },
            { key: 'rights', label: 'Haklar' }
        ],
        newspaper: [
            { key: 'newspaper_name', label: 'Gazete Adı', required: true },
            { key: 'date', label: 'Tarih', type: 'date', required: true },
            { key: 'publication_place', label: 'Yayın Yeri', required: true },
            { key: 'pages', label: 'Sayfa (Tek)', required: true },
            { key: 'title', label: 'Haber/Yazı Başlığı' },
            { key: 'author', label: 'Yazar' },
            { key: 'page_range', label: 'Sayfa Aralığı' },
            { key: 'section', label: 'Bölüm' },
            { key: 'column_name', label: 'Köşe Adı' },
            { key: 'edition', label: 'Baskı' },
            { key: 'language', label: 'Dil', type: 'select', options: [{ value: 'tr', label: 'Türkçe' }, { value: 'en', label: 'İngilizce' }, { value: 'de', label: 'Almanca' }, { value: 'fr', label: 'Fransızca' }, { value: 'ot', label: 'Osmanlıca' }, { value: 'other', label: 'Diğer' }] },
            { key: 'issn', label: 'ISSN' },
            { key: 'url', label: 'URL', type: 'url' },
            { key: 'archive', label: 'Arşiv' },
            { key: 'rights', label: 'Haklar' }
        ],
        encyclopedia: [
            { key: 'title', label: 'Madde Başlığı', required: true },
            { key: 'encyclopedia_title', label: 'Ansiklopedi Adı', required: true },
            { key: 'publisher', label: 'Yayınevi', required: true },
            { key: 'publication_city', label: 'Yayın Yeri', required: true },
            { key: 'language', label: 'Dil', type: 'select', options: [{ value: 'tr', label: 'Türkçe' }, { value: 'en', label: 'İngilizce' }, { value: 'de', label: 'Almanca' }, { value: 'fr', label: 'Fransızca' }, { value: 'ot', label: 'Osmanlıca' }, { value: 'other', label: 'Diğer' }] },
            { key: 'publication_year', label: 'Yayın Yılı', type: 'number' },
            { key: 'short_title', label: 'Kısa Başlık' },
            { key: 'author', label: 'Yazar' },
            { key: 'volume', label: 'Cilt' },
            { key: 'pages', label: 'Sayfa' },
            { key: 'access_date', label: 'Erişim Tarihi', type: 'date' },
            { key: 'isbn', label: 'ISBN' },
            { key: 'url', label: 'URL', type: 'url' },
            { key: 'archive', label: 'Arşiv' },
            { key: 'rights', label: 'Haklar' }
        ]
    };

    return (
        <div className="space-y-12 animate-in fade-in slide-in-from-bottom-8 duration-700">
            <div className="text-center max-w-2xl mx-auto">
                <h2 className="text-4xl font-display font-black text-gray-900 mb-4 tracking-tight" id="metadata-title">
                    Belge <span className="text-primary italic">Bilgileri</span>
                </h2>
                <p className="text-gray-500 font-medium">
                    Belgeniz için gerekli tanımlayıcı bilgileri girin. Yıldızlı (*) alanlar zorunludur.
                </p>
            </div>

            <div className="bg-white rounded-[40px] shadow-2xl shadow-gray-200/50 border border-gray-100 p-10">
                <div className="flex flex-col md:flex-row gap-12">
                    {/* Sidebar / Types */}
                    <div className="w-full md:w-64 space-y-4">
                        <h4 className="text-xs font-black uppercase tracking-[0.2em] text-gray-400 mb-6 flex items-center gap-2">
                            <span className="w-4 h-px bg-gray-200"></span> Belge Türü
                        </h4>
                        {types.map((type) => (
                            <button
                                key={type.id}
                                onClick={() => setMetadataType(type.id)}
                                className={`w-full flex items-center gap-4 p-4 rounded-2xl font-bold transition-all ${metadataType === type.id
                                    ? 'bg-primary text-white shadow-lg shadow-primary/20 scale-105'
                                    : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
                                    }`}
                            >
                                <type.icon className="w-5 h-5" />
                                {type.label}
                            </button>
                        ))}

                        {metadataType && (
                            <div className="mt-12 p-6 rounded-3xl bg-gray-50 border border-gray-100">
                                <div className="flex justify-between items-end mb-4">
                                    <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Doluluk</span>
                                    <span className="text-lg font-display font-black text-primary">{completeness}%</span>
                                </div>
                                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${completeness}%` }}
                                        className="h-full bg-primary"
                                    />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Form Content */}
                    <div className="flex-1">
                        <AnimatePresence mode="wait">
                            {!metadataType ? (
                                <motion.div
                                    key="no-type"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    className="h-full flex flex-col items-center justify-center text-center p-12 border-4 border-dashed border-gray-100 rounded-[32px]"
                                >
                                    <div className="w-20 h-20 bg-gray-50 rounded-full flex items-center justify-center text-gray-300 mb-6">
                                        <Info className="w-10 h-10" />
                                    </div>
                                    <h5 className="text-xl font-black text-gray-900 mb-2">Henüz Seçim Yapılmadı</h5>
                                    <p className="text-gray-400 text-sm font-medium">Lütfen soldan belge türünü seçerek devam edin.</p>
                                </motion.div>
                            ) : (
                                <motion.div
                                    key={metadataType}
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -20 }}
                                    className="space-y-8"
                                >
                                    {/* Auto-fetch section */}
                                    {(metadataType === 'article' || metadataType === 'book') && (
                                        <div className="p-8 rounded-[32px] bg-primary/5 border-2 border-primary/10">
                                            <h5 className="text-sm font-black uppercase tracking-tight text-primary-dark mb-4 flex items-center gap-2">
                                                <Zap className="w-4 h-4" /> Otomatik Doldur
                                            </h5>
                                            <div className="flex gap-3">
                                                <div className="relative flex-1">
                                                    <input
                                                        type="text"
                                                        placeholder={metadataType === 'book' ? "ISBN girin..." : "DOI veya arXiv ID girin..."}
                                                        value={identifierValue}
                                                        onChange={(e) => setIdentifierValue(e.target.value)}
                                                        className="w-full bg-white border-2 border-white focus:border-primary px-6 py-4 rounded-2xl outline-none font-medium transition-all shadow-sm"
                                                    />
                                                </div>
                                                <button
                                                    onClick={fetchMetadataFromIdentifier}
                                                    disabled={fetchingMetadata}
                                                    className="px-8 bg-primary text-white font-bold rounded-2xl hover:bg-primary-dark transition-all flex items-center gap-2 shadow-lg shadow-primary/20 disabled:opacity-50"
                                                >
                                                    {fetchingMetadata ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                                                    Getir
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    {/* Dynamic Fields */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        {schemas[metadataType].map((field) => (
                                            <div key={field.key} className="space-y-2">
                                                <label className="text-xs font-black uppercase tracking-widest text-gray-400 ml-1">
                                                    {field.label} {field.required && <span className="text-primary">*</span>}
                                                </label>

                                                {field.type === 'select' ? (
                                                    <div className="space-y-2">
                                                        <div className="relative">
                                                            <select
                                                                value={metadata[field.key] && field.options.some(opt => opt.value === metadata[field.key]) ? metadata[field.key] : (metadata[field.key] ? 'other' : (field.key === 'language' ? 'tr' : ''))}
                                                                onChange={(e) => {
                                                                    const val = e.target.value;
                                                                    if (val === 'other') {
                                                                        handleMetadataChange(field.key, ''); // Clear to let user type
                                                                    } else {
                                                                        handleMetadataChange(field.key, val);
                                                                    }
                                                                }}
                                                                className={`w-full bg-gray-50 border-2 border-gray-100 focus:border-primary/30 focus:bg-white px-5 py-3 rounded-xl outline-none transition-all font-medium appearance-none ${field.required && !metadata[field.key] && field.key !== 'language' ? 'border-primary/20 bg-white' : ''}`}
                                                            >
                                                                {field.options && field.options.map(opt => (
                                                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                                                ))}
                                                            </select>
                                                            <div className="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none text-gray-400">
                                                                <svg className="w-4 h-4 fill-current" viewBox="0 0 20 20"><path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" fillRule="evenodd"></path></svg>
                                                            </div>
                                                        </div>
                                                        {(!metadata[field.key] || !field.options.some(opt => opt.value === metadata[field.key])) && (metadata[field.key] !== undefined || field.key !== 'language') && (
                                                            // Show input if value is not in options (custom) OR if explicitly 'other' selected (which clears value)
                                                            // Logic: If current value is NOT in options, show input.
                                                            // Exception: Initial load for language is 'tr' (in options).
                                                            // If user selects 'other', we set value to ''. '' is not in options, so input shows.
                                                            // But we need to distinguish between "empty because just opened" and "empty because other selected".
                                                            // Actually, if value is '' and field is language, default is 'tr'.
                                                            // Let's rely on the select value logic above.
                                                            // If select value resolves to 'other', show input.
                                                            (metadata[field.key] && !field.options.some(opt => opt.value === metadata[field.key])) || (metadata[field.key] === '') ? (
                                                                <input
                                                                    type="text"
                                                                    value={metadata[field.key] || ''}
                                                                    onChange={(e) => handleMetadataChange(field.key, e.target.value)}
                                                                    className="w-full bg-white border-2 border-primary/20 focus:border-primary px-5 py-3 rounded-xl outline-none transition-all font-medium animate-in fade-in slide-in-from-top-1"
                                                                    placeholder="Lütfen dili yazınız..."
                                                                    autoFocus
                                                                />
                                                            ) : null
                                                        )}
                                                    </div>
                                                ) : (
                                                    <input
                                                        type={field.type || 'text'}
                                                        value={metadata[field.key] || ''}
                                                        onChange={(e) => handleMetadataChange(field.key, e.target.value)}
                                                        className={`w-full bg-gray-50 border-2 border-gray-100 focus:border-primary/30 focus:bg-white px-5 py-3 rounded-xl outline-none transition-all font-medium ${field.required && !metadata[field.key] ? 'border-primary/20 bg-white' : ''
                                                            }`}
                                                        placeholder={field.required ? 'Zorunlu alan' : ''}
                                                    />
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MetadataForm;
