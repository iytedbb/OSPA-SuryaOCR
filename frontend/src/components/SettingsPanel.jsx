import React from 'react';
import { motion } from 'framer-motion';
import { Settings, Brain, Zap, FileJson, FileCode, FileType, CheckCircle2, Loader2 } from 'lucide-react';

const SettingsPanel = ({
    processMode,
    setProcessMode,
    layoutEngine,
    handleLayoutEngineChange,
    outputFormats,
    toggleFormat,
    startProcessing,
    processing
}) => {
    const formats = [
        { id: 'md', label: 'Markdown', icon: FileType, color: 'text-blue-500' },
        { id: 'xml', label: 'XML', icon: FileCode, color: 'text-orange-500' }
    ];

    return (
        <div className="space-y-12 animate-in fade-in slide-in-from-bottom-8 duration-700">
            <div className="text-center max-w-2xl mx-auto">
                <h2 className="text-4xl font-display font-black text-gray-900 mb-4 tracking-tight" id="processing-title">
                    İşlem <span className="text-primary italic">Ayarları</span>
                </h2>
                <p className="text-gray-500 font-medium">
                    OCR motoru, layout motoru ve çıktı formatlarını seçerek işlemi başlatın.
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 max-w-6xl mx-auto">
                {/* Process Mode */}
                <div className="bg-white p-8 rounded-[40px] shadow-xl border border-gray-100 flex flex-col">
                    <h4 className="text-xs font-black uppercase tracking-[0.2em] text-gray-400 mb-8 flex items-center gap-2">
                        <span className="w-4 h-px bg-gray-200"></span> İşlem Türü
                    </h4>
                    <div className="space-y-4 flex-1">
                        {[
                            { id: 'ocr', label: 'Tam OCR Çözümleme', desc: 'Metin tanıma ve layout analizi birlikte yapılır.', icon: Brain },
                            { id: 'layout', label: 'Sadece Layout Analizi', desc: 'Sadece metin bölgeleri ve koordinatları tespit edilir.', icon: Settings }
                        ].map(mode => (
                            <button
                                key={mode.id}
                                onClick={() => setProcessMode(mode.id)}
                                className={`w-full p-6 rounded-3xl border-2 text-left transition-all ${processMode === mode.id ? 'border-primary bg-primary/5' : 'border-gray-50 hover:border-gray-100 bg-gray-50/50'
                                    }`}
                            >
                                <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${processMode === mode.id ? 'bg-primary text-white' : 'bg-gray-200 text-gray-400'
                                    }`}>
                                    <mode.icon className="w-5 h-5" />
                                </div>
                                <div className="font-bold text-gray-900 mb-1">{mode.label}</div>
                                <div className="text-[10px] font-medium text-gray-500 leading-tight uppercase tracking-wider">{mode.desc}</div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Layout Engine */}
                <div className="bg-white p-8 rounded-[40px] shadow-xl border border-gray-100 flex flex-col">
                    <h4 className="text-xs font-black uppercase tracking-[0.2em] text-gray-400 mb-8 flex items-center gap-2">
                        <span className="w-4 h-px bg-gray-200"></span> Layout Motoru
                    </h4>
                    <div className="space-y-4 flex-1">
                        {[
                            { id: 'surya', label: 'Surya Layout', desc: 'Akademik ve karmaşık belgeler için optimize edilmiştir.', icon: Brain, stats: '98% Acc' },
                            { id: 'yolo', label: 'YOLO Layout', desc: 'Hızlı ve nesne tabanlı tespit için idealdir.', icon: Zap, stats: 'Realtime' }
                        ].map(engine => (
                            <button
                                key={engine.id}
                                onClick={() => handleLayoutEngineChange(engine.id)}
                                className={`w-full p-6 rounded-3xl border-2 text-left transition-all relative overflow-hidden ${layoutEngine === engine.id ? 'border-primary bg-primary/5' : 'border-gray-50 hover:border-gray-100 bg-gray-50/50'
                                    }`}
                            >
                                <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${layoutEngine === engine.id ? 'bg-primary text-white' : 'bg-gray-200 text-gray-400'
                                    }`}>
                                    <engine.icon className="w-5 h-5" />
                                </div>
                                <div className="font-bold text-gray-900 mb-1">{engine.label}</div>
                                <p className="text-[10px] font-medium text-gray-500 leading-tight uppercase tracking-wider">{engine.desc}</p>
                                <div className="absolute top-6 right-6 text-[8px] font-black uppercase bg-white px-2 py-0.5 rounded-full border border-gray-100 text-gray-400">
                                    {engine.stats}
                                </div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Output Formats */}
                <div className="bg-white p-8 rounded-[40px] shadow-xl border border-gray-100 flex flex-col">
                    <h4 className="text-xs font-black uppercase tracking-[0.2em] text-gray-400 mb-8 flex items-center gap-2">
                        <span className="w-4 h-px bg-gray-200"></span> Çıktı Formatları
                    </h4>
                    <div className="space-y-4 flex-1">
                        {formats.map(format => (
                            <button
                                key={format.id}
                                onClick={() => toggleFormat(format.id)}
                                className={`w-full flex items-center gap-4 p-5 rounded-3xl border-2 transition-all ${outputFormats.includes(format.id) ? 'border-primary bg-primary/5' : 'border-gray-50 hover:border-gray-100 bg-gray-50/50'
                                    }`}
                            >
                                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${outputFormats.includes(format.id) ? 'bg-white shadow-md' : 'bg-gray-200'
                                    }`}>
                                    <format.icon className={`w-6 h-6 ${outputFormats.includes(format.id) ? format.color : 'text-gray-400'}`} />
                                </div>
                                <div className="flex-1 text-left">
                                    <div className={`font-black uppercase tracking-tight ${outputFormats.includes(format.id) ? 'text-gray-900' : 'text-gray-400'}`}>
                                        {format.label}
                                    </div>
                                </div>
                                {outputFormats.includes(format.id) && (
                                    <CheckCircle2 className="w-5 h-5 text-primary" />
                                )}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="flex justify-center pt-8">
                <button
                    onClick={startProcessing}
                    disabled={processing || outputFormats.length === 0}
                    className="group relative px-12 py-6 bg-primary text-white rounded-[32px] font-display font-black text-2xl shadow-2xl shadow-primary/40 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-4 overflow-hidden"
                >
                    <div className="absolute inset-0 bg-white/20 origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500"></div>
                    <span className="relative flex items-center gap-4">
                        {processing ? <Loader2 className="animate-spin w-8 h-8" /> : (
                            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                        )}
                        İŞLEMİ BAŞLAT
                    </span>
                </button>
            </div>
        </div>
    );
};

export default SettingsPanel;
