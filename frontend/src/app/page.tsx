"use client";

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import pricesData from '../prices.json';
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
  const [checkoutStep, setCheckoutStep] = useState<'select_payment' | 'qris_invoice' | 'manual_invoice' | 'success_screen'>('select_payment');
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<'qris' | 'manual' | null>(null);
  const [accountCount, setAccountCount] = useState(1);
  const [loadingCheckout, setLoadingCheckout] = useState(false);
  const [qrisData, setQrisData] = useState<{
    transaction_id: string;
    payment_url: string;
    qris_url: string;
    total_amount: number;
    expired_at: string;
  } | null>(null);
  const [timeLeft, setTimeLeft] = useState(1800);

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



  // Pricing Data with Cheaper/Discounted Prices loaded dynamically
  const [pricingData, setPricingData] = useState<Record<'regular' | 'forward' | 'userbot', PackageItem[]>>(pricesData as any);

  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const res = await fetch('/api/prices');
        if (res.ok) {
          const data = await res.json();
          if (data && (data.regular || data.forward || data.userbot)) {
            setPricingData(data);
          }
        }
      } catch (err) {
        console.error("Gagal mengambil data harga dinamis:", err);
      }
    };
    fetchPrices();
  }, []);

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

  // Countdown timer effect
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (checkoutStep === 'qris_invoice' && timeLeft > 0) {
      timer = setInterval(() => {
        setTimeLeft(prev => prev - 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [checkoutStep, timeLeft]);

  // Format countdown time
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Automatic check status polling function
  const checkStatusAutomatic = async (trxId: string) => {
    try {
      const res = await fetch(`/api/check-status/${trxId}`);
      const data = await res.json();
      if (data.status && data.payment_status === 'success') {
        triggerHaptic('heavy');
        setCheckoutStep('success_screen');
        return true;
      }
    } catch (err) {
      console.error("Auto polling error:", err);
    }
    return false;
  };

  // Polling effect when QRIS page is active
  useEffect(() => {
    let pollInterval: NodeJS.Timeout;
    if (checkoutStep === 'qris_invoice' && qrisData?.transaction_id) {
      pollInterval = setInterval(async () => {
        const isPaid = await checkStatusAutomatic(qrisData.transaction_id);
        if (isPaid) {
          clearInterval(pollInterval);
        }
      }, 4000);
    }
    return () => clearInterval(pollInterval);
  }, [checkoutStep, qrisData]);

  // Handler Lanjutkan Pembayaran (Continue)
  const handleContinueCheckout = async () => {
    if (!selectedPaymentMethod) {
      alert("Silakan pilih metode pembayaran terlebih dahulu.");
      return;
    }

    triggerHaptic('medium');

    if (selectedPaymentMethod === 'manual') {
      setCheckoutStep('manual_invoice');
    } else if (selectedPaymentMethod === 'qris') {
      if (!user) {
        alert("Gagal mendeteksi akun Telegram Anda. Pastikan Anda membuka Mini App ini dari dalam bot Telegram.");
        return;
      }
      if (!selectedPackage) return;

      setLoadingCheckout(true);
      const currentPrice = selectedPackage.type === 'userbot'
        ? selectedPackage.price * accountCount
        : selectedPackage.price;

      const packName = selectedPackage.type === 'userbot'
        ? `Jaseb Userbot ${selectedPackage.duration}`
        : `Jaseb ${selectedPackage.type.toUpperCase()} ${selectedPackage.lpm} LPM ${selectedPackage.duration}`;

      try {
        const payload = {
          user_id: user.id,
          username: user.username || "",
          first_name: user.first_name || "",
          last_name: user.last_name || "",
          package_name: packName,
          amount: currentPrice,
          duration: selectedPackage.duration,
          lpm: selectedPackage.type === 'userbot' ? 0 : selectedPackage.lpm,
          package_type: selectedPackage.type,
          request_lpm: selectedPackage.type !== 'userbot' ? userIdsInput : ""
        };

        const response = await fetch('/api/checkout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        });

        const resData = await response.json();
        if (resData.status && resData.data) {
          setQrisData(resData.data);
          setTimeLeft(1800); // Reset countdown timer to 30 minutes
          setCheckoutStep('qris_invoice');
        } else {
          alert(`❌ Gagal membuat transaksi: ${resData.error || 'Terjadi kesalahan sistem.'}`);
        }
      } catch (err) {
        console.error("Checkout Error:", err);
        alert("❌ Terjadi kesalahan koneksi. Silakan coba lagi.");
      } finally {
        setLoadingCheckout(false);
      }
    }
  };

  // Manual payment status check button click handler
  const handleCheckQRISStatusManual = async () => {
    if (!qrisData) return;
    triggerHaptic('heavy');
    setLoadingCheckout(true);
    try {
      const res = await fetch(`/api/check-status/${qrisData.transaction_id}`);
      const data = await res.json();
      if (data.status) {
        if (data.payment_status === 'success') {
          triggerHaptic('heavy');
          setCheckoutStep('success_screen');
        } else {
          alert("⏳ Pembayaran belum terdeteksi. Silakan bayar terlebih dahulu.");
        }
      } else {
        alert(`❌ Gagal cek status: ${data.error || 'Terjadi kesalahan sistem.'}`);
      }
    } catch (err) {
      console.error(err);
      alert("❌ Terjadi kesalahan koneksi.");
    } finally {
      setLoadingCheckout(false);
    }
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

                {(() => {
                  const currentPrice = selectedPackage.type === 'userbot' ? selectedPackage.price * accountCount : selectedPackage.price;
                  return (
                    <>
                      <style dangerouslySetInnerHTML={{__html: `
                        @keyframes scan-laser {
                          0% { top: 0%; }
                          50% { top: 100%; }
                          100% { top: 0%; }
                        }
                        .animate-scan {
                          animation: scan-laser 2.5s linear infinite;
                        }
                      `}} />

                      {/* STEP 1: SELECT PAYMENT */}
                      {checkoutStep === 'select_payment' && (
                        <div className="space-y-4">
                          <div className="flex justify-between items-start">
                            <div>
                              <h3 className="text-sm font-black text-geun-dark uppercase tracking-wider">Metode Pembayaran</h3>
                              <p className="text-[9px] text-geun-muted font-bold mt-0.5">Pilih opsi pembayaran Anda</p>
                            </div>
                            <button
                              onClick={() => { triggerHaptic('light'); setIsModalOpen(false); }}
                              className="w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-400 font-bold text-xs transition-colors"
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
                              disabled={!selectedPaymentMethod || loadingCheckout}
                              onClick={handleContinueCheckout}
                              className={`w-full py-3.5 rounded-2xl text-[10px] font-black uppercase tracking-wider text-center block transition-all duration-300 ${
                                selectedPaymentMethod && !loadingCheckout
                                  ? 'bg-gradient-to-r from-geun-blue to-geun-purple text-white shadow-premium active:scale-98 cursor-pointer'
                                  : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                              }`}
                            >
                              {loadingCheckout ? (
                                <span className="flex items-center justify-center gap-2">
                                  <svg className="animate-spin h-3.5 w-3.5 text-slate-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                  Menyiapkan...
                                </span>
                              ) : (
                                'Lanjutkan Pembayaran'
                              )}
                            </button>
                          </div>
                        </div>
                      )}

                      {/* STEP 2A: QRIS INVOICE VIEW */}
                      {checkoutStep === 'qris_invoice' && (
                        <div className="space-y-5">
                          <div className="flex justify-between items-center">
                            <button
                              onClick={() => { triggerHaptic('light'); setCheckoutStep('select_payment'); }}
                              className="flex items-center gap-1.5 text-[9.5px] font-black text-geun-blue uppercase tracking-wider hover:opacity-80 transition-all duration-300"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                              </svg>
                              Kembali
                            </button>
                            <button
                              onClick={() => { triggerHaptic('light'); setIsModalOpen(false); }}
                              className="w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-400 font-bold text-xs transition-colors"
                            >
                              ✕
                            </button>
                          </div>

                          <div className="text-center space-y-1">
                            <h3 className="text-sm font-black text-geun-dark uppercase tracking-wider">QRIS Pembayaran Otomatis</h3>
                            <p className="text-[9px] text-geun-muted font-bold">Pindai barcode di bawah ini untuk membayar</p>
                          </div>

                          {/* Barcode Render & Scanning laser animation */}
                          <div className="flex flex-col items-center justify-center space-y-3">
                            <div className="relative p-3.5 bg-white border border-slate-200/80 rounded-[24px] shadow-premium overflow-hidden">
                              <div className="absolute left-0 right-0 h-[2.5px] bg-red-500 animate-scan"></div>
                              {qrisData?.qris_url ? (
                                <img
                                  src={qrisData.qris_url}
                                  alt="QRIS Barcode"
                                  className="w-48 h-48 object-contain"
                                />
                              ) : (
                                <div className="w-48 h-48 flex items-center justify-center bg-slate-50 text-slate-400 text-xs font-semibold">
                                  QRIS Tidak Tersedia
                                </div>
                              )}
                            </div>

                            {/* Detail Tagihan & Countdown */}
                            <div className="flex items-center justify-between w-full bg-slate-50 border border-slate-200/50 px-4 py-3 rounded-2xl">
                              <div className="text-left">
                                <p className="text-[8px] text-slate-400 font-bold uppercase tracking-wider">Total Tagihan</p>
                                <p className="text-sm font-black text-geun-blue">
                                  Rp {qrisData?.total_amount.toLocaleString('id-ID')}
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="text-[8px] text-slate-400 font-bold uppercase tracking-wider">Batas Waktu</p>
                                <p className="text-xs font-black text-red-500 flex items-center gap-1.5 justify-end">
                                  <span className="w-2 h-2 rounded-full bg-red-500 animate-ping shrink-0"></span>
                                  {formatTime(timeLeft)}
                                </p>
                              </div>
                            </div>
                          </div>

                          {/* Guide / Instruction */}
                          <div className="bg-amber-50/70 border border-amber-200/60 p-4 rounded-2xl text-[9px] text-amber-800 leading-relaxed space-y-1">
                            <p className="font-black uppercase tracking-wide">💡 PANDUAN SCAN QRIS:</p>
                            <ul className="list-disc pl-3 font-semibold space-y-0.5 text-amber-700/90">
                              <li>Simpan/screenshot QRIS di atas atau gunakan HP lain untuk scan.</li>
                              <li>Dapat discan menggunakan GoPay, DANA, OVO, ShopeePay, LinkAja, atau m-Banking apa saja.</li>
                              <li>Sistem akan mendeteksi & memproses aktivasi pesanan secara otomatis segera setelah transfer diterima.</li>
                            </ul>
                          </div>

                          {/* Status Indicator & Alternative Web Checkout */}
                          <div className="pt-2 flex flex-col items-center justify-center space-y-3">
                            <div className="flex items-center gap-2 text-[10px] font-extrabold text-slate-500 bg-slate-100 px-4 py-2.5 rounded-full border border-slate-200/50 shadow-inner">
                              <span className="w-2.5 h-2.5 rounded-full border-2 border-geun-blue border-t-transparent animate-spin shrink-0"></span>
                              <span className="animate-pulse tracking-wide uppercase">Menunggu Pembayaran Otomatis...</span>
                            </div>

                            {qrisData?.payment_url && (
                              <a
                                href={qrisData.payment_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[9px] font-black text-geun-muted hover:text-geun-blue uppercase tracking-wider underline transition-colors"
                              >
                                Alternatif: Bayar via Browser / Web Checkout ↗
                              </a>
                            )}
                          </div>
                        </div>
                      )}

                      {/* STEP 2B: MANUAL INVOICE VIEW */}
                      {checkoutStep === 'manual_invoice' && (
                        <div className="space-y-5">
                          <div className="flex justify-between items-center">
                            <button
                              onClick={() => { triggerHaptic('light'); setCheckoutStep('select_payment'); }}
                              className="flex items-center gap-1.5 text-[9.5px] font-black text-geun-blue uppercase tracking-wider hover:opacity-80 transition-all duration-300"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                              </svg>
                              Kembali
                            </button>
                            <button
                              onClick={() => { triggerHaptic('light'); setIsModalOpen(false); }}
                              className="w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-400 font-bold text-xs transition-colors"
                            >
                              ✕
                            </button>
                          </div>

                          <div className="text-center space-y-1">
                            <h3 className="text-sm font-black text-geun-dark uppercase tracking-wider">Transfer Manual</h3>
                            <p className="text-[9px] text-geun-muted font-bold">Lakukan transfer lalu kirim format & bukti ke Admin</p>
                          </div>

                          {/* Bank Accounts */}
                          <div className="bg-slate-50 border border-slate-200/50 p-4 rounded-2xl space-y-2.5 text-xs text-slate-700">
                            <p className="font-extrabold text-slate-800 uppercase text-[9px] tracking-wide text-geun-blue">Rekening Pembayaran:</p>
                            <div className="space-y-2 font-semibold text-[10px] text-slate-600">
                              <p className="flex justify-between">
                                <span>🏦 BANK BCA:</span>
                                <span className="font-black text-slate-800">8840742131 a/n GEUN</span>
                              </p>
                              <p className="flex justify-between">
                                <span>📱 DANA / GOPAY:</span>
                                <span className="font-black text-slate-800">0821-1234-5678 a/n GEUN</span>
                              </p>
                            </div>
                          </div>

                          {/* Quantities for Userbot */}
                          {selectedPackage.type === 'userbot' && (
                            <div className="space-y-3 bg-[#F8FAFC] p-4 rounded-2xl border border-slate-200/50 shadow-soft">
                              <div className="flex items-center justify-between">
                                <div>
                                  <label className="text-[10px] font-black text-slate-800 uppercase tracking-wider">Jumlah Akun Userbot</label>
                                </div>
                                <div className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl p-1 shadow-sm">
                                  <button
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
                                    className="w-6 h-6 rounded-lg bg-slate-50 hover:bg-slate-100 flex items-center justify-center text-slate-600 font-black text-xs active:scale-90 transition-all border border-slate-200/50"
                                  >
                                    -
                                  </button>
                                  <span className="text-xs font-extrabold text-slate-800 min-w-[28px] text-center">{accountCount}</span>
                                  <button
                                    onClick={() => { triggerHaptic('medium'); setAccountCount(prev => prev + 1); }}
                                    className="w-6 h-6 rounded-lg bg-slate-50 hover:bg-slate-100 flex items-center justify-center text-slate-600 font-black text-xs active:scale-90 transition-all border border-slate-200/50"
                                  >
                                    +
                                  </button>
                                </div>
                              </div>
                              {accountCount > 1 && (
                                <div className="space-y-1.5 pt-1.5 border-t border-slate-200/50">
                                  <label className="text-[9px] font-black text-slate-700 uppercase tracking-wider block">Daftar UserID Akun (Pisah Spasi)</label>
                                  <input
                                    type="text"
                                    value={userIdsInput}
                                    onChange={(e) => setUserIdsInput(e.target.value)}
                                    placeholder="Contoh: 8310379779 8371902690"
                                    className="w-full text-[10px] p-2.5 bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-geun-blue/50 text-slate-700 shadow-inner"
                                  />
                                </div>
                              )}
                            </div>
                          )}

                          {/* Copy Format Box */}
                          <div className="space-y-2">
                            <label className="text-[9px] font-bold text-geun-muted uppercase tracking-wider">Format Pesanan:</label>
                            <div className="relative">
                              <div className="bg-[#F8FAFC] rounded-2xl p-4 border border-slate-200/70 font-mono text-[9.5px] leading-relaxed relative overflow-hidden select-none text-slate-700 shadow-inner">
                                {selectedPackage.type === 'userbot' ? (
                                  <>
                                    <p className="font-bold text-geun-blue border-b border-slate-200/50 pb-1.5 mb-2">🛎 𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧</p>
                                    <p>– Username: "{getUsername() || '@username'}"</p>
                                    <p>– Durasi: "{selectedPackage.duration}"</p>
                                    <p>– Jumlah Akun: "{accountCount} Akun"</p>
                                    <p>– Nomor: "(isi nomor HP akun userbot)"</p>
                                    <p>– Payment: "Transfer Manual"</p>
                                    <p>– Total Harga: Rp {currentPrice.toLocaleString('id-ID')}</p>
                                  </>
                                ) : (
                                  <>
                                    <p className="font-bold text-geun-blue border-b border-slate-200/50 pb-1.5 mb-2">🛎 𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦</p>
                                    <p>– Username: "{getUsername() || '@username'}"</p>
                                    <p>– Durasi: "{selectedPackage.duration}"</p>
                                    <p>– Paket: "JASEB {selectedPackage.type.toUpperCase()} {selectedPackage.lpm} LPM"</p>
                                    <p>– Payment: "Transfer Manual"</p>
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

                          {/* Action Button */}
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
                      )}

                      {/* STEP 3: SUCCESS SCREEN */}
                      {checkoutStep === 'success_screen' && (
                        <div className="space-y-6 py-4 text-center">
                          <div className="flex justify-center">
                            <div className="w-16 h-16 bg-emerald-50 border border-emerald-200 rounded-full flex items-center justify-center text-emerald-500 shadow-premium animate-bounce">
                              <svg className="w-9 h-9" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                              </svg>
                            </div>
                          </div>

                          <div className="space-y-2">
                            <h3 className="text-base font-black text-slate-800 uppercase tracking-wider">Pembayaran Sukses!</h3>
                            <p className="text-[10px] text-slate-500 font-bold leading-relaxed px-4">
                              Terima kasih! Pembayaran QRIS Anda telah terverifikasi secara otomatis. Layanan Anda sudah aktif.
                            </p>
                          </div>

                          <div className="bg-slate-50 border border-slate-200/50 p-4 rounded-2xl mx-2 text-left space-y-1.5 text-[9.5px]">
                            <p className="font-extrabold text-slate-800 uppercase text-[9px] tracking-wide text-geun-blue">📋 Langkah Lanjutan:</p>
                            <p className="font-semibold text-slate-600 leading-normal">
                              Silakan buka obrolan bot Telegram Anda. Bot telah mengirimi Anda instruksi setup lanjutan (meminta nomor HP untuk Userbot atau materi promosi untuk Jaseb).
                            </p>
                          </div>

                          <div className="pt-2 px-2">
                            <button
                              onClick={() => {
                                triggerHaptic('heavy');
                                const webapp = (window as any).Telegram?.WebApp;
                                if (webapp) {
                                  webapp.close();
                                } else {
                                  setIsModalOpen(false);
                                }
                              }}
                              className="w-full bg-gradient-to-r from-geun-blue to-geun-purple text-white py-3.5 rounded-2xl text-[10px] font-black uppercase tracking-wider text-center block shadow-premium hover:opacity-90 active:scale-98 transition-all duration-300"
                            >
                              Selesai & Buka Bot
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  );
                })()}
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
