import { useState, useRef, useEffect } from "react";
import { Slider } from "../ui/slider";
import { Button } from "../ui/button";
import { Building2, Factory, Home, Send, Shield, Power, TrendingUp, X, Activity } from "lucide-react";
import { createPortal } from "react-dom";
import { useGrid } from "../../lib/context";

// ── Escalation steps (matches simulator.py mode_escalate) ──────────────────
const ESCALATION_STEPS = [
  { demand: 1100, supply: 1500, temperature: 26, label: "Morning — grid calm",             emoji: "🌅", zone_multiplier: 0.85 },
  { demand: 1300, supply: 1500, temperature: 30, label: "Mid-morning — demand rising",     emoji: "☀️",  zone_multiplier: 0.90 },
  { demand: 1550, supply: 1500, temperature: 35, label: "Noon — approaching threshold",    emoji: "🌤",  zone_multiplier: 1.05 },
  { demand: 1750, supply: 1480, temperature: 39, label: "Early afternoon — tight supply",  emoji: "🌡",  zone_multiplier: 1.20 },
  { demand: 1950, supply: 1450, temperature: 43, label: "Peak heatwave — overload begins", emoji: "🔥", zone_multiplier: 1.35 },
  { demand: 2150, supply: 1400, temperature: 46, label: "Generator struggling",            emoji: "⚡", zone_multiplier: 1.45 },
  { demand: 2300, supply: 1100, temperature: 48, label: "CRITICAL — generator trip",       emoji: "🚨", zone_multiplier: 1.50 },
  { demand: 2100, supply: 1200, temperature: 47, label: "Still critical — cascading risk", emoji: "🚨", zone_multiplier: 1.45 },
  { demand: 1800, supply: 1350, temperature: 44, label: "Emergency supply restored",       emoji: "🔴", zone_multiplier: 1.30 },
  { demand: 1500, supply: 1450, temperature: 40, label: "Slowly recovering",               emoji: "⚠️",  zone_multiplier: 1.10 },
  { demand: 1200, supply: 1500, temperature: 34, label: "Evening cool-down",               emoji: "✅", zone_multiplier: 0.90 },
  { demand: 900,  supply: 1500, temperature: 29, label: "Night — grid stable",             emoji: "✅", zone_multiplier: 0.60 },
];

const BASE_ZONES = [
  { name: "hospital",     protected: true,  base_demand: 80  },
  { name: "airport",      protected: true,  base_demand: 100 },
  { name: "metro_rail",   protected: true,  base_demand: 120 },
  { name: "industry1",    protected: false, base_demand: 300 },
  { name: "industry2",    protected: false, base_demand: 250 },
  { name: "residential1", protected: false, base_demand: 200 },
  { name: "residential2", protected: false, base_demand: 180 },
  { name: "commercial1",  protected: false, base_demand: 160 },
];

function buildZones(multiplier: number) {
  return BASE_ZONES.map((z) => ({
    name: z.name,
    protected: z.protected,
    demand: parseFloat((z.base_demand * multiplier * (0.95 + Math.random() * 0.1)).toFixed(2)),
  }));
}

const RISK_COLOR: Record<string, string> = {
  LOW: "#10B981", MEDIUM: "#F59E0B", HIGH: "#F97316", CRITICAL: "#EF4444", UNKNOWN: "#64748B",
};
const RISK_ICON: Record<string, string> = {
  LOW: "✅", MEDIUM: "⚠️", HIGH: "🔴", CRITICAL: "🚨", UNKNOWN: "❓",
};

interface SimStep {
  stepLabel:   string;
  emoji:       string;
  demand:      number;
  supply:      number;
  temperature: number;
  deficit:     number;
  risk:        string;
  mlRisk:      string;
  llmRisk:     string;
  plans:       number;
  hitl:        boolean;
  status:      "pending" | "running" | "done" | "error";
}

function SimModal({ steps, currentIdx, isRunning, onStop, onClose, onRerun }: any) {
  const activeRef = useRef<HTMLDivElement>(null);
  useEffect(() => { activeRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [currentIdx]);
  const done = steps.filter((s: any) => s.status === "done").length;
  const total = ESCALATION_STEPS.length;
  const pct = Math.round((done / total) * 100);

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-md p-6">
      <div className="w-full max-w-3xl rounded-[2.5rem] bg-[#0B0D11] border-2 border-white/10 shadow-2xl flex flex-col overflow-hidden h-[80vh]">
        <div className="flex items-center justify-between px-8 py-6 border-b border-white/5 bg-[#16191f] shrink-0">
          <div className="flex items-center gap-4">
            <TrendingUp className="h-6 w-6 text-purple-400" />
            <h2 className="text-xl font-bold text-white uppercase tracking-tight">Escalation Simulation</h2>
          </div>
          <div className="flex items-center gap-4">
            <div className="px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-mono text-white/60">PROGRESS: {pct}%</div>
            <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors"><X className="h-5 w-5 text-white/40" /></button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-8 space-y-4 custom-scrollbar">
          {steps.map((step: any, i: number) => {
            const isActive = i === currentIdx;
            const isDone = step.status === "done";
            const riskColor = RISK_COLOR[step.risk] || "#64748b";
            return (
              <div key={i} ref={isActive ? activeRef : undefined} className={`rounded-2xl border p-5 transition-all duration-300 ${isActive ? 'bg-purple-500/10 border-purple-500/40 shadow-[0_0_20px_rgba(167,139,250,0.1)]' : 'bg-white/[0.02] border-white/5'}`}>
                <div className="flex items-center gap-5">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center border font-bold text-lg" style={{ backgroundColor: isDone ? `${riskColor}20` : 'transparent', borderColor: isDone ? riskColor : '#ffffff10', color: isDone ? riskColor : '#ffffff20' }}>
                    {step.status === "running" ? <Activity className="animate-spin h-5 w-5" /> : isDone ? RISK_ICON[step.risk] : i + 1}
                  </div>
                  <div className="flex-1">
                    <p className={`font-bold ${isActive ? 'text-white' : 'text-white/40'}`}>{step.emoji} {step.stepLabel}</p>
                    <p className="text-xs font-mono text-white/20 mt-1">DEMAND: {step.demand}MW | SUPPLY: {step.supply}MW | TEMP: {step.temperature}°C</p>
                  </div>
                  {isDone && (
                    <div className="flex gap-2">
                       <span className="px-3 py-1 rounded-lg text-[10px] font-bold border" style={{ color: riskColor, borderColor: `${riskColor}40` }}>{step.risk}</span>
                       {step.hitl && <span className="px-3 py-1 rounded-lg bg-red-500/20 text-red-400 text-[10px] font-bold border border-red-500/40">HITL</span>}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className="px-8 py-6 border-t border-white/5 bg-[#16191f] flex justify-end gap-3">
          {isRunning ? <button onClick={onStop} className="px-8 py-3 rounded-xl bg-red-500 text-white font-bold uppercase tracking-widest text-xs">Stop Simulation</button> : <button onClick={onRerun} className="px-8 py-3 rounded-xl bg-purple-600 text-white font-bold uppercase tracking-widest text-xs">Run Again</button>}
          <button onClick={onClose} className="px-8 py-3 rounded-xl bg-white/5 text-white/60 font-bold uppercase tracking-widest text-xs">Close</button>
        </div>
      </div>
    </div>,
    document.body
  );
}

function PrioritySlider({ label, icon: Icon, value, onChange, description, color }: any) {
  return (
    <div className="space-y-5 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center border-2 border-white/10 shadow-2xl" style={{ backgroundColor: `${color}20` }}>
            <Icon className="h-7 w-7" style={{ color }} />
          </div>
          <div>
            <span className="text-lg font-bold text-white block tracking-tight leading-none mb-1">{label}</span>
            <p className="text-xs text-slate-400 font-bold uppercase tracking-widest opacity-60">{description}</p>
          </div>
        </div>
        <span className="font-mono text-xl font-bold tracking-tighter" style={{ color }}>{value}%</span>
      </div>
      <Slider value={[value]} onValueChange={(v) => onChange(v[0])} max={100} step={1} className="[&_[data-slot=slider-range]]:bg-emerald-500 [&_[data-slot=slider-thumb]]:h-7 [&_[data-slot=slider-thumb]]:w-7 [&_[data-slot=slider-thumb]]:border-4 [&_[data-slot=slider-thumb]]:border-emerald-500 shadow-2xl cursor-pointer" />
    </div>
  );
}

export function OperatorSidebar() {
  const { sendMessage } = useGrid();
  const [hospitalProtection, setHospitalProtection] = useState(95);
  const [industrialShedding, setIndustrialShedding] = useState(40);
  const [residentialRotation, setResidentialRotation] = useState(25);
  const [isLoading, setIsLoading] = useState(false);
  const [isEmergencyActive, setIsEmergencyActive] = useState(false);

  const [showSim, setShowSim] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [simSteps, setSimSteps] = useState<SimStep[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const abortRef = useRef(false);

  const makeBlankSteps = (): SimStep[] =>
    ESCALATION_STEPS.map((s) => ({
      stepLabel: s.label, emoji: s.emoji, demand: s.demand, supply: s.supply, temperature: s.temperature,
      deficit: s.demand - s.supply, risk: "UNKNOWN", mlRisk: "?", llmRisk: "?", plans: 0, hitl: false, status: "pending",
    }));

  const handleCommitIntent = async () => {
    setIsLoading(true);
    try {
      const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
      await fetch(`${BACKEND_URL}/grid-state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ demand: 520, supply: 480, temperature: 42.5, zones: buildZones(1.2) })
      });
    } catch (error) { console.error(error); } finally { setIsLoading(false); }
  };

  const runSimulation = async () => {
    abortRef.current = false;
    const steps = makeBlankSteps();
    setSimSteps(steps);
    setIsRunning(true);
    setShowSim(true);
    const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
    for (let i = 0; i < ESCALATION_STEPS.length; i++) {
      if (abortRef.current) break;
      setCurrentIdx(i);
      setSimSteps(prev => { const next = [...prev]; next[i].status = "running"; return next; });
      try {
        const res = await fetch(`${BACKEND_URL}/grid-state`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ demand: ESCALATION_STEPS[i].demand, supply: ESCALATION_STEPS[i].supply, temperature: ESCALATION_STEPS[i].temperature, zones: buildZones(ESCALATION_STEPS[i].zone_multiplier) }),
        });
        const data = await res.json();
        setSimSteps(prev => {
          const next = [...prev];
          next[i] = { ...next[i], risk: (data.risk_level || "UNKNOWN").toUpperCase(), mlRisk: (data.ml_risk_level || "?").toUpperCase(), llmRisk: (data.llm_risk_level || "?").toUpperCase(), plans: data.plans_generated || 0, hitl: data.requires_human_approval || false, status: "done" };
          return next;
        });
      } catch (e) { console.error(e); }
      await new Promise(r => setTimeout(r, 3000));
    }
    setIsRunning(false);
  };

  const handleEmergencyCut = () => {
    if (window.confirm("CRITICAL: Initiate immediate emergency load shed?")) {
      setIsEmergencyActive(true);
      sendMessage({ type: "manual_override", action: "emergency_cut", note: "CRITICAL: Manual emergency cut initiated." });
      setTimeout(() => setIsEmergencyActive(false), 3000);
    }
  };

  return (
    <>
      <aside className="w-96 rounded-[2.5rem] bg-[#16191f]/80 backdrop-blur-3xl border-2 border-white/10 p-8 flex flex-col shadow-2xl h-full">
        <div className="flex items-center gap-5 mb-8 pb-8 border-b-2 border-white/5">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/20 border-2 border-emerald-500/40 shadow-[0_0_30px_rgba(16,185,129,0.2)] flex items-center justify-center">
            <Shield className="h-8 w-8 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white tracking-tighter uppercase leading-none">HUMAN INTENT</h2>
            <p className="text-sm text-emerald-500/60 font-bold uppercase tracking-[0.3em] mt-1">Command Console</p>
          </div>
        </div>

        <div className="flex-1 space-y-8 overflow-auto custom-scrollbar pr-3">
          <PrioritySlider label="Hospital Protection" icon={Building2} value={hospitalProtection} onChange={setHospitalProtection} description="LIFELINE SERVICES" color="#10B981" />
          <PrioritySlider label="Industrial Load" icon={Factory} value={industrialShedding} onChange={setIndustrialShedding} description="SECTOR REDUCTION" color="#F59E0B" />
          <PrioritySlider label="Residential Rotation" icon={Home} value={residentialRotation} onChange={setResidentialRotation} description="GRID BALANCING" color="#3B82F6" />
          <div className="pt-8 border-t-2 border-white/5">
            <Button onClick={handleCommitIntent} disabled={isLoading} className="w-full h-16 bg-emerald-600 hover:bg-emerald-500 text-white text-lg font-bold tracking-widest border-b-4 border-emerald-800">
              <Send className="h-6 w-6 mr-3" /> {isLoading ? "SUBMITTING..." : "COMMIT INTENT"}
            </Button>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t-2 border-white/5 space-y-3">
          <button onClick={() => isRunning ? (abortRef.current = true) : runSimulation()} className="w-full h-14 rounded-2xl border-2 transition-all flex items-center justify-center gap-3 font-bold tracking-widest text-sm shadow-2xl" style={isRunning ? { backgroundColor: "#EF444415", borderColor: "#EF4444", color: "#EF4444" } : { backgroundColor: "#7C3AED15", borderColor: "#7C3AED60", color: "#A78BFA" }}>
            {isRunning ? <><span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" /> STOP SIMULATION</> : <><Activity className="h-5 w-5" /> RUN ESCALATION SIM</>}
          </button>

          {/* RESTORED VIEW SIMULATION RESULTS BUTTON */}
          {!isRunning && simSteps.length > 0 && (
            <button
              onClick={() => setShowSim(true)}
              className="w-full h-12 rounded-xl border border-white/10 bg-white/5 text-white/60 text-xs font-bold tracking-widest flex items-center justify-center gap-2 hover:bg-white/10 transition-all uppercase"
            >
              <TrendingUp className="h-3 w-3" />
              View Simulation History
            </button>
          )}

          <button onClick={handleEmergencyCut} disabled={isEmergencyActive} className={`w-full h-20 rounded-2xl border-4 transition-all group relative overflow-hidden shadow-2xl active:scale-95 ${isEmergencyActive ? 'bg-rose-600 border-rose-400 text-white' : 'bg-rose-500/10 border-rose-500/20 text-rose-500 hover:border-rose-500/80 hover:bg-rose-500/20'}`}>
            <div className="relative flex items-center justify-center gap-4">
              <Power className={`h-6 w-6 ${isEmergencyActive ? 'animate-spin' : ''}`} />
              <span className="text-xl font-bold tracking-[0.15em] uppercase">{isEmergencyActive ? "EXECUTING..." : "EMERGENCY CUT"}</span>
            </div>
          </button>
        </div>
      </aside>

      {showSim && <SimModal steps={simSteps} currentIdx={currentIdx} isRunning={isRunning} onStop={() => (abortRef.current = true)} onClose={() => setShowSim(false)} onRerun={runSimulation} />}
    </>
  );
}
