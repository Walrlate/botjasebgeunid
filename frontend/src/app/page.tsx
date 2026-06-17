"use client";

import React, { useState, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import pricesData from '../prices.json';

// Import Modular Components
import { Header } from '../components/Header';
import { Navbar } from '../components/Navbar';
import { HomeTab } from '../components/HomeTab';
import { ToolsTab } from '../components/ToolsTab';
import { HistoryTab } from '../components/HistoryTab';
import { ProfileTab } from '../components/ProfileTab';
import { CheckoutModal } from '../components/CheckoutModal';

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
    userSecondsLeft: 0,
    userInterval: 0,
  });

  const fetchUserStats = async (userId: number) => {
    try {
      const webapp = typeof window !== 'undefined' ? (window as any).Telegram?.WebApp : null;
      const initData = webapp?.initData || '';
      const res = await fetch(`/api/user-stats/${userId}`, {
        headers: {
          'x-telegram-init-data': initData
        }
      });
      const result = await res.json();
      if (result.status && result.data) {
        const d = result.data;
        setStats(prev => ({
          ...prev,
          broadcasts: d.total_sent,
          userBotStatus: d.userbot_status,
          userPackage: d.package_name,
          userLpm: d.capacity_lpm,
          userDays: d.days_left,
          userSecondsLeft: d.seconds_left,
          userInterval: d.interval,
        }));
      }
    } catch (err) {
      console.error("Gagal refresh stats:", err);
    }
  };

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
      const interval = parseFloat(params.get('int') || '0');

      setStats({
        broadcasts: b,
        lpm: l,
        userbots: u,
        userBotStatus: ub,
        userPackage: pkg,
        userLpm: ulpm,
        userDays: days,
        userSecondsLeft: 0,
        userInterval: interval,
      });
    }
  }, []);

  // Effect untuk Auto-Update Stats (Real-time polling 30 detik)
  useEffect(() => {
    if (user?.id) {
      fetchUserStats(user.id);
      
      // Deteksi query param 'tab' untuk langsung membuka tab history
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get('tab');
      if (tabParam === 'history') {
        setActiveTab('history');
        fetchHistory(user.id);
      }

      const intervalId = setInterval(() => fetchUserStats(user.id), 30000);
      return () => clearInterval(intervalId);
    }
  }, [user?.id]);

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
      const webapp = typeof window !== 'undefined' ? (window as any).Telegram?.WebApp : null;
      const initData = webapp?.initData || '';
      const res = await fetch(`/api/history/${userId}`, {
        headers: {
          'x-telegram-init-data': initData
        }
      });
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
  const qrisTaxPercent = (pricingData as any).qris_tax_percent !== undefined ? (pricingData as any).qris_tax_percent : 0.7;

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
    
    const basePrice = selectedPackage.type === 'userbot'
      ? selectedPackage.price * accountCount
      : selectedPackage.price;
      
    const qrisFee = selectedPaymentMethod === 'qris' ? Math.round(basePrice * (qrisTaxPercent / 100)) : 0;
    const finalAmount = basePrice + qrisFee;

    const trxIdLine = manualTrxData?.transaction_id
      ? `\n– ID Order: ${manualTrxData.transaction_id}`
      : '';

    if (selectedPackage.type === 'userbot') {
      return `🛎 <b>𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧</b>${trxIdLine}
– ID Telegram: ${user?.id || 'Belum terdeteksi'}
– Username: ${getUsername() || '@username'}
– Durasi userbot: ${selectedPackage.duration}
– Jumlah Akun: ${accountCount} Akun
– Nomor Telegram: (isi nomor HP akun userbot Anda)
– Password: (isi password jika ada 2FA, jika tidak kosongkan)
– Payment: ${paymentText}
– Total Harga: Rp ${finalAmount.toLocaleString('id-ID')}`;
    } else {
      return `🛎 <b>𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦</b>${trxIdLine}
– ID Telegram: ${user?.id || 'Belum terdeteksi'}
– Username akun: ${getUsername() || '@username'}
– Durasi Jaseb: ${selectedPackage.duration}
– Paket jaseb: JASEB ${selectedPackage.type.toUpperCase()} ${selectedPackage.lpm} LPM
– Payment: ${paymentText}
– Request Lpm: (isi @lpm1 @lpm2, kalau gaada kosongin/hapus)
– Total Harga: Rp ${finalAmount.toLocaleString('id-ID')}`;
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

  const checkStatusAutomatic = async (trxId: string) => {
    try {
      const res = await fetch(`/api/check-status/${trxId}`);
      const data = await res.json();
      // Response format: {success: true, data: {status: "success"|"pending"}}
      const paymentStatus = data?.data?.status || data?.payment_status || '';
      if (data.success && paymentStatus === 'success') {
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
    const basePrice = selectedPackage.type === 'userbot'
      ? selectedPackage.price * accountCount
      : selectedPackage.price;

    const qrisFee = selectedPaymentMethod === 'qris' ? Math.round(basePrice * (qrisTaxPercent / 100)) : 0;
    const finalAmount = basePrice + qrisFee;

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
        amount: finalAmount,
        duration: selectedPackage.duration,
        lpm: selectedPackage.type === 'userbot' ? 0 : selectedPackage.lpm,
        package_type: selectedPackage.type,
        request_lpm: "",
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

  return (
    <div className="min-h-screen bg-geun-bg text-geun-dark flex justify-center items-start overflow-hidden relative">
      <div className="glow-orb w-64 h-64 bg-blue-400/10 top-[-80px] left-[-80px]"></div>
      <div className="glow-orb w-80 h-80 bg-indigo-300/10 bottom-[100px] right-[-100px]"></div>

      <div className="w-full max-w-md min-h-screen bg-[#F4F6F9] flex flex-col relative shadow-[0_0_50px_rgba(0,122,255,0.06)] border-x border-slate-200/50 pb-28 overflow-y-auto z-10">
        <div className="absolute inset-0 grid-bg pointer-events-none z-0"></div>

        <Header user={user} getDisplayName={getDisplayName} getUsername={getUsername} />

        <main className="flex-1 p-4 relative z-10">
          <AnimatePresence mode="wait">
            {activeTab === 'home' && (
              <HomeTab
                stats={stats}
                selectedType={selectedType}
                setSelectedType={setSelectedType}
                selectedLpmFilter={selectedLpmFilter}
                setSelectedLpmFilter={setSelectedLpmFilter}
                filteredPackages={filteredPackages}
                handleSelectPackage={handleSelectPackage}
                openAccordion={openAccordion}
                setOpenAccordion={setOpenAccordion}
                triggerHaptic={triggerHaptic}
              />
            )}

            {activeTab === 'tools' && (
              <ToolsTab
                rawWording={rawWording}
                setRawWording={setRawWording}
                selectedTemplate={selectedTemplate}
                setSelectedTemplate={setSelectedTemplate}
                wordingCopied={wordingCopied}
                setWordingCopied={setWordingCopied}
                enhancedWording={enhancedWording}
                triggerHaptic={triggerHaptic}
              />
            )}

            {activeTab === 'history' && (
              <HistoryTab
                history={history}
                loadingHistory={loadingHistory}
              />
            )}

            {activeTab === 'profile' && (
              <ProfileTab
                user={user}
                stats={stats}
                setActiveTab={setActiveTab}
                getDisplayName={getDisplayName}
                getUsername={getUsername}
                triggerHaptic={triggerHaptic}
              />
            )}
          </AnimatePresence>
        </main>

        <AnimatePresence>
          <CheckoutModal
            isModalOpen={isModalOpen}
            setIsModalOpen={setIsModalOpen}
            selectedPackage={selectedPackage}
            checkoutStep={checkoutStep}
            setCheckoutStep={setCheckoutStep}
            selectedPaymentMethod={selectedPaymentMethod}
            setSelectedPaymentMethod={setSelectedPaymentMethod}
            accountCount={accountCount}
            setAccountCount={setAccountCount}
            loadingCheckout={loadingCheckout}
            qrisData={qrisData}
            manualTrxData={manualTrxData}
            timeLeft={timeLeft}
            handleContinueCheckout={handleContinueCheckout}
            handleCopyOrderFormat={handleCopyOrderFormat}
            getOrderFormatText={getOrderFormatText}
            user={user}
            triggerHaptic={triggerHaptic}
            qrisTaxPercent={qrisTaxPercent}
          />
        </AnimatePresence>

        <Navbar activeTab={activeTab} handleTabChange={handleTabChange} />
      </div>
    </div>
  );
};

export default Dashboard;
