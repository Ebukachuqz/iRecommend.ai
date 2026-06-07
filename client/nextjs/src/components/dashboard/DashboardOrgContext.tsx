"use client";

import { createContext, useContext } from "react";

type DashboardOrgContextValue = {
  orgId: string;
  orgName: string;
  userEmail: string;
};

const DashboardOrgContext = createContext<DashboardOrgContextValue | null>(null);

export function DashboardOrgProvider({
  value,
  children,
}: {
  value: DashboardOrgContextValue;
  children: React.ReactNode;
}) {
  return <DashboardOrgContext.Provider value={value}>{children}</DashboardOrgContext.Provider>;
}

export function useDashboardOrg() {
  const context = useContext(DashboardOrgContext);
  if (!context) {
    throw new Error("useDashboardOrg must be used inside DashboardOrgProvider.");
  }
  return context;
}
