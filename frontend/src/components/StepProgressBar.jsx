import React from 'react';
import { motion } from 'framer-motion';
import { Upload, Info, Settings, FileText, CheckCircle2 } from 'lucide-react';

const StepProgressBar = ({ currentStep, steps, completedSteps }) => {
    return (
        <div className="wizard-progress relative mb-12 max-w-5xl mx-auto">
            <div className="progress-steps flex justify-between items-center relative py-4">
                {/* Progress Line */}
                <div className="absolute top-1/2 left-0 w-full h-1 bg-gray-200 -translate-y-1/2 rounded-full z-0">
                    <motion.div
                        className="h-full bg-primary rounded-full shadow-[0_0_15px_rgba(185,54,50,0.4)]"
                        initial={{ width: 0 }}
                        animate={{ width: `${(currentStep / (steps.length - 1)) * 100}%` }}
                        transition={{ duration: 0.5, ease: "easeInOut" }}
                    />
                </div>

                {/* Steps */}
                {steps.map((step, index) => {
                    const isActive = index === currentStep;
                    const isCompleted = completedSteps.includes(index) || index < currentStep;

                    return (
                        <div key={step.id} className={`step relative z-10 flex flex-col items-center gap-3 bg-transparent px-4 group cursor-default transition-all duration-300 ${isActive ? 'active scale-110' : ''} ${isCompleted ? 'completed' : ''}`}>
                            <div className={`
                                w-14 h-14 rounded-full flex items-center justify-center font-bold text-lg border-2 transition-all duration-500 shadow-lg
                                ${isActive ? 'bg-primary border-primary text-white shadow-primary/40 animate-[pulse-scale_2s_infinite]' :
                                    isCompleted ? 'bg-green-500 border-green-500 text-white' :
                                        'bg-white border-primary/20 text-gray-400'}
                            `}>
                                {isCompleted ? <CheckCircle2 className="w-6 h-6" /> : index + 1}
                            </div>

                            <div className={`step-label text-sm font-display font-bold text-center transition-colors duration-300 ${isActive ? 'text-primary' : 'text-gray-500'}`}>
                                {step.title}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default StepProgressBar;
