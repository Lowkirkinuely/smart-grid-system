import React, { useState } from "react";

export default function IndiaMap({ onStateClick }: { onStateClick: (name: string) => void }) {
  const [hoveredRegion, setHoveredRegion] = useState<string | null>(null);

  // Power Grid Regions
  const regions = [
    { id: "NR", name: "Northern Grid", path: "M250 50 L350 80 L380 180 L320 280 L180 280 L150 180 L180 80 Z", status: "CRITICAL", load: "112%", color: "#ef4444" },
    { id: "WR", name: "Western Grid", path: "M180 280 L100 320 L70 450 L180 550 L250 450 L220 280 Z", status: "STABLE", load: "74%", color: "#10b981" },
    { id: "SR", name: "Southern Grid", path: "M250 450 L350 550 L250 750 L150 550 Z", status: "STABLE", load: "62%", color: "#10b981" },
    { id: "ER", name: "Eastern Grid", path: "M320 280 L450 320 L480 450 L350 550 L250 450 L320 280 Z", status: "WARNING", load: "91%", color: "#f59e0b" },
    { id: "NER", name: "North-Eastern Grid", path: "M450 320 L550 300 L580 380 L480 450 Z", status: "STABLE", load: "45%", color: "#10b981" },
  ];

  return (
    <div className="w-full h-full flex items-center justify-center relative bg-transparent p-10">
      
      {/* TACTICAL TOOLTIP */}
      {hoveredRegion && (
        <div className="absolute top-10 right-10 bg-[#16191f]/95 backdrop-blur-2xl border-2 border-white/10 p-6 rounded-[2rem] shadow-2xl z-50 animate-in fade-in zoom-in duration-200 min-w-[280px] pointer-events-none">
          <p className="text-[10px] font-bold text-white/30 uppercase tracking-[0.3em] mb-1 text-right">Regional Despatch Centre</p>
          <p className="text-3xl font-bold text-white tracking-tighter mb-4">{hoveredRegion.toUpperCase()}</p>
          
          {regions.filter(r => r.name === hoveredRegion).map(r => (
            <div key={r.id} className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-white/40 uppercase">Current Load</span>
                <span className="font-mono text-xl font-bold" style={{ color: r.color }}>{r.load}</span>
              </div>
              <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div className="h-full transition-all duration-500" style={{ width: r.load, backgroundColor: r.color }} />
              </div>
              <div className="flex items-center gap-3 pt-2 border-t border-white/5">
                <div className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ backgroundColor: r.color }} />
                <p className="text-sm font-black tracking-widest" style={{ color: r.color }}>STATUS: {r.status}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* REGIONAL GRID SVG */}
      <svg viewBox="0 0 600 800" className="w-full h-full drop-shadow-[0_0_50px_rgba(0,0,0,0.5)]">
        <g>
          {regions.map((region) => (
            <path
              key={region.id}
              d={region.path}
              fill={region.color}
              fillOpacity={hoveredRegion === region.name ? "0.4" : "0.15"}
              stroke={region.color}
              strokeWidth={hoveredRegion === region.name ? "4" : "2"}
              className="transition-all duration-300 cursor-pointer"
              onMouseEnter={() => setHoveredRegion(region.name)}
              onMouseLeave={() => setHoveredRegion(null)}
              onClick={() => onStateClick(region.name)}
              style={{
                filter: hoveredRegion === region.name ? `drop-shadow(0 0 15px ${region.color})` : 'none'
              }}
            />
          ))}
        </g>

        {/* Region Labels */}
        {regions.map(r => {
            const coords = r.path.split(' ')[0].replace('M', '').split(' ');
            return (
                <text 
                    key={`label-${r.id}`}
                    x={parseInt(coords[0]) + 20} 
                    y={parseInt(coords[1]) + 60} 
                    fill="white" 
                    fontSize="10" 
                    className="font-bold opacity-30 pointer-events-none uppercase tracking-widest"
                >
                    {r.id}
                </text>
            )
        })}
      </svg>

      {/* LEGEND */}
      <div className="absolute bottom-10 left-10 flex flex-col gap-4 pointer-events-auto">
         <div className="flex items-center gap-4 bg-white/5 px-6 py-3 rounded-2xl border border-white/5 backdrop-blur-md shadow-xl">
            <div className="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_10px_#10b981]" />
            <span className="text-[11px] font-bold text-white/40 uppercase tracking-[0.2em]">Grid Stable</span>
         </div>
         <div className="flex items-center gap-4 bg-white/5 px-6 py-3 rounded-2xl border border-white/5 backdrop-blur-md shadow-xl">
            <div className="w-3 h-3 rounded-full bg-rose-500 shadow-[0_0_10px_#ef4444] animate-pulse" />
            <span className="text-[11px] font-bold text-white/40 uppercase tracking-[0.2em]">Regional Stress</span>
         </div>
      </div>
    </div>
  );
}
