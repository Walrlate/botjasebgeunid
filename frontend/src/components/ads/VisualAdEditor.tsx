"use client";

import React, { useState } from 'react';
import AdPreviewer from './AdPreviewer';

const VisualAdEditor = () => {
  const [title, setTitle] = useState("Nama Toko Saya");
  const [content, setContent] = useState("Daftar Harga:\n- Netflix 1U 1D 1.5K\n- Spotify 1 Month 10K");
  const [color, setColor] = useState("#007AFF");
  const [isExpandable, setIsExpandable] = useState(false);

  const colors = [
    { name: 'Sapphire', value: '#007AFF' },
    { name: 'Rose', value: '#FF2D55' },
    { name: 'Gold', value: '#FFD700' },
    { name: 'Emerald', value: '#34C759' },
    { name: 'Purple', value: '#5856D6' }
  ];

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      
      {/* Editor Form */}
      <div className="bg-white border border-slate-200/60 rounded-3xl p-5 space-y-4 shadow-soft">
        <h2 className="text-xs font-black text-slate-800 uppercase tracking-wider flex items-center gap-2 mb-2">
          <span>✍️</span> Edit Iklan Anda
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="text-[9px] font-bold text-slate-400 uppercase tracking-wider ml-1">Judul Toko</label>
            <input 
              type="text" 
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs text-slate-800 placeholder-slate-400 focus:ring-1 focus:ring-blue-500/20 focus:border-blue-500/80 outline-none transition-all mt-1 font-semibold"
              placeholder="Masukkan nama toko..."
            />
          </div>

          <div>
            <label className="text-[9px] font-bold text-slate-400 uppercase tracking-wider ml-1">Isi Iklan / Pricelist</label>
            <textarea 
              rows={4}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs text-slate-800 placeholder-slate-400 focus:ring-1 focus:ring-blue-500/20 focus:border-blue-500/80 outline-none transition-all mt-1 resize-none font-semibold"
              placeholder="List harga anda..."
            />
          </div>

          <div>
            <label className="text-[9px] font-bold text-slate-400 uppercase tracking-wider ml-1">Warna Garis Samping</label>
            <div className="flex gap-3 mt-1.5">
              {colors.map((c) => (
                <button
                  key={c.value}
                  onClick={() => setColor(c.value)}
                  className={`w-7 h-7 rounded-full border-2 transition-all ${
                    color === c.value 
                      ? 'border-slate-800 scale-110 shadow-[0_0_8px_rgba(0,0,0,0.15)]' 
                      : 'border-transparent opacity-60 hover:opacity-100'
                  }`}
                  style={{ backgroundColor: c.value }}
                  title={c.name}
                  type="button"
                />
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between p-3.5 bg-slate-50 border border-slate-200/50 rounded-xl">
            <div className="flex flex-col">
              <span className="text-xs font-bold text-slate-700">Bisa Disembunyikan (Expandable)?</span>
              <span className="text-[9px] text-slate-450 text-slate-400 mt-0.5">Membantu memperingkas pesan yang panjang</span>
            </div>
            <input 
              type="checkbox" 
              checked={isExpandable}
              onChange={(e) => setIsExpandable(e.target.checked)}
              className="w-5 h-5 rounded-md accent-blue-500 cursor-pointer"
            />
          </div>
        </div>
      </div>

      {/* Real-time Preview */}
      <AdPreviewer 
        title={title} 
        content={content} 
        color={color} 
        isExpandable={isExpandable} 
      />
    </div>
  );
};

export default VisualAdEditor;
