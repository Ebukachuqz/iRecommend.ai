import type { Metadata } from "next";

import { SimulatorClient } from "@/app/dashboard/simulator/SimulatorClient";

export const metadata: Metadata = {
  title: "Product Launch Simulator",
};

export default function DashboardSimulatorPage() {
  return <SimulatorClient />;
}
