import React from 'react';
import useOCR from './hooks/useOCR';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import NeuralBackground from './components/NeuralBackground';
import StepProgressBar from './components/StepProgressBar';
import FileUploader from './components/FileUploader';
import MetadataForm from './components/MetadataForm';
import SettingsPanel from './components/SettingsPanel';
import ProcessingView from './components/ProcessingView';
import ResultsView from './components/ResultsView';
import LayoutViewer from './components/LayoutViewer';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, CheckCircle2, ChevronRight, ChevronLeft, Upload } from 'lucide-react';
import ScrollToTop from './components/ScrollToTop';

const steps = [
  { id: 'upload', title: 'Dosya Yükleme', description: 'OCR için belge seçimi' },
  { id: 'metadata', title: 'Metadata Girişi', description: 'Belge bilgilerini tanımlayın' },
  { id: 'process', title: 'İşlem Ayarları', description: 'Motor ve format seçimi' },
  { id: 'results', title: 'Sonuçlar', description: 'Çıktıları inceleyin' }
];

function App() {
  const { state, actions } = useOCR();

  const calculateCompleteness = () => {
    if (!state.metadataType) return 0;
    const schemas = {
      book: 17,
      article: 13,
      newspaper: 11,
      encyclopedia: 11
    };
    const totalFields = schemas[state.metadataType] || 6;
    const filled = Object.values(state.metadata).filter(v => v && v.toString().trim()).length;
    return Math.min(100, Math.round((filled / totalFields) * 100));
  };

  return (
    <div className="flex flex-col min-h-screen relative font-body text-gray-900 bg-[#f9fafb] selection:bg-primary/20 selection:text-primary-dark">
      <Navbar />

      {/* Neural Background - subtle and behind everything */}
      <div className="fixed inset-0 z-0 pointer-events-none opacity-40">
        <NeuralBackground />
      </div>

      <main className="flex-1 w-full max-w-[1240px] mx-auto p-4 md:p-8 lg:p-12 z-10 relative">

        {/* Wizard Progress Section - As a separate card floating above */}
        <div className="mb-12">
          <div className="bg-white/80 backdrop-blur-md rounded-2xl shadow-sm border border-gray-100 p-6">
            <StepProgressBar
              currentStep={state.currentStep}
              steps={steps}
              completedSteps={state.completedSteps}
            />
          </div>
        </div>

        {/* Main Wizard Content Card */}
        <div className="relative bg-white rounded-[32px] shadow-[0_20px_60px_-15px_rgba(0,0,0,0.1)] border border-gray-100 min-h-[650px] overflow-hidden transition-all duration-500">
          {/* Red Top Border Feature */}
          <div className="absolute top-0 left-0 right-0 h-2 bg-gradient-to-r from-[#B93632] via-[#962825] to-[#B93632] z-20 shadow-md"></div>

          <div className="relative z-10 h-full flex flex-col p-8 md:p-16">
            <div className="flex-1">
              <AnimatePresence mode="wait">
                {state.currentStep === 0 && (
                  <motion.div
                    key="step0"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="h-full flex flex-col items-center"
                  >
                    <div className="text-center mb-12 max-w-3xl mx-auto">
                      <div className="inline-flex items-center justify-center p-3 bg-red-50 rounded-2xl mb-6 text-primary">
                        <Upload className="w-8 h-8" />
                      </div>
                      <h2 className="text-4xl md:text-5xl font-display font-bold text-gray-900 mb-6 tracking-tight">
                        Dosya Yükleme ve Ayarlar
                      </h2>
                      <p className="text-lg text-gray-500 font-medium leading-relaxed max-w-2xl mx-auto">
                        Önce dosyanızı yükleyin, ardından doğrudan OCR mı yoksa ön işleme ile mi devam etmek istediğinizi seçin.
                      </p>
                    </div>

                    <div className="w-full max-w-4xl mx-auto">
                      <FileUploader
                        selectedFile={state.selectedFile}
                        uploadedFileInfo={state.uploadedFileInfo}
                        isUploading={state.isUploading}
                        isDragOver={state.isDragOver}
                        processingType={state.processingType}
                        setProcessingType={actions.setProcessingType}
                        onFileSelect={actions.handleFileUpload}
                        onDrop={(e) => {
                          e.preventDefault();
                          actions.setIsDragOver(false);
                          actions.handleFileUpload(e.dataTransfer.files[0]);
                        }}
                        onDragOver={(e) => { e.preventDefault(); actions.setIsDragOver(true); }}
                        onDragLeave={() => actions.setIsDragOver(false)}
                      />
                    </div>
                  </motion.div>
                )}

                {state.currentStep === 1 && (
                  <motion.div
                    key="step1"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                  >
                    <div className="text-center mb-10">
                      <h2 className="text-3xl font-display font-bold text-gray-900 mb-2">Metadata Girişi</h2>
                      <p className="text-gray-500">Belgeniz için tanımlayıcı bilgiler ekleyin.</p>
                    </div>
                    <MetadataForm
                      metadataType={state.metadataType}
                      setMetadataType={actions.setMetadataType}
                      metadata={state.metadata}
                      handleMetadataChange={actions.handleMetadataChange}
                      identifierValue={state.identifierValue}
                      setIdentifierValue={actions.setIdentifierValue}
                      fetchMetadataFromIdentifier={actions.fetchMetadataFromIdentifier}
                      fetchingMetadata={state.fetchingMetadata}
                      completeness={calculateCompleteness()}
                    />
                  </motion.div>
                )}

                {state.currentStep === 2 && (
                  <motion.div
                    key="step2"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                  >
                    <div className="text-center mb-10">
                      <h2 className="text-3xl font-display font-bold text-gray-900 mb-2">İşlem Ayarları</h2>
                      <p className="text-gray-500">Kullanılacak motorları ve çıktı formatlarını yapılandırın.</p>
                    </div>
                    {!state.processing ? (
                      <SettingsPanel
                        processMode={state.processMode}
                        setProcessMode={actions.setProcessMode}
                        layoutEngine={state.layoutEngine}
                        handleLayoutEngineChange={actions.handleLayoutEngineChange}
                        outputFormats={state.outputFormats}
                        toggleFormat={actions.toggleFormat}
                        startProcessing={actions.startProcessing}
                        processing={state.processing}
                      />
                    ) : (
                      <ProcessingView
                        processingProgress={state.processingProgress}
                        processingStep={state.processingStep}
                        currentPage={state.currentPage}
                        totalPages={state.totalPages}
                        liveStats={state.liveStats}
                        elapsedTime={state.elapsedTime}
                        userFriendlyStatus={state.processingStep}
                        layoutEngine={state.layoutEngine}
                      />
                    )}
                  </motion.div>
                )}

                {state.currentStep === 3 && (
                  <motion.div
                    key="step3"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                  >
                    <ResultsView
                      results={state.results}
                      onRestart={actions.onRestart}
                      onReset={actions.onReset}
                      onShowLayout={() => actions.setShowLayoutViewer(true)}
                      downloadableOutputs={Object.entries(state.results.outputs || {})}
                      totalDownloadableFiles={Object.keys(state.results.outputs || {}).length}
                      metadata={state.metadata}
                      metadataType={state.metadataType}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Navigation Buttons Area */}
            <div className="mt-12 pt-8 border-t border-gray-100 flex justify-between items-center">
              <button
                onClick={actions.prevStep}
                disabled={state.currentStep === 0 || state.processing}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl font-bold transition-all duration-300 ${state.currentStep === 0 ? 'opacity-0 pointer-events-none' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'
                  } disabled:opacity-50`}
              >
                <ChevronLeft className="w-5 h-5" /> Geri
              </button>

              <div className="text-sm font-medium text-gray-400 font-mono">
                Adım {state.currentStep + 1} / 4
              </div>

              {!state.processing && state.currentStep < 3 && (
                <button
                  id="next-step-button"
                  onClick={actions.nextStep}
                  className={`group flex items-center gap-3 px-10 py-4 rounded-2xl bg-primary text-white font-bold hover:bg-primary-dark hover:shadow-xl hover:shadow-primary/20 active:scale-95 transition-all duration-300 ${state.uploadedFileInfo && state.processingType ? 'ring-4 ring-primary/20 animate-pulse' : ''
                    }`}
                >
                  İleri <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </button>
              )}
            </div>
          </div>
        </div>
      </main>

      <Footer />

      {/* Modals */}
      <AnimatePresence>
        {state.showLayoutViewer && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-md flex items-center justify-center p-4 md:p-8"
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="w-full max-w-6xl max-h-[90vh] overflow-y-auto"
            >
              <LayoutViewer
                uploadedFileInfo={state.uploadedFileInfo}
                onClose={() => actions.setShowLayoutViewer(false)}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Notifications */}
      <AnimatePresence>
        {state.notification && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            className={`fixed bottom-8 right-8 z-[200] px-8 py-4 rounded-2xl shadow-2xl flex items-center gap-4 ${state.notification.type === 'error' ? 'bg-red-500 text-white' : 'bg-green-500 text-white'
              }`}
          >
            {state.notification.type === 'error' ? <AlertCircle className="w-6 h-6" /> : <CheckCircle2 className="w-6 h-6" />}
            <span className="font-bold">{state.notification.message}</span>
          </motion.div>
        )}
      </AnimatePresence>
      <ScrollToTop />
    </div>
  );
}

export default App;
