import React, { useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, File, X, Brain, Zap, Loader2, Info } from 'lucide-react';

const FileUploader = ({
    selectedFile,
    uploadedFileInfo,
    isUploading,
    isDragOver,
    onFileSelect,
    onDrop,
    onDragOver,
    onDragLeave,
    processingType,
    setProcessingType
}) => {
    const fileInputRef = useRef(null);

    const containerVariants = {
        idle: { scale: 1, borderColor: 'rgba(185, 54, 50, 0.1)' },
        dragOver: { scale: 1.02, borderColor: 'rgba(185, 54, 50, 1)', backgroundColor: 'rgba(185, 54, 50, 0.05)' }
    };

    const handleTypeSelect = (type) => {
        setProcessingType(type);

        // İleri butonuna kaydır
        // Bazen React state güncellemeleri ve animasyonlar (opacity/height) 
        // DOM'un son halini almasını geciktirebilir. Bu yüzden biraz daha bekliyoruz.
        const scrollToNext = () => {
            const nextBtn = document.getElementById('next-step-button');
            if (nextBtn) {
                nextBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });

                // Yedek: Eğer buton hala görünür değilse window seviyesinde kaydır
                const rect = nextBtn.getBoundingClientRect();
                if (rect.top > window.innerHeight || rect.top < 0) {
                    window.scrollTo({
                        top: window.pageYOffset + rect.top - (window.innerHeight / 2),
                        behavior: 'smooth'
                    });
                }
            }
        };

        // İki aşamalı kaydırma (biri hızlı, biri animasyonlar bitince)
        setTimeout(scrollToNext, 400);
        setTimeout(scrollToNext, 800);
    };

    return (
        <div className="space-y-12 animate-in fade-in slide-in-from-bottom-8 duration-700">
            <div className="text-center max-w-2xl mx-auto">
                <h2 className="text-4xl font-display font-black text-gray-900 mb-4 tracking-tight" id="upload-title">
                    Belgenizi <span className="text-primary italic">Yükleyin</span>
                </h2>
                <p className="text-gray-500 font-medium">
                    Tarihsel belgelerinizi, gazetelerinizi veya akademik mecmualarınızı sürükleyip bırakın.
                    Sistemimiz en uygun modelleri sizin için seçecektir.
                </p>
            </div>

            <motion.div
                variants={containerVariants}
                animate={isDragOver ? "dragOver" : "idle"}
                onDrop={onDrop}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onClick={() => fileInputRef.current?.click()}
                className="relative group cursor-pointer aspect-video md:aspect-[21/9] rounded-[40px] border-4 border-dashed border-gray-200 flex flex-col items-center justify-center transition-all overflow-hidden bg-white hover:border-primary/50 hover:bg-red-50/30"
            >
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={(e) => onFileSelect(e.target.files[0])}
                    className="hidden"
                    accept=".pdf,.png,.jpg,.jpeg,.tiff"
                />

                <AnimatePresence mode="wait">
                    {isUploading ? (
                        <motion.div
                            key="loading"
                            initial={{ opacity: 0, scale: 0.8 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.8 }}
                            className="flex flex-col items-center"
                        >
                            <div className="relative">
                                <Loader2 className="w-20 h-20 text-primary animate-spin" />
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <Upload className="w-6 h-6 text-primary" />
                                </div>
                            </div>
                            <p className="mt-6 font-bold text-primary animate-pulse uppercase tracking-[0.2em] text-xs">Yükleniyor...</p>
                        </motion.div>
                    ) : uploadedFileInfo ? (
                        <motion.div
                            key="uploaded"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="flex flex-col items-center text-center p-8"
                        >
                            <div className="w-20 h-20 bg-green-500 rounded-3xl flex items-center justify-center text-white shadow-xl shadow-green-500/20 mb-6">
                                <File className="w-10 h-10" />
                            </div>
                            <h3 className="text-2xl font-black text-gray-900 mb-2 truncate max-w-md">{selectedFile?.name}</h3>
                            <div className="flex gap-4">
                                <span className="text-xs font-bold uppercase tracking-widest text-gray-400 bg-gray-100 px-3 py-1 rounded-full">
                                    {uploadedFileInfo.page_count} Sayfa
                                </span>
                                <span className="text-xs font-bold uppercase tracking-widest text-green-600 bg-green-50 px-3 py-1 rounded-full border border-green-100">
                                    Hazır
                                </span>
                            </div>
                            <button
                                onClick={(e) => { e.stopPropagation(); onFileSelect(null); }}
                                className="mt-8 px-6 py-3 bg-white border border-gray-200 text-gray-500 rounded-xl font-bold hover:text-primary hover:border-primary transition-colors flex items-center gap-2"
                            >
                                <X className="w-4 h-4" /> Dosyayı Değiştir
                            </button>
                        </motion.div>
                    ) : (
                        <motion.div
                            key="idle"
                            className="flex flex-col items-center text-center"
                        >
                            <div className="mb-6 opacity-50">
                                <div className="w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mx-auto text-gray-400">
                                    <Upload className="w-10 h-10" />
                                </div>
                            </div>

                            <h3 className="text-2xl font-display font-bold text-gray-900 mb-2">Dosyayı Buraya Sürükleyin</h3>
                            <p className="text-gray-400 text-sm font-medium mb-8">veya tıklayarak seçin</p>

                            <div className="bg-[#B93632] hover:bg-[#962825] text-white px-8 py-4 rounded-xl font-bold shadow-lg shadow-red-900/20 transition-all transform hover:scale-105 active:scale-95 flex items-center gap-3">
                                <File className="w-5 h-5" />
                                Dosya Seç
                            </div>

                            <p className="mt-8 text-[10px] font-bold text-gray-300 uppercase tracking-widest">
                                PDF, JPG, PNG, TIFF DESTEKLENİR
                            </p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>

            <AnimatePresence>
                {uploadedFileInfo && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        className="space-y-8"
                    >
                        <div className="text-center">
                            <h4 className="text-xl font-display font-black text-gray-900 mb-2" id="processing-choice-title">
                                İşlem Türünü <span className="text-primary italic">Seçin</span>
                            </h4>
                            <p className="text-gray-400 text-sm font-medium">Bozulmuş veya düşük kaliteli belgeler için ön işleme önerilir.</p>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
                            <button
                                onClick={() => handleTypeSelect('normal')}
                                className={`group relative p-8 rounded-[32px] border-2 text-left transition-all overflow-hidden ${processingType === 'normal'
                                    ? 'border-primary bg-primary/5 shadow-xl shadow-primary/5'
                                    : 'border-gray-100 hover:border-primary/30 bg-white'
                                    }`}
                            >
                                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-6 transition-all ${processingType === 'normal' ? 'bg-primary text-white shadow-lg' : 'bg-gray-100 text-gray-400 group-hover:bg-primary/10 group-hover:text-primary'
                                    }`}>
                                    <Zap className="w-8 h-8" />
                                </div>
                                <h5 className="text-lg font-black text-gray-900 mb-2 uppercase tracking-tight">Normal OCR</h5>
                                <p className="text-sm text-gray-500 font-medium leading-relaxed">
                                    Belgeniz doğrudan yüksek doğruluklu Surya modelleri ile işlenir. Temiz belgeler için idealdir.
                                </p>
                                {processingType === 'normal' && (
                                    <motion.div layoutId="check" className="absolute top-6 right-6 text-primary">
                                        <CheckCircle className="w-6 h-6" />
                                    </motion.div>
                                )}
                            </button>

                            <button
                                onClick={() => handleTypeSelect('preprocessing')}
                                className={`group relative p-8 rounded-[32px] border-2 text-left transition-all overflow-hidden ${processingType === 'preprocessing'
                                    ? 'border-primary bg-primary/5 shadow-xl shadow-primary/5'
                                    : 'border-gray-100 hover:border-primary/30 bg-white'
                                    }`}
                            >
                                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-6 transition-all ${processingType === 'preprocessing' ? 'bg-primary text-white shadow-lg' : 'bg-gray-100 text-gray-400 group-hover:bg-primary/10 group-hover:text-primary'
                                    }`}>
                                    <Brain className="w-8 h-8" />
                                </div>
                                <h5 className="text-lg font-black text-gray-900 mb-2 uppercase tracking-tight">Ön İşleme + OCR</h5>
                                <p className="text-sm text-gray-500 font-medium leading-relaxed">
                                    Gürültü giderme, ikilileştirme ve sayfa düzeltme adımları uygulanır. Tarihsel dokümanlar için önerilir.
                                </p>
                                {processingType === 'preprocessing' && (
                                    <motion.div layoutId="check" className="absolute top-6 right-6 text-primary">
                                        <CheckCircle className="w-6 h-6" />
                                    </motion.div>
                                )}
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const CheckCircle = ({ className }) => (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
);

export default FileUploader;
