import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, Timer, Clock, Layers } from 'lucide-react';

const ProcessingView = ({
    processingProgress,
    processingStep,
    currentPage,
    totalPages,
    liveStats,
    elapsedTime,
    userFriendlyStatus,
    layoutEngine
}) => {
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* COMPACT TOP HEADER */}
            <div className="flex justify-between items-center bg-white px-8 py-5 rounded-3xl border border-gray-100 shadow-sm">
                <div>
                    <h2 className="text-2xl font-display font-black text-gray-900 tracking-tight">
                        Sistem <span className="text-primary italic">Çalışıyor</span>
                    </h2>
                    <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mt-1">
                        Motor: <span className="text-primary">{layoutEngine?.toUpperCase() || 'SURYA'}</span> • {processingStep}
                    </p>
                </div>
                <div className="text-right">
                    <div className="text-3xl font-display font-black text-primary">{Math.round(processingProgress)}%</div>
                    <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Tamamlandı</div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">

                {/* LEFT COLUMN: LIVE SCANNER (Primary) */}
                <div className="lg:col-span-12 xl:col-span-7">
                    <div className="scanner-container !min-h-[500px] lg:!min-h-[620px] h-full">
                        <div className="processing-badge">Canlı Analiz</div>

                        <div className="scanner-line"></div>
                        <div className="scanner-overlay"></div>

                        <AnimatePresence mode="wait">
                            {liveStats.preview_image_url ? (
                                <motion.img
                                    key={currentPage}
                                    initial={{ opacity: 0, scale: 1.02 }}
                                    animate={{ opacity: 0.9, scale: 1 }}
                                    exit={{ opacity: 0 }}
                                    transition={{ duration: 0.4 }}
                                    src={liveStats.preview_image_url}
                                    className="live-preview-image max-h-[560px]"
                                    alt="Live Scanning"
                                />
                            ) : (
                                <div className="flex flex-col items-center justify-center text-gray-300">
                                    <Loader2 className="w-12 h-12 animate-spin mb-4 opacity-50" />
                                    <div className="text-xs font-black uppercase tracking-[0.3em]">Bekleniyor...</div>
                                </div>
                            )}
                        </AnimatePresence>

                        {/* Decoration Accents */}
                        <div className="absolute top-0 left-0 w-12 h-12 border-t-4 border-l-4 border-primary/20 rounded-tl-3xl m-6"></div>
                        <div className="absolute top-0 right-0 w-12 h-12 border-t-4 border-r-4 border-primary/20 rounded-tr-3xl m-6"></div>
                        <div className="absolute bottom-0 left-0 w-12 h-12 border-b-4 border-l-4 border-primary/20 rounded-bl-3xl m-6"></div>
                        <div className="absolute bottom-0 right-0 w-12 h-12 border-b-4 border-r-4 border-primary/20 rounded-br-3xl m-6"></div>
                    </div>
                </div>

                {/* RIGHT COLUMN: PROGRESS & STATS (Dashboard) */}
                <div className="lg:col-span-12 xl:col-span-5 space-y-6">

                    {/* Status & Page Info Card */}
                    <div className="bg-white p-8 rounded-[40px] border border-gray-100 shadow-sm space-y-8">
                        <div className="flex justify-between items-start">
                            <div className="space-y-1">
                                <div className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em]">İşlem Durumu</div>
                                <div className="text-2xl font-display font-black text-gray-900 leading-none">
                                    Sayfa {currentPage} <span className="text-gray-300 font-medium">/ {totalPages}</span>
                                </div>
                            </div>
                            <div className="p-4 bg-red-50 text-primary rounded-2xl shadow-inner">
                                <Layers className="w-7 h-7" />
                            </div>
                        </div>

                        {/* Compact Stats Grid */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-gray-50/50 p-5 rounded-3xl border border-gray-100/50">
                                <div className="flex items-center gap-2 mb-2 text-primary">
                                    <Timer className="w-4 h-4" />
                                    <span className="text-[10px] font-black uppercase tracking-widest">Geçen Süre</span>
                                </div>
                                <div className="text-xl font-black text-gray-900">{elapsedTime}</div>
                            </div>
                            <div className="bg-gray-50/50 p-5 rounded-3xl border border-gray-100/50">
                                <div className="flex items-center gap-2 mb-2 text-blue-500">
                                    <Clock className="w-4 h-4" />
                                    <span className="text-[10px] font-black uppercase tracking-widest">Tahmini Kalan</span>
                                </div>
                                <div className="text-xl font-black text-gray-900">{liveStats.remainingTimeText || "---"}</div>
                            </div>
                        </div>

                        {/* Mini Progress Bar Detail */}
                        <div className="space-y-3">
                            <div className="flex justify-between text-[10px] font-black uppercase tracking-widest text-gray-400">
                                <span>İş akışı ilerlemesi</span>
                                <span>{Math.round(processingProgress)}%</span>
                            </div>
                            <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${processingProgress}%` }}
                                    className="h-full bg-primary shadow-[0_0_15px_rgba(185,54,50,0.4)]"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Dashboard Logs Terminal */}
                    <div className="bg-gray-900 rounded-[40px] p-8 font-mono text-[11px] overflow-hidden shadow-2xl border border-white/5 relative h-[300px] flex flex-col group">
                        <div className="flex gap-2 mb-5 shrink-0">
                            <div className="w-3 h-3 rounded-full bg-red-500/30"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-500/30"></div>
                            <div className="w-3 h-3 rounded-full bg-green-500/30"></div>
                            <span className="ml-4 text-[10px] font-bold text-white/30 uppercase tracking-[0.2em]">Power Engine Console</span>
                        </div>

                        <div className="space-y-4 text-white/60 overflow-y-auto flex-1 pr-2 custom-scrollbar scroll-smooth">
                            <div className="flex gap-4 leading-relaxed">
                                <span className="text-primary/70 shrink-0 select-none">[{new Date().toLocaleTimeString()}]</span>
                                <span>GPU acceleration pipeline synchronized.</span>
                            </div>
                            <div className="flex gap-4 leading-relaxed">
                                <span className="text-primary/70 shrink-0 select-none">[{new Date().toLocaleTimeString()}]</span>
                                <span>Batch mode: High Efficiency Active.</span>
                            </div>
                            {processingStep && (
                                <motion.div
                                    key={processingStep + currentPage}
                                    initial={{ opacity: 0, x: -5 }} animate={{ opacity: 1, x: 0 }}
                                    className="flex gap-4 leading-relaxed text-green-400"
                                >
                                    <span className="font-bold shrink-0">[{new Date().toLocaleTimeString()}]</span>
                                    <span>{processingStep.toUpperCase()}...</span>
                                </motion.div>
                            )}
                            <div className="opacity-20 flex gap-4 animate-pulse">
                                <span className="shrink-0">[{new Date().toLocaleTimeString()}]</span>
                                <span>Listening for engine callbacks...</span>
                            </div>
                        </div>

                        <div className="absolute top-0 right-0 p-10 pointer-events-none opacity-[0.03] group-hover:opacity-[0.07] transition-opacity">
                            <Loader2 className="w-32 h-32 text-white animate-spin-slow" />
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
};

export default ProcessingView;
