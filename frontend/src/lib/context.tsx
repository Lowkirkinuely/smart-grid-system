/**
 * Grid Context Provider for sharing state across components
 */

import React, { createContext, useContext } from "react";
import { useGridState, GridUIState } from "./hooks";

interface GridContextType {
  gridState: GridUIState;
  sendMessage: (message: any) => void;
  applyPlan: (planId: string, note?: string) => void;
}

const GridContext = createContext<GridContextType | null>(null);

export function GridProvider({ children }: { children: React.ReactNode }) {
  const { gridState, sendMessage, applyPlan } = useGridState();

  return (
    <GridContext.Provider value={{ gridState, sendMessage, applyPlan }}>
      {children}
    </GridContext.Provider>
  );
}

/**
 * Hook to use grid context
 */
export function useGrid() {
  const context = useContext(GridContext);
  if (!context) {
    throw new Error("useGrid must be used within GridProvider");
  }
  return context;
}
