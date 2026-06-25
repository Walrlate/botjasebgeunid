"use client";

import React from 'react';
import { motion } from 'framer-motion';

interface ToolsTabProps {
  rawWording: string;
  setRawWording: (val: string) => void;
  selectedTemplate: 'premium' | 'minimalist' | 'flash';
  setSelectedTemplate: (val: 'premium' | 'minimalist' | 'flash') => void;
  wordingCopied: boolean;
  setWordingCopied: (val: boolean) => void;
  enhancedWording: (text: string, template: 'premium' | 'minimalist' | 'flash') => string;
  triggerHaptic: (style?: 'light' | 'medium' | 'heavy') => void;
}

export const ToolsTab: React.FC<ToolsTabProps> = ({
  rawWording,
  setRawWording,
  selectedTemplate,
  setSelectedTemplate,
  wordingCopied,
  setWordingCopied,
  enhancedWording,
  triggerHaptic,
}) => {
  
  const handleCopyWording = () => {
    triggerHaptic('medium');
    navigator.clipboard.writeText(enhancedWording(rawWording, selectedTemplate));
    setWordingCopied(true);
    setTimeout(() => setWordingCopied(false), 2000);
  };

  return (
    <motion.div
      key="tools"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      className="space-y-6 pb-20"
    >
      <div className="text-center space-y-1">
        <h2 className="text-lg font-black text-slate-800 tracking-wide uppercase">⚡ Fitur Gratis</h2>
        <p className="text-[10px] text-slate-400 font-semibold">Tingkatkan efisiensi promosi Anda secara instan</p>
      </div>

      <div className="glass-panel rounded-3xl p-5 border border-slate-200/60 shadow-soft space-y-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-2xl bg-geun-blue/10 flex items-center justify-center text-geun-blue">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
              <path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </div>
          <div>
            <h3 className="text-xs font-black text-slate-800 uppercase">Wording Beautifier</h3>
          </div>
        </div>
        <textarea
          value={rawWording}
          onChange={(e) => setRawWording(e.target.value)}
          placeholder="Pesan promosi mentah..."
          className="w-full min-h-[100px] text-[10px] p-3.5 bg-[#F8FAFC] border border-slate-200 rounded-2xl focus:outline-none text-slate-700 shadow-inner resize-none"
        />
        <div className="grid grid-cols-3 gap-2">
          {(['premium', 'minimalist', 'flash'] as const).map((temp) => (
            <button
              key={temp}
              onClick={() => { triggerHaptic('light'); setSelectedTemplate(temp); }}
              className={`py-2 rounded-xl text-[9px] font-black uppercase border ${selectedTemplate === temp ? 'bg-geun-blue text-white border-geun-blue' : 'bg-white text-slate-500 border-slate-200'}`}
            >
              {temp}
            </button>
          ))}
        </div>
        {rawWording.trim() && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-[8.5px] font-black text-slate-400 uppercase">Pratinjau</label>
              <button
                onClick={handleCopyWording}
                className={`px-3 py-1 rounded-lg text-[8px] font-black uppercase ${wordingCopied ? 'bg-emerald-50 text-emerald-600' : 'bg-geun-blue/10 text-geun-blue'}`}
              >
                {wordingCopied ? 'Tersalin' : 'Salin'}
              </button>
            </div>
            <div className="p-4 bg-[#F8FAFC] border border-slate-200 rounded-2xl text-[9.5px] font-mono text-slate-700 whitespace-pre-wrap leading-relaxed shadow-inner max-h-[150px] overflow-y-auto">
              {enhancedWording(rawWording, selectedTemplate)}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
};
