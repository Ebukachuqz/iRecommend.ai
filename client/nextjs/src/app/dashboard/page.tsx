"use client";

import { useRouter } from "next/navigation";
import { Loader2, Upload } from "lucide-react";
import { useEffect, useState } from "react";

import { ReviewCsvUploadFlow } from "@/components/uploads/ReviewCsvUploadFlow";
import { Button } from "@/components/ui/button";
import {
  getMyOrganisation,
  getOrganisationSummary,
  type Organisation,
  type OrganisationSummary,
} from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

export default function DashboardPage() {
  const router = useRouter();
  const [organisation, setOrganisation] = useState<Organisation | null>(null);
  const [summary, setSummary] = useState<OrganisationSummary | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function verifyOrganisation() {
      setChecking(true);
      setError(null);
      const supabase = createBrowserClient();

      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!mounted) {
        return;
      }

      if (!session) {
        router.replace("/auth/login");
        return;
      }

      try {
        const result = await getMyOrganisation(session.access_token);
        if (!mounted) {
          return;
        }

        if (!result.organisation) {
          router.replace("/onboarding");
          return;
        }

        setOrganisation(result.organisation);
        const nextSummary = await getOrganisationSummary(session.access_token, result.organisation.id);
        if (!mounted) {
          return;
        }
        setSummary(nextSummary);
      } catch (err) {
        if (!mounted) {
          return;
        }
        setError(err instanceof Error ? err.message : "Unable to verify organisation setup.");
      } finally {
        if (mounted) {
          setChecking(false);
        }
      }
    }

    void verifyOrganisation();

    return () => {
      mounted = false;
    };
  }, [router]);

  if (checking) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
        <section className="command-card max-w-xl p-8 text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
          <p className="mt-4 text-sm font-medium text-text-secondary">Checking organisation setup...</p>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
        <section className="command-card max-w-xl p-8 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-error text-lg font-bold text-white">
            !
          </div>
          <h1 className="mt-6 font-display text-3xl font-semibold text-text-primary">
            Could not verify your organisation.
          </h1>
          <p className="mt-3 text-sm leading-6 text-error">{error}</p>
        </section>
      </main>
    );
  }

  if (showUpload && organisation) {
    return (
      <main className="min-h-screen bg-background px-4 py-12">
        <section className="mx-auto max-w-3xl">
          <button
            type="button"
            onClick={() => setShowUpload(false)}
            className="text-sm font-semibold text-primary underline-offset-4 hover:underline"
          >
            Back to dashboard
          </button>
          <div className="mt-6 command-card p-8">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              Customer intelligence setup
            </p>
            <h1 className="mt-3 font-display text-3xl font-semibold text-text-primary">
              Upload customer reviews
            </h1>
            <p className="mt-3 text-sm leading-6 text-text-secondary">
              Map your CSV columns and build behavioural personas for {organisation.name}.
            </p>
            <div className="mt-8">
              <ReviewCsvUploadFlow
                orgId={organisation.id}
                onComplete={async () => {
                  const supabase = createBrowserClient();
                  const {
                    data: { session },
                  } = await supabase.auth.getSession();
                  if (session) {
                    setSummary(await getOrganisationSummary(session.access_token, organisation.id));
                  }
                }}
              />
            </div>
          </div>
        </section>
      </main>
    );
  }

  if ((summary?.persona_count || 0) === 0) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
        <section className="command-card max-w-2xl p-8 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary-light text-primary">
            <Upload className="h-6 w-6" />
          </div>
          <p className="mt-6 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
            {organisation?.name || "Organisation"} workspace
          </p>
          <h1 className="mt-3 font-display text-3xl font-semibold text-text-primary">
            Upload your customer reviews CSV to build your first personas.
          </h1>
          <p className="mt-3 text-sm leading-6 text-text-secondary">
            iRecommend needs review history before it can explain why customers buy, complain, and recommend products.
          </p>
          <Button
            type="button"
            onClick={() => setShowUpload(true)}
            className="violet-focus-ring mt-8 bg-primary text-white hover:bg-primary-hover"
          >
            <Upload className="mr-2 h-4 w-4" />
            Upload customer reviews
          </Button>
        </section>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <section className="command-card max-w-xl p-8 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-lg font-bold text-white">
          i
        </div>
        <p className="mt-6 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
          {organisation?.name || "Organisation"} setup complete
        </p>
        <h1 className="mt-3 font-display text-3xl font-semibold text-text-primary">
          Dashboard coming in the next dashboard build.
        </h1>
        <p className="mt-3 text-sm leading-6 text-text-secondary">
          Organisation setup complete. You have {summary?.persona_count || 0} personas from{" "}
          {summary?.review_count || 0} reviews. The merchant intelligence dashboard will appear here next.
        </p>
      </section>
    </main>
  );
}
