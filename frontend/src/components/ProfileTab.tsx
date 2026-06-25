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
  is_admin?: boolean;
  userbots_list?: any[];
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
  const [expandedUbot, setExpandedUbot] = React.useState<string | null>(null);
  
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
                <p className="text-[7.5px] text-slate-400 font-bold uppercase">
                  {stats.userPackage.toLowerCase().includes('userbot') ? 'Kapasitas Grup' : 'Kapasitas'}
                </p>
                <p className="font-bold text-geun-blue text-[10px] mt-0.5">
                  {stats.userPackage.toLowerCase().includes('userbot')
                    ? `${stats.userbots_list?.reduce((acc: number, ub: any) => acc + (ub.joined_groups?.length || 0), 0) || 0} Grup`
                    : `${stats.userLpm} LPM`}
                </p>
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

        {/* Real-time Userbots List Section */}
        {stats.userbots_list && stats.userbots_list.length > 0 && (
          <div className="mt-4 text-left space-y-2 border-t border-slate-100 pt-4">
            <h4 className="text-[9px] font-black text-slate-400 uppercase tracking-widest pb-1.5 flex justify-between items-center">
              <span>{stats.is_admin ? "👥 KONTROL USERBOT PEMBELI (OWNER)" : "🤖 DAFTAR USERBOT ANDA"}</span>
              <span className="text-[7.5px] bg-slate-100 text-slate-500 font-bold px-1.5 py-0.5 rounded-full lowercase">realtime</span>
            </h4>
            <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
              {stats.userbots_list.map((ub: any, index: number) => {
                const isOnline = ub.status === 'connected';
                const ownerName = stats.is_admin && ub.users 
                  ? (ub.users.username ? `@${ub.users.username}` : ub.users.full_name || `ID: ${ub.user_id}`)
                  : null;
                const isExpanded = expandedUbot === ub.phone_number;
                return (
                  <div key={index} className="bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-xs space-y-2 transition-all duration-300">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-3">
                        {ub.photo_url ? (
                          <img src={ub.photo_url} alt="Ubot avatar" className="w-9 h-9 rounded-xl border border-slate-200 object-cover shadow-sm" />
                        ) : (
                          <div className="w-9 h-9 bg-gradient-to-br from-blue-400 to-indigo-500 rounded-xl flex items-center justify-center font-black text-white text-xs shadow-sm">
                            {ub.display_name ? ub.display_name.charAt(0) : "🤖"}
                          </div>
                        )}
                        
                        <div className="space-y-0.5">
                          <p className="font-bold text-slate-700 leading-tight">{ub.display_name || ub.phone_number}</p>
                          {ub.display_name && (
                            <p className="text-[8.5px] text-slate-400 font-semibold leading-none">{ub.phone_number}</p>
                          )}
                          {ownerName && (
                            <p className="text-[8.5px] text-geun-blue font-extrabold leading-none mt-0.5">{ownerName}</p>
                          )}
                        </div>
                      </div>
                      <span className={`font-bold uppercase tracking-wider text-[8px] px-2 py-0.5 rounded-full ${isOnline ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                        {isOnline ? 'Connected' : 'Disconnected'}
                      </span>
                    </div>

                    {isOnline && ub.joined_groups && ub.joined_groups.length > 0 && (
                      <div className="pt-2 border-t border-slate-200/60">
                        <button
                          onClick={() => {
                            triggerHaptic('light');
                            setExpandedUbot(isExpanded ? null : ub.phone_number);
                          }}
                          className="flex items-center justify-between w-full text-[9px] font-black text-slate-500 hover:text-geun-blue tracking-wider uppercase"
                        >
                          <span>📁 Lihat Grup ({ub.joined_groups.length})</span>
                          <span>{isExpanded ? '▲' : '▼'}</span>
                        </button>
                        
                        {isExpanded && (
                          <div className="mt-2 space-y-1 max-h-36 overflow-y-auto pl-2 border-l-2 border-slate-200 pr-1">
                            {ub.joined_groups.map((group: any, gIdx: number) => (
                              <div key={gIdx} className="flex justify-between items-center text-[10px] py-1 border-b border-slate-100 last:border-b-0">
                                <span className="font-bold text-slate-600 truncate max-w-[170px]">{group.name}</span>
                                {group.link ? (
                                  <a
                                    href={group.link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[9px] text-geun-blue font-extrabold hover:underline"
                                  >
                                    Grup ↗
                                  </a>
                                ) : (
                                  <span className="text-[8px] text-slate-400 font-bold uppercase italic">Privat</span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {(!stats.userbots_list || stats.userbots_list.length === 0) && stats.userPackage.toLowerCase().includes('userbot') && (
          <div className="mt-4 text-left space-y-2 border-t border-slate-100 pt-4">
            <h4 className="text-[9px] font-black text-slate-400 uppercase tracking-widest pb-1.5 flex justify-between items-center">
              <span>{stats.is_admin ? "👥 KONTROL USERBOT PEMBELI (OWNER)" : "🤖 DAFTAR USERBOT ANDA"}</span>
              <span className="text-[7.5px] bg-slate-100 text-slate-500 font-bold px-1.5 py-0.5 rounded-full lowercase">realtime</span>
            </h4>
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 text-center text-slate-400 text-[10px] font-bold uppercase tracking-wider">
              Belum ada userbot terhubung
              <br />
              <span className="text-[8.5px] text-slate-400 lowercase tracking-normal font-medium block mt-1">Sambungkan via Telegram (/panel) untuk memindai grup secara otomatis</span>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
};
