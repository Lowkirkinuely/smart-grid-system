import { useState } from "react";
import { Sparkles, Shield, DollarSign, Play, ChevronUp, ChevronDown } from "lucide-react";
import { Button } from "../ui/button";
import type { AiAnalysis, GridPlan } from "../../types/grid";

function CircularGauge({ value, max, color, label, size = 70 }: { value: number; max: number; color: string; label: string; size?: number }) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  const radius = (size - 10) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="w-full h-full -rotate-90" viewBox={`0 0 ${size} ${size}`}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
          <circle
            cx={size / 2}
            cy={size / 2}
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
          <span className="text-xl font-black text-white leading-none">{Math.round(percentage)}</span>
          <span className="text-[8px] font-bold text-white/30 uppercase">{label}</span>
        </div>
      </div>
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

const planIcons: Record<number, typeof Sparkles> = {
  1: Sparkles,
  2: Shield,
  3: DollarSign,
};

type PlanDrawerProps = {
  plans: GridPlan[];
  aiAnalysis?: AiAnalysis | null;
  recommendedPlanId?: number | null;
  lastUpdated?: string | null;
  loading?: boolean;
  onApplyPlan?: (planId: number) => void;
  onRejectPlans?: () => void;
};

function PlanCard({ plan, recommended, onExecute }: { plan: GridPlan; recommended?: boolean; onExecute?: (id: number) => void }) {
  const coverage = plan.deficit_mw > 0 ? Math.min(100, Math.round((plan.power_saved / plan.deficit_mw) * 100)) : 100;
  const Icon = planIcons[plan.plan_id] ?? Sparkles;
  return (
    <div
      className={`flex-1 min-w-[320px] bg-white/5 rounded-[2.5rem] p-6 border border-white/10 flex flex-col shadow-2xl justify-between h-full transition-all ${
        recommended ? "border-emerald-500/60 shadow-[0_20px_60px_rgba(16,185,129,0.3)]" : ""
      }`}
    >
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/5 border border-white/10">
              <Icon className="h-5 w-5 text-white" />
            </div>
            <div>
              <h3 className="text-xl font-black text-white leading-none tracking-tight">{plan.label}</h3>
              <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Plan {plan.plan_id}</p>
            </div>
          </div>
          <span className="text-xs font-black uppercase tracking-[0.4em] text-emerald-300">{coverage}% cover</span>
        </div>
        <div className="flex justify-between items-end gap-6 mb-4">
          <div>
            <p className="text-[10px] font-bold text-white/40 uppercase tracking-[0.3em]">Power Saved</p>
            <p className="text-3xl font-black text-white">{plan.power_saved.toFixed(1)} MW</p>
          </div>
          <CircularGauge value={coverage} max={100} color={recommended ? "#10B981" : "#8b5cf6"} label="Coverage" size={80} />
        </div>
        <div className="flex flex-wrap gap-2 mt-2">
          {plan.cuts.length > 0 ? (
            plan.cuts.map((cut) => (
              <span key={cut} className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] font-bold uppercase tracking-[0.2em] text-white/60">
                {cut.replace(/_/g, " ")}
              </span>
            ))
          ) : (
            <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] font-bold uppercase tracking-[0.2em] text-white/60">No cuts needed</span>
          )}
        </div>
        <p className="text-[11px] text-white/40 mt-5 leading-relaxed">{plan.note}</p>
      </div>
      <button
        className="w-full h-14 mt-6 rounded-xl font-black text-base tracking-[0.2em] text-white transition-all active:scale-95 uppercase shadow-[0_10px_30px_rgba(0,0,0,0.3)] border-b-4 border-black/30"
        style={{ backgroundColor: recommended ? "#10B981" : "#8b5cf6" }}
        onClick={(event) => {
          event.stopPropagation();
          onExecute?.(plan.plan_id);
        }}
      >
        <Play className="h-5 w-5 mr-2" /> Execute Strategy
      </button>
    </div>
  );
}

export function PlanDrawer({
  plans,
  aiAnalysis,
  recommendedPlanId,
  lastUpdated,
  loading,
  onApplyPlan,
  onRejectPlans,
}: PlanDrawerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const planCount = plans.length;
  const totalSaved = plans.reduce((sum, plan) => sum + plan.power_saved, 0);
  const riskLabel = aiAnalysis?.risk_level?.toUpperCase() ?? "IDLE";
  const stageDetail = aiAnalysis?.requires_human_approval ? "Human approval required" : "Autonomous";
  const updatedLabel = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
    : "Waiting for grid";
  const harmScoreMap: Record<string, number> = {
    low: 3,
    medium: 5,
    high: 8,
    critical: 10,
  };
  const harmScore = harmScoreMap[(aiAnalysis?.risk_level?.toLowerCase() ?? "low")] ?? 4;

  return (
    <div
      className={`transition-all duration-700 ease-in-out rounded-[3rem] border-2 border-white/10 shadow-2xl overflow-hidden mb-6 ${
        isExpanded
          ? "w-[95%] h-[520px] bg-[#0B0D11]/95 backdrop-blur-3xl p-8"
          : "w-[900px] h-24 bg-[#16191f]/40 backdrop-blur-xl p-6 cursor-pointer hover:border-purple-500/50"
      }`}
      onClick={() => !isExpanded && setIsExpanded(true)}
    >
      <div className="flex items-center justify-between h-full max-h-12">
        <div className="flex items-center gap-6">
          <Sparkles className="text-purple-400 h-8 w-8 shrink-0" />
          <div className="flex flex-col justify-center">
            <h2 className="text-2xl font-black text-white uppercase leading-none tracking-tighter">AI OPTIMIZATION</h2>
            {!isExpanded && <p className="text-[10px] text-purple-400 font-bold tracking-widest uppercase mt-1 opacity-70">{planCount} Candidates Ready</p>}
          </div>
        </div>

        <div className="flex items-center gap-8">
          <div className="flex flex-col items-end">
            <span className="text-xs font-bold uppercase tracking-[0.3em] text-white/40">Risk Level</span>
            <span className="text-2xl font-black text-white tracking-tight">{riskLabel}</span>
            <p className="text-[9px] font-bold uppercase tracking-[0.3em] text-white/40">{stageDetail}</p>
          </div>
          {onRejectPlans && (
            <Button
              variant="ghost"
              className="text-white/50 border border-white/10 px-4"
              onClick={(event) => {
                event.stopPropagation();
                onRejectPlans();
              }}
            >
              Reject Plans
            </Button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            className="w-12 h-12 hover:bg-white/10 rounded-full transition-colors flex items-center justify-center border border-white/10 shrink-0"
          >
            {isExpanded ? <ChevronDown className="text-white h-7 w-7" /> : <ChevronUp className="text-white h-7 w-7" />}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="mt-6 border-t border-white/5 pt-6 h-[437px]">
          <div className="flex items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <CircularGauge value={aiAnalysis?.avg_confidence ? aiAnalysis.avg_confidence * 100 : 0} max={100} color="#10B981" label="Confidence" size={80} />
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.4em] text-white/40">Total Savings</p>
                <p className="text-3xl font-black text-white tracking-tight">{totalSaved.toFixed(1)} MW</p>
                <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/40">{planCount} plans</p>
              </div>
            </div>
            <div className="space-y-2 text-right">
              <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/40">Harm Profile</p>
              <HarmScoreBar score={harmScore} />
            </div>
            <div className="text-right">
              <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/40">Last Update</p>
              <p className="text-lg font-mono font-bold text-white">{updatedLabel}</p>
            </div>
          </div>
          <div className="flex gap-6 mt-6 overflow-x-auto pb-6 custom-scrollbar min-h-[360px]" role="region" aria-label="Optimization plans">
            {planCount > 0 ? (
              plans.map((plan) => (
                <PlanCard
                  key={plan.plan_id}
                  plan={plan}
                  recommended={plan.plan_id === recommendedPlanId || (!recommendedPlanId && plan.plan_id === 1)}
                  onExecute={onApplyPlan}
                />
              ))
            ) : (
              <div className="flex flex-1 items-center justify-center text-center text-white/40">
                {loading ? "Waiting for simulation telemetry..." : "Simulation offline — no plans yet."}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
