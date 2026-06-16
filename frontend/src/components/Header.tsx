"use client";

import React from 'react';

interface HeaderProps {
  user: {
    id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    photo_url?: string;
  } | null;
  getDisplayName: () => string;
  getUsername: () => string;
}

export const Header: React.FC<HeaderProps> = ({ user, getDisplayName, getUsername }) => {
  return (
    <header className="flex justify-between items-center px-5 py-4 border-b border-slate-200/50 bg-[#F4F6F9] sticky top-0 z-40">
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
  );
};
