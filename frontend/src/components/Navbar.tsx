"use client";

import React from 'react';

const HomeIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 drop-shadow-[0_2px_8px_rgba(0,122,255,0.25)]' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
);

const UserIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 shadow-icon' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
  </svg>
);

const ToolsIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 shadow-icon' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
  </svg>
);

const HistoryIcon = ({ active }: { active: boolean }) => (
  <svg className={`w-5 h-5 transition-all duration-300 ${active ? 'text-geun-blue scale-110 shadow-icon' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

interface NavbarProps {
  activeTab: string;
  handleTabChange: (tab: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, handleTabChange }) => {
  return (
    <nav className="absolute bottom-6 left-4 right-4 h-16 bg-white/70 backdrop-blur-xl border border-slate-200/80 rounded-3xl flex items-center justify-around px-2 shadow-premium z-40">
      <button onClick={() => handleTabChange('home')} className={`flex flex-col items-center justify-center w-12 h-12 transition-spring relative ${activeTab === 'home' ? 'scale-105' : 'text-slate-400'}`}>
        <HomeIcon active={activeTab === 'home'} />
        {activeTab === 'home' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}
      </button>
      <button onClick={() => handleTabChange('tools')} className={`flex flex-col items-center justify-center w-12 h-12 transition-spring relative ${activeTab === 'tools' ? 'scale-105' : 'text-slate-400'}`}>
        <ToolsIcon active={activeTab === 'tools'} />
        {activeTab === 'tools' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}
      </button>
      <button onClick={() => handleTabChange('history')} className={`flex flex-col items-center justify-center w-12 h-12 transition-spring relative ${activeTab === 'history' ? 'scale-105' : 'text-slate-400'}`}>
        <HistoryIcon active={activeTab === 'history'} />
        {activeTab === 'history' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}
      </button>
      <button onClick={() => handleTabChange('profile')} className={`flex flex-col items-center justify-center w-12 h-12 transition-spring relative ${activeTab === 'profile' ? 'scale-105' : 'text-slate-400'}`}>
        <UserIcon active={activeTab === 'profile'} />
        {activeTab === 'profile' && <span className="absolute bottom-1 w-1.5 h-1.5 bg-geun-blue rounded-full animate-pulse shadow-[0_0_8px_rgba(0,122,255,0.8)]"></span>}
      </button>
    </nav>
  );
};
