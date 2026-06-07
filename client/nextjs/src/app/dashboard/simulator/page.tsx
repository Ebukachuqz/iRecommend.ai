import Link from "next/link";
import { Rocket } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function DashboardSimulatorPage() {
  return (
    <section className="flex min-h-[70vh] items-center justify-center">
      <div className="aurora-panel max-w-3xl p-8 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 text-white">
          <Rocket className="h-7 w-7" />
        </div>
        <h1 className="mt-6 font-display text-3xl font-semibold text-white">
          Product Launch Simulator
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-white/80">
          For now, launch simulations live inside each customer profile. Choose a customer, then test how they may react to a new product.
        </p>
        <Button
          render={<Link href="/dashboard/customers" />}
          className="violet-focus-ring mt-8 bg-white text-primary hover:bg-primary-light"
        >
          Choose a customer
        </Button>
      </div>
    </section>
  );
}
