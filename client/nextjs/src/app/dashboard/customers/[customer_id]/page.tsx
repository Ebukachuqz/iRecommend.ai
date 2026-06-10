"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Check, Loader2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useDashboardOrg } from "@/components/dashboard/DashboardOrgContext";
import { Stars, StrictnessBadge, TruncatedCustomerId } from "@/components/dashboard/DashboardUi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  getDashboardCustomer,
  simulateMerchantCustomer,
  type DashboardCustomerProfile,
  type MerchantSimulationResult,
} from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

function section(persona: Record<string, unknown>, key: string) {
  const value = persona[key];
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function stringList(value: unknown) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function textValue(value: unknown, fallback = "Unknown") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export default function CustomerProfilePage() {
  const params = useParams<{ customer_id: string }>();
  const customerId = decodeURIComponent(params.customer_id);
  const { orgId } = useDashboardOrg();
  const [profile, setProfile] = useState<DashboardCustomerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadProfile() {
      setLoading(true);
      setError(null);
      try {
        const supabase = createBrowserClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) {
          throw new Error("Log in again to view this profile.");
        }
        const nextProfile = await getDashboardCustomer(session.access_token, orgId, customerId);
        if (mounted) {
          setProfile(nextProfile);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Unable to load customer profile.");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    void loadProfile();
    return () => {
      mounted = false;
    };
  }, [customerId, orgId]);

  if (loading) {
    return <div className="skeleton-shimmer h-96 rounded-lg" />;
  }

  if (error || !profile) {
    return (
      <section className="command-card p-8">
        <h1 className="font-display text-display-sm text-text-primary">Profile unavailable</h1>
        <p className="mt-3 text-body-sm text-error-text">{error || "Customer profile not found."}</p>
      </section>
    );
  }

  return <CustomerBriefing profile={profile} orgId={orgId} />;
}

function CustomerBriefing({ profile, orgId }: { profile: DashboardCustomerProfile; orgId: string }) {
  const persona = profile.persona;
  const writing = section(persona, "writing_style");
  const preferences = section(persona, "preferences");
  const rating = section(persona, "rating_behavior");
  const purchase = section(persona, "purchase_behavior");
  const evidence = section(persona, "evidence");
  const avgRating = Number(rating.average_rating || 0);

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <Link href="/dashboard/customers" className="inline-flex items-center gap-2 text-body-sm font-medium text-primary">
        <ArrowLeft className="h-4 w-4" />
        Back to customers
      </Link>

      <header>
        <p className="text-label-lg text-primary">Analyst briefing</p>
        <h1 className="mt-2 font-display text-display-md text-text-primary">
          Customer <TruncatedCustomerId customerId={profile.customer_id} />
        </h1>
        <p className="mt-2 text-body-md text-text-secondary">{profile.review_count} reviews inform this persona.</p>
      </header>

      <section className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          <BriefingCard title="Rating behaviour" subtitle="How this customer scores products.">
            <div className="flex flex-wrap items-center gap-4">
              <Stars rating={avgRating} />
              <span className="metric-number font-display text-metric-lg text-text-primary">{avgRating.toFixed(1)}</span>
              <StrictnessBadge value={String(rating.strictness || "moderate")} />
            </div>
            <p className="mt-4 text-body-sm text-text-secondary">
              {textValue(rating.rating_patterns, "No detailed rating pattern yet.")}
            </p>
          </BriefingCard>

          <BriefingCard title="Buying style" subtitle="What this customer tends to buy and how they choose.">
            <ChipGroup label="Preferred categories" items={stringList(purchase.preferred_categories)} />
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <LabeledValue label="Price sensitivity" value={textValue(purchase.price_sensitivity)} />
              <LabeledValue label="Quality sensitivity" value={textValue(purchase.quality_sensitivity)} />
            </div>
          </BriefingCard>

          <BriefingCard title="Writing style" subtitle="How this customer sounds when giving feedback.">
            <div className="grid gap-3 sm:grid-cols-3">
              <LabeledValue label="Tone" value={textValue(writing.tone)} />
              <LabeledValue label="Length" value={textValue(writing.length)} />
              <LabeledValue label="Formality" value={textValue(writing.formality)} />
            </div>
            <div className="mt-4">
              <ChipGroup label="Vocabulary markers" items={stringList(writing.vocabulary_markers)} />
            </div>
          </BriefingCard>
        </div>

        <div className="space-y-6 lg:col-span-2">
          <BriefingCard title="What they value" subtitle="Signals to preserve in products and messaging.">
            <IconList items={stringList(preferences.what_they_value)} icon="check" />
          </BriefingCard>
          <BriefingCard title="What they complain about" subtitle="Risks to remove before launch.">
            <IconList items={stringList(preferences.common_complaints)} icon="x" />
          </BriefingCard>
          <BriefingCard title="Attributes" subtitle="Product traits that attract or repel this customer.">
            <ChipGroup label="Liked attributes" items={stringList(preferences.liked_attributes)} tone="green" />
            <div className="mt-4">
              <ChipGroup label="Disliked attributes" items={stringList(preferences.disliked_attributes)} tone="red" />
            </div>
          </BriefingCard>
        </div>
      </section>

      <BriefingCard title="Evidence from reviews" subtitle="Examples that support this persona.">
        <details>
          <summary className="cursor-pointer text-body-sm font-medium text-primary">Show review evidence</summary>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <QuoteList title="Positive examples" items={stringList(evidence.positive_examples)} />
            <QuoteList title="Negative examples" items={stringList(evidence.negative_examples)} />
          </div>
        </details>
      </BriefingCard>

      <QuickSimulation orgId={orgId} customerId={profile.customer_id} />

      <BriefingCard title="Raw persona JSON" subtitle="Developer view for debugging and handoff.">
        <details>
          <summary className="cursor-pointer text-body-sm font-medium text-primary">View full JSON</summary>
          <pre className="mt-4 max-h-96 overflow-auto rounded-lg bg-surface-0 p-4 text-mono-sm text-text-secondary">
            {JSON.stringify(persona, null, 2)}
          </pre>
        </details>
      </BriefingCard>
    </div>
  );
}

function BriefingCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="command-card p-6">
      <h2 className="font-display text-heading-xl text-text-primary">{title}</h2>
      <p className="mt-2 text-body-sm text-text-secondary">{subtitle}</p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function LabeledValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-0 p-3">
      <p className="text-label-sm text-text-muted">{label}</p>
      <p className="mt-2 text-body-sm font-semibold capitalize text-text-primary">{value}</p>
    </div>
  );
}

function ChipGroup({ label, items, tone = "violet" }: { label: string; items: string[]; tone?: "violet" | "green" | "red" }) {
  const color =
    tone === "green"
      ? "border-success bg-success-light text-success-text"
      : tone === "red"
        ? "border-error bg-error-light text-error-text"
        : "border-border bg-surface-0 text-text-secondary";
  return (
    <div>
      <p className="text-label-sm text-text-muted">{label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {(items.length ? items : ["No signal yet"]).map((item) => (
          <span key={item} className={`inline-flex h-5 items-center rounded-full border px-2 text-label-sm ${color}`}>
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function IconList({ items, icon }: { items: string[]; icon: "check" | "x" }) {
  const Icon = icon === "check" ? Check : X;
  const color = icon === "check" ? "text-success" : "text-error";
  const safeItems = items.length ? items : ["No signal yet"];
  return (
    <ul className="space-y-3">
      {safeItems.map((item) => (
        <li key={item} className="flex items-start gap-3 text-body-sm text-text-secondary">
          <Icon className={`mt-1 h-4 w-4 shrink-0 ${color}`} />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function QuoteList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="text-body-sm font-semibold text-text-primary">{title}</h3>
      <div className="mt-3 space-y-3">
        {(items.length ? items : ["No review evidence captured yet."]).map((item) => (
          <blockquote key={item} className="rounded-lg border border-border bg-surface-0 p-4 text-body-sm italic text-text-secondary">
            &quot;{item}&quot;
          </blockquote>
        ))}
      </div>
    </div>
  );
}

function QuickSimulation({ orgId, customerId }: { orgId: string; customerId: string }) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [price, setPrice] = useState("");
  const [features, setFeatures] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MerchantSimulationResult | null>(null);

  const featureList = useMemo(
    () => features.split("\n").map((item) => item.trim()).filter(Boolean),
    [features],
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !category.trim()) {
      setError("Product title and category are required.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const supabase = createBrowserClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        throw new Error("Log in again before running a simulation.");
      }
      setResult(
        await simulateMerchantCustomer(session.access_token, orgId, customerId, {
          title: title.trim(),
          category: category.trim(),
          price: price ? Number(price) : undefined,
          features: featureList,
          description: description.trim() || undefined,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to simulate this product.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="command-card p-6">
      <h2 className="font-display text-heading-xl text-text-primary">How would this customer react to a product?</h2>
      <p className="mt-2 text-body-sm text-text-secondary">
        Test customer reactions before investing in inventory.
      </p>
      <form onSubmit={(event) => void handleSubmit(event)} className="mt-6 grid gap-4 lg:grid-cols-2">
        <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Product title" />
        <Input value={category} onChange={(event) => setCategory(event.target.value)} placeholder="Category" />
        <Input value={price} onChange={(event) => setPrice(event.target.value)} placeholder="Price" type="number" step="0.01" />
        <Textarea value={features} onChange={(event) => setFeatures(event.target.value)} placeholder={"Features, one per line"} className="min-h-24" />
        <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description" className="min-h-24 lg:col-span-2" />
        <Button disabled={loading} className="lg:col-span-2">
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Simulate
        </Button>
      </form>
      {error ? <p className="mt-4 text-body-sm text-error-text">{error}</p> : null}
      {result ? (
        <div className="mt-6 rounded-lg border border-border bg-surface-1 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <Stars rating={result.final_predicted_rating} />
            <span className="font-display text-2xl font-semibold text-text-primary">
              {result.final_predicted_rating.toFixed(1)} / 5
            </span>
          </div>
          <h3 className="mt-4 text-body-md font-semibold text-text-primary">{result.simulated_review_title}</h3>
          <p className="mt-2 text-body-sm italic text-text-secondary">&quot;{result.simulated_review_text}&quot;</p>
          {result.reasoning_summary ? (
            <p className="mt-4 rounded-lg bg-surface-0 p-4 text-body-sm text-text-secondary">
              {result.reasoning_summary}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
