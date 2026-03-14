import IndiaMap from "./components/IndiaMap";
import { GlobalHeader } from "./components/dashboard/global-header";
import { OperatorSidebar } from "./components/dashboard/operator-sidebar";
import { AgentSidebar } from "./components/dashboard/agent-sidebar";
import { PlanDrawer } from "./components/dashboard/plan-drawer";
import { useGridData } from "./hooks/use-grid-data";

export default function PowerGridDashboard() {
  const {
    gridState,
    plans,
    aiAnalysis,
    alerts,
    threadId,
    lastUpdated,
    recommendedPlanId,
    statusStage,
    connectionState,
    loading,
    error,
    applyPlan,
    rejectPlans,
    sendManualOverride,
  } = useGridData();

  return (
    <main className="h-screen w-screen overflow-hidden bg-[#0B0D11] relative font-sans text-slate-200">
      {/* 1. BACKGROUND LAYER: The Map fills everything */}
      <div className="absolute inset-0 z-0">
         <IndiaMap onStateClick={(name: string) => console.log(name)} />
      </div>

      {/* 2. UI LAYER: Floating elements */}
      <div className="relative z-10 h-full w-full pointer-events-none flex flex-col p-6">
        
        {/* Floating Header */}
      <div className="pointer-events-auto mb-6">
        <GlobalHeader
          gridState={gridState}
          aiAnalysis={aiAnalysis}
          statusStage={statusStage}
          connectionState={connectionState}
          lastUpdated={lastUpdated}
        />
      </div>

      {/* Middle Section: Sidebars */}
      <div className="flex-1 flex justify-between min-h-0 mb-6">
        <div className="pointer-events-auto">
          <OperatorSidebar
            aiAnalysis={aiAnalysis}
            plans={plans}
            threadId={threadId}
            lastUpdated={lastUpdated}
            connectionState={connectionState}
            onCommitIntent={() => sendManualOverride("commit_intent")}
            onTriggerManualOverride={(action) => sendManualOverride(action)}
            onRejectPlans={() => rejectPlans("Operator override via UI")}
          />
        </div>
        <div className="pointer-events-auto">
          <AgentSidebar
            aiAnalysis={aiAnalysis}
            alerts={alerts}
            gridState={gridState}
            lastUpdated={lastUpdated}
            loading={loading}
            error={error}
          />
        </div>
      </div>

      {/* Bottom Section: Floating Plan Drawer */}
      <div className="pointer-events-auto flex justify-center">
          <PlanDrawer
            plans={plans}
            aiAnalysis={aiAnalysis}
            recommendedPlanId={recommendedPlanId}
            lastUpdated={lastUpdated}
            loading={loading}
            onApplyPlan={applyPlan}
            onRejectPlans={() => rejectPlans("Operator override via UI")}
          />
        </div>
      </div>
    </main>
  );
}
