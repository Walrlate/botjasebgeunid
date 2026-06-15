"use client";

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
}

interface PackageItem {
  duration: string;
  lpm: number;
  bonus?: string;
  originalPrice: number;
  promoPrice: number;
}



const HomeIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 drop-shadow-[0_2px_8px_rgba(0,122,255,0.25)]' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
);

const EditIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 drop-shadow-[0_2px_8px_rgba(0,122,255,0.25)]' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
  </svg>
);

const UserIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 drop-shadow-[0_2px_8px_rgba(0,122,255,0.25)]' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
  </svg>
);

const ToolsIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 drop-shadow-[0_2px_8px_rgba(0,122,255,0.25)]' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
  </svg>
);


const enhancedWording = (text: string, template: 'premium' | 'minimalist' | 'flash', contact: string = '@Geun_ID') => {
  if (!text) return '';
  const divider = "━━━━━━━━━━━━━━━━━━━━";
  const cleanText = text.trim();
  
  if (template === 'premium') {
    return `💎 𝖯𝖱𝖤𝖬𝖨𝖴𝖬 𝖲𝖳𝖮𝖱𝖤 𝖯𝖱𝖮𝖬𝖮 💎\n${divider}\n\n📢 **INFO PROMOSI:**\n${cleanText}\n\n${divider}\n🛒 Hubungi Kami: ${contact}\n⚡ Powered by GeunID Autopilot`;
  }
  if (template === 'minimalist') {
    return `✨ 𝖦𝖤𝖴𝖭𝖨𝖣 𝖬𝖨𝖭𝖨𝖬𝖠𝖫𝖨𝖲𝖳 ✨\n\n📌 _Pesan Promosi:_\n"${cleanText}"\n\n💬 Order via Admin: ${contact}`;
  }
  if (template === 'flash') {
    return `🔥 𝖥𝖫𝖠𝖲𝖧 𝖲𝖠𝖫𝖤 𝖫𝖨𝖬𝖨𝖳𝖤𝖣 🔥\n${divider}\n\n⚡ **PROMO TERBATAS:**\n👉 ${cleanText}\n\n${divider}\n🚨 Hubungi Segera: ${contact} sebelum habis!`;
  }
  return cleanText;
};


const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('home');
  const [openAccordion, setOpenAccordion] = useState<string | null>(null);
  const [user, setUser] = useState<TelegramUser | null>(null);
  const [isTelegramWebview, setIsTelegramWebview] = useState(false);

  // States for Free Tools Tab
  const [rawWording, setRawWording] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<'premium' | 'minimalist' | 'flash'>('premium');
  const [wordingCopied, setWordingCopied] = useState(false);
  const [lpmToScan, setLpmToScan] = useState('');
  const [lpmCopied, setLpmCopied] = useState(false);
  const [userIdsInput, setUserIdsInput] = useState('');
  
  // State for Pricing Configurator
  const [selectedType, setSelectedType] = useState<'regular' | 'forward' | 'userbot'>('regular');
  const [selectedLpmFilter, setSelectedLpmFilter] = useState<20 | 30 | 50>(20);
  
  // State for Order Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedPackage, setSelectedPackage] = useState<{
    lpm: number;
    type: string;
    duration: string;
    price: number;
  } | null>(null);
  const [copied, setCopied] = useState(false);
  const [checkoutStep, setCheckoutStep] = useState<'select_payment' | 'invoice'>('select_payment');
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<'qris' | 'manual' | null>(null);
  const [accountCount, setAccountCount] = useState(1);

  const [stats, setStats] = useState({
    broadcasts: 0,
    lpm: 0,
    userbots: 0,
    userBotStatus: 'disconnected',
    userPackage: 'Tidak Aktif',
    userLpm: 0,
    userDays: 0,
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const webapp = (window as any).Telegram?.WebApp;
      if (webapp && webapp.initDataUnsafe?.user) {
        setIsTelegramWebview(true);
        setUser(webapp.initDataUnsafe.user);
        webapp.ready();
        webapp.expand();
      }

      // Parse query parameters for real-time stats from Telegram Bot
      const params = new URLSearchParams(window.location.search);
      const b = parseInt(params.get('b') || '0', 10);
      const l = parseInt(params.get('l') || '0', 10);
      const u = parseInt(params.get('u') || '0', 10);
      const ub = params.get('ub') || 'disconnected';
      const pkg = params.get('pkg') || 'Tidak Aktif';
      const ulpm = parseInt(params.get('ulpm') || '0', 10);
      const days = parseInt(params.get('days') || '0', 10);

      setStats({
        broadcasts: b,
        lpm: l,
        userbots: u,
        userBotStatus: ub,
        userPackage: pkg,
        userLpm: ulpm,
        userDays: days,
      });
    }
  }, []);

  const triggerHaptic = (style: 'light' | 'medium' | 'heavy' = 'light') => {
    if (typeof window !== 'undefined') {
      const webapp = (window as any).Telegram?.WebApp;
      if (webapp?.HapticFeedback) {
        webapp.HapticFeedback.impactOccurred(style);
      }
    }
  };

  const handleTabChange = (tab: string) => {
    triggerHaptic('light');
    setActiveTab(tab);
  };

  const getDisplayName = () => {
    if (!user) return 'Premium User';
    return `${user.first_name} ${user.last_name || ''}`.trim();
  };

  const getUsername = () => {
    if (!user) return '@geun_buyer';
    return user.username ? `@${user.username}` : `@id_${user.id}`;
  };



  // Pricing Data with Cheaper/Discounted Prices
  const pricingData: Record<'regular' | 'forward' | 'userbot', PackageItem[]> = {
    regular: [
      // 20 LPM
      { duration: '5 Hari', lpm: 20, originalPrice: 15000, promoPrice: 9500 },
      { duration: '7 Hari', lpm: 20, bonus: '+2 Hari', originalPrice: 25000, promoPrice: 16500 },
      { duration: '14 Hari', lpm: 20, bonus: '+3 Hari', originalPrice: 50000, promoPrice: 32500 },
      { duration: '30 Hari', lpm: 20, bonus: '+4 Hari', originalPrice: 65000, promoPrice: 42500 },
      // 30 LPM
      { duration: '3 Hari', lpm: 30, originalPrice: 20000, promoPrice: 13500 },
      { duration: '7 Hari', lpm: 30, originalPrice: 35000, promoPrice: 23500 },
      { duration: '10 Hari', lpm: 30, originalPrice: 50000, promoPrice: 32500 },
      { duration: '30 Hari', lpm: 30, originalPrice: 85000, promoPrice: 55500 },
      // 50 LPM
      { duration: '3 Hari', lpm: 50, originalPrice: 30000, promoPrice: 19500 },
      { duration: '7 Hari', lpm: 50, originalPrice: 55000, promoPrice: 36500 },
      { duration: '14 Hari', lpm: 50, originalPrice: 80000, promoPrice: 52500 },
      { duration: '30 Hari', lpm: 50, originalPrice: 130000, promoPrice: 85500 },
    ],
    forward: [
      // 20 LPM
      { duration: '3 Hari', lpm: 20, originalPrice: 15000, promoPrice: 9500 },
      { duration: '5 Hari', lpm: 20, originalPrice: 20000, promoPrice: 13500 },
      { duration: '7 Hari', lpm: 20, bonus: '+2 Hari', originalPrice: 30000, promoPrice: 19500 },
      { duration: '10 Hari', lpm: 20, bonus: '+2 Hari', originalPrice: 40000, promoPrice: 26500 },
      { duration: '14 Hari', lpm: 20, bonus: '+4 Hari', originalPrice: 55000, promoPrice: 36500 },
      { duration: '30 Hari', lpm: 20, bonus: '+5 Hari', originalPrice: 75000, promoPrice: 49500 },
      // 30 LPM
      { duration: '3 Hari', lpm: 30, originalPrice: 30000, promoPrice: 19500 },
      { duration: '5 Hari', lpm: 30, originalPrice: 40000, promoPrice: 26500 },
      { duration: '7 Hari', lpm: 30, originalPrice: 45000, promoPrice: 29500 },
      { duration: '14 Hari', lpm: 30, originalPrice: 70000, promoPrice: 46500 },
      { duration: '30 Hari', lpm: 30, originalPrice: 120000, promoPrice: 79500 },
      // 50 LPM
      { duration: '3 Hari', lpm: 50, originalPrice: 45000, promoPrice: 29500 },
      { duration: '7 Hari', lpm: 50, originalPrice: 75000, promoPrice: 49500 },
      { duration: '14 Hari', lpm: 50, originalPrice: 110000, promoPrice: 72550 },
      { duration: '30 Hari', lpm: 50, originalPrice: 180000, promoPrice: 119500 },
    ],
    userbot: [
      { duration: '7 Hari', lpm: 0, originalPrice: 15000, promoPrice: 10000 },
      { duration: '30 Hari', lpm: 0, originalPrice: 35000, promoPrice: 25000 },
      { duration: '60 Hari', lpm: 0, originalPrice: 70000, promoPrice: 50000 },
    ]
  };

  const activePackages = pricingData[selectedType] || [];
  const filteredPackages = selectedType === 'userbot'
    ? activePackages
    : activePackages.filter(item => item.lpm === selectedLpmFilter);


  const handleSelectPackage = (item: PackageItem) => {
    triggerHaptic('medium');
    setSelectedPackage({
      lpm: item.lpm,
      type: selectedType,
      duration: item.duration + (item.bonus ? ` (${item.bonus})` : ''),
      price: item.promoPrice
    });
    setCheckoutStep('select_payment');
    setSelectedPaymentMethod(null);
    setAccountCount(1);
    setIsModalOpen(true);
    setCopied(false);
  };

  const getOrderFormatText = () => {
    if (!selectedPackage) return '';
    const paymentText = selectedPaymentMethod === 'qris'
      ? 'QRIS'
      : selectedPaymentMethod === 'manual'
      ? 'Transfer Manual'
      : 'Belum Memilih';
    
    const currentPrice = selectedPackage.type === 'userbot'
      ? selectedPackage.price * accountCount
      : selectedPackage.price;

    if (selectedPackage.type === 'userbot') {
      const uidsSection = accountCount > 1 && userIdsInput.trim()
        ? `\n– List UserID: ${userIdsInput.trim()}`
        : '';
      return `🛎 𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧
– Username: ${getUsername() || '@username'}
– Durasi userbot: ${selectedPackage.duration}
– Jumlah Akun: ${accountCount} Akun${uidsSection}
– Nomor Telegram: (isi nomor HP akun userbot Anda)
– Password: (isi password jika ada 2FA, jika tidak kosongkan)
– Payment: ${paymentText}
– Total Harga: Rp ${currentPrice.toLocaleString('id-ID')}`;
    } else {
      return `🛎 𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦
– Username akun: ${getUsername() || '@username'}
– Durasi Jaseb: ${selectedPackage.duration}
– Paket jaseb: JASEB ${selectedPackage.type.toUpperCase()} ${selectedPackage.lpm} LPM
– Payment: ${paymentText}
– Request Lpm: (isi @lpm1 @lpm2, kalau gaada kosongin/hapus)
– Total Harga: Rp ${currentPrice.toLocaleString('id-ID')}`;
    }

  };


  const handleCopyOrderFormat = () => {
    triggerHaptic('heavy');
    const text = getOrderFormatText();
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatBroadcast = (val: number) => {
    if (val >= 1000) {
      return { number: (val / 1000).toFixed(1), unit: 'K Terkirim' };
    }
    return { number: val.toString(), unit: 'Terkirim' };
  };
  const bData = formatBroadcast(stats.broadcasts);

  return (
    <div className="min-h-screen bg-geun-bg text-geun-dark flex justify-center items-start overflow-hidden relative">
      
      {/* Soft Pastel Background Glow Blobs */}
      <div className="glow-orb w-64 h-64 bg-blue-400/10 top-[-80px] left-[-80px]"></div>
      <div className="glow-orb w-80 h-80 bg-indigo-300/10 bottom-[100px] right-[-100px]"></div>

      {/* Main WebView Container */}
      <div className="w-full max-w-md min-h-screen bg-[#F4F6F9] flex flex-col relative shadow-[0_0_50px_rgba(0,122,255,0.06)] border-x border-slate-200/50 pb-28 overflow-y-auto z-10">
        
        {/* Background Grid Pattern Layer */}
        <div className="absolute inset-0 grid-bg pointer-events-none z-0"></div>

        {/* Header with Frosted Glassmorphism */}
        <header className="flex justify-between items-center px-5 py-4 border-b border-slate-200/50 bg-[#F4F6F9]/65 backdrop-blur-xl sticky top-0 z-40">
          <div className="relative z-10">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-geun-blue shadow-[0_0_8px_rgba(0,122,255,0.4)] animate-pulse"></span>
              <h1 className="text-lg font-bold tracking-wider text-geun-dark uppercase">
                GEUNID<span className="text-geun-blue font-black">.JASEB</span>
              </h1>
            </div>
          </div>
          
          {/* User Profile Capsule */}
          <div className="flex items-center gap-2 bg-white/80 border border-slate-200/60 rounded-2xl p-1.5 pr-2.5 relative z-10 shadow-soft">
            {user?.photo_url ? (
              <img src={user.photo_url} alt="Profile" className="w-7 h-7 rounded-xl object-cover border border-slate-200" />
            ) : (
              <div className="w-7 h-7 bg-gradient-to-br from-geun-blue to-geun-purple rounded-xl flex items-center justify-center font-bold text-white text-xs shadow-md">
                {getDisplayName().charAt(0)}
              </div>
            )}
            <div className="text-left leading-tight">
              <p className="text-[9.5px] font-semibold text-slate-800 max-w-[90px] truncate">{getDisplayName()}</p>
              <p className="text-[8px] font-semibold text-slate-400">{getUsername()}</p>
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 relative z-10">
          <AnimatePresence mode="wait">
            {activeTab === 'home' && (
              <motion.div
                key="home"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
                className="space-y-6"
              >
                
                {/* Promo Banner Card */}
                <div className="relative overflow-hidden rounded-3xl border border-slate-200/80 shadow-soft bg-white group transition-all duration-300 hover:shadow-premium">
                  {/* Banner Image Container */}
                  <div className="relative w-full aspect-video overflow-hidden bg-slate-900">
                    <img 
                      src="/images/promo_banner.jpg" 
                      alt="GeunID Promo Banner" 
                      className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.02]"
                    />
                  </div>

                  {/* Promo Details / Description */}
                  <div className="p-5 bg-white border-t border-slate-100">
                    <p className="text-[10px] font-medium text-slate-500 leading-relaxed">
                      Nikmati potongan harga spesial hingga <span className="font-extrabold text-geun-blue">35%</span> dan <span className="font-extrabold text-emerald-600">bonus durasi aktif</span> untuk semua layanan sebar iklan otomatis Jaseb Regular, Forward, & Userbot!
                    </p>
                  </div>
                </div>

              {/* Status Info Row */}
              <div className="grid grid-cols-2 gap-3">
                <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between shadow-soft">
                  <span className="text-[8.5px] font-semibold text-slate-400 uppercase tracking-widest">Total Broadcast</span>
                  <div className="flex items-baseline gap-1 mt-1.5">
                    <span className="text-2xl font-bold text-slate-800 tracking-tight">{bData.number}</span>
                    <span className="text-[9.5px] font-bold text-geun-blue tracking-wide">{bData.unit}</span>
                  </div>
                </div>
                <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between shadow-soft">
                  <span className="text-[8.5px] font-semibold text-slate-400 uppercase tracking-widest">System Status</span>
                  <div className="flex items-center gap-1.5 mt-2.5">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                    </span>
                    <span className="text-[9px] font-bold text-emerald-600 uppercase tracking-widest">Active</span>
                  </div>
                </div>
              </div>
              <section className="space-y-4">
                <div className="flex justify-between items-center px-1">
                  <h3 className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Pilih Jenis Layanan</h3>
                </div>

                {/* Package Type Selector - Pill Switcher */}
                <div className="p-1 bg-slate-200/50 border border-slate-200/40 rounded-2xl grid grid-cols-3 gap-1 relative shadow-inner">
                  {(['regular', 'forward', 'userbot'] as const).map((type) => {
                    const isActive = selectedType === type;
                    return (
                      <button
                        key={type}
                        onClick={() => { triggerHaptic('light'); setSelectedType(type); }}
                        className={`py-2.5 rounded-xl text-[10.5px] font-bold transition-colors duration-300 relative z-10 tracking-wide capitalize ${
                          isActive ? 'text-geun-blue' : 'text-geun-muted'
                        }`}
                      >
                        {type}
                        {isActive && (
                          <motion.div
                            layoutId="activeTabIndicator"
                            className="absolute inset-0 bg-white border border-slate-200 shadow-sm rounded-xl z-[-1]"
                            transition={{ type: "spring", stiffness: 380, damping: 30 }}
                          />
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Sub-Category Filter - LPM Switcher */}
                {selectedType !== 'userbot' && (
                  <div className="flex justify-center gap-2.5 mt-2 bg-slate-200/30 p-1 border border-slate-200/30 rounded-2xl relative">
                    {([20, 30, 50] as const).map((lpmValue) => {
                      const isLpmActive = selectedLpmFilter === lpmValue;
                      return (
                        <button
                          key={lpmValue}
                          onClick={() => { triggerHaptic('light'); setSelectedLpmFilter(lpmValue); }}
                          className={`flex-1 py-1.5 rounded-xl text-[9px] font-bold tracking-widest transition-colors duration-300 relative z-10 ${
                            isLpmActive ? 'text-geun-blue font-extrabold' : 'text-slate-400'
                          }`}
                        >
                          {lpmValue} LPM
                          {isLpmActive && (
                            <motion.div
                              layoutId="activeLpmIndicator"
                              className="absolute inset-0 bg-white border border-slate-200/50 shadow-sm rounded-xl z-[-1]"
                              transition={{ type: "spring", stiffness: 380, damping: 30 }}
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}


                {/* Duration Tickets List - Tearing Stub Effect */}
                <div className="space-y-3.5 mt-4">
                  {filteredPackages.map((item, index) => (
                    <div 
                      key={index}
                      className="glass-panel rounded-2xl p-4 flex items-center justify-between transition-spring card-glow-blue border border-slate-200/60 relative overflow-hidden shadow-soft"
                    >
                      {/* Ticket notches left and right */}
                      <div className="ticket-notch-l"></div>
                      <div className="ticket-notch-r"></div>

                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-geun-blue/10 flex items-center justify-center border border-geun-blue/5">
                          <svg className="w-4 h-4 text-geun-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <p className="text-[12.5px] font-bold text-slate-800 leading-none tracking-wide">{item.duration}</p>
                            {item.bonus && (
                              <span className="text-[7.5px] text-white px-1.5 py-0.5 rounded-full font-bold shimmer-badge-emerald">
                                {item.bonus}
                              </span>
                            )}
                          </div>
                          <p className="text-[7.5px] text-slate-400 font-bold uppercase tracking-widest mt-1.5">
                            {selectedType === 'userbot' ? 'USERBOT' : `Jaseb ${selectedType} • ${item.lpm} LPM`}
                          </p>


                        </div>
                      </div>

                      {/* Ticket Tearing Dashed Line */}
                      <div className="absolute top-0 bottom-0 left-[62%] w-[1px] border-l border-dashed border-slate-200 pointer-events-none"></div>

                      <div className="flex items-center gap-3 relative z-10 pl-2">
                        <div className="text-right">
                          <p className="text-[8.5px] text-slate-400/80 font-semibold line-through">Rp {item.originalPrice.toLocaleString('id-ID')}</p>
                          <p className="text-[13px] font-extrabold text-slate-800 tracking-tight">Rp {item.promoPrice.toLocaleString('id-ID')}</p>
                        </div>
                        <button
                          onClick={() => handleSelectPackage(item)}
                          className="bg-gradient-to-r from-geun-blue to-geun-purple text-white hover:opacity-90 active:scale-95 px-3.5 py-2 rounded-xl text-[9.5px] font-bold uppercase tracking-widest transition-spring shadow-premium"
                        >
                          Pilih
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Accordion Edukasi & Rules */}
              <section className="glass-panel rounded-3xl p-5 space-y-4 border border-slate-200/60 shadow-soft">
                <div className="border-b border-slate-200 pb-3">
                  <div className="flex items-center gap-1.5">
                    <svg className="w-5 h-5 text-geun-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                    <h3 className="text-[9.5px] font-bold text-slate-400 uppercase tracking-widest">FAQ</h3>
                  </div>
                </div>

                <div className="space-y-2.5">
                  {/* Accordion Item 1: Pengertian Jaseb */}
                  <div className="border border-slate-100 rounded-2xl overflow-hidden bg-white/50">
                    <button
                      onClick={() => {
                        triggerHaptic('light');
                        setOpenAccordion(openAccordion === 'what_is_jaseb' ? null : 'what_is_jaseb');
                      }}
                      className="w-full flex items-center justify-between px-4 py-3.5 text-left text-[10px] font-bold text-slate-700 hover:bg-slate-50 transition-colors duration-200"
                    >
                      <span>💡 Apa itu Jasa Sebar (Jaseb)?</span>
                      <svg
                        className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-300 ${openAccordion === 'what_is_jaseb' ? 'rotate-180 text-geun-blue' : ''}`}
                        fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    <AnimatePresence initial={false}>
                      {openAccordion === 'what_is_jaseb' && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2, ease: 'easeInOut' }}
                          className="overflow-hidden border-t border-slate-100 bg-white"
                        >
                          <div className="p-4 text-[9.5px] leading-relaxed text-slate-500 space-y-2">
                            <p>
                              <strong>Jasa Sebar (Jaseb)</strong> adalah layanan promosi otomatis di Telegram untuk menyebarkan pesan iklan (teks, gambar, atau video) Anda ke grup LPM (List Promosi Megalink) secara otomatis 24 jam non-stop.
                            </p>
                            <p>
                              Keuntungannya, Anda tidak perlu membuang waktu menyebar iklan secara manual di HP Anda. Sistem cluster bot kami yang akan mengurusnya.
                            </p>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Accordion Item 2: Pengertian Userbot */}
                  <div className="border border-slate-100 rounded-2xl overflow-hidden bg-white/50">
                    <button
                      onClick={() => {
                        triggerHaptic('light');
                        setOpenAccordion(openAccordion === 'what_is_userbot' ? null : 'what_is_userbot');
                      }}
                      className="w-full flex items-center justify-between px-4 py-3.5 text-left text-[10px] font-bold text-slate-700 hover:bg-slate-50 transition-colors duration-200"
                    >
                      <span>🤖 Apa itu Userbot?</span>
                      <svg
                        className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-300 ${openAccordion === 'what_is_userbot' ? 'rotate-180 text-geun-blue' : ''}`}
                        fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    <AnimatePresence initial={false}>
                      {openAccordion === 'what_is_userbot' && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2, ease: 'easeInOut' }}
                          className="overflow-hidden border-t border-slate-100 bg-white"
                        >
                          <div className="p-4 text-[9.5px] leading-relaxed text-slate-500 space-y-2">
                            <p>
                              <strong>Userbot</strong> memiliki fungsi penyebaran iklan yang sama dengan Jaseb. Perbedaannya terletak pada akun pengirimnya:
                            </p>
                            <ul className="list-disc pl-4 space-y-1 mt-1 font-semibold">
                              <li>• <strong>Jaseb Biasa:</strong> Menggunakan akun Admin (kami yang menyediakan).</li>
                              <li>• <strong>Userbot:</strong> Menggunakan akun Telegram pribadi Anda sendiri (akun buyer) yang dihubungkan melalui sistem OTP/2FA aman.</li>
                            </ul>
                            <p>
                              Dengan Userbot, iklan Anda terkirim murni atas nama toko Anda sendiri, mendukung kirim foto/video, serta meminimalkan filter watermark toko.
                            </p>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Accordion Item 3: SNK Jaseb & Userbot */}
                  <div className="border border-slate-100 rounded-2xl overflow-hidden bg-white/50">
                    <button
                      onClick={() => {
                        triggerHaptic('light');
                        setOpenAccordion(openAccordion === 'snk_jaseb_userbot' ? null : 'snk_jaseb_userbot');
                      }}
                      className="w-full flex items-center justify-between px-4 py-3.5 text-left text-[10px] font-bold text-slate-700 hover:bg-slate-50 transition-colors duration-200"
                    >
                      <span>📜 SNK</span>

                      <svg
                        className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-300 ${openAccordion === 'snk_jaseb_userbot' ? 'rotate-180 text-geun-blue' : ''}`}
                        fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    <AnimatePresence initial={false}>
                      {openAccordion === 'snk_jaseb_userbot' && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2, ease: 'easeInOut' }}
                          className="overflow-hidden border-t border-slate-100 bg-white"
                        >
                          <div className="p-4 text-[9.5px] leading-relaxed text-slate-500 space-y-4">
                            {/* Section Jasa Sebar */}
                            <div>
                              <p className="font-extrabold text-geun-blue border-b border-slate-100 pb-1 mb-2">─── JASA SEBAR</p>
                              <div className="space-y-1.5 pl-1">
                                <p>✧ Jaseb free request lpm/grub maxs 10 lpm</p>
                                <p>✧ Job freelance minimal order 3 hari keatas, tidak menerima 1 hari</p>
                                <p>✧ Perpanjang jaseb - 1 h sebelum jaseb habis</p>
                                <p>✧ Tidak ada jaminan gacor atau rame orderan, karena tugas admin hanya mempromosikan list kalian</p>
                                <p>✧ Tidak menerima jaseb bentuk list sebar penipu</p>
                                <p>✧ Semua orderan diproses sesuai antrian yang ada</p>
                              </div>
                            </div>
                            
                            {/* Section Userbot */}
                            <div>
                              <p className="font-extrabold text-geun-purple border-b border-slate-100 pb-1 mb-2">──── USERBOT</p>
                              <div className="space-y-1.5 pl-1">
                                <p>✧ Gunakan akun id 1/2/5/6 dan sudah melakukan interaksi untuk meminimalisir terkena deak</p>
                                <p>✧ Akun terkena deak mendapatkan garansi userbot sampai durasi habis dan chat ulang admin buat konfirmasi</p>
                                <p>✧ Dilarang menghapus device userbot di akun kalian, jika hapus device tidak ada garansi userbot</p>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </section>


              </motion.div>

            )}

            {activeTab === 'profile' && (
              <motion.div
                key="profile"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
                className="space-y-6"
              >
              <div className="glass-panel rounded-3xl p-6 text-center space-y-4 border border-slate-200/60 shadow-soft">
                <div className="flex justify-center">
                  {user?.photo_url ? (
                    <img src={user.photo_url} alt="Profile" className="w-20 h-20 rounded-3xl border-2 border-geun-blue object-cover shadow-[0_4px_12px_rgba(0,122,255,0.15)]" />
                  ) : (
                    <div className="w-20 h-20 bg-gradient-to-br from-geun-blue to-geun-purple rounded-3xl flex items-center justify-center font-black text-white text-3xl shadow-lg">
                      {getDisplayName().charAt(0)}
                    </div>
                  )}
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-800 leading-tight tracking-wide">{getDisplayName()}</h3>
                  <p className="text-xs font-semibold text-slate-400">{getUsername()}</p>
                </div>
                
                <div className="h-[1px] bg-slate-200 my-2"></div>
                
                <div className="grid grid-cols-2 gap-3 text-left">
                  <div className="bg-slate-100/50 p-3.5 rounded-xl border border-slate-200/40">
                    <p className="text-[7.5px] text-slate-400 uppercase font-bold tracking-widest">ID Telegram</p>
                    <p className="text-xs font-bold text-slate-800 mt-1">{user?.id || '8844645901'}</p>
                  </div>
                  <div className="bg-slate-100/50 p-3.5 rounded-xl border border-slate-200/40">
                    <p className="text-[7.5px] text-slate-400 uppercase font-bold tracking-widest">Sesi Sinyal</p>
                    <p className="text-xs font-bold text-emerald-600 mt-1">Connected</p>
                  </div>
                </div>

                <div className="h-[1px] bg-slate-100 my-1"></div>

                <div className="space-y-2.5 text-left text-xs">
                  <div className="flex justify-between items-center bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                    <span className="font-semibold text-slate-500">Status Userbot:</span>
                    <span className={`font-bold uppercase tracking-wider text-[9px] px-2 py-0.5 rounded-full ${
                      stats.userBotStatus === 'connected' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                    }`}>
                      {stats.userBotStatus === 'connected' ? 'Connected' : 'Disconnected'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                    <span className="font-semibold text-slate-500">Paket Aktif:</span>
                    <span className="font-bold text-slate-700">
                      {stats.userPackage === 'Tidak Aktif' ? 'Tidak Ada' : stats.userPackage}
                    </span>
                  </div>
                  {stats.userPackage !== 'Tidak Aktif' && (
                    <div className="grid grid-cols-2 gap-2 mt-1">
                      <div className="bg-slate-50 p-2 rounded-xl border border-slate-100 text-center">
                        <p className="text-[7.5px] text-slate-400 font-bold uppercase tracking-widest">Kapasitas</p>
                        <p className="font-bold text-geun-blue text-xs mt-0.5">{stats.userLpm} LPM</p>
                      </div>
                      <div className="bg-slate-50 p-2 rounded-xl border border-slate-100 text-center">
                        <p className="text-[7.5px] text-slate-400 font-bold uppercase tracking-widest">Masa Aktif</p>
                        <p className="font-bold text-emerald-600 text-xs mt-0.5">{stats.userDays} Hari</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              </motion.div>
            )}

            {activeTab === 'tools' && (
              <motion.div
                key="tools"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
                className="space-y-6 pb-20"
              >
                {/* Header Section */}
                <div className="text-center space-y-1">
                  <h2 className="text-lg font-black text-slate-800 tracking-wide uppercase">⚡ Fitur Gratis</h2>
                  <p className="text-[10px] text-slate-400 font-semibold">Tingkatkan efisiensi promosi Anda secara instan</p>
                </div>

                {/* Card 1: AI Wording Beautifier */}
                <div className="glass-panel rounded-3xl p-5 border border-slate-200/60 shadow-soft space-y-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-2xl bg-geun-blue/10 flex items-center justify-center text-geun-blue shadow-sm">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-xs font-black text-slate-800 uppercase tracking-wide">AI Wording Beautifier</h3>
                      <p className="text-[8.5px] text-slate-400 font-semibold mt-0.5">Format tulisan promosi Anda menjadi mewah</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <textarea
                      value={rawWording}
                      onChange={(e) => setRawWording(e.target.value)}
                      placeholder="Tempel pesan promosi mentah Anda di sini..."
                      className="w-full min-h-[100px] text-[10px] p-3.5 bg-[#F8FAFC] border border-slate-200 rounded-2xl focus:outline-none focus:ring-1 focus:ring-geun-blue/50 text-slate-700 shadow-inner leading-relaxed resize-none"
                    />

                    {/* Template Selector Chips */}
                    <div className="space-y-1.5">
                      <label className="text-[8.5px] font-black text-slate-400 uppercase tracking-wider block">Pilih Desain Teks</label>
                      <div className="grid grid-cols-3 gap-2">
                        {(['premium', 'minimalist', 'flash'] as const).map((temp) => (
                          <button
                            key={temp}
                            type="button"
                            onClick={() => { triggerHaptic('light'); setSelectedTemplate(temp); }}
                            className={`py-2 rounded-xl text-[9px] font-black uppercase tracking-wider border transition-all duration-300 ${
                              selectedTemplate === temp
                                ? 'bg-geun-blue text-white border-geun-blue shadow-md'
                                : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'
                            }`}
                          >
                            {temp}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Preview Box */}
                    {rawWording.trim() && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <label className="text-[8.5px] font-black text-slate-400 uppercase tracking-wider">Pratinjau Hasil</label>
                          <button
                            onClick={() => {
                              triggerHaptic('medium');
                              navigator.clipboard.writeText(enhancedWording(rawWording, selectedTemplate));
                              setWordingCopied(true);
                              setTimeout(() => setWordingCopied(false), 2000);
                            }}
                            className={`px-3 py-1 rounded-lg text-[8px] font-black uppercase tracking-wider transition-all duration-200 ${
                              wordingCopied ? 'bg-emerald-50 text-emerald-600 border border-emerald-200' : 'bg-geun-blue/10 text-geun-blue hover:bg-geun-blue/20'
                            }`}
                          >
                            {wordingCopied ? 'Tersalin' : 'Salin Hasil'}
                          </button>
                        </div>
                        <div className="p-4 bg-[#F8FAFC] border border-slate-200 rounded-2xl text-[9.5px] font-mono text-slate-700 whitespace-pre-wrap leading-relaxed shadow-inner max-h-[150px] overflow-y-auto">
                          {enhancedWording(rawWording, selectedTemplate)}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Card 2: LPM Group Auto-Scanner */}
                <div className="glass-panel rounded-3xl p-5 border border-slate-200/60 shadow-soft space-y-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-2xl bg-geun-purple/10 flex items-center justify-center text-geun-purple shadow-sm">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-xs font-black text-slate-800 uppercase tracking-wide">LPM Auto-Scanner Helper</h3>
                      <p className="text-[8.5px] text-slate-400 font-semibold mt-0.5">Validasi & simpan grup LPM aktif secara massal</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <p className="text-[9px] text-slate-500 leading-relaxed font-semibold">
                      Masukkan satu atau lebih username/link grup LPM di bawah ini (pisah dengan spasi atau baris baru). Sistem akan menghasilkan perintah pemindaian otomatis untuk bot Anda.
                    </p>
                    <textarea
                      value={lpmToScan}
                      onChange={(e) => setLpmToScan(e.target.value)}
                      placeholder="Masukkan daftar username atau link grup LPM... (Contoh: @lpm_store @lpm_promosi_jualbeli)"
                      className="w-full min-h-[90px] text-[10px] p-3.5 bg-[#F8FAFC] border border-slate-200 rounded-2xl focus:outline-none focus:ring-1 focus:ring-geun-purple/50 text-slate-700 shadow-inner leading-relaxed resize-none"
                    />

                    {lpmToScan.trim() && (
                      (() => {
                        const links = lpmToScan.match(/(?:https?:\/\/)?(?:t\.me\/|@)?([a-zA-Z0-9_]{5,32}|joinchat\/[a-zA-Z0-9_\-]+)/g) || [];
                        const formatted = links.map(l => l.startsWith('@') || l.includes('t.me') ? l : `@${l}`).join(' ');
                        const scanCmd = `/scan ${formatted}`;

                        return (
                          <div className="space-y-3.5">
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <label className="text-[8.5px] font-black text-slate-400 uppercase tracking-wider">Perintah Scan Bot</label>
                                <button
                                  onClick={() => {
                                    triggerHaptic('medium');
                                    navigator.clipboard.writeText(scanCmd);
                                    setLpmCopied(true);
                                    setTimeout(() => setLpmCopied(false), 2000);
                                  }}
                                  className={`px-3 py-1 rounded-lg text-[8px] font-black uppercase tracking-wider transition-all duration-200 ${
                                    lpmCopied ? 'bg-emerald-50 text-emerald-600 border border-emerald-200' : 'bg-geun-purple/10 text-geun-purple hover:bg-geun-purple/20'
                                  }`}
                                >
                                  {lpmCopied ? 'Tersalin' : 'Salin Perintah'}
                                </button>
                              </div>
                              <div className="p-3.5 bg-[#F8FAFC] border border-slate-200 rounded-2xl text-[9.5px] font-mono text-slate-700 leading-relaxed shadow-inner break-all">
                                {scanCmd}
                              </div>
                            </div>

                            <a
                              href={`https://t.me/GeunIDJaseb_Bot?text=${encodeURIComponent(scanCmd)}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={() => triggerHaptic('heavy')}
                              className="w-full bg-gradient-to-r from-geun-blue to-geun-purple text-white py-3 rounded-2xl text-[9px] font-black uppercase tracking-wider text-center block shadow-soft hover:opacity-90 active:scale-98 transition-all"
                            >
                              🚀 Kirim & Scan di Bot Telegram
                            </a>
                          </div>
                        );
                      })()
                    )}
                  </div>
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </main>

        {/* Premium Bottom Sheet Modal Drawer */}
        <AnimatePresence>
          {isModalOpen && selectedPackage && (
            <div className="fixed inset-0 z-50 flex items-end justify-center">
              {/* Backdrop blur overlay */}
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setIsModalOpen(false)}
                className="absolute inset-0 bg-slate-900/40 backdrop-blur-md"
              />
              
              {/* Bottom Sheet Body */}
              <motion.div 
                initial={{ y: "100%" }}
                animate={{ y: 0 }}
                exit={{ y: "100%" }}
                transition={{ type: "spring", damping: 25, stiffness: 220 }}
                className="w-full max-w-md bg-white border-t border-slate-200/80 rounded-t-[32px] p-6 pb-8 space-y-5 shadow-2xl relative z-10 max-h-[85%] overflow-y-auto"
              >
                {/* Bottom Sheet Pull Indicator Bar */}
                <div className="w-12 h-1 bg-slate-200 rounded-full mx-auto mb-1"></div>

                {checkoutStep === 'select_payment' ? (
                  <div className="space-y-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="text-sm font-black text-geun-dark uppercase tracking-wider">Metode Pembayaran</h3>
                        <p className="text-[9px] text-geun-muted font-bold mt-0.5">Pilih opsi pembayaran Anda</p>
                      </div>
                      <button
                        onClick={() => { triggerHaptic('light'); setIsModalOpen(false); }}
                        className="w-6.5 h-6.5 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-400 font-bold text-xs transition-colors"
                      >
                        ✕
                      </button>
                    </div>

                    <div className="space-y-3 pt-2">
                      {/* Option 1: QRIS */}
                      <div
                        onClick={() => { triggerHaptic('light'); setSelectedPaymentMethod('qris'); }}
                        className={`glass-panel rounded-2xl p-4 flex items-center justify-between border cursor-pointer transition-all duration-300 relative overflow-hidden ${
                          selectedPaymentMethod === 'qris'
                            ? 'border-geun-blue bg-geun-blue/5 shadow-active-glow ring-1 ring-geun-blue'
                            : 'border-slate-200/60 hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-center gap-3.5">
                          <div className={`w-12 h-12 rounded-xl flex items-center justify-center border transition-colors ${
                            selectedPaymentMethod === 'qris' ? 'bg-white border-geun-blue/20' : 'bg-slate-100 border-slate-200'
                          }`}>
                            <svg className={`w-7 h-7 ${selectedPaymentMethod === 'qris' ? 'text-geun-blue' : 'text-slate-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 013.75 9.375v-4.5zM3.75 14.625c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5a1.125 1.125 0 01-1.125-1.125v-4.5zM13.5 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0113.5 9.375v-4.5z" />
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15 15h.008v.008H15V15zm0 2.25h.008v.008H15v-.008zm-.75-.75h.008v.008h-.008v-.008zm2.25-.75h.008v.008H16.5V15zm0 2.25h.008v.008H16.5v-.008zm-.75-.75h.008v.008h-.008v-.008zm2.25-.75h.008v.008H18V15zm0 2.25h.008v.008H18v-.008zm-.75-.75h.008v.008h-.008v-.008zm-2.25-2.25h.008v.008H15v-.008zm0 4.5h.008v.008H15v-.008z" />
                            </svg>
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <p className="text-xs font-black text-slate-800 leading-none tracking-wide">QRIS Otomatis (KlikQRIS)</p>
                              <span className="text-[7px] text-white px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wider shimmer-badge">
                                Otomatis
                              </span>
                            </div>
                            <p className="text-[9px] text-slate-400 font-semibold mt-1">Verifikasi instan & otomatis 24/7.</p>
                          </div>
                        </div>
                        <div className={`w-5 h-5 rounded-full border flex items-center justify-center transition-colors ${
                          selectedPaymentMethod === 'qris' ? 'border-geun-blue bg-geun-blue' : 'border-slate-300'
                        }`}>
                          {selectedPaymentMethod === 'qris' && (
                            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                      </div>

                      {/* Option 2: Transfer Manual */}
                      <div
                        onClick={() => { triggerHaptic('light'); setSelectedPaymentMethod('manual'); }}
                        className={`glass-panel rounded-2xl p-4 flex items-center justify-between border cursor-pointer transition-all duration-300 relative overflow-hidden ${
                          selectedPaymentMethod === 'manual'
                            ? 'border-geun-blue bg-geun-blue/5 shadow-active-glow ring-1 ring-geun-blue'
                            : 'border-slate-200/60 hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-center gap-3.5">
                          <div className={`w-12 h-12 rounded-xl flex items-center justify-center border transition-colors ${
                            selectedPaymentMethod === 'manual' ? 'bg-white border-geun-blue/20' : 'bg-slate-100 border-slate-200'
                          }`}>
                            <svg className={`w-7 h-7 ${selectedPaymentMethod === 'manual' ? 'text-geun-blue' : 'text-slate-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" />
                            </svg>
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <p className="text-xs font-black text-slate-800 leading-none tracking-wide">Transfer Manual / E-Wallet</p>
                            </div>
                            <p className="text-[9px] text-slate-400 font-semibold mt-1">BCA, DANA, Gopay.</p>
                          </div>
                        </div>
                        <div className={`w-5 h-5 rounded-full border flex items-center justify-center transition-colors ${
                          selectedPaymentMethod === 'manual' ? 'border-geun-blue bg-geun-blue' : 'border-slate-300'
                        }`}>
                          {selectedPaymentMethod === 'manual' && (
                            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Elegant Action Button */}
                    <div className="pt-4">
                      <button
                        disabled={!selectedPaymentMethod}
                        onClick={() => { triggerHaptic('medium'); setCheckoutStep('invoice'); }}
                        className={`w-full py-3.5 rounded-2xl text-[10px] font-black uppercase tracking-wider text-center block transition-all duration-300 ${
                          selectedPaymentMethod
                            ? 'bg-gradient-to-r from-geun-blue to-geun-purple text-white shadow-premium active:scale-98 cursor-pointer'
                            : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                        }`}
                      >
                        Lanjutkan Pembayaran
                      </button>
                    </div>
                  </div>
                ) : (
                  (() => {
                    const currentPrice = selectedPackage.type === 'userbot' ? selectedPackage.price * accountCount : selectedPackage.price;

                    return (
                      <div className="space-y-5">
                        <div className="flex justify-between items-center">
                          <button
                            onClick={() => { triggerHaptic('light'); setCheckoutStep('select_payment'); }}
                            className="flex items-center gap-1.5 text-[9.5px] font-black text-geun-blue uppercase tracking-wider hover:opacity-80 transition-all duration-300"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                            </svg>
                            Ubah Metode
                          </button>
                          <button
                            onClick={() => { triggerHaptic('light'); setIsModalOpen(false); }}
                            className="w-6.5 h-6.5 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-400 font-bold text-xs transition-colors"
                          >
                            ✕
                          </button>
                        </div>

                        <div className="flex justify-between items-start">
                          <div>
                            <h3 className="text-sm font-black text-geun-dark uppercase tracking-wider">Rincian Layanan</h3>
                            <p className="text-[9px] text-geun-muted font-bold mt-0.5">Konfirmasi Pesanan Jaseb Anda</p>
                          </div>
                        </div>

                        {/* Elegant Invoice layout */}
                        <div className="bg-[#F8FAFC] border border-slate-200/60 p-4.5 rounded-2xl space-y-3 shadow-soft">
                          <div className="flex justify-between text-xs items-center">
                            <span className="text-geun-muted font-bold">Layanan</span>
                            <span className="font-black text-geun-dark uppercase bg-geun-blue/10 text-geun-blue px-2.5 py-0.5 rounded-md text-[10px]">
                              Jaseb {selectedPackage.type}
                            </span>
                          </div>

                          <div className="flex justify-between text-xs items-center border-t border-slate-200/50 pt-3">
                            <span className="text-geun-muted font-bold">Limit LPM</span>
                            <span className="font-black text-geun-dark">{selectedPackage.lpm} Grup LPM</span>
                          </div>

                          <div className="flex justify-between text-xs items-center border-t border-slate-200/50 pt-3">
                            <span className="text-geun-muted font-bold">Durasi Aktif</span>
                            <span className="font-black text-geun-dark">{selectedPackage.duration}</span>
                          </div>

                          {selectedPackage.type === 'userbot' && (
                            <div className="flex justify-between text-xs items-center border-t border-slate-200/50 pt-3">
                              <span className="text-geun-muted font-bold">Jumlah Akun</span>
                              <span className="font-black text-geun-dark">{accountCount} Akun</span>
                            </div>
                          )}

                          <div className="flex justify-between text-xs items-center border-t border-slate-200/50 pt-3">
                            <span className="text-geun-muted font-bold">Metode Pembayaran</span>
                            <span className="font-black text-geun-dark">
                              {selectedPaymentMethod === 'qris' ? 'QRIS (KlikQRIS)' : 'Transfer Manual / E-Wallet'}
                            </span>
                          </div>

                          <div className="flex justify-between text-xs items-center border-t border-slate-200/50 pt-3">
                            <span className="text-geun-muted font-bold">Total Harga</span>
                            <span className="font-black text-geun-blue text-sm">Rp {currentPrice.toLocaleString('id-ID')}</span>
                          </div>
                        </div>

                        {/* Interactive Quantity Selector for Userbot */}
                        {selectedPackage.type === 'userbot' && (
                          <div className="space-y-3 bg-[#F8FAFC] p-4.5 rounded-2xl border border-slate-200/50 shadow-soft">
                            <div className="flex items-center justify-between">
                              <div>
                                <label className="text-[10px] font-black text-slate-800 uppercase tracking-wider">
                                  Jumlah Akun Userbot
                                </label>
                                <p className="text-[8px] text-slate-400 font-semibold mt-0.5">
                                  Beli untuk banyak akun sekaligus
                                </p>
                              </div>
                              
                              <div className="flex items-center gap-3.5 bg-white border border-slate-200 rounded-xl p-1 shadow-sm">
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (accountCount > 1) {
                                      triggerHaptic('medium');
                                      setAccountCount(prev => {
                                        const next = prev - 1;
                                        if (next <= 1) setUserIdsInput('');
                                        return next;
                                      });
                                    }
                                  }}
                                  className="w-7 h-7 rounded-lg bg-slate-50 hover:bg-slate-100 flex items-center justify-center text-slate-600 font-black text-sm active:scale-90 transition-all select-none border border-slate-200/50"
                                >
                                  -
                                </button>
                                <span className="text-xs font-extrabold text-slate-800 min-w-[36px] text-center">
                                  {accountCount}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => {
                                    triggerHaptic('medium');
                                    setAccountCount(prev => prev + 1);
                                  }}
                                  className="w-7 h-7 rounded-lg bg-slate-50 hover:bg-slate-100 flex items-center justify-center text-slate-600 font-black text-sm active:scale-90 transition-all select-none border border-slate-200/50"
                                >
                                  +
                                </button>
                              </div>
                            </div>

                            {/* UserID List Input for Multi-Account Purchase */}
                            {accountCount > 1 && (
                              <div className="space-y-1.5 pt-1.5 border-t border-slate-200/60">
                                <label className="text-[9px] font-black text-slate-700 uppercase tracking-wider block">
                                  Daftar UserID Akun (Pisah dengan spasi)
                                </label>
                                <input
                                  type="text"
                                  value={userIdsInput}
                                  onChange={(e) => setUserIdsInput(e.target.value)}
                                  placeholder="Contoh: 8310379779 8371902690 8188030043"
                                  className="w-full text-[10px] p-2.5 bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-geun-blue/50 text-slate-700 shadow-inner"
                                />
                                <p className="text-[7.5px] text-slate-400 font-semibold leading-relaxed">
                                  *Pastikan akun target sudah melakukan start pada bot @GeunIDJaseb_Bot terlebih dahulu.
                                </p>
                              </div>
                            )}

                            <div className="h-[1px] bg-slate-200/60 my-1"></div>
                            <p className="text-[7.5px] text-slate-400 font-bold uppercase tracking-wider leading-relaxed">
                              *Catatan: <span className="text-geun-blue font-extrabold">Tempel daftar UserID Anda langsung di Telegram</span> saat mengirim format ini agar tata letak tidak berantakan.
                            </p>
                          </div>
                        )}

                        {/* Premium Caution Warning for Userbot Account Age */}
                        {selectedPackage.type === 'userbot' && (
                          <div className="bg-amber-50 border border-amber-200/80 rounded-2xl p-3.5 flex items-start gap-2.5 shadow-soft">
                            <svg className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <div className="space-y-0.5">
                              <p className="text-[9.5px] font-black text-amber-800 uppercase tracking-wider">Peringatan Keamanan Akun</p>
                              <p className="text-[8.5px] font-semibold text-amber-700/90 leading-normal">
                                Pastikan akun Telegram Anda berusia minimal <span className="font-bold">5 bulan ke atas</span> demi mengurangi risiko penangguhan/banned akun oleh sistem anti-spam Telegram.
                              </p>
                            </div>
                          </div>
                        )}

                        {/* Plain, clean order format copy box (No IDE headers, pure elegant copy-box) */}
                        <div className="space-y-2">
                          <div className="flex items-center gap-1.5 ml-1">
                            <svg className="w-3.5 h-3.5 text-geun-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 002-2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                            </svg>
                            <label className="text-[9px] font-bold text-geun-muted uppercase tracking-wider">Format Pesanan</label>
                          </div>

                          <div className="relative">
                            <div className="bg-[#F8FAFC] rounded-2xl p-4 border border-slate-200/70 font-mono text-[9.5px] leading-relaxed relative overflow-hidden select-none text-slate-700 shadow-inner">
                              {selectedPackage.type === 'userbot' ? (
                                <>
                                  <p className="font-bold text-geun-blue border-b border-slate-200/50 pb-1.5 mb-2">🛎 𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧</p>
                                  <p>– Username: "{getUsername() || '@username'}"</p>
                                  <p>– Durasi userbot: "{selectedPackage.duration}"</p>
                                  <p>– Nomor Telegram: "(isi nomor HP akun userbot Anda)"</p>
                                  <p>– Password: "(isi password jika ada 2FA, jika tidak kosongkan)"</p>
                                  <p>– Payment: "{selectedPaymentMethod === 'qris' ? 'QRIS' : 'Transfer Manual'}"</p>
                                  <p>– Total Harga: Rp {currentPrice.toLocaleString('id-ID')}</p>
                                </>
                              ) : (
                                <>
                                  <p className="font-bold text-geun-blue border-b border-slate-200/50 pb-1.5 mb-2">🛎 𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦</p>
                                  <p>– Username akun: "{getUsername() || '@username'}"</p>
                                  <p>– Durasi Jaseb: "{selectedPackage.duration}"</p>
                                  <p>– Paket jaseb: "JASEB {selectedPackage.type.toUpperCase()} {selectedPackage.lpm} LPM"</p>
                                  <p>– Payment: "{selectedPaymentMethod === 'qris' ? 'QRIS' : 'Transfer Manual'}"</p>
                                  <p>– Request Lpm: "(isi @lpm1 @lpm2, kalau gaada kosongin/hapus)"</p>
                                  <p>– Total Harga: Rp {currentPrice.toLocaleString('id-ID')}</p>
                                </>
                              )}


                            </div>

                            <button
                              onClick={handleCopyOrderFormat}
                              className={`absolute top-3 right-3 px-3 py-1.5 rounded-xl text-[9px] font-black uppercase tracking-wider transition-all duration-300 ${
                                copied
                                  ? 'bg-emerald-50 text-emerald-600 border border-emerald-200'
                                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 shadow-sm'
                              }`}
                            >
                              {copied ? 'Tersalin' : 'Salin'}
                            </button>
                          </div>
                        </div>

                        {/* Elegant Action Button */}
                        <div className="pt-2">
                          <a
                            href={`https://t.me/Geun_ID?text=${encodeURIComponent(getOrderFormatText())}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={() => triggerHaptic('heavy')}
                            className="bg-gradient-to-r from-geun-blue to-geun-purple hover:opacity-90 active:scale-98 text-white py-3.5 rounded-2xl text-[10px] font-black uppercase tracking-wider text-center block shadow-premium transition-all duration-300"
                          >
                            💬 Kirim Format ke Admin
                          </a>
                        </div>
                      </div>
                    );
                  })()
                )}
              </motion.div>
            </div>
          )}
        </AnimatePresence>

        {/* Premium Floating Bottom Glass Tab Bar */}
        <nav className="absolute bottom-6 left-4 right-4 h-16 bg-white/70 backdrop-blur-xl border border-slate-200/80 rounded-3xl flex items-center justify-around px-2 shadow-premium z-40">
          <button 
            onClick={() => handleTabChange('home')}
            className={`flex flex-col items-center justify-center w-12 h-12 rounded-xl transition-spring relative ${activeTab === 'home' ? 'scale-105' : 'text-slate-400 hover:text-slate-600'}`}
          >
            <HomeIcon active={activeTab === 'home'} />
            {activeTab === 'home' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}
          </button>

          <button 
            onClick={() => handleTabChange('tools')}
            className={`flex flex-col items-center justify-center w-12 h-12 rounded-xl transition-spring relative ${activeTab === 'tools' ? 'scale-105' : 'text-slate-400 hover:text-slate-600'}`}
          >
            <ToolsIcon active={activeTab === 'tools'} />
            {activeTab === 'tools' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}
          </button>

          <button 
            onClick={() => handleTabChange('profile')}
            className={`flex flex-col items-center justify-center w-12 h-12 rounded-xl transition-spring relative ${activeTab === 'profile' ? 'scale-105' : 'text-slate-400 hover:text-slate-600'}`}
          >
            <UserIcon active={activeTab === 'profile'} />
            {activeTab === 'profile' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}
          </button>
        </nav>

      </div>
    </div>
  );
};

export default Dashboard;
