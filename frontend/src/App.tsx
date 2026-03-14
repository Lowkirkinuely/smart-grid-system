import IndiaMap from "./components/IndiaMap";
import { GlobalHeader } from "./components/dashboard/global-header";
import { OperatorSidebar } from "./components/dashboard/operator-sidebar";
import { AgentSidebar } from "./components/dashboard/agent-sidebar";
import { PlanDrawer } from "./components/dashboard/plan-drawer";
import { GridProvider } from "./lib/context";

export default function PowerGridDashboard() {
  return (
    <GridProvider>
      <main className="h-screen w-screen overflow-hidden bg-[#0B0D11] relative font-sans text-slate-200">
      {/* 1. BACKGROUND LAYER: The Map fills everything */}
      <div className="absolute inset-0 z-0">
         <IndiaMap />
      </div>

      {/* 2. UI LAYER: Floating elements */}
      <div className="relative z-10 h-full w-full pointer-events-none flex flex-col p-6">
        
        {/* Floating Header */}
        <div className="pointer-events-auto mb-6">
          <GlobalHeader />
        </div>

        {/* Middle Section: Sidebars */}
        <div className="flex-1 flex justify-between min-h-0 mb-6">
          <div className="pointer-events-auto">
            <OperatorSidebar />
          </div>
          <div className="pointer-events-auto">
            <AgentSidebar />
          </div>
        </div>

        {/* Bottom Section: Floating Plan Drawer */}
        <div className="pointer-events-auto flex justify-center">
          <PlanDrawer />
        </div>
      </div>
    </main>
    </GridProvider>
  );
}
