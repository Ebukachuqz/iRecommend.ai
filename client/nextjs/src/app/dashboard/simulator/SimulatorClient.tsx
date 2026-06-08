"use client";

import { AlertCircle, Check, Download, Loader2, Rocket, Upload, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Stars } from "@/components/dashboard/DashboardUi";
import { useDashboardOrg } from "@/components/dashboard/DashboardOrgContext";
import { ProductCsvUploadFlow } from "@/components/uploads/ProductCsvUploadFlow";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import {
  getMerchantProducts,
  simulateMerchantLaunchBulk,
  type MerchantBulkSimulationResult,
  type MerchantCatalogProduct,
  type MerchantSimulationProduct,
} from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

const categories = ["Electronics", "Health & Household", "Beauty & Personal Care"];

const SAMPLE_RESULT: MerchantBulkSimulationResult = {
  avg_predicted_rating: 4.1,
  pct_4_plus: 0.67,
  pct_3_or_below: 0.33,
  top_praises: ["cleaner air in small rooms", "quiet overnight use", "simple maintenance"],
  top_concerns: ["replacement filter cost", "whether it covers larger rooms", "price sensitivity"],
  interpretation:
    "Customers are likely to respond positively to the compact form factor and practical health benefit, but filter cost may slow conversion. Lead with long-term value, quiet operation, and clear room-size guidance in launch copy.",
  simulations: [
    {
      customer_id: "CUST-1042",
      product_title: "Compact Air Purifier",
      final_predicted_rating: 5,
      simulated_review_title: "Quiet and genuinely useful",
      simulated_review_text:
        "I would give this a high rating if it stays quiet overnight and the filter is easy to replace. The compact size makes it practical for a bedroom or small office.",
      confidence: 0.82,
      reasoning_summary: "This customer values practical health benefits and low-maintenance products.",
      evidence_used: ["values convenience", "praises quiet appliances"],
    },
    {
      customer_id: "CUST-2188",
      product_title: "Compact Air Purifier",
      final_predicted_rating: 4,
      simulated_review_title: "Good, but filter cost matters",
      simulated_review_text:
        "The purifier sounds useful and I like the size, but I would want clear information about replacement filters before buying. If filters are expensive, that would lower the value.",
      confidence: 0.76,
      reasoning_summary: "This customer is value-sensitive and tends to question recurring costs.",
      evidence_used: ["price sensitivity", "mentions maintenance costs"],
    },
    {
      customer_id: "CUST-3307",
      product_title: "Compact Air Purifier",
      final_predicted_rating: 3,
      simulated_review_title: "Might be too small",
      simulated_review_text:
        "It could work for a small room, but I would be skeptical about performance unless the coverage area is clearly proven. The description needs more specifics.",
      confidence: 0.69,
      reasoning_summary: "This customer is strict and looks for proof before rating new products highly.",
      evidence_used: ["strict rating behaviour", "asks for technical details"],
    },
  ],
};

type ResultMode = "empty" | "loading" | "sample" | "live" | "error";

async function getAccessToken() {
  const supabase = createBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    throw new Error("Log in again before running a launch simulation.");
  }
  return session.access_token;
}

function featureList(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function SimulatorClient() {
  const { orgId } = useDashboardOrg();
  const [products, setProducts] = useState<MerchantCatalogProduct[]>([]);
  const [productsLoading, setProductsLoading] = useState(true);
  const [showProductUpload, setShowProductUpload] = useState(false);
  const [productError, setProductError] = useState<string | null>(null);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState(categories[0]);
  const [price, setPrice] = useState("");
  const [features, setFeatures] = useState("");
  const [description, setDescription] = useState("");
  const [scope, setScope] = useState<"sample" | "specific">("sample");
  const [sampleSize, setSampleSize] = useState(3);
  const [customerId, setCustomerId] = useState("");
  const [mode, setMode] = useState<ResultMode>("empty");
  const [result, setResult] = useState<MerchantBulkSimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSampleBanner, setShowSampleBanner] = useState(false);

  const productPayload = useMemo<MerchantSimulationProduct>(
    () => ({
      title: title.trim(),
      category,
      price: price ? Number(price) : undefined,
      features: featureList(features),
      description: description.trim() || undefined,
    }),
    [category, description, features, price, title],
  );

  const loadProducts = useCallback(async () => {
    setProductsLoading(true);
    setProductError(null);
    try {
      const token = await getAccessToken();
      const response = await getMerchantProducts(token, orgId);
      setProducts(response.products);
    } catch (err) {
      setProductError(err instanceof Error ? err.message : "Unable to load your product catalog.");
    } finally {
      setProductsLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  function applyCatalogProduct(productId: string) {
    setSelectedProductId(productId);
    const product = products.find((item) => item.id === productId || item.product_id === productId);
    if (!product) {
      return;
    }
    setTitle(product.product_name);
    setCategory(product.category || categories[0]);
    setPrice(product.price != null ? String(product.price) : "");
    setFeatures((product.features || []).join("\n"));
    setDescription(product.description || "");
  }

  function loadSampleResult() {
    setResult(SAMPLE_RESULT);
    setMode("sample");
    setError(null);
    setShowSampleBanner(true);
    toast.info("Loaded sample launch simulation.");
  }

  async function runLiveSimulation() {
    if (!productPayload.title || !productPayload.category) {
      setError("Product name and category are required.");
      setMode("error");
      return;
    }
    if (scope === "specific" && !customerId.trim()) {
      setError("Enter a customer ID or switch back to sample customers.");
      setMode("error");
      return;
    }

    setMode("loading");
    setError(null);
    setShowSampleBanner(false);
    try {
      const token = await getAccessToken();
      const response = await simulateMerchantLaunchBulk(token, orgId, {
        product: productPayload,
        customer_ids: scope === "specific" ? [customerId.trim()] : null,
        sample_size: sampleSize,
      });
      setResult(response);
      setMode("live");
      toast.success("Live launch simulation complete.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to run the live simulation.";
      setError(message);
      setMode("error");
      toast.error(message);
    }
  }

  const resultDownload = useMemo(() => {
    if (!result) {
      return "#";
    }
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    return URL.createObjectURL(blob);
  }, [result]);

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">Launch intelligence</p>
        <h1 className="mt-2 font-display text-4xl font-semibold text-text-primary">Product Launch Simulator</h1>
        <p className="mt-2 max-w-3xl text-text-secondary">
          Test how your customers would react to a new product before you manufacture a single unit.
        </p>
      </header>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="space-y-6">
          <div className="command-card p-6">
            <h2 className="font-display text-2xl font-semibold text-text-primary">Product details</h2>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Describe the product you want to test, or autofill from your uploaded catalog.
            </p>

            {productsLoading ? (
              <div className="mt-5 h-12 animate-pulse rounded-xl bg-soft-surface" />
            ) : products.length ? (
              <div className="mt-5 space-y-3">
                <label className="block">
                  <span className="text-sm font-semibold text-text-primary">Select from your catalog</span>
                  <select
                    value={selectedProductId}
                    onChange={(event) => applyCatalogProduct(event.target.value)}
                    className="violet-focus-ring mt-2 h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-text-primary outline-none"
                  >
                    <option value="">Choose a catalog product...</option>
                    {products.map((product) => {
                      const id = product.id || product.product_id || product.product_name;
                      return (
                        <option key={id} value={id}>
                          {product.product_name} - {product.category}
                        </option>
                      );
                    })}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => setShowProductUpload((current) => !current)}
                  className="text-sm font-semibold text-primary underline-offset-4 hover:underline"
                >
                  Upload more products
                </button>
              </div>
            ) : (
              <div className="mt-5 rounded-2xl border border-dashed border-primary/30 bg-primary-light/40 p-4">
                <p className="text-sm font-semibold text-text-primary">No catalog uploaded yet</p>
                <p className="mt-1 text-sm leading-6 text-text-secondary">
                  Manual entry works now. Upload a catalog if you want simulator autofill.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowProductUpload((current) => !current)}
                  className="mt-4"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  Upload product catalog
                </Button>
              </div>
            )}

            {productError ? <p className="mt-3 text-sm text-error">{productError}</p> : null}

            <div className="mt-6 grid gap-4">
              <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Wireless Ergonomic Mouse" className="violet-focus-ring h-11" />
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="violet-focus-ring h-11 rounded-lg border border-border bg-surface px-3 text-sm text-text-primary outline-none"
              >
                {categories.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <Input value={price} onChange={(event) => setPrice(event.target.value)} placeholder="49.99" type="number" step="0.01" className="violet-focus-ring h-11" />
              <Textarea value={features} onChange={(event) => setFeatures(event.target.value)} placeholder={"USB-C charging\nErgonomic grip\n6-month battery"} className="violet-focus-ring min-h-32" />
              <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Short product description" className="violet-focus-ring min-h-24" />
            </div>
          </div>

          {showProductUpload ? (
            <div className="command-card p-6">
              <ProductCsvUploadFlow
                orgId={orgId}
                onComplete={() => {
                  setShowProductUpload(false);
                  void loadProducts();
                }}
              />
            </div>
          ) : null}

          <div className="command-card p-6">
            <h2 className="font-display text-2xl font-semibold text-text-primary">Simulation scope</h2>
            <div className="mt-5 grid gap-3">
              <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-border p-4 hover:border-primary/30">
                <input type="radio" checked={scope === "sample"} onChange={() => setScope("sample")} className="mt-1" />
                <span>
                  <span className="block font-semibold text-text-primary">Sample customers</span>
                  <span className="mt-1 block text-sm text-text-secondary">Recommended for live demos. Smaller samples run faster.</span>
                </span>
              </label>
              {scope === "sample" ? (
                <label className="block">
                  <span className="text-sm font-semibold text-text-primary">Sample size</span>
                  <select
                    value={sampleSize}
                    onChange={(event) => setSampleSize(Number(event.target.value))}
                    className="violet-focus-ring mt-2 h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-text-primary outline-none"
                  >
                    {[3, 5, 10].map((size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-border p-4 hover:border-primary/30">
                <input type="radio" checked={scope === "specific"} onChange={() => setScope("specific")} className="mt-1" />
                <span>
                  <span className="block font-semibold text-text-primary">Specific customer</span>
                  <span className="mt-1 block text-sm text-text-secondary">Use a known customer ID for a focused analyst briefing.</span>
                </span>
              </label>
              {scope === "specific" ? (
                <Input value={customerId} onChange={(event) => setCustomerId(event.target.value)} placeholder="Customer ID" className="violet-focus-ring h-11" />
              ) : null}
            </div>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <Button
                type="button"
                disabled={mode === "loading"}
                onClick={() => void runLiveSimulation()}
                className="violet-focus-ring h-11 bg-primary text-white hover:bg-primary-hover"
              >
                {mode === "loading" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
                Run live simulation
              </Button>
              <Button type="button" variant="outline" onClick={loadSampleResult} className="h-11">
                Load sample result
              </Button>
            </div>
            <p className="mt-3 text-xs leading-5 text-text-muted">
              Live simulation uses your real customer personas. Sample result shows a pre-cached demo.
            </p>
          </div>
        </div>

        <ResultsPanel
          mode={mode}
          result={result}
          error={error}
          onRetry={() => void runLiveSimulation()}
          onLoadSample={loadSampleResult}
          showSampleBanner={showSampleBanner}
          onDismissSample={() => setShowSampleBanner(false)}
          downloadHref={resultDownload}
        />
      </section>
    </div>
  );
}

function ResultsPanel({
  mode,
  result,
  error,
  onRetry,
  onLoadSample,
  showSampleBanner,
  onDismissSample,
  downloadHref,
}: {
  mode: ResultMode;
  result: MerchantBulkSimulationResult | null;
  error: string | null;
  onRetry: () => void;
  onLoadSample: () => void;
  showSampleBanner: boolean;
  onDismissSample: () => void;
  downloadHref: string;
}) {
  if (mode === "loading") {
    return (
      <section className="command-card p-6">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <h2 className="font-display text-2xl font-semibold text-text-primary">Simulating customer reactions...</h2>
        </div>
        <p className="mt-2 text-sm text-text-secondary">Running live LLM simulation across selected personas.</p>
        <Progress className="mt-6" value={66} />
        <div className="mt-6 space-y-4">
          {[0, 1, 2].map((item) => (
            <div key={item} className="h-32 animate-pulse rounded-2xl bg-soft-surface" />
          ))}
        </div>
      </section>
    );
  }

  if (mode === "error") {
    return (
      <section className="command-card p-6">
        <div className="flex h-full min-h-[520px] flex-col items-center justify-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-error/10 text-error">
            <AlertCircle className="h-7 w-7" />
          </div>
          <h2 className="mt-5 font-display text-2xl font-semibold text-text-primary">Live simulation could not finish</h2>
          <p className="mt-3 max-w-md text-sm leading-6 text-text-secondary">
            {error || "The simulator hit a temporary issue. Try again with 3 customers, or use the sample result for the demo."}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Button type="button" onClick={onRetry} className="bg-primary text-white hover:bg-primary-hover">
              Try again
            </Button>
            <Button type="button" variant="outline" onClick={onLoadSample}>
              Load sample result instead
            </Button>
          </div>
        </div>
      </section>
    );
  }

  if (!result) {
    return (
      <section className="command-card p-6">
        <div className="flex h-full min-h-[520px] flex-col items-center justify-center text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-primary-light text-primary">
            <Rocket className="h-8 w-8" />
          </div>
          <h2 className="mt-6 font-display text-2xl font-semibold text-text-primary">Results will appear here.</h2>
          <p className="mt-3 max-w-sm text-sm leading-6 text-text-secondary">
            Fill in product details and click Run live simulation, or load the sample result instantly.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-6">
      {mode === "sample" && showSampleBanner ? (
        <div className="flex items-start gap-3 rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <p className="flex-1">
            This is a sample result. Run a live simulation to use your actual customer data.
          </p>
          <button type="button" onClick={onDismissSample} aria-label="Dismiss sample result banner">
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : null}

      <div className="aurora-panel p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/70">Predicted average rating</p>
        <div className="mt-4 flex flex-wrap items-end gap-4">
          <div className="rounded-2xl bg-white/12 px-4 py-3">
            <Stars rating={result.avg_predicted_rating} />
          </div>
          <p className="font-display text-5xl font-semibold text-white">{result.avg_predicted_rating.toFixed(1)}</p>
          <p className="pb-2 text-white/75">Across {result.simulations.length} customer personas</p>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <MetricChip label="Customers likely to rate 4+" value={percent(result.pct_4_plus)} tone="green" />
          <MetricChip label="Customers likely to rate 3 or below" value={percent(result.pct_3_or_below)} tone="amber" />
          <MetricChip label="Most likely reaction" value={result.top_concerns[0] || "No concern detected"} tone="red" />
        </div>
      </div>

      <div className="command-card p-6">
        <h2 className="font-display text-2xl font-semibold text-text-primary">What this means</h2>
        <p className="mt-3 text-sm leading-6 text-text-secondary">{result.interpretation}</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <InsightBox title="Likely praises" items={result.top_praises} icon="check" />
        <InsightBox title="Likely concerns" items={result.top_concerns} icon="x" />
      </div>

      <div className="command-card p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="font-display text-2xl font-semibold text-text-primary">Customer reactions</h2>
            <p className="mt-2 text-sm text-text-secondary">A sample of predicted reviews from your personas.</p>
          </div>
          <a
            href={downloadHref}
            download="irecommend-launch-simulation.json"
            className="inline-flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline"
          >
            <Download className="h-4 w-4" />
            Download results
          </a>
        </div>
        <div className="mt-6 space-y-4">
          {result.simulations.map((simulation) => (
            <ReactionCard key={simulation.customer_id} simulation={simulation} />
          ))}
        </div>
      </div>
    </section>
  );
}

function MetricChip({ label, value, tone }: { label: string; value: string; tone: "green" | "amber" | "red" }) {
  const color =
    tone === "green"
      ? "bg-success/15 text-white"
      : tone === "amber"
        ? "bg-warning/20 text-white"
        : "bg-error/20 text-white";
  return (
    <div className={`rounded-2xl border border-white/15 p-3 ${color}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/70">{label}</p>
      <p className="mt-2 text-lg font-semibold">{value}</p>
    </div>
  );
}

function InsightBox({ title, items, icon }: { title: string; items: string[]; icon: "check" | "x" }) {
  const Icon = icon === "check" ? Check : X;
  const color = icon === "check" ? "text-success" : "text-error";
  return (
    <div className="command-card p-5">
      <h3 className="font-display text-xl font-semibold text-text-primary">{title}</h3>
      <ul className="mt-4 space-y-3">
        {(items.length ? items : ["No signal detected"]).slice(0, 3).map((item) => (
          <li key={item} className="flex items-start gap-3 text-sm leading-6 text-text-secondary">
            <Icon className={`mt-1 h-4 w-4 shrink-0 ${color}`} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ReactionCard({ simulation }: { simulation: MerchantBulkSimulationResult["simulations"][number] }) {
  const [expanded, setExpanded] = useState(false);
  const text = simulation.simulated_review_text || "";
  const shouldClamp = text.length > 180;
  return (
    <article className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.12em] text-primary">
            {simulation.customer_id.slice(0, 8)}
          </p>
          <h3 className="mt-2 font-semibold text-text-primary">{simulation.simulated_review_title}</h3>
        </div>
        <div className="text-right">
          <Stars rating={simulation.final_predicted_rating} />
          <p className="mt-1 text-xs font-semibold text-text-secondary">
            Confidence {Math.round((simulation.confidence || 0) * 100)}%
          </p>
        </div>
      </div>
      <p className="mt-4 text-sm italic leading-6 text-text-secondary">
        &quot;{expanded || !shouldClamp ? text : `${text.slice(0, 180)}...`}&quot;
      </p>
      {shouldClamp ? (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="mt-3 text-sm font-semibold text-primary underline-offset-4 hover:underline"
        >
          {expanded ? "Show less" : "Expand review"}
        </button>
      ) : null}
    </article>
  );
}
