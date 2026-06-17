"use client";

import React from 'react';
import { motion } from 'framer-motion';

interface HistoryItem {
  group_name: string;
  msg_link: string | null;
  status: string;
  error_msg: string | null;
  sent_at: string;
}

interface HistoryTabProps {
  history: HistoryItem[];
  loadingHistory: boolean;
}

export const HistoryTab: React.FC<HistoryTabProps> = ({ history, loadingHistory }) => {
  return (
    <motion.div
      key="history"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      className="space-y-6 pb-20"
    >
      <div className="text-center space-y-1">
        <h2 className="text-lg font-black text-slate-800 tracking-wide uppercase">📋 Riwayat Jaseb</h2>
        <p className="text-[10px] text-slate-400 font-semibold">Pantau pengiriman iklan Anda (Bot & Userbot)</p>
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
                  <div className="mt-3 pt-3 border-t border-slate-50">
                    <button
                      onClick={() => {
                        if (item.msg_link) {
                          const webapp = (window as any).Telegram?.WebApp;
                          if (webapp) {
                            if (item.msg_link.startsWith('https://t.me/')) {
                              webapp.openTelegramLink(item.msg_link);
                            } else {
                              webapp.openLink(item.msg_link);
                            }
                          } else {
                            window.open(item.msg_link, '_blank');
                          }
                        }
                      }}
                      className="flex items-center gap-1.5 text-[9px] font-black text-geun-blue uppercase border-none bg-transparent p-0 cursor-pointer"
                    >
                      Bukti Kirim ↗
                    </button>
                  </div>
                ) : item.status === 'failed' && item.error_msg && (
                  <div className="mt-3 pt-3 border-t border-slate-50">
                    <p className="text-[9px] font-semibold text-rose-500 italic">⚠️ Error: {item.error_msg}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 space-y-3">
            <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mx-auto opacity-50">
              <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-[11px] font-black text-slate-400 uppercase">Belum Ada Riwayat</p>
          </div>
        )}
      </div>
    </motion.div>
  );
};
