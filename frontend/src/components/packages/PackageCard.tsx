import React from 'react';

interface PackageCardProps {
  name: string;
  lpm_count: number;
  duration: string;
  price: string;
  isPopular?: boolean;
  features: string[];
}

const PackageCard: React.FC<PackageCardProps> = ({ name, lpm_count, duration, price, isPopular, features }) => {
  return (
    <div className={`relative overflow-hidden rounded-2xl p-5 transition-all duration-300 hover:scale-[1.01] border ${
      isPopular 
        ? 'border-blue-500 bg-slate-900/80 shadow-[0_0_20px_rgba(59,130,246,0.2)]' 
        : 'border-slate-800/70 bg-slate-900/40 hover:border-slate-700/80'
    }`}>
      {isPopular && (
        <div className="absolute top-0 right-0 bg-blue-500 text-white text-[9px] font-black px-3 py-1 rounded-bl-xl uppercase tracking-widest">
          Terlaris
        </div>
      )}
      
      <div className="mb-3">
        <h3 className="text-lg font-black text-white tracking-tight">{name}</h3>
        <p className="text-xs font-semibold text-blue-400 mt-0.5">{lpm_count} Grup LPM • {duration}</p>
      </div>

      <div className="space-y-1.5 mb-5">
        {features.map((feature, index) => (
          <div key={index} className="flex items-center gap-2 text-xs text-slate-400">
            <span className="text-blue-500 font-bold">✓</span>
            {feature}
          </div>
        ))}
      </div>

      <div className="flex justify-between items-end">
        <div>
          <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider">Harga Mulai</p>
          <p className="text-xl font-black text-white tracking-tight">{price}</p>
        </div>
        <button className={`px-5 py-2 rounded-xl text-xs font-bold transition-all active:scale-95 ${
          isPopular 
            ? 'bg-blue-500 text-white shadow-[0_4px_12px_rgba(59,130,246,0.3)] hover:bg-blue-600' 
            : 'bg-slate-800 text-slate-200 hover:bg-slate-700 border border-slate-700/50'
        }`}>
          Pilih Paket
        </button>
      </div>
    </div>
  );
};

export default PackageCard;
