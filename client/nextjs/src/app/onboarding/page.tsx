"use client";

import { useRouter } from "next/navigation";
import { Check, Code2, Loader2, ShoppingBag, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Logo } from "@/components/layout/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  createOrganisation,
  getMyOrganisation,
  updateOrganisationSettings,
} from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

type Step = 1 | 2 | 3;

const markets = [
  { label: "Global", value: "global" },
  { label: "Nigeria", value: "Nigeria" },
  { label: "Kenya", value: "Kenya" },
  { label: "Ghana", value: "Ghana" },
  { label: "South Africa", value: "South Africa" },
  { label: "Other", value: "Other" },
];

function StepIndicator({ currentStep }: { currentStep: Step }) {
  return (
    <div className="flex items-center justify-between">
      {[1, 2, 3].map((step, index) => (
        <div key={step} className="flex flex-1 items-center">
          <div
            className={`flex h-9 w-9 items-center justify-center rounded-full border text-sm font-bold ${
              currentStep >= step
                ? "border-primary bg-primary text-white"
                : "border-border bg-surface text-text-muted"
            }`}
          >
            {currentStep > step ? <Check className="h-4 w-4" /> : step}
          </div>
          {index < 2 && (
            <div
              className={`mx-3 h-px flex-1 ${currentStep > step ? "bg-primary" : "bg-border"}`}
            />
          )}
        </div>
      ))}
    </div>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [businessName, setBusinessName] = useState("");
  const [orgId, setOrgId] = useState<string | null>(null);
  const [selectedMarket, setSelectedMarket] = useState("global");
  const [loading, setLoading] = useState(false);
  const [checkingOrg, setCheckingOrg] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const getAccessToken = useCallback(async () => {
    const supabase = createBrowserClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session) {
      router.replace("/auth/login");
      throw new Error("Login is required to continue onboarding.");
    }
    return session.access_token;
  }, [router]);

  useEffect(() => {
    let mounted = true;
    getAccessToken()
      .then((token) => getMyOrganisation(token))
      .then((result) => {
        if (!mounted) {
          return;
        }
        if (result.organisation) {
          localStorage.setItem("irecommend_org_id", result.organisation.id);
          router.replace("/dashboard");
          router.refresh();
          return;
        }
        setCheckingOrg(false);
      })
      .catch((err) => {
        if (!mounted) {
          return;
        }
        setCheckingOrg(false);
        setError(err instanceof Error ? err.message : "Unable to check organisation setup.");
      });
    return () => {
      mounted = false;
    };
  }, [getAccessToken, router]);

  async function handleBusinessSetup() {
    const name = businessName.trim();
    if (!name) {
      setError("Business name is required.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const token = await getAccessToken();
      const existing = await getMyOrganisation(token);
      if (existing.organisation) {
        localStorage.setItem("irecommend_org_id", existing.organisation.id);
        router.replace("/dashboard");
        router.refresh();
        return;
      }

      const result = await createOrganisation(token, name);
      setOrgId(result.org_id);
      localStorage.setItem("irecommend_org_id", result.org_id);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create organisation.");
    } finally {
      setLoading(false);
    }
  }

  async function handleFinish() {
    setLoading(true);
    setError(null);
    try {
      const token = await getAccessToken();
      let resolvedOrgId = orgId || localStorage.getItem("irecommend_org_id");
      if (!resolvedOrgId) {
        const result = await getMyOrganisation(token);
        resolvedOrgId = result.organisation?.id || null;
      }
      if (!resolvedOrgId) {
        throw new Error("Create your organisation before continuing.");
      }

      await updateOrganisationSettings(token, resolvedOrgId, selectedMarket);
      router.replace("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save market context.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-background px-4 py-8">
      <div className="mx-auto max-w-3xl">
        <Logo />
      </div>

      <section className="mx-auto mt-10 max-w-[600px]">
        <StepIndicator currentStep={step} />

        <div className="command-card mt-8 p-8">
          {checkingOrg ? (
            <div className="flex min-h-64 flex-col items-center justify-center text-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="mt-4 text-sm font-medium text-text-secondary">Checking your organisation setup...</p>
            </div>
          ) : (
            <>
              {step === 1 && (
                <div>
                  <h1 className="font-display text-3xl font-semibold text-text-primary">
                    Tell us about your business
                  </h1>
                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    This is how you&apos;ll appear in iRecommend.
                  </p>

                  <label className="mt-8 block">
                    <span className="text-sm font-semibold text-text-primary">Business name</span>
                    <Input
                      value={businessName}
                      onChange={(event) => setBusinessName(event.target.value)}
                      placeholder="Acme Store"
                      className="violet-focus-ring mt-2 h-11"
                    />
                  </label>

                  <Button
                    type="button"
                    disabled={!businessName.trim() || loading}
                    onClick={() => void handleBusinessSetup()}
                    className="violet-focus-ring mt-8 h-11 w-full bg-primary text-white hover:bg-primary-hover"
                  >
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Continue
                  </Button>
                </div>
              )}

              {step === 2 && (
                <div>
                  <h1 className="font-display text-3xl font-semibold text-text-primary">
                    Connect your customer data
                  </h1>
                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    Choose how to bring in your customer review history.
                  </p>

                  <div className="mt-8 space-y-4">
                    <div className="violet-focus-ring rounded-2xl border border-primary bg-primary-light p-5">
                      <div className="flex items-start gap-4">
                        <div className="rounded-xl bg-surface p-3 text-primary">
                          <Upload className="h-5 w-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h2 className="font-display text-lg font-semibold text-text-primary">Upload CSV</h2>
                            <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-semibold text-white">
                              Selected
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-text-secondary">
                            Upload a CSV of your customer reviews. We&apos;ll walk you through mapping your columns.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="relative cursor-not-allowed rounded-2xl border border-border bg-soft-surface p-5 opacity-70">
                      <span className="absolute right-4 top-4 rounded-full border border-border bg-surface px-2 py-0.5 text-xs font-semibold text-text-muted">
                        Coming soon
                      </span>
                      <div className="flex items-start gap-4">
                        <div className="rounded-xl bg-surface p-3 text-text-muted">
                          <ShoppingBag className="h-5 w-5" />
                        </div>
                        <div>
                          <h2 className="font-display text-lg font-semibold text-text-primary">Connect Shopify</h2>
                          <p className="mt-2 text-sm leading-6 text-text-secondary">
                            Sync your Shopify store reviews and orders.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="relative cursor-not-allowed rounded-2xl border border-border bg-soft-surface p-5 opacity-70">
                      <span className="absolute right-4 top-4 rounded-full border border-border bg-surface px-2 py-0.5 text-xs font-semibold text-text-muted">
                        Coming soon
                      </span>
                      <div className="flex items-start gap-4">
                        <div className="rounded-xl bg-surface p-3 text-text-muted">
                          <Code2 className="h-5 w-5" />
                        </div>
                        <div>
                          <h2 className="font-display text-lg font-semibold text-text-primary">Connect via API</h2>
                          <p className="mt-2 text-sm leading-6 text-text-secondary">
                            For developers who want to send customer intelligence data directly.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <Button
                    type="button"
                    onClick={() => setStep(3)}
                    className="violet-focus-ring mt-8 h-11 w-full bg-primary text-white hover:bg-primary-hover"
                  >
                    Continue
                  </Button>
                </div>
              )}

              {step === 3 && (
                <div>
                  <h1 className="font-display text-3xl font-semibold text-text-primary">
                    Where are your customers?
                  </h1>
                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    This helps iRecommend contextualise your customer behaviour.
                  </p>

                  <div className="mt-8 flex flex-wrap gap-3">
                    {markets.map((market) => (
                      <button
                        key={market.value}
                        type="button"
                        onClick={() => setSelectedMarket(market.value)}
                        className={`violet-focus-ring rounded-full border px-4 py-2 text-sm font-semibold transition ${
                          selectedMarket === market.value
                            ? "border-primary bg-primary-light text-primary"
                            : "border-border bg-surface text-text-secondary hover:text-text-primary"
                        }`}
                      >
                        {market.label}
                      </button>
                    ))}
                  </div>

                  <p className="mt-6 rounded-xl bg-soft-surface px-4 py-3 text-sm leading-6 text-text-secondary">
                    This setting shapes future personalisation features. iRecommend currently operates globally.
                  </p>

                  <Button
                    type="button"
                    disabled={loading}
                    onClick={() => void handleFinish()}
                    className="violet-focus-ring mt-8 h-11 w-full bg-primary text-white hover:bg-primary-hover"
                  >
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Go to your dashboard
                  </Button>
                </div>
              )}

              {error && <p className="mt-6 text-sm font-medium text-error">{error}</p>}
            </>
          )}
        </div>
      </section>
    </main>
  );
}
