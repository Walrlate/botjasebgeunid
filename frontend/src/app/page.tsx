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

interface HistoryItem {
  group_name: string;
  msg_link: string | null;
  status: string;
  error_msg: string | null;
  sent_at: string;
}

const HomeIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 drop-shadow-[0_2px_8px_rgba(0,122,255,0.25)]' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
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

const HistoryIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 drop-shadow-[0_2px_8px_rgba(0,122,255,0.25)]' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
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
  
  // State for History
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  
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
  const [manualTrxData, setManualTrxData] = useState<{
    transaction_id: string;
    total_amount: number;
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
    if (tab === 'history' && user) {
      fetchHistory(user.id);
    }
  };

  const fetchHistory = async (userId: number) => {
    setLoadingHistory(true);
    try {
      const res = await fetch(`/api/history/${userId}`);
      const data = await res.json();
      if (data.status) {
        setHistory(data.data);
      }
    } catch (err) {
      console.error("Gagal mengambil riwayat:", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const getDisplayName = () => {
    if (!user) return 'Premium User';
    return `${user.first_name} ${user.last_name || ''}`.trim();
  };

  const getUsername = () => {
    if (!user) return '@geun_buyer';
    return user.username ? `@${user.username}` : `@id_${user.id}`;
  };

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
    setManualTrxData(null);
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

    const trxIdLine = manualTrxData?.transaction_id
      ? `\n– ID Order: ${manualTrxData.transaction_id}`
      : '';

    if (selectedPackage.type === 'userbot') {
      const uidsSection = accountCount > 1 && userIdsInput.trim()
        ? `\n– List UserID: ${userIdsInput.trim()}`
        : '';
      return `🛎 <b>𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧</b>${trxIdLine}
– ID Telegram: ${user?.id || 'Belum terdeteksi'}
– Username: ${getUsername() || '@username'}
– Durasi userbot: ${selectedPackage.duration}
– Jumlah Akun: ${accountCount} Akun${uidsSection}
– Nomor Telegram: (isi nomor HP akun userbot Anda)
– Password: (isi password jika ada 2FA, jika tidak kosongkan)
– Payment: ${paymentText}
– Total Harga: Rp ${currentPrice.toLocaleString('id-ID')}`;
    } else {
      return `🛎 <b>𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦</b>${trxIdLine}
– ID Telegram: ${user?.id || 'Belum terdeteksi'}
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

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (checkoutStep === 'qris_invoice' && timeLeft > 0) {
      timer = setInterval(() => {
        setTimeLeft(prev => prev - 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [checkoutStep, timeLeft]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

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

  const handleContinueCheckout = async () => {
    if (!selectedPaymentMethod) {
      alert("Silakan pilih metode pembayaran terlebih dahulu.");
      return;
    }
    triggerHaptic('medium');
    if (!user) {
      alert("Gagal mendeteksi akun Telegram Anda.");
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
        request_lpm: selectedPackage.type !== 'userbot' ? userIdsInput : "",
        payment_method: selectedPaymentMethod
      };

      const response = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const resData = await response.json();
      if (resData.status && resData.data) {
        if (selectedPaymentMethod === 'manual') {
          setManualTrxData(resData.data);
          setCheckoutStep('manual_invoice');
        } else {
          setQrisData(resData.data);
          setTimeLeft(1800);
          setCheckoutStep('qris_invoice');
        }
      } else {
        alert(`❌ Gagal membuat transaksi: ${resData.error || 'Terjadi kesalahan sistem.'}`);
      }
    } catch (err) {
      console.error("Checkout Error:", err);
      alert("❌ Terjadi kesalahan koneksi.");
    } finally {
      setLoadingCheckout(false);
    }
  };

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
          alert("⏳ Pembayaran belum terdeteksi.");
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
      <div className="glow-orb w-64 h-64 bg-blue-400/10 top-[-80px] left-[-80px]"></div>
      <div className="glow-orb w-80 h-80 bg-indigo-300/10 bottom-[100px] right-[-100px]"></div>

      <div className="w-full max-w-md min-h-screen bg-[#F4F6F9] flex flex-col relative shadow-[0_0_50px_rgba(0,122,255,0.06)] border-x border-slate-200/50 pb-28 overflow-y-auto z-10">
        <div className="absolute inset-0 grid-bg pointer-events-none z-0"></div>

        <header className="flex justify-between items-center px-5 py-4 border-b border-slate-200/50 bg-[#F4F6F9]/65 backdrop-blur-xl sticky top-0 z-40">
          <div className="relative z-10">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-geun-blue shadow-[0_0_8px_rgba(0,122,255,0.4)] animate-pulse"></span>
              <h1 className="text-lg font-bold tracking-wider text-geun-dark uppercase">
                GEUNID<span className="text-geun-blue font-black">.JASEB</span>
              </h1>
            </div>
          </div>
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
                initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -15 }}
                className="space-y-6"
              >
                <div className="relative overflow-hidden rounded-3xl border border-slate-200/80 shadow-soft bg-white group transition-all duration-300 hover:shadow-premium">
                  <div className="relative w-full aspect-video overflow-hidden bg-slate-900">
                    <img src="/images/promo_banner.jpg" alt="Promo" className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.02]" />
                  </div>
                  <div className="p-5 bg-white border-t border-slate-100">
                    <p className="text-[10px] font-medium text-slate-500 leading-relaxed">
                      Nikmati potongan harga spesial hingga <span className="font-extrabold text-geun-blue">35%</span> dan <span className="font-extrabold text-emerald-600">bonus durasi aktif</span>!
                    </p>
                  </div>
                </div>

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
                    <h3 className="text-[9.5px] font-bold text-slate-400 uppercase tracking-widest">FAQ</h3>
                  </div>
                  <div className="space-y-2.5">
                    <div className="border border-slate-100 rounded-2xl overflow-hidden bg-white/50">
                      <button onClick={() => { triggerHaptic('light'); setOpenAccordion(openAccordion === 'what_is_jaseb' ? null : 'what_is_jaseb'); }} className="w-full flex items-center justify-between px-4 py-3.5 text-left text-[10px] font-bold text-slate-700 hover:bg-slate-50 transition-colors">
                        <span>💡 Apa itu Jasa Sebar (Jaseb)?</span>
                        <svg className={`w-3.5 h-3.5 text-slate-400 transition-transform ${openAccordion === 'what_is_jaseb' ? 'rotate-180 text-geun-blue' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5"><path d="M19 9l-7 7-7-7" /></svg>
                      </button>
                      <AnimatePresence>
                        {openAccordion === 'what_is_jaseb' && (
                          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden border-t border-slate-100 bg-white">
                            <div className="p-4 text-[9.5px] text-slate-500 space-y-2">
                              <p><strong>Jasa Sebar (Jaseb)</strong> adalah layanan promosi otomatis di Telegram untuk menyebarkan pesan iklan Anda ke grup LPM secara otomatis 24 jam non-stop.</p>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                </section>
              </motion.div>
            )}

            {activeTab === 'tools' && (
              <motion.div
                key="tools"
                initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -15 }}
                className="space-y-6 pb-20"
              >
                <div className="text-center space-y-1">
                  <h2 className="text-lg font-black text-slate-800 tracking-wide uppercase">⚡ Fitur Gratis</h2>
                  <p className="text-[10px] text-slate-400 font-semibold">Tingkatkan efisiensi promosi Anda secara instan</p>
                </div>

                <div className="glass-panel rounded-3xl p-5 border border-slate-200/60 shadow-soft space-y-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-2xl bg-geun-blue/10 flex items-center justify-center text-geun-blue"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg></div>
                    <div><h3 className="text-xs font-black text-slate-800 uppercase">AI Wording Beautifier</h3></div>
                  </div>
                  <textarea value={rawWording} onChange={(e) => setRawWording(e.target.value)} placeholder="Pesan promosi mentah..." className="w-full min-h-[100px] text-[10px] p-3.5 bg-[#F8FAFC] border border-slate-200 rounded-2xl focus:outline-none text-slate-700 shadow-inner resize-none" />
                  <div className="grid grid-cols-3 gap-2">
                    {(['premium', 'minimalist', 'flash'] as const).map((temp) => (
                      <button key={temp} onClick={() => { triggerHaptic('light'); setSelectedTemplate(temp); }} className={`py-2 rounded-xl text-[9px] font-black uppercase border ${selectedTemplate === temp ? 'bg-geun-blue text-white border-geun-blue' : 'bg-white text-slate-500 border-slate-200'}`}>{temp}</button>
                    ))}
                  </div>
                  {rawWording.trim() && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-[8.5px] font-black text-slate-400 uppercase">Pratinjau</label>
                        <button onClick={() => { triggerHaptic('medium'); navigator.clipboard.writeText(enhancedWording(rawWording, selectedTemplate)); setWordingCopied(true); setTimeout(() => setWordingCopied(false), 2000); }} className={`px-3 py-1 rounded-lg text-[8px] font-black uppercase ${wordingCopied ? 'bg-emerald-50 text-emerald-600' : 'bg-geun-blue/10 text-geun-blue'}`}>{wordingCopied ? 'Tersalin' : 'Salin'}</button>
                      </div>
                      <div className="p-4 bg-[#F8FAFC] border border-slate-200 rounded-2xl text-[9.5px] font-mono text-slate-700 whitespace-pre-wrap leading-relaxed shadow-inner max-h-[150px] overflow-y-auto">{enhancedWording(rawWording, selectedTemplate)}</div>
                    </div>
                  )}
                </div>

                <div className="glass-panel rounded-3xl p-5 border border-slate-200/60 shadow-soft space-y-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-2xl bg-geun-purple/10 flex items-center justify-center text-geun-purple"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg></div>
                    <div><h3 className="text-xs font-black text-slate-800 uppercase">LPM Auto-Scanner Helper</h3></div>
                  </div>
                  <textarea value={lpmToScan} onChange={(e) => setLpmToScan(e.target.value)} placeholder="Username atau link grup LPM..." className="w-full min-h-[90px] text-[10px] p-3.5 bg-[#F8FAFC] border border-slate-200 rounded-2xl focus:outline-none text-slate-700 shadow-inner resize-none" />
                  {lpmToScan.trim() && (
                    <div className="space-y-3.5">
                      <div className="p-3.5 bg-[#F8FAFC] border border-slate-200 rounded-2xl text-[9.5px] font-mono text-slate-700 leading-relaxed shadow-inner break-all">{`/scan ${lpmToScan.match(/(?:https?:\/\/)?(?:t\.me\/|@)?([a-zA-Z0-9_]{5,32}|joinchat\/[a-zA-Z0-9_\-]+)/g)?.map(l => l.startsWith('@') || l.includes('t.me') ? l : `@${l}`).join(' ')}`}</div>
                      <a href={`https://t.me/GeunIDJaseb_Bot?text=${encodeURIComponent(`/scan ${lpmToScan.match(/(?:https?:\/\/)?(?:t\.me\/|@)?([a-zA-Z0-9_]{5,32}|joinchat\/[a-zA-Z0-9_\-]+)/g)?.map(l => l.startsWith('@') || l.includes('t.me') ? l : `@${l}`).join(' ')}`)}`} target="_blank" rel="noopener noreferrer" onClick={() => triggerHaptic('heavy')} className="w-full bg-gradient-to-r from-geun-blue to-geun-purple text-white py-3 rounded-2xl text-[9px] font-black uppercase text-center block shadow-soft">🚀 Kirim ke Bot</a>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === 'history' && (
              <motion.div
                key="history"
                initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -15 }}
                className="space-y-6 pb-20"
              >
                <div className="text-center space-y-1">
                  <h2 className="text-lg font-black text-slate-800 tracking-wide uppercase">📋 Riwayat Broadcast</h2>
                  <p className="text-[10px] text-slate-400 font-semibold">Pantau status penyebaran iklan Anda secara real-time</p>
                </div>
                <div className="glass-panel rounded-3xl p-5 border border-slate-200/60 shadow-soft">
                  {loadingHistory ? (
                    <div className="flex flex-col items-center justify-center py-12 space-y-3">
                      <div className="w-8 h-8 border-4 border-geun-blue border-t-transparent rounded-full animate-spin"></div>
                      <p className="text-[10px] font-bold text-slate-400 uppercase">Mengambil Data...</p>
                    </div>
                  ) : history.length > 0 ? (
                    <div className="space-y-3">
                      {history.map((item, idx) => (
                        <div key={idx} className="bg-white border border-slate-100 rounded-2xl p-3.5 shadow-sm hover:shadow-md transition-all">
                          <div className="flex justify-between items-start">
                            <div className="space-y-1">
                              <p className="text-[11px] font-black text-slate-800 truncate max-w-[180px]">{item.group_name}</p>
                              <p className="text-[8.5px] font-bold text-slate-400 uppercase">{item.sent_at}</p>
                            </div>
                            <span className={`text-[8px] font-black px-2 py-0.5 rounded-full uppercase ${item.status === 'success' ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'}`}>
                              {item.status === 'success' ? 'Sukses' : 'Gagal'}
                            </span>
                          </div>
                          {item.status === 'success' && item.msg_link ? (
                            <div className="mt-3 pt-3 border-t border-slate-50"><a href={item.msg_link} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-[9px] font-black text-geun-blue uppercase">Lihat Pesan ↗</a></div>
                          ) : item.status === 'failed' && item.error_msg && (
                            <div className="mt-3 pt-3 border-t border-slate-50"><p className="text-[9px] font-semibold text-rose-500 italic">⚠️ Error: {item.error_msg}</p></div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 space-y-3">
                      <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mx-auto opacity-50"><HistoryIcon active={false} /></div>
                      <p className="text-[11px] font-black text-slate-400 uppercase">Belum Ada Riwayat</p>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === 'profile' && (
              <motion.div
                key="profile"
                initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -15 }}
                className="space-y-6"
              >
                <div className="glass-panel rounded-3xl p-6 text-center space-y-4 border border-slate-200/60 shadow-soft">
                  <div className="flex justify-center">
                    {user?.photo_url ? (
                      <img src={user.photo_url} alt="Profile" className="w-20 h-20 rounded-3xl border-2 border-geun-blue object-cover shadow-lg" />
                    ) : (
                      <div className="w-20 h-20 bg-gradient-to-br from-geun-blue to-geun-purple rounded-3xl flex items-center justify-center font-black text-white text-3xl shadow-lg">{getDisplayName().charAt(0)}</div>
                    )}
                  </div>
                  <div><h3 className="text-base font-bold text-slate-800 tracking-wide">{getDisplayName()}</h3><p className="text-xs font-semibold text-slate-400">{getUsername()}</p></div>
                  <div className="h-[1px] bg-slate-200 my-2"></div>
                  <div className="grid grid-cols-2 gap-3 text-left">
                    <div className="bg-slate-100/50 p-3.5 rounded-xl border border-slate-200/40"><p className="text-[7.5px] text-slate-400 uppercase font-bold tracking-widest">ID Telegram</p><p className="text-xs font-bold text-slate-800 mt-1">{user?.id || '8844645901'}</p></div>
                    <div className="bg-slate-100/50 p-3.5 rounded-xl border border-slate-200/40"><p className="text-[7.5px] text-slate-400 uppercase font-bold tracking-widest">Sesi Sinyal</p><p className="text-xs font-bold text-emerald-600 mt-1">Connected</p></div>
                  </div>
                  <div className="space-y-2.5 text-left text-xs">
                    <div className="flex justify-between items-center bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                      <span className="font-semibold text-slate-500">Status Userbot:</span>
                      <span className={`font-bold uppercase tracking-wider text-[9px] px-2 py-0.5 rounded-full ${stats.userBotStatus === 'connected' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>{stats.userBotStatus === 'connected' ? 'Connected' : 'Disconnected'}</span>
                    </div>
                    <div className="flex justify-between items-center bg-slate-50 p-2.5 rounded-xl border border-slate-100"><span className="font-semibold text-slate-500">Paket Aktif:</span><span className="font-bold text-slate-700">{stats.userPackage}</span></div>
                    {stats.userPackage !== 'Tidak Aktif' && (
                      <div className="grid grid-cols-2 gap-2 mt-1">
                        <div className="bg-slate-50 p-2 rounded-xl border border-slate-100 text-center"><p className="text-[7.5px] text-slate-400 font-bold uppercase">Kapasitas</p><p className="font-bold text-geun-blue text-xs mt-0.5">{stats.userLpm} LPM</p></div>
                        <div className="bg-slate-50 p-2 rounded-xl border border-slate-100 text-center"><p className="text-[7.5px] text-slate-400 font-bold uppercase">Masa Aktif</p><p className="font-bold text-emerald-600 text-xs mt-0.5">{stats.userDays} Hari</p></div>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </main>

        <AnimatePresence>
          {isModalOpen && selectedPackage && (
            <div className="fixed inset-0 z-50 flex items-end justify-center">
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setIsModalOpen(false)} className="absolute inset-0 bg-slate-900/40 backdrop-blur-md" />
              <motion.div initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }} transition={{ type: "spring", damping: 25, stiffness: 220 }} className="w-full max-w-md bg-white border-t border-slate-200/80 rounded-t-[32px] p-6 pb-8 space-y-5 shadow-2xl relative z-10 max-h-[85%] overflow-y-auto" >
                <div className="w-12 h-1 bg-slate-200 rounded-full mx-auto mb-1"></div>
                {(() => {
                  const currentPrice = selectedPackage.type === 'userbot' ? selectedPackage.price * accountCount : selectedPackage.price;
                  return (
                    <>
                      <style dangerouslySetInnerHTML={{__html: `@keyframes scan-laser { 0% { top: 0%; } 50% { top: 100%; } 100% { top: 0%; } } .animate-scan { animation: scan-laser 2.5s linear infinite; }`}} />
                      {checkoutStep === 'select_payment' && (
                        <div className="space-y-4">
                          <div className="flex justify-between items-start">
                            <div><h3 className="text-sm font-black text-geun-dark uppercase">Metode Pembayaran</h3></div>
                            <button onClick={() => setIsModalOpen(false)} className="w-7 h-7 rounded-full bg-slate-100 text-slate-400 text-xs">✕</button>
                          </div>
                          <div className="space-y-3 pt-2">
                            <div onClick={() => { triggerHaptic('light'); setSelectedPaymentMethod('qris'); }} className={`glass-panel rounded-2xl p-4 flex items-center justify-between border transition-all ${selectedPaymentMethod === 'qris' ? 'border-geun-blue bg-geun-blue/5' : 'border-slate-200'}`}>
                              <div className="flex items-center gap-3.5"><div className="w-12 h-12 rounded-xl flex items-center justify-center bg-slate-100 border border-slate-200"><svg className="w-7 h-7 text-geun-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 013.75 9.375v-4.5zM3.75 14.625c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5a1.125 1.125 0 01-1.125-1.125v-4.5zM13.5 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0113.5 9.375v-4.5z" /></svg></div><div><p className="text-xs font-black text-slate-800">QRIS Otomatis</p></div></div>
                              <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${selectedPaymentMethod === 'qris' ? 'border-geun-blue bg-geun-blue' : 'border-slate-300'}`}>{selectedPaymentMethod === 'qris' && <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" /></svg>}</div>
                            </div>
                            <div onClick={() => { triggerHaptic('light'); setSelectedPaymentMethod('manual'); }} className={`glass-panel rounded-2xl p-4 flex items-center justify-between border transition-all ${selectedPaymentMethod === 'manual' ? 'border-geun-blue bg-geun-blue/5' : 'border-slate-200'}`}>
                              <div className="flex items-center gap-3.5"><div className="w-12 h-12 rounded-xl flex items-center justify-center bg-slate-100 border border-slate-200"><svg className="w-7 h-7 text-geun-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" /></svg></div><div><p className="text-xs font-black text-slate-800">Transfer Manual</p></div></div>
                              <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${selectedPaymentMethod === 'manual' ? 'border-geun-blue bg-geun-blue' : 'border-slate-300'}`}>{selectedPaymentMethod === 'manual' && <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" /></svg>}</div>
                            </div>
                          </div>
                          <button disabled={!selectedPaymentMethod || loadingCheckout} onClick={handleContinueCheckout} className={`w-full py-3.5 rounded-2xl text-[10px] font-black uppercase text-white shadow-premium ${selectedPaymentMethod && !loadingCheckout ? 'bg-gradient-to-r from-geun-blue to-geun-purple' : 'bg-slate-200'}`}>{loadingCheckout ? 'Menyiapkan...' : 'Lanjutkan Pembayaran'}</button>
                        </div>
                      )}
                      {checkoutStep === 'qris_invoice' && (
                        <div className="space-y-5">
                          <div className="flex justify-between items-center"><button onClick={() => setCheckoutStep('select_payment')} className="text-[9.5px] font-black text-geun-blue uppercase">Kembali</button><button onClick={() => setIsModalOpen(false)} className="w-7 h-7 rounded-full bg-slate-100 text-slate-400 text-xs">✕</button></div>
                          <div className="text-center space-y-1"><h3 className="text-sm font-black text-geun-dark uppercase">QRIS Pembayaran Otomatis</h3></div>
                          <div className="flex flex-col items-center space-y-3">
                            <div className="relative p-3.5 bg-white border border-slate-200/80 rounded-[24px] shadow-premium overflow-hidden"><div className="absolute left-0 right-0 h-[2.5px] bg-red-500 animate-scan"></div>{qrisData?.qris_url ? <img src={qrisData.qris_url} alt="QRIS" className="w-48 h-48" /> : <div className="w-48 h-48 flex items-center justify-center bg-slate-50 text-slate-400 text-xs">Tidak Tersedia</div>}</div>
                            <div className="flex justify-between w-full bg-slate-50 border border-slate-200 px-4 py-3 rounded-2xl">
                              <div className="text-left"><p className="text-[8px] uppercase">Total</p><p className="text-sm font-black text-geun-blue">Rp {qrisData?.total_amount.toLocaleString('id-ID')}</p></div>
                              <div className="text-right"><p className="text-[8px] uppercase">Waktu</p><p className="text-xs font-black text-red-500">{formatTime(timeLeft)}</p></div>
                            </div>
                          </div>
                          <div className="pt-2 flex flex-col items-center space-y-3"><div className="flex items-center gap-2 text-[10px] font-extrabold text-slate-500 bg-slate-100 px-4 py-2.5 rounded-full"><span className="w-2.5 h-2.5 rounded-full border-2 border-geun-blue border-t-transparent animate-spin"></span><span className="animate-pulse uppercase">Menunggu Pembayaran...</span></div></div>
                        </div>
                      )}
                      {checkoutStep === 'manual_invoice' && (
                        <div className="space-y-5">
                          <div className="flex justify-between items-center"><button onClick={() => setCheckoutStep('select_payment')} className="text-[9.5px] font-black text-geun-blue uppercase">Kembali</button><button onClick={() => setIsModalOpen(false)} className="w-7 h-7 rounded-full bg-slate-100 text-slate-400 text-xs">✕</button></div>
                          <div className="text-center space-y-1"><h3 className="text-sm font-black text-geun-dark uppercase">Transfer Manual</h3></div>
                          <div className="bg-slate-50 border border-slate-200 p-4 rounded-2xl space-y-2.5 text-xs">
                            <p className="font-extrabold uppercase text-[9px] text-geun-blue">Rekening:</p>
                            <div className="space-y-2 font-semibold text-[10px] text-slate-600"><p className="flex justify-between"><span>🏦 BANK BCA:</span><span className="font-black">8840742131 a/n GEUN</span></p></div>
                          </div>
                          <div className="space-y-2">
                            <label className="text-[9px] font-bold text-geun-muted uppercase">Format Pesanan:</label>
                            <div className="relative"><div className="bg-[#F8FAFC] rounded-2xl p-4 border border-slate-200 font-mono text-[9.5px] leading-relaxed text-slate-700 shadow-inner">
                              <p className="font-bold text-geun-blue">🛎 𝗙𝗢𝗥𝗠𝗔𝗧 {selectedPackage.type.toUpperCase()}</p>
                              {manualTrxData?.transaction_id && <p>– ID Order: {manualTrxData.transaction_id}</p>}
                              <p>– ID Telegram: {user?.id}</p>
                              <p>– Total Harga: Rp {currentPrice.toLocaleString('id-ID')}</p>
                            </div><button onClick={handleCopyOrderFormat} className="absolute top-3 right-3 px-3 py-1.5 bg-white border border-slate-200 rounded-xl text-[9px] font-black uppercase shadow-sm">Salin</button></div>
                          </div>
                          <a href={`https://t.me/Geun_ID?text=${encodeURIComponent(getOrderFormatText())}`} target="_blank" rel="noopener noreferrer" onClick={() => triggerHaptic('heavy')} className="bg-gradient-to-r from-geun-blue to-geun-purple text-white py-3.5 rounded-2xl text-[10px] font-black uppercase text-center block shadow-premium">💬 Kirim ke Admin</a>
                        </div>
                      )}
                      {checkoutStep === 'success_screen' && (
                        <div className="space-y-6 py-4 text-center">
                          <div className="flex justify-center"><div className="w-16 h-16 bg-emerald-50 border border-emerald-200 rounded-full flex items-center justify-center text-emerald-500 shadow-premium animate-bounce"><svg className="w-9 h-9" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3"><path d="M5 13l4 4L19 7" /></svg></div></div>
                          <div className="space-y-2"><h3 className="text-base font-black text-slate-800 uppercase">Pembayaran Sukses!</h3><p className="text-[10px] text-slate-500 font-bold leading-relaxed px-4">Terima kasih! Pembayaran Anda telah terverifikasi secara otomatis. Layanan Anda sudah aktif.</p></div>
                          <div className="pt-2 px-2"><button onClick={() => { triggerHaptic('heavy'); (window as any).Telegram?.WebApp?.close(); setIsModalOpen(false); }} className="w-full bg-gradient-to-r from-geun-blue to-geun-purple text-white py-3.5 rounded-2xl text-[10px] font-black uppercase shadow-premium">Selesai & Buka Bot</button></div>
                        </div>
                      )}
                    </>
                  );
                })()}
              </motion.div>
            </div>
          )}
        </AnimatePresence>

        <nav className="absolute bottom-6 left-4 right-4 h-16 bg-white/70 backdrop-blur-xl border border-slate-200/80 rounded-3xl flex items-center justify-around px-2 shadow-premium z-40">
          <button onClick={() => handleTabChange('home')} className={`flex flex-col items-center justify-center w-12 h-12 transition-spring relative ${activeTab === 'home' ? 'scale-105' : 'text-slate-400'}`}><HomeIcon active={activeTab === 'home'} />{activeTab === 'home' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}</button>
          <button onClick={() => handleTabChange('tools')} className={`flex flex-col items-center justify-center w-12 h-12 transition-spring relative ${activeTab === 'tools' ? 'scale-105' : 'text-slate-400'}`}><ToolsIcon active={activeTab === 'tools'} />{activeTab === 'tools' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}</button>
          <button onClick={() => handleTabChange('history')} className={`flex flex-col items-center justify-center w-12 h-12 transition-spring relative ${activeTab === 'history' ? 'scale-105' : 'text-slate-400'}`}><HistoryIcon active={activeTab === 'history'} />{activeTab === 'history' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}</button>
          <button onClick={() => handleTabChange('profile')} className={`flex flex-col items-center justify-center w-12 h-12 transition-spring relative ${activeTab === 'profile' ? 'scale-105' : 'text-slate-400'}`}><UserIcon active={activeTab === 'profile'} />{activeTab === 'profile' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}</button>
        </nav>
      </div>
    </div>
  );
};

export default Dashboard;
