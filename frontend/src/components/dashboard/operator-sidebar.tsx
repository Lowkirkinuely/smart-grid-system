import { useState } from "react";
import { Slider } from "../ui/slider";
import { Button } from "../ui/button";
import { Building2, Factory, Home, Send, Shield, Power } from "lucide-react";
import { useGrid } from "../../lib/context";

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
  const [hospitalProtection, setHospitalProtection] = useState(95);
  const [industrialShedding, setIndustrialShedding] = useState(40);
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

      <div className="flex-1 space-y-8 overflow-auto custom-scrollbar pr-3">
        <PrioritySlider label="Hospital Protection" icon={Building2} value={hospitalProtection} onChange={setHospitalProtection} description="LIFELINE SERVICES" color="#10B981" />
        <PrioritySlider label="Industrial Load" icon={Factory} value={industrialShedding} onChange={setIndustrialShedding} description="SECTOR REDUCTION" color="#F59E0B" />
        <PrioritySlider label="Residential Rotation" icon={Home} value={residentialRotation} onChange={setResidentialRotation} description="GRID BALANCING" color="#3B82F6" />
        
        <div className="pt-8 border-t-2 border-white/5">
          <Button 
            onClick={handleCommitIntent}
            disabled={isLoading}
            className="w-full h-16 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-700 text-white text-lg font-bold tracking-widest border-b-4 border-emerald-800"
          >
            <Send className="h-6 w-6 mr-3" /> 
            {isLoading ? "SUBMITTING..." : "COMMIT INTENT"}
          </Button>
        </div>
      </div>

      <div className="mt-8 pt-8 border-t-2 border-white/5">
        <button className="w-full h-20 rounded-2xl bg-rose-500/10 border-4 border-rose-500/20 hover:border-rose-500/80 transition-all group relative overflow-hidden shadow-2xl">
          <div className="relative flex items-center justify-center gap-4 text-rose-500">
            <Power className="h-6 w-6" />
            <span className="text-xl font-bold tracking-[0.15em] uppercase">EMERGENCY CUT</span>
          </div>
        </button>
      </div>
    </aside>
  );
}
