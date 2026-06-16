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

interface StatsType {
  broadcasts: number;
  lpm: number;
  userbots: number;
  userBotStatus: string;
  userPackage: string;
  userLpm: number;
  userDays: number;
  userSecondsLeft: number;
  userInterval: number;
}

interface ProfileTabProps {
  user: TelegramUser | null;
  stats: StatsType;
  setActiveTab: (tab: string) => void;
  getDisplayName: () => string;
  getUsername: () => string;
  triggerHaptic: (style?: 'light' | 'medium' | 'heavy') => void;
}

export const ProfileTab: React.FC<ProfileTabProps> = ({
  user,
  stats,
  setActiveTab,
  getDisplayName,
  getUsername,
  triggerHaptic,
}) => {
  
  const formatRemainingTime = (seconds: number, days: number) => {
    if (seconds <= 0 && days <= 0) return "Expired";
    if (seconds > 86400 || days > 0) return `${days} Hari`;
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (hours > 0) return `${hours}j ${minutes}m`;
    return `${minutes} Menit`;
  };

  return (
    <motion.div
      key="profile"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      className="space-y-6"
    >
      <div className="glass-panel rounded-3xl p-6 text-center space-y-4 border border-slate-200/60 shadow-soft">
        <div className="flex justify-center">
          {user?.photo_url ? (
            <img src={user.photo_url} alt="Profile" className="w-20 h-20 rounded-3xl border-2 border-geun-blue object-cover shadow-lg" />
          ) : (
            <div className="w-20 h-20 bg-gradient-to-br from-geun-blue to-geun-purple rounded-3xl flex items-center justify-center font-black text-white text-3xl shadow-lg">
              {getDisplayName().charAt(0)}
            </div>
          )}
        </div>
        <div>
          <h3 className="text-base font-bold text-slate-800 tracking-wide">{getDisplayName()}</h3>
          <p className="text-xs font-semibold text-slate-400">{getUsername()}</p>
        </div>
        <div className="h-[1px] bg-slate-200 my-2"></div>
        
        <div className="space-y-2.5 text-left text-xs">
          {stats.userPackage.toLowerCase().includes('userbot') ? (
            <div className="flex justify-between items-center bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <span className="font-semibold text-slate-500">Status Userbot:</span>
              <span className={`font-bold uppercase tracking-wider text-[9px] px-2 py-0.5 rounded-full ${stats.userBotStatus === 'connected' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                {stats.userBotStatus === 'connected' ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          ) : stats.userPackage !== 'Tidak Aktif' ? (
            <div className="flex justify-between items-center bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <span className="font-semibold text-slate-500">Sistem Pengirim:</span>
              <span className="font-bold uppercase tracking-wider text-[9px] px-2 py-0.5 rounded-full bg-blue-100 text-geun-blue">
                Bot GeunID (Aktif)
              </span>
            </div>
          ) : null}
          
          <div className="flex justify-between items-center bg-slate-50 p-2.5 rounded-xl border border-slate-100">
            <span className="font-semibold text-slate-500">Paket Aktif:</span>
            <span className="font-bold text-slate-700">{stats.userPackage}</span>
          </div>

          {stats.userPackage !== 'Tidak Aktif' ? (
            <div className="grid grid-cols-3 gap-2 mt-1">
              <div className="bg-slate-50 p-2 rounded-xl border border-slate-100 text-center">
                <p className="text-[7.5px] text-slate-400 font-bold uppercase">Kapasitas</p>
                <p className="font-bold text-geun-blue text-[10px] mt-0.5">{stats.userLpm} LPM</p>
              </div>
              <div className={`p-2 rounded-xl border text-center transition-all duration-500 ${stats.userSecondsLeft > 0 && stats.userSecondsLeft < 21600 ? 'bg-rose-50 border-rose-200 animate-pulse' : 'bg-slate-50 border-slate-100'}`}>
                <p className={`text-[7.5px] font-bold uppercase ${stats.userSecondsLeft > 0 && stats.userSecondsLeft < 21600 ? 'text-rose-500' : 'text-slate-400'}`}>Masa Aktif</p>
                <p className={`font-bold text-[10px] mt-0.5 ${stats.userSecondsLeft > 0 && stats.userSecondsLeft < 21600 ? 'text-rose-600' : 'text-emerald-600'}`}>
                  {formatRemainingTime(stats.userSecondsLeft, stats.userDays)}
                </p>
              </div>
              <div className="bg-slate-50 p-2 rounded-xl border border-slate-100 text-center">
                <p className="text-[7.5px] text-slate-400 font-bold uppercase">Jadwal</p>
                <p className="font-bold text-slate-700 text-[10px] mt-0.5">
                  {stats.userInterval < 1 ? `${Math.round(stats.userInterval * 60)} mnt` : `${stats.userInterval} jam`}
                </p>
              </div>
            </div>
          ) : (
            <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100 text-center">
              <p className="text-[10px] font-bold text-slate-400 uppercase">Belum Ada Paket Aktif</p>
              <button onClick={() => { triggerHaptic('light'); setActiveTab('home'); }} className="mt-2 text-geun-blue font-black text-[10px] uppercase">
                Beli Paket Sekarang →
              </button>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 text-left mt-2">
          <div className="bg-slate-100/50 p-3.5 rounded-xl border border-slate-200/40">
            <p className="text-[7.5px] text-slate-400 uppercase font-bold tracking-widest">ID Telegram</p>
            <p className="text-xs font-bold text-slate-800 mt-1">{user?.id || '-'}</p>
          </div>
          <div className="bg-slate-100/50 p-3.5 rounded-xl border border-slate-200/40">
            <p className="text-[7.5px] text-slate-400 uppercase font-bold tracking-widest">Sesi Sinyal</p>
            <p className="text-xs font-bold text-emerald-600 mt-1">Stabil</p>
          </div>
        </div>
      </div>
    </motion.div>
  );
};
