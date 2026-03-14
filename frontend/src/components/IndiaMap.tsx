import { useState, useEffect } from "react";

export default function IndiaMap() {
  const [mapData, setMapData] = useState<any>(null);
  const [hoveredRegion, setHoveredRegion] = useState<string | null>(null);

  useEffect(() => {
    import("@svg-maps/india")
      .then((mod) => {
        setMapData(mod.default || mod);
      })
      .catch(() => console.error("Failed to load India map"));
  }, []);
  if (!mapData) return <div className="w-full h-full bg-[#0B0D11]" />;

  return (
    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#0a1a2e] via-[#0B0D11] to-[#0f1b2e] relative overflow-hidden">
      <style>{`
        .map-region {
          fill: #e0e7ff;
          stroke: #1e293b;
          stroke-width: 0.5;
          opacity: 0.15;
          transition: all 0.2s ease-in-out;
          cursor: pointer;
        }
        .map-region:hover {
          fill: #6366f1;
          opacity: 0.3;
        }
      `}</style>

      <div className="w-full h-full flex items-center justify-center">
        <svg
          viewBox={mapData.viewBox}
          className="w-full h-full"
          onMouseLeave={() => setHoveredRegion(null)}
        >
          {mapData.locations?.map((location: any) => (
            <path
              key={location.id}
              d={location.path}
              className="map-region"
              onMouseEnter={() => setHoveredRegion(location.name)}
            />
          ))}
        </svg>
      </div>

      {/* Info Card */}
      <div className="absolute bottom-6 left-6 bg-[#1a2332]/80 backdrop-blur-xl border border-indigo-500/20 rounded-xl p-4 text-sm max-w-xs shadow-2xl">
        <div className="font-bold text-indigo-300 mb-2">Grid Overview</div>
        <div className="text-slate-400 text-xs space-y-1">
          <div>• Hover regions for details</div>
          <div>• Real-time grid status</div>
          <div>• Zone power distribution</div>
        </div>
      </div>

      {/* Hovered Region Label */}
      {hoveredRegion && (
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-indigo-600/90 backdrop-blur-lg px-6 py-3 rounded-lg shadow-2xl pointer-events-none">
          <span className="font-bold text-white text-lg">{hoveredRegion}</span>
        </div>
      )}
    </div>
  );
}
