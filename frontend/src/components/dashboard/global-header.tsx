import { Thermometer, Zap, Activity, ShieldAlert, Clock, Globe } from "lucide-react";
import type { AiAnalysis, ConnectionState, GridStatePayload } from "../../types/grid";

const RISK_COLORS: Record<string, string> = {
  low: "#10B981",
  medium: "#f59e0b",
  high: "#ef4444",
  critical: "#be123c",
};

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

type GlobalHeaderProps = {
  gridState?: GridStatePayload | null;
  aiAnalysis?: AiAnalysis | null;
  statusStage?: string | null;
  connectionState?: ConnectionState;
  lastUpdated?: string | null;
};

export function GlobalHeader({
  gridState,
  aiAnalysis,
  statusStage,
  connectionState = "connecting",
  lastUpdated,
}: GlobalHeaderProps) {
  const temperature = gridState?.temperature;
  const supply = gridState?.supply;
  const demand = gridState?.demand;
  const deficit = demand !== undefined && supply !== undefined ? demand - supply : undefined;
  const riskLevel = aiAnalysis?.risk_level ?? "idle";
  const riskColor = RISK_COLORS[riskLevel.toLowerCase()] ?? "#a855f7";
  const riskLabel = aiAnalysis?.risk_level?.toUpperCase() ?? "IDLE";
  const updatedLabel = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "Waiting for data";
  const stageLabel = statusStage ?? "Standing by for next cycle";
  const connectionLabel = connectionState === "open" ? "Real-time" : connectionState === "connecting" ? "Connecting" : "Disconnected";
  const metrics = [
    {
      icon: Thermometer,
      label: "Ambient Temp",
      value: temperature !== undefined ? temperature.toFixed(1) : "--",
      unit: "°C",
      color: "#F59E0B",
    },
    {
      icon: Zap,
      label: "Total Supply",
      value: supply !== undefined ? Math.round(supply).toString() : "--",
      unit: "MW",
      color: "#10B981",
    },
    {
      icon: Activity,
      label: "Live Demand",
      value: demand !== undefined ? Math.round(demand).toString() : "--",
      unit: "MW",
      color: "#3B82F6",
    },
    {
      icon: ShieldAlert,
      label: "System Deficit",
      value:
        deficit !== undefined
          ? `${deficit >= 0 ? "+" : ""}${deficit.toFixed(1)}`
          : "--",
      unit: "MW",
      color: deficit !== undefined && deficit >= 0 ? "#EF4444" : "#10B981",
      trend: aiAnalysis?.requires_human_approval ? "HITL" : aiAnalysis?.ml_llm_disagreement ? "ML/LLM" : undefined,
    },
  ];

  return (
    <header className="h-32 w-full rounded-[2.5rem] bg-[#16191f]/60 backdrop-blur-3xl border-2 border-white/10 flex items-center justify-between px-10 shadow-2xl overflow-hidden relative group">
      <div className="flex items-center gap-6">
        <div className="w-14 h-14 rounded-2xl bg-emerald-500/20 flex items-center justify-center border-2 border-emerald-500/30 shadow-[0_0_25px_rgba(16,185,129,0.2)]">
          <Globe className="h-8 w-8 text-emerald-400" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tighter leading-none">GRID CONTROL</h1>
          <div className="flex items-center gap-2 mt-2">
            <div
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ backgroundColor: connectionState === "open" ? "#10B981" : connectionState === "connecting" ? "#fbbf24" : "#ef4444" }}
            />
            <span className="text-[11px] font-bold uppercase tracking-[0.4em] text-emerald-500/60">
              {connectionLabel} // All India Grid
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 flex justify-center mx-6">
        <div className="flex bg-black/30 rounded-3xl border border-white/5 shadow-inner">
          {metrics.map((metric) => (
            <HeaderMetric key={metric.label} {...metric} />
          ))}
        </div>
      </div>

      <div className="flex flex-col items-end gap-3 border-l-2 border-white/5 pl-10">
        <div className="flex items-center gap-3 text-sm font-bold">
          <span className="text-xs text-white/40 uppercase tracking-[0.3em]">Pipeline</span>
          <span className="text-white" style={{ color: riskColor }}>
            {riskLabel}
          </span>
        </div>
        <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/30 max-w-[220px] text-right">
          {stageLabel}
        </p>
        <div className="flex items-center gap-3">
          <Clock className="h-5 w-5 text-purple-400" />
          <div className="text-right">
            <p className="text-3xl font-mono font-bold tracking-tight text-white">{updatedLabel}</p>
            <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/30">Last Update</p>
          </div>
        </div>
      </div>
    </header>
  );
}
