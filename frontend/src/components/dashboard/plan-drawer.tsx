import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { Sparkles, Shield, DollarSign, Play, ChevronUp, ChevronDown, Check, AlertCircle, Info, X } from "lucide-react";
import { useGrid } from "../../lib/context";

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

function PlanDetailsModal({ plan, isOpen, onClose }: { plan: any; isOpen: boolean; onClose: () => void }) {
  if (!isOpen || !plan) return null;

  const cuts = plan.cuts || [];
  const totalCut = cuts.reduce((sum: number, cut: any) => sum + (cut.power_mw || 0), 0);

  const modal = (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[9999] p-4">
      {/* Modal Container - Smaller and contained */}
      <div className="bg-[#16191f] rounded-[2rem] border-2 border-white/10 shadow-2xl flex flex-col w-full max-w-md max-h-[75vh]">
        
        {/* Fixed Header with Close Button */}
        <div className="flex items-start justify-between gap-4 px-6 py-5 border-b border-white/10 shrink-0">
          <div className="flex items-start gap-3 flex-1">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-white/5 border border-white/10 mt-1">
              <Sparkles className="h-5 w-5 text-purple-400" />
            </div>
            <div className="min-w-0">
              <h3 className="text-lg font-black text-white leading-tight truncate">{plan.name}</h3>
              <p className="text-xs text-white/50 mt-0.5 line-clamp-2">{plan.description || plan.note || "Strategy details"}</p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            className="p-1.5 hover:bg-white/10 rounded-lg transition-colors shrink-0 mt-1"
            aria-label="Close modal"
          >
            <X className="w-5 h-5 text-white/70 hover:text-white" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
          
          {/* Key Metrics - Compact */}
          <div className="grid grid-cols-3 gap-3 bg-white/5 rounded-lg p-3 border border-white/10">
            <div className="text-center">
              <div className="text-xl font-bold text-purple-400">{plan.confidence || 75}%</div>
              <div className="text-[9px] text-white/50 uppercase tracking-widest mt-0.5">Confidence</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-bold text-emerald-400">{plan.power_saved || 0} MW</div>
              <div className="text-[9px] text-white/50 uppercase tracking-widest mt-0.5">Saved</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-bold text-orange-400">{plan.harm_score || 5}/10</div>
              <div className="text-[9px] text-white/50 uppercase tracking-widest mt-0.5">Harm</div>
            </div>
          </div>

          {/* Load Cuts Breakdown */}
          {cuts.length > 0 ? (
            <div>
              <h4 className="text-sm font-bold text-white uppercase tracking-tight mb-2">Cuts</h4>
              <div className="space-y-2">
                {cuts.map((cut: any, idx: number) => (
                  <div key={idx} className="bg-white/5 rounded-lg p-3 border border-white/10">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-bold text-white truncate">{cut.zone || `Zone ${idx + 1}`}</span>
                      <span className="text-sm font-bold text-emerald-400 ml-2">{cut.power_mw || 0} MW</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400"
                          style={{ width: `${totalCut > 0 ? (cut.power_mw / totalCut) * 100 : 0}%` }}
                        />
                      </div>
                      <span className="text-xs text-white/50 w-8 text-right">
                        {totalCut > 0 ? ((cut.power_mw / totalCut) * 100).toFixed(0) : 0}%
                      </span>
                    </div>
                  </div>
                ))}
                <div className="mt-2 pt-2 border-t border-white/10">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-white">Total</span>
                    <span className="text-lg font-bold text-emerald-400">{totalCut.toFixed(1)} MW</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-white/50 text-sm">No load cuts specified</p>
          )}

          {/* Strategy Info */}
          {plan.use_case && (
            <div>
              <h4 className="text-xs font-bold text-white/60 uppercase tracking-widest mb-1">Use Case</h4>
              <p className="text-sm text-white/80">{plan.use_case}</p>
          </div>
        )}

          {/* Recommended For */}
          {plan.recommended_for && (
            <div>
              <h4 className="text-xs font-bold text-white/60 uppercase tracking-widest mb-1.5">Risk Levels</h4>
              <div className="flex flex-wrap gap-1.5">
                {(Array.isArray(plan.recommended_for) ? plan.recommended_for : []).map((level: string) => (
                  <span key={level} className="px-2 py-1 bg-purple-500/20 border border-purple-500/50 rounded-full text-xs font-bold text-purple-300 uppercase">
                    {level}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}

// --- MAIN COMPONENT ---

export function PlanDrawer() {
  const [isExpanded, setIsExpanded] = useState(false);
  const [executingPlan, setExecutingPlan] = useState<string | null>(null);
  const [executedPlans, setExecutedPlans] = useState<Set<string>>(new Set());
  const [selectedPlanForDetails, setSelectedPlanForDetails] = useState<any | null>(null);
  const { gridState, applyPlan } = useGrid();

  useEffect(() => {
    console.log("[PlanDrawer] Plans updated:", gridState.plans.length, "plans");
  }, [gridState.plans]);

  // Map backend plans to UI format
  const displayPlans = gridState.plans.map((plan, idx) => {
    const icons = [Sparkles, Shield, DollarSign];
    const colors = ["#10B981", "#8B5CF6", "#F59E0B"];
    return {
      ...plan,
      name: plan.label || plan.name || `Plan ${idx + 1}`, // FIX: Prefer label from backend
      icon: icons[idx % icons.length],
      color: colors[idx % colors.length],
      harm: plan.harm_score || 5,
      saved: plan.power_saved || 0,
      confidence: plan.confidence || 75,
    };
  });

  const handleExecuteStrategy = async (planId: string, planName: string) => {
    setExecutingPlan(planId);
    console.log(`[PlanDrawer] Executing plan ${planId}: ${planName}`);
    try {
      // FIX: Pass the validated planName to ensure logs aren't "undefined"
      applyPlan(planId, `Operator authorized ${planName}`);
      
      // Wait for execution feedback
      await new Promise(resolve => setTimeout(resolve, 1200));
      
      setExecutedPlans(prev => new Set(prev).add(planId));
      setExecutingPlan(null);
      
      // Show success state for 3 seconds
      setTimeout(() => {
        setExecutedPlans(prev => {
          const updated = new Set(prev);
          updated.delete(planId);
          return updated;
        });
      }, 3000);
    } catch (error) {
      console.error("Plan execution failed:", error);
      setExecutingPlan(null);
    }
  };

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
            {!isExpanded && <p className="text-[10px] text-purple-400 font-bold tracking-widest uppercase mt-1 opacity-70">{displayPlans.length} Candidates Ready for Command</p>}
          </div>
        </div>

        <div className="flex items-center gap-8">
          {!isExpanded && (
            <div className="flex items-center gap-8">
                <div className="flex flex-col items-end justify-center">
                    <span className="text-2xl font-black text-emerald-400 font-mono tracking-tighter leading-none">
                      {gridState.plans.reduce((sum, p) => sum + (p.power_saved || 0), 0).toFixed(0)} MW
                    </span>
                    <span className="text-[9px] font-bold text-emerald-500/40 uppercase tracking-widest leading-none mt-1">Yield Potential</span>
                </div>
                <div className="px-4 py-2 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center justify-center">
                  <span className={`text-[10px] font-black text-purple-400 uppercase tracking-widest ${gridState.isLoading ? 'animate-pulse' : ''}`}>
                      {gridState.isLoading ? 'Analyzing...' : 'Neural Net Active'}
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
          {displayPlans.length > 0 ? (
            displayPlans.map((plan) => (
            <div key={plan.plan_id} className="flex-1 min-w-[320px] bg-white/5 rounded-[2.5rem] p-6 border border-white/10 flex flex-col shadow-2xl justify-between h-full">
              <div>
                <div className="flex items-center justify-between gap-4 mb-3">
                  <div className="flex items-center gap-3 flex-1">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/5 border border-white/10">
                      <plan.icon className="h-5 w-5" style={{ color: plan.color }} />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-xl font-black text-white leading-none mb-1 tracking-tight">{plan.name}</h3>
                      <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest truncate max-w-[180px]">{plan.description || plan.note}</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => setSelectedPlanForDetails(plan)}
                    className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                    title="View plan details"
                  >
                    <Info className="w-5 h-5 text-white/50 hover:text-white" />
                  </button>
                </div>
                
                <div className="flex justify-around mb-4 border-y border-white/5 py-4">
                   <CircularGauge value={plan.confidence} max={100} color={plan.color} label="Confidence" />
                   <CircularGauge value={Math.abs(plan.saved)} max={200} color="#10B981" label="MW Saved" />
                </div>

                <div className="mb-4">
                  <HarmScoreBar score={plan.harm} />
                </div>
              </div>

              <button 
                onClick={() => handleExecuteStrategy(plan.plan_id, plan.name)}
                disabled={executingPlan !== null}
                className="w-full h-14 rounded-xl font-black text-base tracking-[0.2em] text-white transition-all active:scale-95 uppercase shadow-[0_10px_30px_rgba(0,0,0,0.3)] border-b-4 border-black/30 disabled:opacity-50" 
                style={{ 
                  backgroundColor: executedPlans.has(plan.plan_id) ? "#10B981" : (executingPlan === plan.plan_id ? "rgba(0,0,0,0.3)" : plan.color),
                  transition: "all 0.3s ease"
                }}
              >
                <div className="flex items-center justify-center gap-2">
                  {executingPlan === plan.plan_id && (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  {executedPlans.has(plan.plan_id) && (
                    <Check className="w-5 h-5" />
                  )}
                  {executingPlan === plan.plan_id ? "Executing..." : (executedPlans.has(plan.plan_id) ? "Executed" : "Execute Strategy")}
                </div>
              </button>
            </div>
            ))
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <p className="text-white/50 font-bold uppercase tracking-widest mb-2">No plans generated yet</p>
                <p className="text-white/30 text-sm">Submit a grid state or wait for analysis to complete</p>
              </div>
            </div>
          )}
        </div>
      )}
      
      <PlanDetailsModal 
        plan={selectedPlanForDetails} 
        isOpen={!!selectedPlanForDetails} 
        onClose={() => setSelectedPlanForDetails(null)} 
      />
    </div>
  );
}
