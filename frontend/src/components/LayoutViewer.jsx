import React, { useState, useRef, useEffect } from 'react';
import { X, Brain, Target, Columns, Layout, BarChart3, ChevronLeft, ChevronRight, Wand2 } from 'lucide-react';
import axios from 'axios';

const LayoutViewer = ({ uploadedFileInfo, onClose }) => {
    const [currentPage, setCurrentPage] = useState(1);
    const [layoutData, setLayoutData] = useState(null);
    const [selectedMethod, setSelectedMethod] = useState('both');
    const [loading, setLoading] = useState(false);
    const [totalPages, setTotalPages] = useState(1);
    const [statistics, setStatistics] = useState(null);
    const [showStatistics, setShowStatistics] = useState(false);
    const [isPageInputActive, setIsPageInputActive] = useState(false);
    const [pageInputValue, setPageInputValue] = useState(1);
    const submittedRef = useRef(false);
    const pageInputRef = useRef(null);

    useEffect(() => {
        if (uploadedFileInfo) {
            loadLayoutForPage(currentPage);
        }
    }, [uploadedFileInfo, currentPage, selectedMethod]);

    useEffect(() => {
        if (isPageInputActive && pageInputRef.current) {
            pageInputRef.current.focus();
        }
    }, [isPageInputActive]);

    const loadLayoutForPage = async (pageNum) => {
        const pageNumber = Math.max(1, Math.min(pageNum, totalPages || 1));

        if (pageNumber === currentPage && !loading && layoutData) {
            if (
                (selectedMethod === 'surya' && layoutData.surya) ||
                (selectedMethod === 'yolo' && layoutData.yolo) ||
                (selectedMethod === 'both' && layoutData.surya && layoutData.yolo)
            ) {
                return;
            }
        }

        setCurrentPage(pageNumber);
        setLoading(true);

        try {
            const response = await axios.post('/api/layout-detection', {
                file_path: uploadedFileInfo.file_path,
                page_number: pageNumber,
                method: selectedMethod,
            });

            const data = response.data;
            if (data.success) {
                setLayoutData(data.results);
                setTotalPages(data.total_pages);
                if (data.total_pages > 0 && pageNumber !== currentPage) {
                    setCurrentPage(pageNumber);
                }
            } else {
                if (data.total_pages) setTotalPages(data.total_pages);
                console.error(data.error || 'Layout yüklenemedi');
            }
        } catch (error) {
            console.error(`Layout hatası: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handlePageInputSubmit = (e) => {
        const isEnter = e.type === 'keydown' && e.key === 'Enter';
        const isBlur = e.type === 'blur';

        if (isBlur && submittedRef.current) {
            submittedRef.current = false;
            return;
        }

        if (!isEnter && !isBlur) return;

        if (isEnter) {
            e.preventDefault();
            e.target.blur();
            submittedRef.current = true;
        }

        const newPage = parseInt(pageInputValue, 10);
        if (isNaN(newPage) || newPage < 1 || newPage > totalPages) {
            setPageInputValue(currentPage);
            setIsPageInputActive(false);
            return;
        }

        if (newPage !== currentPage) {
            loadLayoutForPage(newPage);
        }
        setIsPageInputActive(false);
    };

    const loadStatistics = async () => {
        try {
            const response = await axios.post('/api/layout-statistics', {
                file_path: uploadedFileInfo.file_path,
            });
            const data = response.data;
            if (data.success) {
                setStatistics(data.statistics);
                setShowStatistics(true);
            }
        } catch (error) {
            console.error('İstatistik yüklenemedi');
        }
    };

    const getTypeColor = (type) => {
        const colors = {
            title: '#DC143C',
            heading: '#B91C1C',
            paragraph: '#991B1B',
            text: '#7F1D1D',
            list: '#F59E0B',
            table: '#6B7280',
            figure: '#7C3AED',
            caption: '#EC4899',
            sectionheader: '#3B82F6',
            pageheader: '#8B5CF6',
            footer: '#6B7280',
        };
        return colors[type.toLowerCase()] || '#6B7280';
    };

    return (
        <div className="bg-white/95 backdrop-blur-xl rounded-3xl p-8 mt-8 shadow-2xl border-2 border-primary overflow-hidden relative">
            <div className="flex justify-between items-center mb-6">
                <h2 className="flex items-center gap-3 font-display text-3xl font-extrabold text-gray-900">
                    <Layout className="w-8 h-8 text-primary" />
                    Layout Görüntüleyici
                </h2>
                <button
                    onClick={onClose}
                    className="flex items-center gap-2 px-6 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold transition-all"
                >
                    <X className="w-5 h-5" /> Kapat
                </button>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-6 mb-8 pb-4 border-b-2 border-gray-100">
                <div className="flex gap-2">
                    {[
                        { id: 'surya', label: 'Surya Layout', icon: Brain },
                        { id: 'yolo', label: 'YOLO Layout', icon: Target },
                        { id: 'both', label: 'Karşılaştır', icon: Columns },
                    ].map((method) => (
                        <button
                            key={method.id}
                            onClick={() => setSelectedMethod(method.id)}
                            className={`flex items-center gap-2 px-5 py-3 rounded-xl font-bold transition-all border-2 ${selectedMethod === method.id
                                ? 'bg-primary text-white border-primary shadow-lg shadow-primary/20'
                                : 'bg-white text-gray-600 border-gray-200 hover:border-primary/50'
                                }`}
                        >
                            <method.icon className="w-5 h-5" />
                            {method.label}
                        </button>
                    ))}
                </div>

                <div className="flex items-center gap-4 bg-gray-50 px-5 py-3 rounded-2xl border-2 border-gray-200 shadow-inner">
                    <button
                        onClick={() => currentPage > 1 && loadLayoutForPage(currentPage - 1)}
                        disabled={currentPage === 1 || loading}
                        className="p-2 rounded-lg bg-white shadow-sm border border-gray-200 disabled:opacity-50 text-gray-700 hover:text-primary transition-colors"
                    >
                        <ChevronLeft className="w-5 h-5" />
                    </button>

                    {isPageInputActive ? (
                        <input
                            ref={pageInputRef}
                            type="number"
                            value={pageInputValue}
                            onChange={(e) => setPageInputValue(e.target.value)}
                            onBlur={handlePageInputSubmit}
                            onKeyDown={handlePageInputSubmit}
                            className="w-20 text-center font-mono font-bold bg-white border-2 border-primary rounded-lg py-1"
                        />
                    ) : (
                        <span
                            onClick={() => {
                                if (totalPages > 0) {
                                    setIsPageInputActive(true);
                                    setPageInputValue(currentPage);
                                }
                            }}
                            className="cursor-pointer text-primary underline font-mono font-bold"
                        >
                            Sayfa {currentPage}
                        </span>
                    )}
                    <span className="text-gray-500 font-bold"> / {totalPages}</span>

                    <button
                        onClick={() => currentPage < totalPages && loadLayoutForPage(currentPage + 1)}
                        disabled={currentPage === totalPages || loading}
                        className="p-2 rounded-lg bg-white shadow-sm border border-gray-200 disabled:opacity-50 text-gray-700 hover:text-primary transition-colors"
                    >
                        <ChevronRight className="w-5 h-5" />
                    </button>
                </div>

                <button
                    onClick={loadStatistics}
                    className="flex items-center gap-2 px-6 py-3 rounded-xl bg-primary text-white font-bold transition-all shadow-lg shadow-primary/30 hover:scale-105 active:scale-95"
                >
                    <BarChart3 className="w-5 h-5" /> İstatistikler
                </button>
            </div>

            {loading && (
                <div className="flex flex-col items-center justify-center py-24 bg-gray-50/50 rounded-3xl border-2 border-dashed border-primary/30">
                    <div className="animate-bounce">
                        <Wand2 className="w-12 h-12 text-primary" />
                    </div>
                    <p className="mt-4 text-gray-600 font-bold text-xl">Layout analizi yapılıyor...</p>
                </div>
            )}

            {!loading && layoutData && (
                <div className={`grid gap-8 mt-6 ${selectedMethod === 'both' ? 'grid-cols-2' : 'grid-cols-1'}`}>
                    {['surya', 'yolo'].map((key) => {
                        if (selectedMethod !== 'both' && selectedMethod !== key) return null;
                        const data = layoutData[key];
                        if (!data) return null;

                        return (
                            <div key={key} className="bg-white rounded-3xl overflow-hidden border-2 border-gray-200 shadow-xl flex flex-col">
                                <div className={`p-4 px-6 text-white flex justify-between items-center bg-gradient-to-r ${key === 'surya' ? 'from-primary to-primary-dark' : 'from-gray-700 to-gray-900'
                                    }`}>
                                    <span className="flex items-center gap-2 font-bold uppercase tracking-wider">
                                        {key === 'surya' ? <Brain className="w-5 h-5" /> : <Target className="w-5 h-5" />}
                                        {key.toUpperCase()} Layout Detection
                                    </span>
                                    <span className="bg-white text-primary px-3 py-1 rounded-full text-xs font-black">
                                        {data.detections.length} tespit
                                    </span>
                                </div>
                                <div className="p-6 bg-gray-50 flex-1 flex items-center justify-center">
                                    <img
                                        src={data.image}
                                        alt={`${key} Layout`}
                                        className="max-w-full h-auto rounded-xl shadow-2xl border-2 border-white"
                                    />
                                </div>
                                <div className="p-4 bg-white border-t border-gray-100 max-h-48 overflow-y-auto space-y-2">
                                    {data.detections.map((det, idx) => (
                                        <div key={idx} className="flex justify-between items-center p-3 rounded-xl bg-gray-50 border border-gray-100 hover:border-primary/30 transition-colors">
                                            <span
                                                className="px-3 py-1 rounded-lg text-white text-[10px] font-black uppercase"
                                                style={{ backgroundColor: getTypeColor(det.type) }}
                                            >
                                                {det.type}
                                            </span>
                                            <span className={`font-mono font-bold text-sm ${det.confidence > 0.8 ? 'text-green-600' : det.confidence > 0.6 ? 'text-yellow-600' : 'text-primary'
                                                }`}>
                                                {(det.confidence * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {showStatistics && statistics && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-2xl z-[5000] flex items-center justify-center p-8" onClick={() => setShowStatistics(false)}>
                    <div className="bg-white rounded-[40px] p-10 max-w-2xl w-full border-4 border-primary shadow-2xl relative animate-in fade-in zoom-in duration-300" onClick={e => e.stopPropagation()}>
                        <h2 className="text-3xl font-display font-black text-gray-900 mb-8 flex items-center gap-4">
                            <BarChart3 className="w-10 h-10 text-primary" />
                            Layout İstatistikleri
                        </h2>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                            {[
                                { label: 'Toplam Sayfa', value: statistics.total_pages, gradient: 'from-primary to-primary-dark' },
                                { label: 'Surya Tespitleri', value: statistics.pages.reduce((sum, p) => sum + p.surya.count, 0), gradient: 'from-blue-600 to-blue-800' },
                                { label: 'YOLO Tespitleri', value: statistics.pages.reduce((sum, p) => sum + p.yolo.count, 0), gradient: 'from-green-600 to-green-800' },
                            ].map((stat, i) => (
                                <div key={i} className={`bg-gradient-to-br ${stat.gradient} p-8 rounded-3xl text-white text-center shadow-xl`}>
                                    <div className="text-4xl font-black mb-2">{stat.value}</div>
                                    <div className="text-xs font-bold uppercase tracking-widest opacity-80">{stat.label}</div>
                                </div>
                            ))}
                        </div>
                        <button
                            onClick={() => setShowStatistics(false)}
                            className="w-full py-5 rounded-2xl bg-gray-900 text-white font-black text-xl hover:bg-gray-800 transition-all shadow-xl"
                        >
                            ANLADIM, KAPAT
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default LayoutViewer;
