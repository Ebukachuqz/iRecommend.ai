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
        <p className="text-label-lg text-primary">Upload data</p>
        <h1 className="mt-2 font-display text-display-md text-text-primary">Upload customer reviews</h1>
        <p className="mt-2 max-w-2xl text-body-md text-text-secondary">
          Map your CSV columns and build behavioural personas for {orgName}. Product catalog upload is available inside the launch simulator.
        </p>
      </header>

      {completeStatus ? (
        <section className="rounded-lg border border-success bg-success-light p-8">
          <CheckCircle2 className="h-9 w-9 text-success" />
          <h2 className="mt-5 font-display text-display-sm text-text-primary">Customer intelligence updated</h2>
          <p className="mt-3 max-w-xl text-body-sm text-text-secondary">
            {completeStatus.personas_generated} personas were generated from{" "}
            {completeStatus.processed_rows} processed rows. Your overview is ready to refresh.
          </p>
          <Button
            render={<Link href="/dashboard" />}
            className="mt-8"
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
