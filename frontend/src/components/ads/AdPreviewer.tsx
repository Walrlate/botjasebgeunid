import React from 'react';

interface AdPreviewProps {
  title: string;
  content: string;
  color: string;
  isExpandable?: boolean;
}

const AdPreviewer: React.FC<AdPreviewProps> = ({ title, content, color, isExpandable = false }) => {
  return (
    <div className="w-full max-w-sm mx-auto px-1">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Pratinjau Pesan Telegram</span>
        <div className="flex-1 h-[1px] bg-slate-200"></div>
      </div>
      
      {/* Telegram Message Style Simulation (Realistic Light Theme) */}
      <div className="bg-[#E2F2FE] rounded-2xl shadow-soft p-3.5 border border-slate-200/50 relative max-w-[90%] select-none">
        <div className="flex gap-2.5">
          {/* Colored Sidebar (The Killer Feature) */}
          <div 
            className="w-[3px] rounded-full shrink-0" 
            style={{ backgroundColor: color }}
          ></div>
          
          <div className="flex-1 min-w-0">
            <div className="flex justify-between items-start mb-1 gap-4">
              <h3 className="font-bold text-xs text-blue-600 truncate leading-tight">{title}</h3>
              {isExpandable && <span className="text-slate-400 text-[10px] select-none">🔗 Expandable</span>}
            </div>
            
            <p className="text-xs text-slate-800 whitespace-pre-wrap leading-relaxed break-words pr-8">
              {content || "Isi iklan Anda akan muncul di sini..."}
            </p>
          </div>
        </div>
        
        {/* Telegram Timestamp & Checks at bottom-right */}
        <div className="absolute bottom-1.5 right-3 flex items-center gap-0.5 text-[9px] text-slate-400 select-none">
          <span>11:15</span>
          <svg className="w-3.5 h-3.5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
      </div>
      
      <p className="text-[9px] text-center mt-3.5 text-slate-400">
        Iklan Anda akan tampil seperti simulasi gelembung chat di atas pada grup LPM tujuan.
      </p>
    </div>
  );
};

export default AdPreviewer;
