"use client";

import React from 'react';
import { motion } from 'framer-motion';

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
}

interface SelectedPackage {
  lpm: number;
  type: string;
  duration: string;
  price: number;
}

interface QrisData {
  transaction_id: string;
  payment_url: string;
  qris_url: string;
  total_amount: number;
  expired_at: string;
}

interface ManualTrxData {
  transaction_id: string;
  total_amount: number;
}

interface CheckoutModalProps {
  isModalOpen: boolean;
  setIsModalOpen: (val: boolean) => void;
  selectedPackage: SelectedPackage | null;
  checkoutStep: 'select_payment' | 'qris_invoice' | 'manual_invoice' | 'success_screen';
  setCheckoutStep: (step: 'select_payment' | 'qris_invoice' | 'manual_invoice' | 'success_screen') => void;
  selectedPaymentMethod: 'qris' | 'manual' | null;
  setSelectedPaymentMethod: (method: 'qris' | 'manual' | null) => void;
  accountCount: number;
  setAccountCount: React.Dispatch<React.SetStateAction<number>>;
  loadingCheckout: boolean;
  qrisData: QrisData | null;
  manualTrxData: ManualTrxData | null;
  timeLeft: number;
  handleContinueCheckout: (adminId?: number | null) => void;
  handleCopyOrderFormat: () => void;
  getOrderFormatText: () => string;
  user: TelegramUser | null;
  triggerHaptic: (style?: 'light' | 'medium' | 'heavy') => void;
  qrisTaxPercent?: number;
  selectedAdminSlot: number | null;
  setSelectedAdminSlot: (id: number | null) => void;
}

export const CheckoutModal: React.FC<CheckoutModalProps> = ({
  isModalOpen,
  setIsModalOpen,
  selectedPackage,
  checkoutStep,
  setCheckoutStep,
  selectedPaymentMethod,
  setSelectedPaymentMethod,
  accountCount,
  setAccountCount,
  loadingCheckout,
  qrisData,
  manualTrxData,
  timeLeft,
  handleContinueCheckout,
  handleCopyOrderFormat,
  getOrderFormatText,
  user,
  triggerHaptic,
  qrisTaxPercent,
  selectedAdminSlot,
  setSelectedAdminSlot,
}) => {
  const [adminSlots, setAdminSlots] = React.useState<any[]>([]);
  const [loadingSlots, setLoadingSlots] = React.useState(false);

  React.useEffect(() => {
    if (isModalOpen && selectedPackage && selectedPackage.type !== 'userbot') {
      setLoadingSlots(true);
      fetch('/api/admin-slots')
        .then(res => res.json())
        .then(data => {
          if (data.status && data.data) {
            setAdminSlots(data.data);
            const firstAvailable = data.data.find((slot: any) => slot.status === 'Tersedia');
            if (firstAvailable) {
              setSelectedAdminSlot(firstAvailable.id);
            } else if (data.data.length > 0) {
              setSelectedAdminSlot(data.data[0].id);
            }
          }
        })
        .catch(err => console.error("Error fetching admin slots:", err))
        .finally(() => setLoadingSlots(false));
    }
  }, [isModalOpen, selectedPackage]);

  if (!isModalOpen || !selectedPackage) return null;

  const basePrice = selectedPackage.type === 'userbot' ? selectedPackage.price * accountCount : selectedPackage.price;
  const qrisPercent = qrisTaxPercent !== undefined ? qrisTaxPercent : 0.7;
  const qrisFee = selectedPaymentMethod === 'qris' ? Math.round(basePrice * (qrisPercent / 100)) : 0;
  const totalPrice = basePrice + qrisFee;

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={() => setIsModalOpen(false)}
        className="absolute inset-0 bg-slate-900/60"
      />
      <motion.div
        initial={{ y: "100%" }}
        animate={{ y: 0 }}
        exit={{ y: "100%" }}
        transition={{ type: "tween", ease: "easeOut", duration: 0.25 }}
        className="w-full max-w-md bg-white border-t border-slate-200/80 rounded-t-[32px] p-6 pb-8 space-y-5 shadow-2xl relative z-10 max-h-[85%] overflow-y-auto"
      >
        <div className="w-12 h-1 bg-slate-200 rounded-full mx-auto mb-1"></div>
        
        <style dangerouslySetInnerHTML={{__html: `@keyframes scan-laser { 0% { top: 0%; } 50% { top: 100%; } 100% { top: 0%; } } .animate-scan { animation: scan-laser 2.5s linear infinite; }`}} />

        {checkoutStep === 'select_payment' && (
          <div className="space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-sm font-black text-geun-dark uppercase">Metode Pembayaran</h3>
              </div>
              <button onClick={() => setIsModalOpen(false)} className="w-7 h-7 rounded-full bg-slate-100 text-slate-400 text-xs">✕</button>
            </div>
            
            {selectedPackage.type === 'userbot' && (
              <div className="bg-slate-50 border border-slate-200 p-4 rounded-2xl flex items-center justify-between">
                <span className="text-xs font-bold text-slate-700">Jumlah Akun:</span>
                <div className="flex items-center gap-3">
                  <button 
                    onClick={() => { triggerHaptic('light'); setAccountCount(prev => Math.max(1, prev - 1)); }}
                    className="w-8 h-8 rounded-xl bg-white border border-slate-200 flex items-center justify-center font-bold text-slate-700 active:bg-slate-100"
                  >
                    -
                  </button>
                  <span className="text-sm font-black text-slate-800 w-4 text-center">{accountCount}</span>
                  <button 
                    onClick={() => { triggerHaptic('light'); setAccountCount(prev => prev + 1); }}
                    className="w-8 h-8 rounded-xl bg-white border border-slate-200 flex items-center justify-center font-bold text-slate-700 active:bg-slate-100"
                  >
                    +
                  </button>
                </div>
              </div>
            )}

            {selectedPackage.type !== 'userbot' && (
              <div className="space-y-3">
                <div className="flex justify-between items-center px-1">
                  <h4 className="text-[9px] font-black text-slate-500 uppercase tracking-wider">PILIH BOT JASEB (SLOT ADMIN)</h4>
                  {loadingSlots && <span className="text-[8px] text-geun-blue animate-pulse font-extrabold uppercase">Loading...</span>}
                </div>
                {adminSlots.length === 0 && !loadingSlots ? (
                  <div className="bg-slate-50 border border-slate-200/50 p-4 rounded-2xl text-center text-xs text-slate-400">
                    ❌ Bot admin pool tidak tersedia
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    {adminSlots.map((slot) => {
                      const isSelected = selectedAdminSlot === slot.id;
                      const isFull = slot.status === 'Penuh';
                      return (
                        <div
                          key={slot.id}
                          onClick={() => {
                            triggerHaptic('light');
                            setSelectedAdminSlot(slot.id);
                          }}
                          className={`relative border p-3 rounded-2xl cursor-pointer flex flex-col justify-between transition-all overflow-hidden ${
                            isSelected
                              ? 'border-geun-blue bg-geun-blue/5 shadow-[0_0_15px_rgba(0,122,255,0.08)]'
                              : 'border-slate-200 bg-white hover:border-slate-300'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[9.5px] font-black text-slate-800 line-clamp-1">{slot.visual_name}</span>
                            <span className={`w-2 h-2 rounded-full ${isFull ? 'bg-red-500 animate-pulse' : 'bg-emerald-500'}`} />
                          </div>
                          <div className="space-y-0.5">
                            <p className="text-[7.5px] font-extrabold text-slate-400 uppercase">Status</p>
                            <p className={`text-[9px] font-black ${isFull ? 'text-red-500' : 'text-emerald-600'}`}>
                              {isFull ? 'Penuh' : 'Tersedia'}
                            </p>
                            {isFull && slot.end_date && (
                              <div className="mt-1 pt-1 border-t border-slate-100/80">
                                <p className="text-[7px] font-extrabold text-slate-400 uppercase">Hingga</p>
                                <p className="text-[8px] font-black text-slate-500 leading-tight">
                                  {slot.end_date.split(' ')[0]}
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            <div className="space-y-3 pt-2">
              <div
                onClick={() => { triggerHaptic('light'); setSelectedPaymentMethod('qris'); }}
                className={`glass-panel rounded-2xl p-4 flex items-center justify-between border transition-all ${selectedPaymentMethod === 'qris' ? 'border-geun-blue bg-geun-blue/5' : 'border-slate-200'}`}
              >
                <div className="flex items-center gap-3.5">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-slate-100 border border-slate-200">
                    <svg className="w-7 h-7 text-geun-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 013.75 9.375v-4.5zM3.75 14.625c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5a1.125 1.125 0 01-1.125-1.125v-4.5zM13.5 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0113.5 9.375v-4.5z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-xs font-black text-slate-800">QRIS Otomatis</p>
                  </div>
                </div>
                <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${selectedPaymentMethod === 'qris' ? 'border-geun-blue bg-geun-blue' : 'border-slate-300'}`}>
                  {selectedPaymentMethod === 'qris' && <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" /></svg>}
                </div>
              </div>
              
              <div
                onClick={() => { triggerHaptic('light'); setSelectedPaymentMethod('manual'); }}
                className={`glass-panel rounded-2xl p-4 flex items-center justify-between border transition-all ${selectedPaymentMethod === 'manual' ? 'border-geun-blue bg-geun-blue/5' : 'border-slate-200'}`}
              >
                <div className="flex items-center gap-3.5">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-slate-100 border border-slate-200">
                    <svg className="w-7 h-7 text-geun-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-xs font-black text-slate-800">Transfer Manual</p>
                  </div>
                </div>
                <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${selectedPaymentMethod === 'manual' ? 'border-geun-blue bg-geun-blue' : 'border-slate-300'}`}>
                  {selectedPaymentMethod === 'manual' && <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" /></svg>}
                </div>
              </div>
            </div>

            {selectedPaymentMethod !== null ? (
              <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-2 text-xs">
                <div className="flex justify-between items-center text-slate-500">
                  <span>Harga Paket:</span>
                  <span className="font-semibold text-slate-700">Rp {basePrice.toLocaleString('id-ID')}</span>
                </div>
                {selectedPaymentMethod === 'qris' && (
                  <div className="flex justify-between items-center text-slate-500">
                    <span>Biaya Layanan QRIS ({qrisPercent}%):</span>
                    <span className="font-semibold text-slate-700">Rp {qrisFee.toLocaleString('id-ID')}</span>
                  </div>
                )}
                {selectedPaymentMethod === 'manual' && (
                  <div className="flex justify-between items-center text-slate-500">
                    <span>Biaya Admin Manual:</span>
                    <span className="font-bold text-emerald-600">Rp 0 (Bebas Biaya)</span>
                  </div>
                )}
                <div className="border-t border-slate-200 pt-2 flex justify-between items-center">
                  <span className="font-extrabold text-slate-700">Total Tagihan:</span>
                  <span className="font-black text-geun-blue text-sm">Rp {totalPrice.toLocaleString('id-ID')}</span>
                </div>
                {selectedPaymentMethod === 'qris' && (
                  <p className="text-[9px] text-slate-400 leading-normal mt-1 italic text-center border-t border-slate-200/50 pt-2">
                    * Catatan: Provider KlikQRIS mungkin menyesuaikan nominal kecil (seperti kode unik) pada langkah berikutnya untuk keperluan verifikasi otomatis.
                  </p>
                )}
              </div>
            ) : (
              <div className="bg-slate-50/50 p-4 py-5 rounded-2xl border border-dashed border-slate-200 text-center text-[10px] text-slate-400 font-extrabold uppercase tracking-wide">
                ℹ️ Silakan pilih metode pembayaran untuk melihat rincian
              </div>
            )}

            <button
              disabled={!selectedPaymentMethod || loadingCheckout || (selectedPackage.type !== 'userbot' && !selectedAdminSlot)}
              onClick={() => handleContinueCheckout(selectedAdminSlot)}
              className={`w-full py-3.5 rounded-2xl text-[10px] font-black uppercase text-white shadow-premium ${selectedPaymentMethod && !loadingCheckout && (selectedPackage.type === 'userbot' || selectedAdminSlot) ? 'bg-gradient-to-r from-geun-blue to-geun-purple' : 'bg-slate-200'}`}
            >
              {loadingCheckout ? 'Menyiapkan...' : 'Lanjutkan Pembayaran'}
            </button>
          </div>
        )}

        {checkoutStep === 'qris_invoice' && (
          <div className="space-y-5">
            <div className="flex justify-between items-center">
              <button onClick={() => setCheckoutStep('select_payment')} className="text-[9.5px] font-black text-geun-blue uppercase">Kembali</button>
              <button onClick={() => setIsModalOpen(false)} className="w-7 h-7 rounded-full bg-slate-100 text-slate-400 text-xs">✕</button>
            </div>
            <div className="text-center space-y-1">
              <h3 className="text-sm font-black text-geun-dark uppercase">QRIS Pembayaran Otomatis</h3>
            </div>
            <div className="flex flex-col items-center space-y-3">
              <div className="relative p-3.5 bg-white border border-slate-200/80 rounded-[24px] shadow-premium overflow-hidden">
                <div className="absolute left-0 right-0 h-[2.5px] bg-red-500 animate-scan"></div>
                {qrisData?.qris_url ? (
                  <img src={qrisData.qris_url} alt="QRIS" className="w-48 h-48" />
                ) : (
                  <div className="w-48 h-48 flex items-center justify-center bg-slate-50 text-slate-400 text-xs">Tidak Tersedia</div>
                )}
              </div>
              <div className="flex justify-between w-full bg-slate-50 border border-slate-200 px-4 py-3 rounded-2xl">
                <div className="text-left">
                  <p className="text-[8px] uppercase">Total</p>
                  <p className="text-sm font-black text-geun-blue">Rp {qrisData?.total_amount.toLocaleString('id-ID')}</p>
                </div>
                <div className="text-right">
                  <p className="text-[8px] uppercase">Waktu</p>
                  <p className="text-xs font-black text-red-500">{formatTime(timeLeft)}</p>
                </div>
              </div>
            </div>
            <div className="pt-2 flex flex-col items-center space-y-3">
              <div className="flex items-center gap-2 text-[10px] font-extrabold text-slate-500 bg-slate-100 px-4 py-2.5 rounded-full">
                <span className="w-2.5 h-2.5 rounded-full border-2 border-geun-blue border-t-transparent animate-spin"></span>
                <span className="animate-pulse uppercase">Menunggu Pembayaran...</span>
              </div>
            </div>
          </div>
        )}

        {checkoutStep === 'manual_invoice' && (
          <div className="space-y-5">
            <div className="flex justify-between items-center">
              <button onClick={() => setCheckoutStep('select_payment')} className="text-[9.5px] font-black text-geun-blue uppercase">Kembali</button>
              <button onClick={() => setIsModalOpen(false)} className="w-7 h-7 rounded-full bg-slate-100 text-slate-400 text-xs">✕</button>
            </div>
            <div className="text-center space-y-1">
              <h3 className="text-sm font-black text-geun-dark uppercase">Transfer Manual</h3>
            </div>
            <div className="bg-slate-50 border border-slate-200 p-4 rounded-2xl space-y-2.5 text-xs">
              <p className="font-extrabold uppercase text-[9px] text-geun-blue">Rekening:</p>
              <div className="space-y-2 font-semibold text-[10px] text-slate-600">
                <p className="flex justify-between"><span>🏦 BANK BCA:</span><span className="font-black">8840742131 a/n GEUN</span></p>
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-[9px] font-bold text-geun-muted uppercase">Format Pesanan:</label>
              <div className="relative">
                <div className="bg-[#F8FAFC] rounded-2xl p-4 border border-slate-200 font-mono text-[9.5px] leading-relaxed text-slate-700 shadow-inner">
                  <p className="font-bold text-geun-blue">🛎 👑 𝗙𝗢𝗥𝗠𝗔𝗧 {selectedPackage.type.toUpperCase()}</p>
                  {manualTrxData?.transaction_id && <p>– ID Order: {manualTrxData.transaction_id}</p>}
                  <p>– ID Telegram: {user?.id}</p>
                  <p>– Total Harga: Rp {totalPrice.toLocaleString('id-ID')}</p>
                </div>
                <button onClick={handleCopyOrderFormat} className="absolute top-3 right-3 px-3 py-1.5 bg-white border border-slate-200 rounded-xl text-[9px] font-black uppercase shadow-sm">Salin</button>
              </div>
            </div>
            <a
              href={`https://t.me/Geun_ID?text=${encodeURIComponent(getOrderFormatText())}`}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => triggerHaptic('heavy')}
              className="bg-gradient-to-r from-geun-blue to-geun-purple text-white py-3.5 rounded-2xl text-[10px] font-black uppercase text-center block shadow-premium"
            >
              💬 Kirim ke Admin
            </a>
          </div>
        )}

        {checkoutStep === 'success_screen' && (
          <div className="space-y-6 py-4 text-center">
            <div className="flex justify-center">
              <div className="w-16 h-16 bg-emerald-50 border border-emerald-200 rounded-full flex items-center justify-center text-emerald-500 shadow-premium animate-bounce">
                <svg className="w-9 h-9" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3">
                  <path d="M5 13l4 4L19 7" />
                </svg>
              </div>
            </div>
            <div className="space-y-2">
              <h3 className="text-base font-black text-slate-800 uppercase">Pembayaran Sukses!</h3>
              <p className="text-[10px] text-slate-500 font-bold leading-relaxed px-4">
                Terima kasih! Pembayaran Anda telah terverifikasi secara otomatis. Layanan Anda sudah aktif.
              </p>
            </div>
            <div className="pt-2 px-2">
              <button
                onClick={() => { triggerHaptic('heavy'); if (typeof window !== 'undefined') { (window as any).Telegram?.WebApp?.close(); } setIsModalOpen(false); }}
                className="w-full bg-gradient-to-r from-geun-blue to-geun-purple text-white py-3.5 rounded-2xl text-[10px] font-black uppercase shadow-premium"
              >
                Selesai & Buka Bot
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
};
