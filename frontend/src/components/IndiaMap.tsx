import { useState, useEffect } from "react";

const REGION_MAP: Record<string, string> = {
  "andaman-and-nicobar-islands": "SR",
  "andhra-pradesh": "SR",
  "arunachal-pradesh": "NER",
  "assam": "NER",
  "bihar": "ER",
  "chandigarh": "NR",
  "chhattisgarh": "WR",
  "dadra-and-nagar-haveli-and-daman-and-diu": "WR",
  "delhi": "NR",
  "goa": "SR",
  "gujarat": "WR",
  "haryana": "NR",
  "himachal-pradesh": "NR",
  "jammu-and-kashmir": "NR",
  "jharkhand": "ER",
  "karnataka": "SR",
  "kerala": "SR",
  "ladakh": "NR",
  "lakshadweep": "SR",
  "madhya-pradesh": "WR",
  "maharashtra": "WR",
  "manipur": "NER",
  "meghalaya": "NER",
  "mizoram": "NER",
  "nagaland": "NER",
  "odisha": "ER",
  "puducherry": "SR",
  "punjab": "NR",
  "rajasthan": "NR",
  "sikkim": "NER",
  "tamil-nadu": "SR",
  "telangana": "SR",
  "tripura": "NER",
  "uttar-pradesh": "NR",
  "uttarakhand": "NR",
  "west-bengal": "ER",
};

const REGION_CONFIG: Record<string, { color: string; label: string; status: string; load: string }> = {
  NR:  { color: "#ef4444", label: "Northern",   status: "CRITICAL", load: "112%" },
  WR:  { color: "#10b981", label: "Western",    status: "STABLE",   load: "74%"  },
  SR:  { color: "#10b981", label: "Southern",   status: "STABLE",   load: "62%"  },
  ER:  { color: "#f59e0b", label: "Eastern",    status: "WARNING",  load: "91%"  },
  NER: { color: "#3b82f6", label: "North-East", status: "STABLE",   load: "45%"  },
};

export default function IndiaMap({ onStateClick }: { onStateClick: (name: string) => void }) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [mapData, setMapData]     = useState<any>(null);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    import("@svg-maps/india")
      .then((mod) => { setMapData(mod.default || mod); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const hoveredRegionId = hoveredId ? REGION_MAP[hoveredId] : null;
  const hoveredRegion   = hoveredRegionId ? REGION_CONFIG[hoveredRegionId] : null;
  const hoveredName     = mapData?.locations?.find((l: any) => l.id === hoveredId)?.name ?? hoveredId;

  if (loading) return (
    <div className="w-full h-full flex items-center justify-center">
      <p className="text-white/30 text-sm font-bold uppercase tracking-widest animate-pulse">Loading Map...</p>
    </div>
  );

  if (!mapData) return (
    <div className="w-full h-full flex items-center justify-center">
      <p className="text-rose-400 text-sm font-bold">Map package missing — run: npm install @svg-maps/india</p>
    </div>
  );

  return (
    <div className="w-full h-full flex items-center justify-center relative bg-transparent">

      {/* FLOATING TOOLTIP (Top Right) */}
      {hoveredId && hoveredRegion && (
        <div className="absolute top-10 right-10 bg-[#16191f]/95 backdrop-blur-2xl border-2 border-white/10 p-6 rounded-[2rem] shadow-2xl z-50 min-w-[260px] pointer-events-none">
          <p className="text-[10px] font-bold text-white/30 uppercase tracking-[0.3em] mb-1 text-right">{hoveredRegion.label} Grid</p>
          <p className="text-2xl font-bold text-white tracking-tight mb-4 capitalize">{hoveredName}</p>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-white/40 uppercase">Current Load</span>
              <span className="font-mono text-xl font-bold" style={{ color: hoveredRegion.color }}>{hoveredRegion.load}</span>
            </div>
            <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full transition-all duration-500" style={{ width: hoveredRegion.load, backgroundColor: hoveredRegion.color }} />
            </div>
            <div className="flex items-center gap-3 pt-2 border-t border-white/5">
              <div className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ backgroundColor: hoveredRegion.color }} />
              <p className="text-sm font-black tracking-widest" style={{ color: hoveredRegion.color }}>STATUS: {hoveredRegion.status}</p>
            </div>
          </div>
        </div>
      )}

      {/* MAIN SVG MAP */}
      <svg viewBox={mapData.viewBox} className="w-full h-full max-h-[85vh]" style={{ filter: "drop-shadow(0 0 40px rgba(0,0,0,0.6))" }}>
        {mapData.locations?.map((location: any) => {
          const regionId = REGION_MAP[location.id];
          const region   = regionId ? REGION_CONFIG[regionId] : null;
          const color    = region?.color ?? "#6b7280";
          const isHover  = hoveredId === location.id;
          return (
            <path
              key={location.id}
              id={location.id}
              d={location.path}
              fill={color}
              fillOpacity={isHover ? 0.55 : 0.2}
              stroke={color}
              strokeWidth={isHover ? 1.5 : 0.5}
              strokeOpacity={isHover ? 1 : 0.7}
              className="transition-all duration-200 cursor-pointer"
              style={{ filter: isHover ? `drop-shadow(0 0 6px ${color})` : "none" }}
              onMouseEnter={() => setHoveredId(location.id)}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() => onStateClick(location.name)}
            />
          );
        })}
      </svg>

            {/* RESPONSIVE REGIONAL STATUS BAR */}
      <div className="absolute bottom-42 left-[28rem] flex flex-row flex-wrap gap-4 pointer-events-auto z-20 pr-10">
        {Object.entries(REGION_CONFIG).map(([id, r]) => (
          <div 
            key={id} 
            className="flex items-center gap-4 bg-[#16191f]/80 px-5 py-2.5 rounded-2xl border border-white/10 backdrop-blur-md shadow-2xl hover:border-white/20 transition-all group min-w-fit"
          >
            <div 
              className="w-3 h-3 rounded-full shrink-0 shadow-[0_0_10px_currentColor] animate-pulse" 
              style={{ backgroundColor: r.color, color: r.color }} 
            />
            <div className="flex flex-col">
              <span className="text-[10px] font-bold text-white/40 uppercase tracking-[0.2em] whitespace-nowrap">{r.label}</span>
              <span className="text-sm font-mono font-bold leading-none mt-1" style={{ color: r.color }}>{r.load}</span>
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}

