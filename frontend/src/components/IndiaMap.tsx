import { useState, useEffect } from "react";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";

const REGION_MAP: Record<string, string> = {
  "andaman-and-nicobar-islands": "SR", "andhra-pradesh": "SR", "arunachal-pradesh": "NER",
  "assam": "NER", "bihar": "ER", "chandigarh": "NR", "chhattisgarh": "WR",
  "dadra-and-nagar-haveli-and-daman-and-diu": "WR", "delhi": "NR", "goa": "SR",
  "gujarat": "WR", "haryana": "NR", "himachal-pradesh": "NR", "jammu-and-kashmir": "NR",
  "jharkhand": "ER", "karnataka": "SR", "kerala": "SR", "ladakh": "NR",
  "lakshadweep": "SR", "madhya-pradesh": "WR", "maharashtra": "WR", "manipur": "NER",
  "meghalaya": "NER", "mizoram": "NER", "nagaland": "NER", "odisha": "ER",
  "puducherry": "SR", "punjab": "NR", "rajasthan": "NR", "sikkim": "NER",
  "tamil-nadu": "SR", "telangana": "SR", "tripura": "NER", "uttar-pradesh": "NR",
  "uttarakhand": "NR", "west-bengal": "ER",
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
      .then((mod) => { 
        setMapData(mod.default || mod); 
        setLoading(false); 
      })
      .catch(() => setLoading(false));
  }, []);

  // Helper to find region by ID more reliably
  const getRegionForId = (id: string) => {
    const cleanId = id.toLowerCase().trim().replace(/\s+/g, '-');
    const regionKey = REGION_MAP[cleanId];
    return regionKey ? REGION_CONFIG[regionKey] : null;
  };

  if (loading) return null;

  const currentHoverRegion = hoveredId ? getRegionForId(hoveredId) : null;
  const hoveredName = mapData?.locations?.find((l: any) => l.id === hoveredId)?.name ?? hoveredId;

  return (
    <div className="w-full h-full relative bg-transparent overflow-hidden">
      
      {/* DRAG INSTRUCTION */}
      <div className="absolute top-6 left-1/2 -translate-x-1/2 z-30 pointer-events-none">
         <div className="bg-[#16191f]/60 backdrop-blur-md border border-white/10 px-4 py-2 rounded-full shadow-2xl">
            <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Click and Drag to Pan Map</span>
         </div>
      </div>

      {/* TOOLTIP */}
      {hoveredId && currentHoverRegion && (
        <div className="absolute top-10 right-10 bg-[#16191f]/95 backdrop-blur-2xl border-2 border-white/10 p-6 rounded-[2rem] shadow-2xl z-50 min-w-[260px] pointer-events-none">
          <p className="text-[10px] font-bold text-white/30 uppercase tracking-[0.3em] mb-1 text-right">{currentHoverRegion.label} Grid</p>
          <p className="text-2xl font-bold text-white tracking-tight mb-4 capitalize">{hoveredName}</p>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-white/40 uppercase">Current Load</span>
              <span className="font-mono text-xl font-bold" style={{ color: currentHoverRegion.color }}>{currentHoverRegion.load}</span>
            </div>
            <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full transition-all duration-500" style={{ width: currentHoverRegion.load, backgroundColor: currentHoverRegion.color }} />
            </div>
            <div className="flex items-center gap-3 pt-2 border-t border-white/5">
              <div className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ backgroundColor: currentHoverRegion.color }} />
              <p className="text-sm font-bold tracking-widest" style={{ color: currentHoverRegion.color }}>STATUS: {currentHoverRegion.status}</p>
            </div>
          </div>
        </div>
      )}

      {/* PAN WRAPPER */}
      <TransformWrapper
        initialScale={1.3}
        minScale={1.3}
        maxScale={1.3}
        limitToBounds={false}
        centerZoomedOut={false}
        panning={{ disabled: false, velocityDisabled: true }}
      >
        <TransformComponent wrapperClass="!w-full !h-full" contentClass="!w-full !h-full flex items-center justify-center">
          <svg 
            viewBox={mapData.viewBox} 
            className="w-full h-[85vh] cursor-grab active:cursor-grabbing outline-none" 
            style={{ filter: "drop-shadow(0 0 40px rgba(0,0,0,0.6))" }}
          >
            <g>
              {mapData.locations?.map((location: any) => {
                const region = getRegionForId(location.id);
                const color = region?.color ?? "#334155"; // Fallback to dark if not found
                const isHover = hoveredId === location.id;

                return (
                  <path
                    key={location.id}
                    id={location.id}
                    d={location.path}
                    className="transition-all duration-300 cursor-pointer outline-none"
                    style={{
                      fill: color,
                      fillOpacity: isHover ? 0.7 : 0.3,
                      stroke: isHover ? "#ffffff" : "#475569",
                      strokeWidth: isHover ? 2 : 1,
                      filter: isHover ? `drop-shadow(0 0 15px ${color})` : "none",
                    }}
                    onMouseEnter={() => setHoveredId(location.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    onClick={() => onStateClick(location.name)}
                  />
                );
              })}
            </g>
          </svg>
        </TransformComponent>
      </TransformWrapper>

      {/* REGIONAL STATUS BAR */}
      <div className="absolute bottom-40 left-[28rem] flex flex-row flex-wrap gap-4 pointer-events-auto z-20 pr-10">
        {Object.entries(REGION_CONFIG).map(([id, r]) => (
          <div key={id} className="flex items-center gap-4 bg-[#16191f]/80 px-5 py-2.5 rounded-2xl border border-white/10 backdrop-blur-md shadow-2xl hover:border-white/20 transition-all group min-w-fit">
            <div className="w-3 h-3 rounded-full shrink-0 shadow-[0_0_10px_currentColor] animate-pulse" style={{ backgroundColor: r.color, color: r.color }} />
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
