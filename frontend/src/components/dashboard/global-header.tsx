import { Thermometer, Zap, Activity, ShieldAlert, Clock, Globe } from "lucide-react";
import { useGrid } from "../../lib/context";
import { useState, useEffect } from "react";

function HeaderMetric({ icon: Icon, label, value, unit, color, trend }: any) {
  return (
    <div className="flex items-center gap-5 px-8 py-3 border-r border-white/5 last:border-r-0 group hover:bg-white/[0.02] transition-colors">
      <div className="p-3 rounded-xl bg-white/5 border border-white/10 group-hover:border-white/20 transition-all shadow-lg">
        <Icon className="h-7 w-7" style={{ color }} />
      </div>
      <div className="flex flex-col">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/30">{label}</span>
          {trend && <span className="text-[10px] font-mono font-bold text-rose-500 animate-pulse">{trend}</span>}
        </div>
        <div className="flex items-baseline gap-1.5 mt-0.5">
          <span className="text-3xl font-mono font-bold tracking-tighter text-white">{value}</span>
          <span className="text-xs font-bold text-white/20 uppercase tracking-widest">{unit}</span>
        </div>
      </div>
    </div>
  );
}

export function GlobalHeader() {
  const { gridState } = useGrid();
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const deficit = gridState.demand - gridState.supply;
  const deficitColor = deficit > 0 ? "#EF4444" : "#10B981";

  return (
    <header className="h-28 w-full rounded-[2.5rem] bg-[#16191f]/60 backdrop-blur-3xl border-2 border-white/10 flex items-center justify-between px-10 shadow-2xl overflow-hidden relative group">
      <div className="flex items-center gap-6">
        <div className="w-14 h-14 rounded-2xl bg-emerald-500/20 flex items-center justify-center border-2 border-emerald-500/30 shadow-[0_0_25px_rgba(16,185,129,0.2)]">
          <Globe className="h-8 w-8 text-emerald-400" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tighter leading-none">GRID CONTROL</h1>
          <div className="flex items-center gap-2 mt-2">
             <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
             <span className="text-[11px] font-bold uppercase tracking-[0.4em] text-emerald-500/60">System Online // All India Grid</span>
          </div>
        </div>
      </div>

      <div className="flex-1 flex justify-center mx-10">
        <div className="flex bg-black/30 rounded-3xl border border-white/5 shadow-inner">
          <HeaderMetric icon={Thermometer} label="Ambient Temp" value={gridState.temperature.toFixed(1)} unit="°C" color="#F59E0B" />
          <HeaderMetric icon={Zap} label="Total Supply" value={gridState.supply.toFixed(0)} unit="MW" color="#10B981" />
          <HeaderMetric icon={Activity} label="Live Demand" value={gridState.demand.toFixed(0)} unit="MW" color="#3B82F6" />
          <HeaderMetric icon={ShieldAlert} label="System Deficit" value={deficit.toFixed(0)} unit="MW" color={deficitColor} />
        </div>
      </div>

      <div className="flex items-center gap-10">
        <div className="flex gap-8">
           <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${gridState.isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
              <span className="text-[10px] font-mono text-white/50">
                {gridState.isConnected ? 'Backend: Connected' : 'Backend: Disconnected'}
              </span>
           </div>
           <div className="flex flex-col items-center">
              <div className="relative w-14 h-14">
                 <svg className="w-full h-full -rotate-90" viewBox="0 0 56 56">
                    <circle cx="28" cy="28" r="24" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
                    <circle cx="28" cy="28" r="24" fill="none" stroke="#10B981" strokeWidth="6" strokeDasharray="150" strokeDashoffset="60" strokeLinecap="round" className="drop-shadow-[0_0_5px_#10B981]" />
                 </svg>
                 <div className="absolute inset-0 flex items-center justify-center font-mono text-xs font-bold text-white">59%</div>
              </div>
              <span className="text-[9px] font-bold text-white/30 uppercase tracking-widest mt-2">Carbon-Free</span>
           </div>
        </div>
        <div className="flex flex-col items-end border-l-2 border-white/5 pl-10">
           <div className="flex items-center gap-3">
              <Clock className="h-5 w-5 text-purple-400" />
              <span className="text-3xl font-mono font-bold tracking-tight text-white">
                {currentTime.toLocaleTimeString("en-IN", { hour12: false })}
              </span>
           </div>
           <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/30 mt-1">Local Time (IST)</span>
        </div>
      </div>
    </header>
  );
}
