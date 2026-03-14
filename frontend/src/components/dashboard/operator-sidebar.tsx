import { Building2, Factory, Home, Send, Shield, Power } from "lucide-react";
import { Slider } from "../ui/slider";
import { Button } from "../ui/button";
import type { AiAnalysis, ConnectionState, GridPlan } from "../../types/grid";

const sliderConfig = [
  { id: "hospital", label: "Hospital Protection", icon: Building2, description: "LIFELINE SERVICES", color: "#10B981" },
  { id: "industrial", label: "Industrial Load", icon: Factory, description: "SECTOR REDUCTION", color: "#F59E0B" },
  { id: "residential", label: "Residential Rotation", icon: Home, description: "GRID BALANCING", color: "#3B82F6" },
];

type PrioritySliderProps = {
  label: string;
  description: string;
  icon: typeof Building2;
  color: string;
  value: number;
  onChange: (value: number) => void;
};

function PrioritySlider({ label, description, icon: Icon, color, value, onChange }: PrioritySliderProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center border-2 border-white/10 shadow-2xl" style={{ backgroundColor: `${color}20` }}>
            <Icon className="h-7 w-7" style={{ color }} />
          </div>
          <div>
            <span className="text-lg font-bold text-white block tracking-tight leading-none">{label}</span>
            <p className="text-xs text-slate-400 font-bold uppercase tracking-[0.3em] opacity-60">{description}</p>
          </div>
        </div>
        <span className="font-mono text-xl font-bold tracking-tighter" style={{ color }}>
          {value}%
        </span>
      </div>
      <Slider
        value={[value]}
        onValueChange={(vals) => onChange(vals[0])}
        max={100}
        step={1}
        className="[&_[data-slot=slider-range]]:bg-emerald-500 [&_[data-slot=slider-thumb]]:h-7 [&_[data-slot=slider-thumb]]:w-7 [&_[data-slot=slider-thumb]]:border-4 [&_[data-slot=slider-thumb]]:border-emerald-500 shadow-2xl cursor-pointer"
      />
    </div>
  );
}

function SnapshotRow({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-2xl bg-white/[0.03] border border-white/5 p-4 space-y-1">
      <p className="text-[9px] font-bold uppercase tracking-[0.3em] text-white/40">{label}</p>
      <p className="text-lg font-black tracking-tight text-white">{value}</p>
      {detail && <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/30">{detail}</p>}
    </div>
  );
}

type OperatorSidebarProps = {
  aiAnalysis?: AiAnalysis | null;
  plans?: GridPlan[];
  threadId?: string | null;
  lastUpdated?: string | null;
  connectionState?: ConnectionState;
  onCommitIntent?: () => void;
  onRejectPlans?: () => void;
  onTriggerManualOverride?: (action: string) => void;
};

import { useMemo, useState } from "react";

export function OperatorSidebar({
  aiAnalysis,
  plans,
  threadId,
  lastUpdated,
  connectionState,
  onCommitIntent,
  onRejectPlans,
  onTriggerManualOverride,
}: OperatorSidebarProps) {
  const planCount = plans?.length ?? 0;
  const threadLabel = threadId ? threadId.slice(-6).toUpperCase() : "—";
  const humanState = aiAnalysis?.requires_human_approval ? "Paused" : "Auto";
  const hitlDetail = aiAnalysis?.requires_human_approval ? "Human review pending" : "Running";
  const mlRisk = aiAnalysis?.ml_risk_level?.toUpperCase() ?? "—";
  const connectionLabel = connectionState ? connectionState.toUpperCase() : "CONNECT";
  const updatedLabel = lastUpdated
    ? `Updated ${new Date(lastUpdated).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
      })}`
    : "Waiting for grid";
  const [sliderValues, setSliderValues] = useState(
    sliderConfig.reduce((acc, slider) => ({ ...acc, [slider.id]: 75 }), {} as Record<string, number>)
  );

  return (
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

      <div className="flex-1 overflow-hidden">
        <div className="bg-[#0d111a]/70 border border-white/5 rounded-[2.5rem] p-5 shadow-[0_10px_40px_rgba(0,0,0,0.6)] h-full flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.4em] text-white/40">Priorities</p>
              <h3 className="text-lg font-black text-white tracking-tight">Human Override</h3>
            </div>
            <span className="text-[9px] font-bold uppercase tracking-[0.2em] text-white/30">Live</span>
          </div>
          <div className="space-y-5 overflow-y-auto pr-1 flex-1 custom-scrollbar">
            {sliderConfig.map((slider) => (
              <PrioritySlider
                key={slider.id}
                label={slider.label}
                description={slider.description}
                icon={slider.icon}
                color={slider.color}
                value={sliderValues[slider.id]}
                onChange={(value) => setSliderValues((prev) => ({ ...prev, [slider.id]: value }))}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        <Button
          className="w-full h-16 bg-emerald-600 hover:bg-emerald-500 text-white text-lg font-bold tracking-widest border-b-4 border-emerald-800"
          onClick={onCommitIntent}
        >
          <Send className="h-6 w-6 mr-3" /> COMMIT INTENT
        </Button>
        <Button
          variant="outline"
          className="w-full h-14 border-emerald-500 text-emerald-400"
          onClick={onRejectPlans}
        >
          REJECT PLANS
        </Button>
        <Button
          variant="ghost"
          className="w-full h-12 text-white/80"
          onClick={() => onTriggerManualOverride?.("increase_protection")}
        >
          Manual override: tighten protection
        </Button>
      </div>

      <div className="mt-8 pt-8 border-t-2 border-white/5 space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <SnapshotRow label="Active Thread" value={threadLabel} detail="Latest ingest" />
          <SnapshotRow label="Plans Ready" value={`${planCount}`} detail="OR-Tools" />
          <SnapshotRow label="HITL" value={humanState} detail={hitlDetail} />
          <SnapshotRow label="ML Risk" value={mlRisk} detail="Model feedback" />
          <SnapshotRow label="Connection" value={connectionLabel} detail="WebSocket" />
          <SnapshotRow label="Last Update" value={updatedLabel} detail="Backend" />
        </div>
      </div>

      <div className="mt-6 flex items-center gap-3 rounded-2xl bg-rose-500/10 border-4 border-rose-500/20 p-4 shadow-2xl">
        <div className="flex flex-col w-full">
          <p className="text-xs font-bold uppercase tracking-[0.3em] text-white/40">Status</p>
          <p className="text-sm font-black text-white tracking-tight">{updatedLabel}</p>
        </div>
        <Power className="h-6 w-6 text-rose-400" />
      </div>
    </aside>
  );
}
