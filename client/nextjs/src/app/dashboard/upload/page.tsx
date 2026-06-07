"use client";

import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { useState } from "react";

import { useDashboardOrg } from "@/components/dashboard/DashboardOrgContext";
import { ReviewCsvUploadFlow } from "@/components/uploads/ReviewCsvUploadFlow";
import { Button } from "@/components/ui/button";
import type { UploadStatus } from "@/lib/saas-api";

export default function DashboardUploadPage() {
  const { orgId, orgName } = useDashboardOrg();
  const [completeStatus, setCompleteStatus] = useState<UploadStatus | null>(null);

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">Upload data</p>
        <h1 className="mt-2 font-display text-4xl font-semibold text-text-primary">Upload customer reviews</h1>
        <p className="mt-2 max-w-2xl text-text-secondary">
          Map your CSV columns and build behavioural personas for {orgName}. Product catalog upload comes later.
        </p>
      </header>

      {completeStatus ? (
        <section className="aurora-panel p-8">
          <CheckCircle2 className="h-9 w-9 text-white" />
          <h2 className="mt-5 font-display text-3xl font-semibold text-white">Customer intelligence updated</h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-white/80">
            {completeStatus.personas_generated} personas were generated from{" "}
            {completeStatus.processed_rows} processed rows. Your overview is ready to refresh.
          </p>
          <Button
            render={<Link href="/dashboard" />}
            className="violet-focus-ring mt-8 bg-white text-primary hover:bg-primary-light"
          >
            View dashboard
          </Button>
        </section>
      ) : (
        <section className="command-card p-8">
          <ReviewCsvUploadFlow orgId={orgId} onComplete={setCompleteStatus} />
        </section>
      )}
    </div>
  );
}
