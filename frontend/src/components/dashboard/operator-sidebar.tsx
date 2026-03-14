import { useState, useRef, useEffect } from "react";
import { Slider } from "../ui/slider";
import { Button } from "../ui/button";
import { Building2, Factory, Home, Send, Shield, Power, TrendingUp, X, Activity } from "lucide-react";
import { createPortal } from "react-dom";

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
const RISK_BG: Record<string, string> = {
  LOW: "#10B98120", MEDIUM: "#F59E0B20", HIGH: "#F9731620", CRITICAL: "#EF444420", UNKNOWN: "#64748B20",
};
const RISK_ICON: Record<string, string> = {
  LOW: "✅", MEDIUM: "⚠️", HIGH: "🔴", CRITICAL: "🚨", UNKNOWN: "❓",
};

// ── Types ──────────────────────────────────────────────────────────────────
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
  error?:      string;
}

// ── Sim Modal ──────────────────────────────────────────────────────────────
function SimModal({
  steps,
  currentIdx,
  isRunning,
  onStop,
  onClose,
  onRerun,
}: {
  steps: SimStep[];
  currentIdx: number;
  isRunning: boolean;
  onStop: () => void;
  onClose: () => void;
  onRerun: () => void;
}) {
  const activeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [currentIdx]);

  const done  = steps.filter((s) => s.status === "done").length;
  const total = ESCALATION_STEPS.length;
  const pct   = Math.round((done / total) * 100);

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-6">
      <div
        className="w-full max-w-3xl rounded-[2.5rem] bg-[#0B0D11]/95 backdrop-blur-3xl border-2 border-white/10 shadow-2xl flex flex-col overflow-hidden"
        style={{ maxHeight: "88vh" }}
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-8 py-5 border-b border-white/5 bg-[#16191f]/80 shrink-0">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-lg font-black text-white uppercase tracking-tight leading-none">Escalation Simulation</h2>
              <p className="text-[10px] text-purple-400/60 font-bold uppercase tracking-[0.3em] mt-1">
                {isRunning ? `Step ${currentIdx + 1} of ${total} — Running` : done === total ? "Cycle Complete" : "Paused"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Progress pill */}
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
              <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: pct === 100 ? "#10B981" : "#A78BFA" }}
                />
              </div>
              <span className="text-xs font-mono font-bold text-white/40">{pct}%</span>
            </div>

            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 transition-colors text-white/40 hover:text-white">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* ── Step cards ── */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3 custom-scrollbar">
          {steps.map((step, i) => {
            const isActive  = i === currentIdx;
            const riskColor = RISK_COLOR[step.risk] ?? RISK_COLOR.UNKNOWN;
            const deficit   = step.deficit;

            return (
              <div
                key={i}
                ref={isActive ? activeRef : undefined}
                className="rounded-2xl border transition-all duration-300"
                style={{
                  backgroundColor: isActive
                    ? "rgba(167,139,250,0.06)"
                    : step.status === "done"
                    ? "rgba(255,255,255,0.02)"
                    : "rgba(255,255,255,0.01)",
                  borderColor: isActive
                    ? "rgba(167,139,250,0.4)"
                    : step.status === "done"
                    ? "rgba(255,255,255,0.06)"
                    : "rgba(255,255,255,0.04)",
                }}
              >
                <div className="flex items-center gap-4 px-5 py-4">
                  {/* Step number / status icon */}
                  <div
                    className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 text-sm font-black border"
                    style={
                      step.status === "done"
                        ? { backgroundColor: `${riskColor}20`, borderColor: `${riskColor}40`, color: riskColor }
                        : isActive
                        ? { backgroundColor: "rgba(167,139,250,0.15)", borderColor: "rgba(167,139,250,0.4)", color: "#A78BFA" }
                        : { backgroundColor: "rgba(255,255,255,0.03)", borderColor: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.2)" }
                    }
                  >
                    {step.status === "running" ? (
                      <div className="w-3.5 h-3.5 border-2 border-purple-400/40 border-t-purple-400 rounded-full animate-spin" />
                    ) : step.status === "done" ? (
                      <span>{RISK_ICON[step.risk] ?? "?"}</span>
                    ) : (
                      <span className="text-[11px]">{i + 1}</span>
                    )}
                  </div>

                  {/* Emoji + label */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-base">{step.emoji}</span>
                      <span
                        className="text-sm font-bold tracking-tight truncate"
                        style={{ color: isActive ? "#E2E8F0" : step.status === "done" ? "#94A3B8" : "#475569" }}
                      >
                        {step.stepLabel}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-[10px] font-mono text-white/20">
                        D:{step.demand}MW · S:{step.supply}MW · {step.temperature}°C
                      </span>
                      {deficit > 0 && step.status !== "pending" && (
                        <span className="text-[10px] font-bold" style={{ color: deficit > 500 ? "#EF4444" : "#F59E0B" }}>
                          −{deficit.toFixed(0)}MW deficit
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Risk badges — only when done */}
                  {step.status === "done" && (
                    <div className="flex items-center gap-2 shrink-0">
                      {/* Risk pill */}
                      <span
                        className="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-widest border"
                        style={{ color: riskColor, backgroundColor: RISK_BG[step.risk] ?? RISK_BG.UNKNOWN, borderColor: `${riskColor}40` }}
                      >
                        {step.risk}
                      </span>

                      {/* ML / LLM mini badges */}
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[9px] font-bold text-white/20 font-mono">ML:{step.mlRisk}</span>
                        <span className="text-[9px] font-bold text-white/20 font-mono">LLM:{step.llmRisk}</span>
                      </div>

                      {/* Plans count */}
                      <div className="flex flex-col items-center px-2 py-1 rounded-lg bg-white/5 border border-white/10">
                        <span className="text-sm font-black text-white">{step.plans}</span>
                        <span className="text-[8px] text-white/30 uppercase tracking-wider">plans</span>
                      </div>

                      {/* HITL badge */}
                      {step.hitl && (
                        <span className="px-2 py-1 rounded-lg bg-red-500/20 border border-red-500/40 text-[9px] font-black text-red-400 uppercase tracking-widest">
                          HITL
                        </span>
                      )}
                    </div>
                  )}

                  {step.status === "error" && (
                    <span className="text-[10px] font-bold text-red-400 shrink-0">Connection failed</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Footer ── */}
        <div className="flex items-center justify-between px-8 py-5 border-t border-white/5 bg-[#16191f]/80 shrink-0">
          {/* Stats row */}
          <div className="flex items-center gap-6">
            {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((r) => {
              const count = steps.filter((s) => s.status === "done" && s.risk === r).length;
              if (!count) return null;
              return (
                <div key={r} className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: RISK_COLOR[r] }} />
                  <span className="text-[10px] font-bold text-white/30 uppercase tracking-wider">{r}: {count}</span>
                </div>
              );
            })}
          </div>

          <div className="flex gap-2">
            {isRunning ? (
              <button
                onClick={onStop}
                className="px-5 py-2 rounded-xl bg-red-500/20 border border-red-500/40 text-red-400 text-xs font-black tracking-widest uppercase hover:bg-red-500/30 transition-all"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={onRerun}
                className="px-5 py-2 rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-400 text-xs font-black tracking-widest uppercase hover:bg-purple-500/30 transition-all"
              >
                Run Again
              </button>
            )}
            <button
              onClick={onClose}
              className="px-5 py-2 rounded-xl bg-white/5 border border-white/10 text-white/40 text-xs font-black tracking-widest uppercase hover:bg-white/10 transition-all"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

// ── PrioritySlider ─────────────────────────────────────────────────────────
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

// ── OperatorSidebar ────────────────────────────────────────────────────────
export function OperatorSidebar() {
  const [hospitalProtection,  setHospitalProtection]  = useState(95);
  const [industrialShedding,  setIndustrialShedding]  = useState(40);
  const [residentialRotation, setResidentialRotation] = useState(25);
  const [isLoading, setIsLoading] = useState(false);

  const handleCommitIntent = async () => {
    setIsLoading(true);
    console.log("[Operator] Committing intent with values:", { hospitalProtection, industrialShedding, residentialRotation });
    try {
      const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
      
      const payload = {
        demand: 520 + (hospitalProtection * 2),
        supply: 480,
        temperature: 42.5,
        zones: [
          { name: "Hospital_North", demand: 150.0 * (hospitalProtection / 100), protected: true, type: "hospital" },
          { name: "Residential_South", demand: 200.0, protected: false, type: "residential" },
          { name: "Industrial_East", demand: 100.0 * (industrialShedding / 100), protected: false, type: "industrial" },
          { name: "Residential_West", demand: 70.0 * (residentialRotation / 100), protected: false, type: "residential" }
        ]
      };
      
      console.log("[Operator] Sending grid state:", payload);
      
      const response = await fetch(`${BACKEND_URL}/grid-state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      console.log("[Operator] Response status:", response.status);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log("[Operator] Grid state submitted successfully:", data);
    } catch (error) {
      console.error("[Operator] Failed to commit intent:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const [showSim,    setShowSim]    = useState(false);
  const [isRunning,  setIsRunning]  = useState(false);
  const [simSteps,   setSimSteps]   = useState<SimStep[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const abortRef                    = useRef(false);

  // Initialise blank step list from scenario definitions
  const makeBlankSteps = (): SimStep[] =>
    ESCALATION_STEPS.map((s) => ({
      stepLabel:   s.label,
      emoji:       s.emoji,
      demand:      s.demand,
      supply:      s.supply,
      temperature: s.temperature,
      deficit:     s.demand - s.supply,
      risk:        "UNKNOWN",
      mlRisk:      "?",
      llmRisk:     "?",
      plans:       0,
      hitl:        false,
      status:      "pending",
    }));

  const runSimulation = async () => {
    abortRef.current = false;
    const steps = makeBlankSteps();
    setSimSteps(steps);
    setCurrentIdx(0);
    setIsRunning(true);
    setShowSim(true);

    const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

    for (let i = 0; i < ESCALATION_STEPS.length; i++) {
      if (abortRef.current) break;

      const cfg = ESCALATION_STEPS[i];
      const d   = parseFloat((cfg.demand      + (Math.random() * 60 - 30)).toFixed(0));
      const s   = parseFloat((cfg.supply      + (Math.random() * 40 - 20)).toFixed(0));
      const t   = parseFloat((cfg.temperature + (Math.random() - 0.5)).toFixed(1));

      // Mark as running
      setCurrentIdx(i);
      setSimSteps((prev) => {
        const next = [...prev];
        next[i] = { ...next[i], demand: d, supply: s, temperature: t, deficit: d - s, status: "running" };
        return next;
      });

      try {
        const res  = await fetch(`${BACKEND_URL}/grid-state`, {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({ demand: d, supply: s, temperature: t, zones: buildZones(cfg.zone_multiplier) }),
        });
        const data = await res.json();

        const risk   = (data.risk_level    ?? "UNKNOWN").toUpperCase();
        const mlRisk = (data.ml_risk_level  ?? "?").toUpperCase();
        const llmRisk= (data.llm_risk_level ?? "?").toUpperCase();

        setSimSteps((prev) => {
          const next = [...prev];
          next[i] = {
            ...next[i],
            risk, mlRisk, llmRisk,
            plans: data.plans_generated ?? 0,
            hitl:  data.requires_human_approval ?? false,
            status: "done",
          };
          return next;
        });
      } catch {
        setSimSteps((prev) => {
          const next = [...prev];
          next[i] = { ...next[i], status: "error" };
          return next;
        });
        break;
      }

      // 3 second pause between steps
      for (let w = 0; w < 30; w++) {
        if (abortRef.current) break;
        await new Promise((r) => setTimeout(r, 100));
      }
    }

    setIsRunning(false);
  };

  const stopSimulation = () => {
    abortRef.current = true;
    setIsRunning(false);
  };

  return (
    <>
      <aside className="w-96 rounded-[2.5rem] bg-[#16191f]/80 backdrop-blur-3xl border-2 border-white/10 p-8 flex flex-col shadow-2xl h-full">
        <div className="flex items-center gap-5 mb-8 pb-8 border-b-2 border-white/5">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/20 flex items-center justify-center border-2 border-emerald-500/40 shadow-[0_0_30px_rgba(16,185,129,0.2)]">
            <Shield className="h-8 w-8 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white tracking-tighter uppercase leading-none">HUMAN INTENT</h2>
            <p className="text-sm text-emerald-500/60 font-bold uppercase tracking-[0.3em] mt-1">Command Console</p>
          </div>
        </div>

        <div className="flex-1 space-y-8 overflow-auto custom-scrollbar pr-3">
          <PrioritySlider label="Hospital Protection"  icon={Building2} value={hospitalProtection}  onChange={setHospitalProtection}  description="LIFELINE SERVICES" color="#10B981" />
          <PrioritySlider label="Industrial Load"      icon={Factory}   value={industrialShedding}  onChange={setIndustrialShedding}  description="SECTOR REDUCTION"  color="#F59E0B" />
          <PrioritySlider label="Residential Rotation" icon={Home}      value={residentialRotation} onChange={setResidentialRotation} description="GRID BALANCING"    color="#3B82F6" />

          <div className="pt-8 border-t-2 border-white/5">
            <Button className="w-full h-16 bg-emerald-600 hover:bg-emerald-500 text-white text-lg font-bold tracking-widest border-b-4 border-emerald-800">
              <Send className="h-6 w-6 mr-3" /> COMMIT INTENT
            </Button>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t-2 border-white/5 space-y-3">

          {/* Escalation Simulation Button */}
          <button
            onClick={() => {
              if (isRunning) { stopSimulation(); }
              else { runSimulation(); }
            }}
            className="w-full h-14 rounded-2xl border-2 transition-all flex items-center justify-center gap-3 font-bold tracking-widest text-sm shadow-2xl"
            style={isRunning
              ? { backgroundColor: "#EF444415", borderColor: "#EF4444",   color: "#EF4444"  }
              : { backgroundColor: "#7C3AED15", borderColor: "#7C3AED60", color: "#A78BFA"  }
            }
          >
            {isRunning ? (
              <>
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                STOP SIMULATION
              </>
            ) : (
              <>
                <Activity className="h-5 w-5" />
                RUN ESCALATION SIM
              </>
            )}
          </button>

          {/* View results button (shown after first run) */}
          {!isRunning && simSteps.length > 0 && (
            <button
              onClick={() => setShowSim(true)}
              className="w-full h-10 rounded-xl border border-white/10 bg-white/5 text-white/40 text-xs font-bold tracking-widest flex items-center justify-center gap-2 hover:bg-white/10 transition-all uppercase"
            >
              <TrendingUp className="h-3 w-3" />
              View Simulation Results
            </button>
          )}

          {/* Emergency Cut */}
          <button className="w-full h-20 rounded-2xl bg-rose-500/10 border-4 border-rose-500/20 hover:border-rose-500/80 transition-all group relative overflow-hidden shadow-2xl">
            <div className="relative flex items-center justify-center gap-4 text-rose-500">
              <Power className="h-6 w-6" />
              <span className="text-xl font-bold tracking-[0.15em] uppercase">EMERGENCY CUT</span>
            </div>
          </button>

        </div>
      </aside>

      {/* Simulation Panel */}
      {showSim && (
        <SimModal
          steps={simSteps}
          currentIdx={currentIdx}
          isRunning={isRunning}
          onStop={stopSimulation}
          onClose={() => setShowSim(false)}
          onRerun={runSimulation}
        />
      )}
    </>
  );
}
