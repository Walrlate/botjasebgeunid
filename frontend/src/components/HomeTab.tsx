"use client";

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface PackageItem {
  duration: string;
  lpm: number;
  bonus?: string;
  originalPrice: number;
  promoPrice: number;
}

interface HomeTabProps {
  stats: {
    broadcasts: number;
  };
  selectedType: 'regular' | 'forward' | 'userbot';
  setSelectedType: (type: 'regular' | 'forward' | 'userbot') => void;
  selectedLpmFilter: 20 | 30 | 50;
  setSelectedLpmFilter: (lpm: 20 | 30 | 50) => void;
  filteredPackages: PackageItem[];
  handleSelectPackage: (item: PackageItem) => void;
  openAccordion: string | null;
  setOpenAccordion: (id: string | null) => void;
  triggerHaptic: (style?: 'light' | 'medium' | 'heavy') => void;
}

export const HomeTab: React.FC<HomeTabProps> = ({
  stats,
  selectedType,
  setSelectedType,
  selectedLpmFilter,
  setSelectedLpmFilter,
  filteredPackages,
  handleSelectPackage,
  openAccordion,
  setOpenAccordion,
  triggerHaptic,
}) => {
  const [displayCount, setDisplayCount] = React.useState(0);

  React.useEffect(() => {
    let startTimestamp: number | null = null;
    const start = displayCount;
    const end = stats.broadcasts;
    const duration = 1.5;
    
    if (start === end) return;

    let animationFrameId: number;
    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / (duration * 1000), 1);
      const easeOutQuad = progress * (2 - progress);
      
      setDisplayCount(Math.floor(start + easeOutQuad * (end - start)));
      
      if (progress < 1) {
        animationFrameId = window.requestAnimationFrame(step);
      }
    };
    
    animationFrameId = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(animationFrameId);
  }, [stats.broadcasts]);

  const formatBroadcast = (val: number) => {
    if (val >= 1000) {
      return { number: (val / 1000).toFixed(1), unit: 'K Terkirim' };
    }
    return { number: val.toString(), unit: 'Terkirim' };
  };
  
  const bData = formatBroadcast(displayCount);

  return (
    <motion.div
      key="home"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      className="space-y-6"
    >
      <div className="relative overflow-hidden rounded-3xl border border-slate-200/80 shadow-soft bg-white group transition-all duration-300 hover:shadow-premium">
        <div className="relative w-full aspect-video overflow-hidden bg-slate-900">
          <img src="/images/promo_banner.jpg" alt="Promo" className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.02]" />
        </div>
        <div className="p-5 bg-white border-t border-slate-100">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="bg-geun-blue/10 text-geun-blue text-[8px] font-black px-2 py-0.5 rounded-full uppercase tracking-widest">Penawaran Terbatas</span>
          </div>
          <p className="text-[10px] font-bold text-slate-600 leading-relaxed">
            Dapatkan efisiensi promosi maksimal dengan paket Jaseb Autopilot kami.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between shadow-soft">
          <span className="text-[8.5px] font-semibold text-slate-400 uppercase tracking-widest">Total Terkirim</span>
          <div className="flex items-baseline gap-1 mt-1.5">
            <span className="text-2xl font-bold text-slate-800 tracking-tight">{bData.number}</span>
            <span className="text-[9.5px] font-bold text-geun-blue tracking-wide">{bData.unit}</span>
          </div>
        </div>
        <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between shadow-soft">
          <span className="text-[8.5px] font-semibold text-slate-400 uppercase tracking-widest">Status Sistem</span>
          <div className="flex items-center gap-1.5 mt-2.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[9px] font-bold text-emerald-600 uppercase tracking-widest">Online</span>
          </div>
        </div>
      </div>

      <section className="space-y-4">
        <div className="p-1 bg-slate-200/50 border border-slate-200/40 rounded-2xl grid grid-cols-3 gap-1 relative shadow-inner">
          {(['regular', 'forward', 'userbot'] as const).map((type) => (
            <button
              key={type}
              onClick={() => { triggerHaptic('light'); setSelectedType(type); }}
              className={`py-2.5 rounded-xl text-[10.5px] font-bold transition-colors duration-300 relative z-10 tracking-wide capitalize ${selectedType === type ? 'text-geun-blue' : 'text-geun-muted'}`}
            >
              {type}
              {selectedType === type && (
                <motion.div layoutId="activeTabIndicator" className="absolute inset-0 bg-white border border-slate-200 shadow-sm rounded-xl z-[-1]" />
              )}
            </button>
          ))}
        </div>

        {selectedType !== 'userbot' && (
          <div className="flex justify-center gap-2.5 mt-2 bg-slate-200/30 p-1 border border-slate-200/30 rounded-2xl relative">
            {([20, 30, 50] as const).map((lpmValue) => (
              <button
                key={lpmValue}
                onClick={() => { triggerHaptic('light'); setSelectedLpmFilter(lpmValue); }}
                className={`flex-1 py-1.5 rounded-xl text-[9px] font-bold tracking-widest transition-colors duration-300 relative z-10 ${selectedLpmFilter === lpmValue ? 'text-geun-blue font-extrabold' : 'text-slate-400'}`}
              >
                {lpmValue} LPM
                {selectedLpmFilter === lpmValue && (
                  <motion.div layoutId="activeLpmIndicator" className="absolute inset-0 bg-white border border-slate-200/50 shadow-sm rounded-xl z-[-1]" />
                )}
              </button>
            ))}
          </div>
        )}

        <div className="space-y-3.5 mt-4">
          {filteredPackages.map((item, index) => (
            <div key={index} className="glass-panel rounded-2xl p-4 flex items-center justify-between transition-spring border border-slate-200/60 relative overflow-hidden shadow-soft">
              <div className="ticket-notch-l"></div><div className="ticket-notch-r"></div>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-geun-blue/10 flex items-center justify-center border border-geun-blue/5">
                  <svg className="w-4 h-4 text-geun-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <p className="text-[12.5px] font-bold text-slate-800 leading-none tracking-wide">{item.duration}</p>
                    {item.bonus && <span className="text-[7.5px] text-white px-1.5 py-0.5 rounded-full font-bold shimmer-badge-emerald">{item.bonus}</span>}
                  </div>
                  <p className="text-[7.5px] text-slate-400 font-bold uppercase tracking-widest mt-1.5">
                    {selectedType === 'userbot' ? 'USERBOT' : `Jaseb ${selectedType} • ${item.lpm} LPM`}
                  </p>
                </div>
              </div>
              <div className="absolute top-0 bottom-0 left-[62%] w-[1px] border-l border-dashed border-slate-200 pointer-events-none"></div>
              <div className="flex items-center gap-3 relative z-10 pl-2">
                <div className="text-right">
                  <p className="text-[8.5px] text-slate-400/80 font-semibold line-through">Rp {item.originalPrice.toLocaleString('id-ID')}</p>
                  <p className="text-[13px] font-extrabold text-slate-800 tracking-tight">Rp {item.promoPrice.toLocaleString('id-ID')}</p>
                </div>
                <button onClick={() => handleSelectPackage(item)} className="bg-gradient-to-r from-geun-blue to-geun-purple text-white px-3.5 py-2 rounded-xl text-[9.5px] font-bold uppercase shadow-premium">Pilih</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="glass-panel rounded-3xl p-5 space-y-4 border border-slate-200/60 shadow-soft">
        <div className="border-b border-slate-200 pb-3 flex items-center gap-1.5">
          <svg className="w-5 h-5 text-geun-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
          <h3 className="text-[9.5px] font-bold text-slate-400 uppercase tracking-widest">FAQ — Bantuan Cepat</h3>
        </div>
        <div className="space-y-2.5">
          {[
            { id: 'q1', q: '💡 Apa itu Jasa Sebar (Jaseb)?', a: 'Layanan promosi otomatis di Telegram untuk menyebarkan pesan iklan Anda ke grup LPM secara otomatis 24 jam non-stop.' },
            { id: 'q2', q: '🔄 Apa bedanya Regular vs Forward?', a: 'Regular menyalin teks Anda, sedangkan Forward meneruskan pesan asli dari channel Anda (menambah views).' },
            { id: 'q3', q: '🤖 Apa itu Paket Userbot?', a: 'Sistem Stealth Mode yang menggunakan akun Telegram Anda sendiri untuk menyebar iklan agar terlihat lebih organik.' }
          ].map((faq) => (
            <div key={faq.id} className="border border-slate-100 rounded-2xl overflow-hidden bg-white/50">
              <button onClick={() => { triggerHaptic('light'); setOpenAccordion(openAccordion === faq.id ? null : faq.id); }} className="w-full flex items-center justify-between px-4 py-3.5 text-left text-[10px] font-bold text-slate-700 hover:bg-slate-50 transition-colors">
                <span>{faq.q}</span>
                <svg className={`w-3.5 h-3.5 text-slate-400 transition-transform ${openAccordion === faq.id ? 'rotate-180 text-geun-blue' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5"><path d="M19 9l-7 7-7-7" /></svg>
              </button>
              <AnimatePresence>
                {openAccordion === faq.id && (
                  <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden border-t border-slate-100 bg-white">
                    <div className="p-4 text-[9.5px] text-slate-500">{faq.a}</div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </section>
    </motion.div>
  );
};
