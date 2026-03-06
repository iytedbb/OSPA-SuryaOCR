import React from 'react';

const Navbar = () => {
    return (
        <header className="sticky top-0 z-[1000] bg-[rgba(253,251,247,0.85)] backdrop-blur-[20px] backdrop-saturate-[180%] py-4 shadow-sm border-b border-primary/10 transition-all duration-300">
            <div className="max-w-[1400px] mx-auto px-6 flex justify-between items-center w-full">
                {/* Logo Section */}
                <a href="/" className="group flex items-center gap-3 text-2xl font-black text-primary font-display no-underline transition-all duration-300 hover:scale-105">
                    <img src="/static/logo.png" alt="OSPA Logo" className="h-8 w-auto object-contain" />
                </a>

                {/* Central Navigation Menu */}
                <nav className="hidden lg:flex items-center gap-1">
                    <a href="/" className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-100 hover:text-primary transition-all relative group">
                        Ana Sayfa
                        <span className="absolute bottom-1 left-0 w-0 h-0.5 bg-primary transition-all duration-300 group-hover:w-full"></span>
                    </a>
                    <a href="/ocr" className="px-4 py-2 rounded-lg text-sm font-semibold text-primary bg-primary/5 hover:bg-primary/10 transition-all relative group">
                        SuryaOCR
                        <span className="absolute bottom-1 left-0 w-full h-0.5 bg-primary rounded-full"></span>
                    </a>
                    <a href="/preprocessing" className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-100 hover:text-primary transition-all relative group">
                        Ön İşleme Aracı
                        <span className="absolute bottom-1 left-0 w-0 h-0.5 bg-primary transition-all duration-300 group-hover:w-full"></span>
                    </a>
                    <a href="https://dbb.iyte.edu.tr/ospa.html" target="_blank" className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-100 hover:text-primary transition-all relative group">
                        Hakkımızda
                        <span className="absolute bottom-1 left-0 w-0 h-0.5 bg-primary transition-all duration-300 group-hover:w-full"></span>
                    </a>
                    <a href="https://ospa.iyte.edu.tr/#contact" target="_blank" className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-100 hover:text-primary transition-all relative group">
                        İletişim
                        <span className="absolute bottom-1 left-0 w-0 h-0.5 bg-primary transition-all duration-300 group-hover:w-full"></span>
                    </a>
                </nav>

                {/* Stats / Right Section */}
                <div className="flex items-center gap-6 font-mono text-[0.65rem] text-gray-500">

                    <div className="hidden xl:block w-px h-4 bg-gray-300"></div>

                    <div className="flex items-center gap-2 font-semibold text-gray-600">
                        <i className="fas fa-microchip"></i>
                        <span>GPU Destekli</span>
                    </div>

                    <div className="hidden xl:block w-px h-4 bg-gray-300"></div>

                    <div className="flex items-center gap-2 font-semibold text-gray-600">
                        <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]"></span>
                        <span className="uppercase tracking-widest">OSPA Hızlandırıcı</span>
                    </div>
                </div>
            </div>
        </header>
    );
};

export default Navbar;
