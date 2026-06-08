"use client";

import { useRouter } from "next/navigation";
import { Check, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Logo } from "@/components/layout/Navbar";
import { ProductCsvUploadFlow } from "@/components/uploads/ProductCsvUploadFlow";
import { ReviewCsvUploadFlow } from "@/components/uploads/ReviewCsvUploadFlow";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  createOrganisation,
  getMyOrganisation,
  updateOrganisationSettings,
} from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

type Step = 1 | 2 | 3 | 4;

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
      {[1, 2, 3, 4].map((step, index) => (
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
          {index < 3 && (
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
  const [reviewsUploaded, setReviewsUploaded] = useState(false);
  const [productsUploaded, setProductsUploaded] = useState(false);
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

  async function handleMarketContext() {
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
      setStep(4);
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
                    Upload your customer reviews
                  </h1>
                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    Tell us what your CSV columns mean. We&apos;ll turn those reviews into customer personas.
                  </p>

                  <div className="mt-8">
                    {orgId ? (
                      <ReviewCsvUploadFlow
                        orgId={orgId}
                        onComplete={() => setReviewsUploaded(true)}
                      />
                    ) : (
                      <p className="rounded-xl border border-error/30 bg-error/5 p-4 text-sm text-error">
                        Create your organisation before uploading reviews.
                      </p>
                    )}
                  </div>

                  <Button
                    type="button"
                    disabled={!reviewsUploaded}
                    onClick={() => setStep(3)}
                    className="violet-focus-ring mt-8 h-11 w-full bg-primary text-white hover:bg-primary-hover"
                  >
                    Continue to market context
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
                    onClick={() => void handleMarketContext()}
                    className="violet-focus-ring mt-8 h-11 w-full bg-primary text-white hover:bg-primary-hover"
                  >
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Continue to product catalog
                  </Button>
                </div>
              )}

              {step === 4 && (
                <div>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h1 className="font-display text-3xl font-semibold text-text-primary">
                        Add your product catalog
                      </h1>
                      <p className="mt-2 text-sm leading-6 text-text-secondary">
                        Optional: upload your products so the launch simulator can reference them later.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        router.replace("/dashboard");
                        router.refresh();
                      }}
                      className="text-sm font-semibold text-text-muted underline-offset-4 hover:text-primary hover:underline"
                    >
                      Skip for now
                    </button>
                  </div>

                  <div className="mt-8">
                    {orgId ? (
                      <ProductCsvUploadFlow orgId={orgId} onComplete={() => setProductsUploaded(true)} />
                    ) : (
                      <p className="rounded-xl border border-error/30 bg-error/5 p-4 text-sm text-error">
                        Create your organisation before uploading products.
                      </p>
                    )}
                  </div>

                  <Button
                    type="button"
                    disabled={!productsUploaded}
                    onClick={() => {
                      router.replace("/dashboard");
                      router.refresh();
                    }}
                    className="violet-focus-ring mt-8 h-11 w-full bg-primary text-white hover:bg-primary-hover"
                  >
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
