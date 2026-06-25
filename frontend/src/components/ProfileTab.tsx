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
  loyalty?: {
    points: number;
    tier: string;
    streak: number;
    discount_percent: number;
    next_tier: string | null;
    next_tier_points: number;
    points_to_next: number;
  };
}

interface ProfileTabProps {
  user: TelegramUser | null;
  stats: StatsType;
  setActiveTab: (tab: string) => void;
  getDisplayName: () => string;
  getUsername: () => string;
  triggerHaptic: (style?: 'light' | 'medium' | 'heavy') => void;
  refreshStats?: () => void;
}

export const ProfileTab: React.FC<ProfileTabProps> = ({
  user,
  stats,
  setActiveTab,
  getDisplayName,
  getUsername,
  triggerHaptic,
  refreshStats,
}) => {
  const [expandedUbot, setExpandedUbot] = React.useState<string | null>(null);
  const [deletingPhone, setDeletingPhone] = React.useState<string | null>(null);

  const handleDeleteUserbot = async (phone: string) => {
    if (!user) return;
    if (!confirm(`Apakah Anda yakin ingin menghapus userbot ${phone}? Sesi akan dihapus secara permanen.`)) {
      return;
    }
    
    triggerHaptic('heavy');
    setDeletingPhone(phone);
    try {
      const initData = (window as any).Telegram?.WebApp?.initData || '';
      const response = await fetch('/api/delete-userbot', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-telegram-init-data': initData,
        },
        body: JSON.stringify({
          user_id: user.id,
          phone_number: phone,
        }),
      });

      const resData = await response.json();
      if (resData.status || response.ok) {
        alert(resData.message || 'Userbot berhasil dihapus.');
        if (refreshStats) refreshStats();
      } else {
        alert(`Gagal menghapus: ${resData.error || 'Terjadi kesalahan'}`);
      }
    } catch (err: any) {
      alert(`Error: ${err.message || 'Gagal menghubungi server'}`);
    } finally {
      setDeletingPhone(null);
    }
  };
  
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

        {/* LOYALTY CARD */}
        {stats.loyalty && (
          <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-950 text-white rounded-3xl p-4 text-left border border-slate-700/50 shadow-xl relative overflow-hidden my-3">
            {/* Ambient background glow */}
            <div className="absolute -top-12 -right-12 w-28 h-28 bg-geun-blue/20 rounded-full blur-2xl"></div>
            {stats.loyalty.tier === 'loyalty' && (
              <div className="absolute -bottom-10 -left-10 w-24 h-24 bg-purple-500/20 rounded-full blur-xl"></div>
            )}
            
            <div className="flex justify-between items-center mb-3">
              <div className="flex items-center gap-2">
                <span className="text-base animate-bounce">
                  {stats.loyalty.tier === 'bronze' && '🥉'}
                  {stats.loyalty.tier === 'silver' && '🥈'}
                  {stats.loyalty.tier === 'gold' && '🥇'}
                  {stats.loyalty.tier === 'loyalty' && '💎'}
                </span>
                <span className="text-[10px] font-black tracking-widest text-slate-300">
                  GEUNID LOYALTY
                </span>
              </div>
              <span className={`text-[8px] font-extrabold px-2.5 py-1 rounded-xl uppercase tracking-wider shadow-sm font-sans ${
                stats.loyalty.tier === 'bronze' ? 'tier-badge-bronze' :
                stats.loyalty.tier === 'silver' ? 'tier-badge-silver' :
                stats.loyalty.tier === 'gold' ? 'tier-badge-gold' :
                'tier-badge-loyalty'
              }`}>
                {stats.loyalty.tier.toUpperCase()}
              </span>
            </div>

            {/* Progress Bar / Points Section */}
            {stats.loyalty.next_tier ? (
              <div className="space-y-2">
                <div className="flex justify-between items-center text-[9px] font-extrabold text-slate-400">
                  <span>Progres Poin</span>
                  <span className="text-white bg-white/10 px-2 py-0.5 rounded-full">{stats.loyalty.points} / {stats.loyalty.next_tier_points} Poin</span>
                </div>
                <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden p-[1px]">
                  {stats.loyalty.points > 0 && (
                    <motion.div 
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(100, (stats.loyalty.points / stats.loyalty.next_tier_points) * 100)}%` }}
                      transition={{ duration: 1.2, ease: "easeOut" }}
                      className={`h-full rounded-full overflow-hidden loyalty-progress-fill ${
                        stats.loyalty.tier === 'bronze' ? 'bg-gradient-to-r from-amber-700 to-amber-500' :
                        stats.loyalty.tier === 'silver' ? 'bg-gradient-to-r from-slate-400 to-slate-200' :
                        stats.loyalty.tier === 'gold' ? 'bg-gradient-to-r from-yellow-500 to-amber-400' :
                        'bg-gradient-to-r from-violet-600 via-pink-500 to-blue-500'
                      }`}
                    />
                  )}
                </div>
                <p className="text-[8.5px] font-bold text-slate-400 flex items-center gap-1">
                  <span>🎯</span>
                  <span>Butuh <span className="text-sky-400 font-black">{stats.loyalty.points_to_next}</span> poin lagi menuju tier <span className="text-white font-black uppercase tracking-wider">{stats.loyalty.next_tier}</span></span>
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex justify-between items-center text-[9px] font-extrabold text-slate-400">
                  <span>Total Akumulasi Poin</span>
                  <span className="text-white bg-white/10 px-2 py-0.5 rounded-full font-mono">{stats.loyalty.points} Poin</span>
                </div>
                <div className="w-full h-2 bg-gradient-to-r from-violet-600 via-pink-500 to-blue-500 rounded-full animate-pulse"></div>
                <p className="text-[8.5px] font-black text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-pink-400 uppercase tracking-wide flex items-center gap-1">
                  <span>👑</span>
                  <span>Anda berada di kasta tertinggi (Loyalty Member)!</span>
                </p>
              </div>
            )}

            {/* Loyalty Benefits */}
            <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-white/5 text-[9px] font-bold text-slate-400">
              <div className="flex items-center gap-1">
                <span className="text-[11px]">🔥</span>
                <span>Streak: <span className="text-white font-extrabold">{stats.loyalty.streak}x</span></span>
              </div>
              <div className="flex items-center gap-1 justify-end">
                <span className="text-[11px]">🎁</span>
                <span>Diskon: <span className="text-emerald-400 font-extrabold">{stats.loyalty.discount_percent}%</span></span>
              </div>
            </div>
          </div>
        )}
        
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
                    ? `${stats.userbots_list?.reduce((acc: number, ub: any) => acc + (ub.joined_groups?.length || ub.groups_count || 0), 0) || 0} Grup`
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
              <span className="text-[7.5px] bg-geun-blue/10 text-geun-blue border border-geun-blue/20 font-black px-2 py-0.5 rounded-full uppercase tracking-wider">GEUNID</span>
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
                      <div className="flex items-center gap-1.5">
                        <span className={`font-bold uppercase tracking-wider text-[8px] px-2 py-0.5 rounded-full ${isOnline ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                          {isOnline ? 'Connected' : 'Disconnected'}
                        </span>
                        {!isOnline && (
                          <button
                            onClick={() => handleDeleteUserbot(ub.phone_number)}
                            disabled={deletingPhone === ub.phone_number}
                            className="bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-600 px-2 py-0.5 rounded-full text-[8px] font-black uppercase tracking-wider transition-colors duration-200 flex items-center gap-0.5 disabled:opacity-50"
                          >
                            {deletingPhone === ub.phone_number ? (
                              <span className="w-2 h-2 border border-rose-600 border-t-transparent rounded-full animate-spin"></span>
                            ) : (
                              <span>🗑️ Hapus</span>
                            )}
                          </button>
                        )}
                      </div>
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
              <span className="text-[7.5px] bg-geun-blue/10 text-geun-blue border border-geun-blue/20 font-black px-2 py-0.5 rounded-full uppercase tracking-wider">GEUNID</span>
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
