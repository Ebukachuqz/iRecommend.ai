"use client";

import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { getMyOrganisation, type Organisation } from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

export default function DashboardPage() {
  const router = useRouter();
  const [organisation, setOrganisation] = useState<Organisation | null>(null);
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
          Organisation setup complete. The merchant intelligence dashboard will appear here next.
        </p>
      </section>
    </main>
  );
}
