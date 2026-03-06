import React from 'react';
import { motion } from 'framer-motion';
import {
    Github as GithubIcon,
    Twitter as TwitterIcon,
    Globe,
    Mail,
    Users,
    Puzzle,
    FlaskConical,
    ExternalLink
} from 'lucide-react';

export default function Footer() {
    return (
        <footer className="border-t border-gray-100 bg-white py-16 mt-auto w-full relative z-10">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
                    {/* Brand Section */}
                    <div className="flex flex-col gap-6">
                        <motion.a
                            href="/"
                            className="flex items-center group w-fit"
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                        >
                            <div className="relative">
                                <img
                                    src="/static/logo.png"
                                    alt="OSPA Logo"
                                    className="h-14 w-auto object-contain relative z-10 filter drop-shadow-sm group-hover:drop-shadow-md transition-all duration-300"
                                />
                                <div className="absolute inset-0 bg-primary/20 blur-xl rounded-full scale-0 group-hover:scale-150 transition-transform duration-500 -z-0 opacity-0 group-hover:opacity-40" />
                            </div>
                        </motion.a>
                        <p className="text-sm text-gray-500 font-medium leading-relaxed max-w-xs">
                            1800-1950 dönemi için yapılandırılmış Prosopografik Dijital Biyografi Arşivi.
                        </p>
                    </div>

                    {/* Biz Kimiz? Section */}
                    <div className="flex flex-col gap-6">
                        <h4 className="text-sm font-bold text-gray-900 uppercase tracking-widest border-b border-gray-100 pb-2">Biz Kimiz?</h4>
                        <ul className="footer-links flex flex-col gap-4">
                            <li>
                                <a href="https://ospa.iyte.edu.tr/" target="_blank" rel="noopener noreferrer" className="group flex items-center gap-3 text-sm text-gray-500 hover:text-primary transition-all duration-300">
                                    <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center group-hover:bg-red-50 transition-colors">
                                        <Globe className="w-5 h-5 text-gray-400 group-hover:text-primary" />
                                    </div>
                                    <span className="font-bold">Projemiz</span>
                                </a>
                            </li>
                            <li>
                                <a href="https://ospa.iyte.edu.tr/#team" target="_blank" rel="noopener noreferrer" className="group flex items-center gap-3 text-sm text-gray-500 hover:text-primary transition-all duration-300">
                                    <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center group-hover:bg-red-50 transition-colors">
                                        <Users className="w-5 h-5 text-gray-400 group-hover:text-primary" />
                                    </div>
                                    <span className="font-bold">Ekibimiz</span>
                                </a>
                            </li>
                            <li>
                                <a href="https://ospa.iyte.edu.tr/#works" target="_blank" rel="noopener noreferrer" className="group flex items-center gap-3 text-sm text-gray-500 hover:text-primary transition-all duration-300">
                                    <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center group-hover:bg-red-50 transition-colors">
                                        <Puzzle className="w-5 h-5 text-gray-400 group-hover:text-primary" />
                                    </div>
                                    <span className="font-bold">Çalışmalarımız</span>
                                </a>
                            </li>
                            <li>
                                <a href="https://ospa.iyte.edu.tr/#team-section" target="_blank" rel="noopener noreferrer" className="group flex items-center gap-3 text-sm text-gray-500 hover:text-primary transition-all duration-300">
                                    <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center group-hover:bg-red-50 transition-colors">
                                        <Mail className="w-5 h-5 text-gray-400 group-hover:text-primary" />
                                    </div>
                                    <span className="font-bold">İletişim</span>
                                </a>
                            </li>
                        </ul>
                    </div>

                    {/* Dış Bağlantılar Section */}
                    <div className="flex flex-col gap-6">
                        <h4 className="text-sm font-bold text-gray-900 uppercase tracking-widest border-b border-gray-100 pb-2">Dış Bağlantılar</h4>
                        <ul className="footer-links flex flex-col gap-4">
                            <li>
                                <a href="https://iyte.edu.tr/" target="_blank" rel="noopener noreferrer" className="group flex items-center gap-3 text-sm text-gray-500 hover:text-primary transition-all duration-300">
                                    <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center group-hover:bg-red-50 transition-colors overflow-hidden">
                                        <img src="/static/iyte-logo.png" alt="İYTE" className="h-[22px] w-auto object-contain transition-all contrast-125" />
                                    </div>
                                    <span className="font-bold">İYTE</span>
                                </a>
                            </li>
                            <li>
                                <a href="https://huggingface.co/dbbiyte" target="_blank" rel="noopener noreferrer" className="group flex items-center gap-3 text-sm text-gray-500 hover:text-primary transition-all duration-300">
                                    <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center group-hover:bg-red-50 transition-colors">
                                        <img src="https://huggingface.co/front/assets/huggingface_logo-noborder.svg" alt="Hugging Face" className="h-5 w-auto" />
                                    </div>
                                    <span className="font-bold">HuggingFace</span>
                                </a>
                            </li>
                            <li>
                                <a href="https://github.com/iytedbb" target="_blank" rel="noopener noreferrer" className="group flex items-center gap-3 text-sm text-gray-500 hover:text-primary transition-all duration-300">
                                    <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center group-hover:bg-red-50 transition-colors">
                                        <i className="fab fa-github text-[18px] text-gray-400 group-hover:text-primary transition-colors"></i>
                                    </div>
                                    <span className="font-bold">GitHub</span>
                                </a>
                            </li>
                            <li>
                                <a href="https://ospa.iyte.edu.tr/" target="_blank" rel="noopener noreferrer" className="group flex items-center gap-3 text-sm text-gray-500 hover:text-primary transition-all duration-300">
                                    <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center group-hover:bg-red-50 transition-colors items-center justify-center">
                                        <img src="/static/o-ospa.png" alt="OSPA" className="h-5 w-auto grayscale group-hover:grayscale-0 transition-all" />
                                    </div>
                                    <span className="font-bold">OSPA</span>
                                </a>
                            </li>
                        </ul>
                    </div>
                </div>

                <div className="mt-16 border-t border-gray-100 pt-8 flex flex-col md:flex-row justify-between items-center gap-8">
                    <p className="text-[11px] font-medium text-gray-400 leading-relaxed max-w-2xl text-center md:text-left">
                        © 323K372 NUMARALI TÜBİTAK 1001 Projesi | Osmanlı'dan Cumhuriyet'e Sosyo-Politik Ağ Analizi Yapay Zekâ Yoluyla Dönem Tanıklıklarını Yeniden Okumak (1900-1940)
                    </p>

                    <ul className="wrapper">
                        <li className="icon twitter">
                            <span className="tooltip">Twitter / X</span>
                            <a href="https://x.com/iytedbb" target="_blank" rel="noopener noreferrer" className="flex items-center justify-center w-full h-full">
                                <i className="fab fa-x-twitter text-[18px]"></i>
                            </a>
                        </li>
                        <li className="icon github">
                            <span className="tooltip">GitHub</span>
                            <a href="https://github.com/Panatios" target="_blank" rel="noopener noreferrer" className="flex items-center justify-center w-full h-full">
                                <i className="fab fa-github text-[18px]"></i>
                            </a>
                        </li>
                        <li className="icon huggingface">
                            <span className="tooltip">HuggingFace</span>
                            <a href="https://huggingface.co/dbbiyte" target="_blank" rel="noopener noreferrer" className="flex items-center justify-center w-full h-full">
                                <img src="https://huggingface.co/front/assets/huggingface_logo-noborder.svg" alt="" className="w-6 h-6" />
                            </a>
                        </li>
                        <li className="icon iyte">
                            <span className="tooltip">İYTE</span>
                            <a href="https://iyte.edu.tr/" target="_blank" rel="noopener noreferrer" className="flex items-center justify-center w-full h-full p-0">
                                <img src="/static/iyte-logo.png" alt="İYTE" className="w-[28px] h-auto object-contain transition-all group-hover:brightness-0 group-hover:invert contrast-125" />
                            </a>
                        </li>
                        <li className="icon lab">
                            <span className="tooltip">DBB Lab</span>
                            <a href="https://dbb.iyte.edu.tr/" target="_blank" rel="noopener noreferrer" className="flex items-center justify-center w-full h-full p-0">
                                <img src="/static/lab-icon.png" alt="Lab" className="w-[24px] h-auto object-contain opacity-70 group-hover:opacity-100 transition-opacity" />
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
        </footer>
    );
}
