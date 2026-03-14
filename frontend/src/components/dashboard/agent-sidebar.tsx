import { useMemo } from "react";
import { BrainCircuit, Activity, Zap, CloudLightning, ShieldCheck } from "lucide-react";
import type { AiAnalysis, GridAlert, GridStatePayload } from "../../types/grid";

type LogEntry = {
  time: string;
  tag: string;
  msg: string;
  color?: string;
};

type AgentSidebarProps = {
  aiAnalysis?: AiAnalysis | null;
  alerts?: GridAlert[];
  gridState?: GridStatePayload | null;
  lastUpdated?: string | null;
  loading?: boolean;
  error?: string | null;
};

export function AgentSidebar({ aiAnalysis, alerts = [], gridState, lastUpdated, loading, error }: AgentSidebarProps) {
  const supply = gridState?.supply ?? 0;
  const demand = gridState?.demand ?? 0;
  const gridHealth = demand > 0 ? Math.min(100, Math.round((supply / demand) * 100)) : 65;
  const stress = supply > 0 ? Math.min(100, Math.round((demand / supply) * 100)) : 80;
  const riskMapping: Record<string, number> = {
    low: 35,
    medium: 60,
    high: 85,
    critical: 98,
  };
  const riskLevel = aiAnalysis?.risk_level?.toLowerCase() ?? "low";
  const riskStatus = riskMapping[riskLevel] ?? 45;
  const sensors = aiAnalysis?.anomaly_detected ? 58 : 96;
  const agents = [
    { id: "grid", name: "GRID", icon: Activity, status: gridHealth, color: "#8B5CF6" },
    { id: "demand", name: "DEMAND", icon: Zap, status: stress, color: "#F59E0B" },
    { id: "disaster", name: "RISK", icon: CloudLightning, status: riskStatus, color: "#EF4444" },
    { id: "priority", name: "SENSORS", icon: ShieldCheck, status: sensors, color: "#10B981" },
  ];

  const logEntries = useMemo(() => {
    const entries: LogEntry[] = [];

    alerts.forEach((alert) => {
      entries.push({
        time: new Date(alert.timestamp).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
        tag: alert.alert_type,
        msg: alert.message,
        color: alert.severity === "critical" ? "#f97316" : alert.severity === "high" ? "#ef4444" : "#10b981",
      });
    });

    aiAnalysis?.recommendations?.slice(0, 3).forEach((recommendation) => {
      entries.push({
        time: lastUpdated
          ? new Date(lastUpdated).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
          : "--",
        tag: "Analysis",
        msg: recommendation,
        color: "#a855f7",
      });
    });

    if (aiAnalysis?.requires_human_approval) {
      entries.unshift({
        time: "NOW",
        tag: "HITL",
        msg: "Waiting for operator confirmation",
        color: "#f97316",
      });
    }

    if (entries.length === 0) {
      entries.push({
        time: "—",
        tag: loading ? "Pipeline" : error ? "Error" : "Agent",
        msg: loading ? "Awaiting grid telemetry..." : error ?? "AI agents are online",
      });
    }

    return entries.slice(0, 7);
  }, [alerts, aiAnalysis, lastUpdated, loading, error]);

  const panelStatus = aiAnalysis?.ml_llm_disagreement ? "ML/LLM mismatch" : "Agents synchronized";

  return (
    <aside className="w-[540px] rounded-[2.5rem] bg-[#16191f]/60 backdrop-blur-3xl border-2 border-white/10 p-10 flex flex-col shadow-2xl h-full">
      <div className="flex items-center justify-between mb-8 pb-6 border-b border-white/5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center border border-purple-500/20 shadow-[0_0_20px_rgba(139,92,246,0.15)]">
            <BrainCircuit className="h-7 w-7 text-purple-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white tracking-tight uppercase leading-none">AGENT NETWORK</h2>
            <p className="text-[11px] text-purple-500/50 font-bold uppercase tracking-[0.3em] mt-1.5">AI Intelligence Layer</p>
          </div>
        </div>
        <div className="flex items-center gap-3 px-4 py-1.5 rounded-full bg-emerald-500/5 border border-emerald-500/10">
          <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_8px_#10b981]" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-400">{panelStatus}</span>
        </div>
      </div>

      <div className="flex justify-between items-center gap-2 mb-10 px-4">
        {agents.map((agent) => (
          <div key={agent.id} className="flex flex-col items-center gap-2 flex-1">
            <div className="relative group">
              <div className="absolute -inset-1 rounded-full opacity-10" style={{ backgroundColor: agent.color }} />
              <div className="relative w-12 h-12 rounded-full flex items-center justify-center border border-white/10 bg-[#16191f] shadow-xl">
                <agent.icon className="h-6 w-6" style={{ color: agent.color }} />
              </div>
              <div className="absolute -bottom-1 -right-1 bg-white text-black text-[9px] font-bold px-1.5 py-0.5 rounded shadow-lg border border-black/5">
                {agent.status}%
              </div>
            </div>
            <span className="text-[9px] font-bold uppercase tracking-[0.2em] text-white/30">{agent.name}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[11px] font-bold uppercase tracking-[0.5em] text-white/20 ml-2">Live Reasoning Log</h3>
        <div className="flex gap-2 mr-2 opacity-30">
          <div className="w-2 h-2 rounded-full bg-white" />
          <div className="w-2 h-2 rounded-full bg-white" />
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
        </div>
      </div>

      <div className="flex-1 bg-black/40 rounded-[2.5rem] border border-white/5 p-8 overflow-hidden relative group shadow-inner min-h-0">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/30 pointer-events-none" />
        <div className="h-full overflow-y-auto custom-scrollbar space-y-8 pr-4">
          {logEntries.map((log, i) => (
            <div key={`${log.tag}-${i}`} className="flex gap-5 font-mono text-[18px] leading-relaxed border-l-2 border-white/5 pl-6 transition-all hover:border-purple-500/30 hover:bg-white/[0.01] py-1 rounded-r-xl">
              <span className="text-slate-600 shrink-0 font-bold tracking-tighter text-sm mt-1">[{log.time}]</span>
              <p className="tracking-tight">
                <span className="font-bold uppercase mr-4" style={{ color: log.color ?? "#8B5CF6" }}>
                  {log.tag}:
                </span>
                <span className="text-slate-200 font-medium">{log.msg}</span>
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-8 flex items-center justify-around py-5 rounded-3xl bg-white/[0.02] border border-white/5 shadow-lg">
        <div className="text-center">
          <p className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em] mb-1.5">Latency</p>
          <p className="text-lg font-mono font-bold text-emerald-400">{loading ? "--" : "12ms"}</p>
        </div>
        <div className="w-[1px] h-10 bg-white/5" />
        <div className="text-center">
          <p className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em] mb-1.5">Accuracy</p>
          <p className="text-lg font-mono font-bold text-purple-400">99.2%</p>
        </div>
        <div className="w-[1px] h-10 bg-white/5" />
        <div className="text-center">
          <p className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em] mb-1.5">Uptime</p>
          <p className="text-lg font-mono font-bold text-blue-400">99.9%</p>
        </div>
      </div>
    </aside>
  );
}
