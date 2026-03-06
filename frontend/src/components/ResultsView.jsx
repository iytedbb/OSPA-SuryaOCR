import React from 'react';
import { motion } from 'framer-motion';
import { Download, FileDown, Home, RefreshCcw, FileType, CheckCircle, Search, Layout } from 'lucide-react';
import axios from 'axios';

const ResultsView = ({
    results,
    onRestart,
    onReset,
    onShowLayout,
    downloadableOutputs,
    totalDownloadableFiles,
    metadata,
    metadataType
}) => {

    // Helper to generate filename from metadata
    const generateFilename = (ext) => {
        if (!metadata || Object.keys(metadata).length === 0) {
            return `ospa_ocr_result.${ext}`;
        }

        try {
            // "Ağaoğlu, A. (1949). Serbest Fırka Hatıraları, Nebioğlu Yayınevi, İstanbul"
            let parts = [];

            // Author logic: Try to format as "Last, F." if possible, else use as is
            if (metadata.author) {
                // Simple heuristic: if 2+ words, assume "First Last" -> "Last, F."
                // But Turkish names can be complex. Let's just use what they entered but formatted.
                // Or follow user example strictly? User example: "Ağaoğlu, A."
                // Let's assume user entered exactly that or we keep it simple.
                // Keeping it simple: Just use the author field directly.
                parts.push(`${metadata.author}`);
            }

            // Year
            let year = metadata.publication_year || metadata.date;
            if (year) {
                // Extract year if full date
                if (year.length > 4) year = year.substring(0, 4);
                parts.push(`(${year})`);
            }

            // Title
            if (metadata.title) {
                parts.push(`${metadata.title}`);
            }

            // Publisher
            if (metadata.publisher) {
                parts.push(`${metadata.publisher}`); // Publisher name
            } else if (metadata.newspaper_name) {
                parts.push(`${metadata.newspaper_name}`);
            }

            // City / Location
            if (metadata.publication_city || metadata.publication_place) {
                let place = metadata.publication_city || metadata.publication_place;
                parts.push(`${place}`);
            }

            if (parts.length === 0) return `ospa_ocr_result.${ext}`;

            // Join with logical separators based on user example:
            // "Author (Year). Title, Publisher, City"
            // Our parts list isn't granular enough for perfect punctuation insertion unless we know which index is which.

            // Let's build strictly:
            let filename = "";

            if (metadata.author) filename += `${metadata.author}`;

            let y = metadata.publication_year || metadata.date;
            if (y) filename += (filename ? " " : "") + `(${y.substring(0, 4)}).`;

            if (metadata.title) filename += (filename ? " " : "") + `${metadata.title},`;

            if (metadata.publisher || metadata.newspaper_name) {
                filename += (filename ? " " : "") + `${metadata.publisher || metadata.newspaper_name},`;
            }

            if (metadata.publication_city || metadata.publication_place) {
                filename += (filename ? " " : "") + `${metadata.publication_city || metadata.publication_place}.`;
            }

            // Sanitize filename
            filename = filename.replace(/[/\\?%*:|"<>]/g, '-').trim();

            if (!filename) return `ospa_ocr_result.${ext}`;

            // Add extension
            return `${filename}.${ext}`;

        } catch (e) {
            console.error("Filename generation error:", e);
            return `ospa_ocr_result.${ext}`;
        }
    };

    const downloadFile = (format, content) => {
        const filename = generateFilename(format);
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const downloadAllFiles = async () => {
        // Use the new /download-zip endpoint which echoes back the content in a zip
        // This avoids DB dependency issues.
        try {
            // Prepare payload
            const files = {};
            downloadableOutputs.forEach(([format, content]) => {
                files[format] = content;
            });

            const filenameBase = generateFilename('zip').replace('.zip', ''); // Remove .zip if added by logic

            const response = await axios.post('/api/download-zip', {
                filename_base: filenameBase,
                files: files
            }, {
                responseType: 'blob'
            });

            // Trigger download
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `${filenameBase}.zip`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);

        } catch (error) {
            console.error("Download all failed:", error);
            alert("İndirme işlemi başlatılamadı.");
        }
    };

    return (
        <div className="space-y-12 animate-in fade-in slide-in-from-bottom-8 duration-700 pb-20">
            <div className="text-center max-w-2xl mx-auto">
                <div className="w-20 h-20 bg-green-500 rounded-3xl flex items-center justify-center text-white shadow-xl shadow-green-500/20 mx-auto mb-6">
                    <CheckCircle className="w-10 h-10" />
                </div>
                <h2 className="text-4xl font-display font-black text-gray-900 mb-4 tracking-tight" id="results-title">
                    İşlem <span className="text-primary italic">Tamamlandı</span>
                </h2>
                <p className="text-gray-500 font-medium">Belgeniz başarıyla işlendi. Sonuçları aşağıda inceleyebilir ve indirebilirsiniz.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 max-w-7xl mx-auto">
                {/* Main Outputs */}
                <div className="lg:col-span-2 space-y-8">
                    {downloadableOutputs.map(([format, content]) => (
                        <motion.div
                            key={format}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="bg-white rounded-[40px] shadow-xl border border-gray-100 overflow-hidden"
                        >
                            <div className="p-8 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
                                <div className="flex items-center gap-4">
                                    <div className={`w-12 h-12 rounded-2xl flex items-center justify-center bg-white shadow-sm border border-gray-100`}>
                                        <FileType className="w-6 h-6 text-primary" />
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-black text-gray-900 uppercase tracking-tight">{format} Çıktısı</h3>
                                        <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">{content.length} karakter işlendi</p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => downloadFile(format, content)}
                                    className="p-3 rounded-xl bg-primary text-white hover:bg-primary-dark transition-all shadow-lg shadow-primary/20"
                                >
                                    <Download className="w-5 h-5" />
                                </button>
                            </div>
                            <div className="p-10 font-mono text-sm text-gray-600 bg-white max-h-[500px] overflow-y-auto leading-relaxed whitespace-pre-wrap">
                                {content}
                            </div>
                        </motion.div>
                    ))}
                </div>

                {/* Action Sidebar */}
                <div className="space-y-8">
                    {/* Download Center */}
                    <div className="bg-gray-900 text-white p-8 rounded-[40px] shadow-2xl relative overflow-hidden">
                        <h4 className="font-display font-bold text-xl mb-8 flex items-center gap-3 relative z-10">
                            <Download className="w-6 h-6 text-primary-light" />
                            İndirme Merkezi
                        </h4>

                        <div className="space-y-4 relative z-10">
                            {totalDownloadableFiles > 1 && (
                                <button
                                    onClick={downloadAllFiles}
                                    className="w-full py-5 bg-gradient-to-r from-green-500 to-green-700 rounded-2xl font-black text-white shadow-xl shadow-green-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all flex flex-col items-center"
                                >
                                    <span className="flex items-center gap-2 text-lg">
                                        <FileDown className="w-6 h-6" /> TÜMÜNÜ İNDİR
                                    </span>
                                    <span className="text-[10px] opacity-70 uppercase tracking-widest mt-1">Zip Arşivi ({totalDownloadableFiles} Dosya)</span>
                                </button>
                            )}

                            <div className="grid grid-cols-2 gap-3">
                                {downloadableOutputs.map(([format, content]) => (
                                    <button
                                        key={format}
                                        onClick={() => downloadFile(format, content)}
                                        className="py-3 bg-white/10 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-white/20 transition-all border border-white/10"
                                    >
                                        {format.toUpperCase()} (. {format})
                                    </button>
                                ))}
                            </div>
                        </div>

                        <Layout className="absolute -bottom-8 -right-8 w-48 h-48 text-white/5" />
                    </div>

                    {/* Quick Actions */}
                    <div className="bg-white p-8 rounded-[40px] shadow-xl border border-gray-100 space-y-4">
                        <button
                            onClick={onShowLayout}
                            className="w-full py-4 rounded-2xl bg-primary/5 text-primary font-black flex items-center justify-center gap-3 hover:bg-primary/10 transition-all"
                        >
                            <Search className="w-5 h-5" /> LAYOUT GÖZDEN GEÇİR
                        </button>
                        <div className="grid grid-cols-2 gap-4">
                            <button
                                onClick={onRestart}
                                className="py-4 rounded-2xl bg-gray-50 text-gray-600 font-bold text-xs flex items-center justify-center gap-2 hover:bg-gray-100 transition-all uppercase tracking-widest"
                            >
                                <RefreshCcw className="w-4 h-4" /> Yeniden
                            </button>
                            <button
                                onClick={onReset}
                                className="py-4 rounded-2xl bg-gray-50 text-gray-600 font-bold text-xs flex items-center justify-center gap-2 hover:bg-gray-100 transition-all uppercase tracking-widest"
                            >
                                <Home className="w-4 h-4" /> Anasayfa
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ResultsView;
