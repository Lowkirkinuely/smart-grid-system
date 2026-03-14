import { useState } from "react";
import { Sparkles, Shield, DollarSign, Play, ChevronUp, ChevronDown } from "lucide-react";

// --- SUB-COMPONENTS ---

function CircularGauge({ value, max, color, label, size = 70 }: { value: number; max: number; color: string; label: string; size?: number }) {
  const percentage = (value / max) * 100;
  const radius = (size - 10) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="w-full h-full -rotate-90" viewBox={`0 0 ${size} ${size}`}>
          <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
          <circle
            cx={size/2}
            cy={size/2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            style={{ filter: `drop-shadow(0 0 8px ${color}60)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-black text-white leading-none">{value}</span>
          <span className="text-[8px] font-bold text-white/30 uppercase">{label === "Confidence" ? "%" : "MW"}</span>
        </div>
      </div>
      <span className="text-[9px] font-black uppercase tracking-[0.1em] text-white/50">{label}</span>
    </div>
  );
}

function HarmScoreBar({ score }: { score: number }) {
  const getColor = (s: number) => {
    if (s <= 3) return "#10B981";
    if (s <= 6) return "#F59E0B";
    return "#EF4444";
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-black uppercase tracking-widest text-white/40">Harm Score</span>
        <span className="font-mono text-sm font-black" style={{ color: getColor(score) }}>{score}/10</span>
      </div>
      <div className="flex items-center gap-1">
        {Array.from({ length: 10 }).map((_, i) => (
          <div
            key={i}
            className="h-2 flex-1 rounded-sm shadow-inner"
            style={{ backgroundColor: i < score ? getColor(score) : "rgba(255,255,255,0.05)" }}
          />
        ))}
      </div>
    </div>
  );
}

// --- MAIN COMPONENT ---

export function PlanDrawer() {
  const [isExpanded, setIsExpanded] = useState(false);

  const plans = [
    { name: "PLAN ALPHA", color: "#10B981", sub: "Balanced Distribution", confidence: 92, saved: 28, harm: 3, icon: Sparkles },
    { name: "PLAN BRAVO", color: "#8B5CF6", sub: "Critical Protection", confidence: 87, saved: 18, harm: 2, icon: Shield },
    { name: "PLAN CHARLIE", color: "#F59E0B", sub: "Economic Priority", confidence: 78, saved: 42, harm: 6, icon: DollarSign }
  ];

  return (
    <div 
      className={`transition-all duration-700 ease-in-out rounded-[3rem] border-2 border-white/10 shadow-2xl overflow-hidden mb-6 ${
        isExpanded 
          ? "w-[95%] h-[480px] bg-[#0B0D11]/95 backdrop-blur-3xl p-8" 
          : "w-[900px] h-24 bg-[#16191f]/40 backdrop-blur-xl p-6 cursor-pointer hover:border-purple-500/50"
      }`}
      onClick={() => !isExpanded && setIsExpanded(true)}
    >
      {/* Header Bar */}
      <div className="flex items-center justify-between h-full max-h-12">
        <div className="flex items-center gap-6">
          <Sparkles className="text-purple-400 h-8 w-8 shrink-0" />
          <div className="flex flex-col justify-center">
            <h2 className="text-2xl font-black text-white uppercase leading-none tracking-tighter">AI OPTIMIZATION</h2>
            {!isExpanded && <p className="text-[10px] text-purple-400 font-bold tracking-widest uppercase mt-1 opacity-70">3 Candidates Ready for Command</p>}
          </div>
        </div>

        <div className="flex items-center gap-8">
          {!isExpanded && (
            <div className="flex items-center gap-8">
                <div className="flex flex-col items-end justify-center">
                    <span className="text-2xl font-black text-emerald-400 font-mono tracking-tighter leading-none">+88 MW</span>
                    <span className="text-[9px] font-bold text-emerald-500/40 uppercase tracking-widest leading-none mt-1">Yield Potential</span>
                </div>
                <div className="px-4 py-2 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center justify-center">
                  <span className="text-[10px] font-black text-purple-400 uppercase tracking-widest animate-pulse">
                      Neural Net Active
                  </span>
                </div>
            </div>
          )}
          <button 
            onClick={(e) => { e.stopPropagation(); setIsExpanded(!isExpanded); }}
            className="w-12 h-12 hover:bg-white/10 rounded-full transition-colors flex items-center justify-center border border-white/10 shrink-0"
          >
            {isExpanded ? <ChevronDown className="text-white h-7 w-7" /> : <ChevronUp className="text-white h-7 w-7" />}
          </button>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="flex gap-6 mt-4 overflow-x-auto pb-2 custom-scrollbar h-[360px]">
          {plans.map((plan) => (
            <div key={plan.name} className="flex-1 min-w-[320px] bg-white/5 rounded-[2.5rem] p-6 border border-white/10 flex flex-col shadow-2xl justify-between h-full">
              <div>
                <div className="flex items-center gap-4 mb-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/5 border border-white/10">
                      <plan.icon className="h-5 w-5" style={{ color: plan.color }} />
                  </div>
                  <div>
                      <h3 className="text-xl font-black text-white leading-none mb-1 tracking-tight">{plan.name}</h3>
                      <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest">{plan.sub}</p>
                  </div>
                </div>
                
                <div className="flex justify-around mb-4 border-y border-white/5 py-4">
                   <CircularGauge value={plan.confidence} max={100} color={plan.color} label="Confidence" />
                   <CircularGauge value={plan.saved} max={50} color="#10B981" label="MW Saved" />
                </div>

                <div className="mb-4">
                  <HarmScoreBar score={plan.harm} />
                </div>
              </div>

              <button className="w-full h-14 rounded-xl font-black text-base tracking-[0.2em] text-white transition-all active:scale-95 uppercase shadow-[0_10px_30px_rgba(0,0,0,0.3)] border-b-4 border-black/30" style={{ backgroundColor: plan.color }}>
                Execute Strategy
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
