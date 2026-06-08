"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  FileText,
  ImageIcon,
  Loader2,
  RefreshCcw,
  Send,
  Sparkles,
} from "lucide-react";

import { Navbar } from "@/components/layout/Navbar";
import { Stars } from "@/components/dashboard/DashboardUi";
import { PersonaSelector } from "@/components/playground/PersonaSelector";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  DEMO_CATEGORIES,
  checkPrototypeHealth,
  getRecommendations,
  listUnseenProducts,
  refineRecommendations,
  simulateReview,
  type DemoCategory,
  type PersonaSelection,
  type ProductInput,
  type ProductSummary,
  type RecommendationItem,
  type RecommendationResult,
  type SimulationResult,
} from "@/lib/prototype-api";

type PlaygroundTab = "simulation" | "recommendations";

const categoryLabelByValue = Object.fromEntries(
  DEMO_CATEGORIES.map((category) => [category.value, category.label]),
) as Record<DemoCategory, string>;

const defaultProduct: ProductInput = {
  title: "",
  category: "Electronics",
  price: undefined,
  features: [],
  description: "",
};

function createSessionId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `playground_${Date.now()}`;
}

function friendlyError(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function confidencePercent(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return 0;
  }
  const normalized = value > 1 ? value : value * 100;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function evidenceList(value?: unknown) {
  if (Array.isArray(value)) {
    return value.map(String).filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function productOptionKey(product: ProductSummary) {
  return product.parent_asin;
}

function productSummaryToInput(product: ProductSummary, category: DemoCategory): ProductInput {
  return {
    parent_asin: product.parent_asin,
    title: product.title || product.parent_asin,
    category,
    main_category: product.main_category,
    price: product.price ?? undefined,
    average_rating: product.average_rating,
    rating_number: product.rating_number,
    store: product.store,
    features: [],
    description: "",
  };
}

function stringFromUnknown(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function imageUrlFromImageObject(value: unknown): string | null {
  if (!value) {
    return null;
  }
  if (typeof value === "string") {
    return stringFromUnknown(value);
  }
  if (typeof value !== "object") {
    return null;
  }

  const image = value as Record<string, unknown>;
  return (
    stringFromUnknown(image.large) ||
    stringFromUnknown(image.hi_res) ||
    stringFromUnknown(image.thumb) ||
    stringFromUnknown(image.url) ||
    stringFromUnknown(image.src)
  );
}

function recommendationImageUrl(item: RecommendationItem) {
  if (item.image_url) {
    return item.image_url;
  }

  const direct = item.images;
  if (Array.isArray(direct) && direct.length > 0) {
    const main = direct.find(
      (image) =>
        typeof image === "object" &&
        image !== null &&
        (image as Record<string, unknown>).variant === "MAIN",
    );
    return imageUrlFromImageObject(main || direct[0]);
  }

  const nestedImages = item.product?.images || item.metadata?.images;
  if (Array.isArray(nestedImages) && nestedImages.length > 0) {
    const main = nestedImages.find(
      (image) =>
        typeof image === "object" &&
        image !== null &&
        (image as Record<string, unknown>).variant === "MAIN",
    );
    return imageUrlFromImageObject(main || nestedImages[0]);
  }

  return imageUrlFromImageObject(direct);
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="command-card flex flex-col items-center justify-center px-8 py-24 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-0 text-text-muted">
        <FileText className="h-8 w-8" />
      </div>
      <h3 className="mt-5 font-display text-heading-lg text-text-primary">{title}</h3>
      <p className="mt-2 max-w-sm text-body-sm text-text-secondary">{description}</p>
    </div>
  );
}

function TopTabs({
  active,
  onChange,
}: {
  active: PlaygroundTab;
  onChange: (tab: PlaygroundTab) => void;
}) {
  const tabs = [
    {
      id: "simulation" as const,
      label: "Review Simulation",
      kicker: "Task A",
      description: "Predict how a customer may rate and review a product.",
    },
    {
      id: "recommendations" as const,
      label: "Recommendations",
      kicker: "Task B",
      description: "Recommend products using customer behaviour, not just popularity.",
    },
  ];

  return (
    <div className="grid gap-3 rounded-lg border border-border bg-surface-1 p-2 md:grid-cols-2">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`rounded-md px-4 py-4 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
            active === tab.id
              ? "border border-primary bg-primary-light text-primary"
              : "border border-transparent text-text-secondary hover:bg-surface-0 hover:text-text-primary"
          }`}
        >
          <span className="text-label-sm">{tab.kicker}</span>
          <span className="mt-1 block text-body-md font-semibold">{tab.label}</span>
          <span className="mt-1 block text-body-sm">{tab.description}</span>
        </button>
      ))}
    </div>
  );
}

function SimulationResultPanel({
  result,
  onReset,
}: {
  result: SimulationResult;
  onReset: () => void;
}) {
  const rating = Math.max(1, Math.min(5, Number(result.final_predicted_rating || 0)));
  const confidence = confidencePercent(result.confidence);
  const evidence = evidenceList(result.evidence_used);

  return (
    <div className="space-y-5">
      <div className="command-card p-6">
        <p className="text-label-md text-primary">
          Predicted rating
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-4">
          <Stars rating={rating} />
          <p className="metric-number font-display text-metric-2xl text-text-primary">{rating.toFixed(1)} / 5</p>
        </div>
        <p className="mt-3 max-w-xl text-body-sm text-text-secondary">
          This is how the selected customer persona is likely to react to the product details.
        </p>
      </div>

      <div className="command-card p-6">
        <p className="text-body-lg font-semibold text-text-primary">{result.simulated_review_title}</p>
        <p className="mt-3 text-body-sm italic text-text-secondary">
          &quot;{result.simulated_review_text}&quot;
        </p>
      </div>

      <div className="command-card space-y-5 p-6">
        <div>
          <div className="flex items-center justify-between text-body-sm">
            <span className="font-semibold text-text-primary">Confidence</span>
            <span className="font-mono text-mono-md text-primary">{confidence}%</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-0">
            <div className="h-full rounded-full bg-primary" style={{ width: `${confidence}%` }} />
          </div>
        </div>

        <div>
          <p className="text-body-sm font-semibold text-text-primary">Why this rating?</p>
          <p className="mt-2 text-body-sm text-text-secondary">
            {result.reasoning_summary || "The prototype returned a rating without extra reasoning."}
          </p>
        </div>

        {evidence.length > 0 && (
          <details className="rounded-lg border border-border bg-surface-0 px-4 py-3 text-body-sm text-text-secondary">
            <summary className="cursor-pointer font-semibold text-text-primary">Evidence used</summary>
            <ul className="mt-3 list-disc space-y-2 pl-5">
              {evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </details>
        )}
      </div>

      <button
        type="button"
        onClick={onReset}
        className="inline-flex items-center gap-2 text-body-sm font-medium text-primary underline-offset-4 hover:underline"
      >
        <RefreshCcw className="h-4 w-4" />
        Simulate another product
      </button>
    </div>
  );
}

function RecommendationResults({
  result,
  refineText,
  setRefineText,
  refining,
  onRefine,
  conversation,
}: {
  result: RecommendationResult;
  refineText: string;
  setRefineText: (value: string) => void;
  refining: boolean;
  onRefine: () => void;
  conversation: { role: "merchant" | "engine"; text: string }[];
}) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-heading-xl text-text-primary">Recommended for you</h2>
        <p className="mt-1 text-body-sm text-text-secondary">Based on your behavioural persona.</p>
      </div>

      <div className="space-y-4">
        {result.recommendations.map((item, index) => {
          const evidence = evidenceList(item.evidence);
          const imageUrl = recommendationImageUrl(item);
          const category =
            item.category ||
            item.main_category ||
            (typeof item.product?.category === "string" ? item.product.category : null) ||
            result.category;
          return (
            <article key={`${item.parent_asin}-${index}`} className="rounded-lg border border-border bg-surface-1 p-5">
              <div className="flex flex-col gap-4 sm:flex-row">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-body-sm font-medium text-text-inverse">
                  {item.rank || index + 1}
                </div>
                <div className="flex h-28 w-full shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border bg-surface-0 sm:w-28">
                  {imageUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={imageUrl}
                      alt={item.title || item.parent_asin}
                      className="h-full w-full object-contain p-2"
                      loading="lazy"
                    />
                  ) : (
                    <ImageIcon className="h-8 w-8 text-text-muted" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-body-md font-semibold text-text-primary">
                      {item.title || item.parent_asin}
                    </h3>
                    <span className="inline-flex h-5 items-center rounded-full border border-border bg-surface-0 px-2 text-label-sm text-text-secondary">
                      {categoryLabelByValue[category as DemoCategory] || category}
                    </span>
                  </div>
                  <p className="mt-1 font-mono text-mono-sm text-text-muted">{item.parent_asin}</p>

                  <div className="mt-4">
                    <p className="text-label-sm text-text-muted">
                      Why this?
                    </p>
                    <p className="mt-1 text-body-sm italic text-text-secondary">
                      &quot;{item.reason || "The recommender selected this product from the candidate pool."}&quot;
                    </p>
                  </div>

                  {evidence.length > 0 && (
                    <details className="mt-4 rounded-lg border border-border bg-surface-0 px-4 py-3 text-body-sm text-text-secondary">
                      <summary className="cursor-pointer font-semibold text-text-primary">
                        Evidence
                      </summary>
                      <ul className="mt-3 list-disc space-y-2 pl-5">
                        {evidence.map((entry) => (
                          <li key={entry}>{entry}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {result.session_id && (
        <div className="command-card p-5">
          <h3 className="font-display text-heading-md text-text-primary">Refine</h3>
          <p className="mt-1 text-body-sm text-text-secondary">
            Keep the same persona and ask the engine to adjust the result.
          </p>

          {conversation.length > 0 && (
            <div className="mt-4 space-y-2 rounded-lg bg-surface-0 p-3">
              {conversation.map((entry, index) => (
                <p key={`${entry.role}-${index}`} className="text-body-xs text-text-secondary">
                  <span className="font-semibold text-text-primary">
                    {entry.role === "merchant" ? "You" : "Engine"}:
                  </span>{" "}
                  {entry.text}
                </p>
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <Input
              value={refineText}
              onChange={(event) => setRefineText(event.target.value)}
              placeholder="Something cheaper... / Different brand... / More options in X"
            />
            <Button
              type="button"
              variant="outline"
              disabled={!refineText.trim() || refining}
              onClick={onRefine}
              className="shrink-0"
            >
              {refining ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Update
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PlaygroundPage() {
  const [activeTab, setActiveTab] = useState<PlaygroundTab>("simulation");
  const [personaSelection, setPersonaSelection] = useState<PersonaSelection | null>(null);
  const [apiWarning, setApiWarning] = useState<string | null>(null);

  const [product, setProduct] = useState<ProductInput>(defaultProduct);
  const [demoProducts, setDemoProducts] = useState<ProductSummary[]>([]);
  const [selectedProductKey, setSelectedProductKey] = useState("");
  const [maxProductsToLoad, setMaxProductsToLoad] = useState(20);
  const [productsLoading, setProductsLoading] = useState(false);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [featuresText, setFeaturesText] = useState("");
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);

  const [requestText, setRequestText] = useState("");
  const [recommendationLimit, setRecommendationLimit] = useState(5);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [recommendationResult, setRecommendationResult] = useState<RecommendationResult | null>(null);
  const [recommendationSessionId, setRecommendationSessionId] = useState<string | null>(null);
  const [refineText, setRefineText] = useState("");
  const [refining, setRefining] = useState(false);
  const [conversation, setConversation] = useState<{ role: "merchant" | "engine"; text: string }[]>([]);

  useEffect(() => {
    checkPrototypeHealth().catch((error) => {
      setApiWarning(friendlyError(error));
    });
  }, []);

  useEffect(() => {
    if (!personaSelection) {
      setDemoProducts([]);
      setSelectedProductKey("");
      setProductsError(null);
      setProductsLoading(false);
      setProduct(defaultProduct);
      return;
    }

    if (personaSelection.mode !== "demo" || !personaSelection.userId) {
      setDemoProducts([]);
      setSelectedProductKey("");
      setProductsError(null);
      setProductsLoading(false);
      setProduct((current) => ({
        ...current,
        category: personaSelection.category || current.category,
      }));
      return;
    }

    setDemoProducts([]);
    setSelectedProductKey("");
    setProductsError(null);
    setProductsLoading(false);
    setProduct((current) => ({
      ...current,
      title: "",
      category: personaSelection.category,
      parent_asin: undefined,
      main_category: undefined,
    }));
  }, [personaSelection]);

  useEffect(() => {
    if (activeTab === "simulation" && personaSelection?.mode === "cold_start") {
      setPersonaSelection(null);
    }
  }, [activeTab, personaSelection?.mode]);

  const productForSubmit = useMemo<ProductInput>(
    () => ({
      ...product,
      features: featuresText
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
    }),
    [featuresText, product],
  );

  const canSimulate = Boolean(
    personaSelection && personaSelection.mode !== "cold_start" && productForSubmit.title.trim(),
  );
  const canRecommend = Boolean(personaSelection);
  const usesDemoProductDropdown = !personaSelection || personaSelection.mode === "demo";

  async function handleLoadUnseenProducts() {
    if (personaSelection?.mode !== "demo" || !personaSelection.userId) {
      setProductsError("Please select a demo customer first.");
      return;
    }
    setProductsLoading(true);
    setProductsError(null);
    setDemoProducts([]);
    setSelectedProductKey("");
    setProduct((current) => ({
      ...current,
      title: "",
      parent_asin: undefined,
      main_category: undefined,
    }));

    try {
      const products = await listUnseenProducts(personaSelection.userId, maxProductsToLoad);
      setDemoProducts(products);
      if (!products.length) {
        setProductsError("No demo products were returned for this customer.");
      }
    } catch (error) {
      setProductsError(friendlyError(error));
    } finally {
      setProductsLoading(false);
    }
  }

  function handleDemoProductSelection(nextKey: string) {
    setSelectedProductKey(nextKey);
    const selected = demoProducts.find((item) => productOptionKey(item) === nextKey);
    if (!selected || !personaSelection) {
      setProduct((current) => ({
        ...current,
        title: "",
        parent_asin: undefined,
        main_category: undefined,
      }));
      return;
    }
    setProduct(productSummaryToInput(selected, personaSelection.category));
    setFeaturesText("");
  }

  async function handleSimulation() {
    if (!personaSelection || !productForSubmit.title.trim()) {
      return;
    }
    setSimulationLoading(true);
    setSimulationError(null);
    setSimulationResult(null);
    try {
      const result = await simulateReview(personaSelection, productForSubmit);
      setSimulationResult(result);
    } catch (error) {
      setSimulationError(friendlyError(error));
    } finally {
      setSimulationLoading(false);
    }
  }

  async function handleRecommendations() {
    if (!personaSelection) {
      return;
    }
    const sessionId = recommendationSessionId || createSessionId();
    setRecommendationSessionId(sessionId);
    setRecommendationLoading(true);
    setRecommendationError(null);
    try {
      const result = await getRecommendations(personaSelection, requestText, sessionId, recommendationLimit);
      setRecommendationResult({ ...result, session_id: result.session_id || sessionId });
      setConversation([
        {
          role: "merchant",
          text: requestText.trim() || "Use the persona alone.",
        },
        {
          role: "engine",
          text: `Returned ${result.recommendations.length} recommendations.`,
        },
      ]);
    } catch (error) {
      setRecommendationError(friendlyError(error));
    } finally {
      setRecommendationLoading(false);
    }
  }

  async function handleRefine() {
    if (!personaSelection || !recommendationResult?.session_id || !refineText.trim()) {
      return;
    }
    const message = refineText.trim();
    setRefining(true);
    setRecommendationError(null);
    try {
      const result = await refineRecommendations(
        recommendationResult.session_id,
        personaSelection,
        message,
        recommendationLimit,
      );
      setRecommendationResult({ ...result, session_id: result.session_id || recommendationResult.session_id });
      setConversation((current) => [
        ...current,
        { role: "merchant", text: message },
        { role: "engine", text: `Updated with ${result.recommendations.length} recommendations.` },
      ]);
      setRefineText("");
    } catch (error) {
      setRecommendationError(friendlyError(error));
    } finally {
      setRefining(false);
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <Navbar />

      <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="rounded-lg border border-border bg-surface-1 p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-label-lg text-primary">
                Public Playground
              </p>
              <h1 className="mt-3 font-display text-display-md text-text-primary">
                Playground
              </h1>
              <p className="mt-3 max-w-2xl text-body-lg text-text-secondary">
                Experience the iRecommend engine live. Using our demo customer database.
              </p>
              <p className="mt-2 max-w-2xl text-body-sm text-text-secondary">
                Try the intelligence engine on demo data. Sign up later to run it on your own customers.
              </p>
            </div>
            <div className="rounded-lg border border-border bg-surface-1 p-4">
              <div className="flex items-start gap-3">
                <div className="rounded-md bg-primary-light p-2 text-primary">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-body-sm font-semibold text-text-primary">Prototype engine</p>
                  <p className="mt-1 max-w-xs text-body-sm text-text-secondary">
                    No account needed. This page calls the existing FastAPI backend on port 8000.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {apiWarning && (
            <div className="mt-5 rounded-lg border border-warning bg-warning-light px-4 py-3 text-body-sm font-medium text-warning-text">
              {apiWarning}
            </div>
          )}
        </div>

        <div className="mt-8">
          <TopTabs active={activeTab} onChange={setActiveTab} />
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-2">
          <PersonaSelector
            value={personaSelection}
            onChange={setPersonaSelection}
            allowColdStart={activeTab === "recommendations"}
          />

          {activeTab === "simulation" ? (
            <div className="command-card space-y-4 p-5">
              <div>
                <p className="font-display text-heading-md text-text-primary">Product details</p>
                <p className="mt-1 text-body-sm text-text-secondary">
                  {usesDemoProductDropdown
                    ? "Pick a real product from the demo database for this customer."
                    : "Describe a product and predict how this customer may react."}
                </p>
              </div>

              {personaSelection?.mode === "custom" && (
                <p className="rounded-lg bg-surface-0 px-3 py-2 text-body-xs text-text-secondary">
                  Pasted personas use custom product details because there is no demo customer history to query.
                </p>
              )}

              {usesDemoProductDropdown ? (
                <div className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
                    <label className="block">
                      <span className="text-label-sm text-text-muted">
                        Max products to load
                      </span>
                      <Input
                        type="number"
                        min={1}
                        max={100}
                        step={1}
                        value={maxProductsToLoad}
                        onChange={(event) =>
                          setMaxProductsToLoad(
                            Math.max(1, Math.min(100, Number(event.target.value) || 1)),
                          )
                        }
                        className="mt-2"
                      />
                    </label>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!personaSelection || productsLoading}
                      onClick={() => void handleLoadUnseenProducts()}
                      className="h-10"
                    >
                      {productsLoading ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        "Load unseen products"
                      )}
                    </Button>
                  </div>

                  <label className="block">
                    <span className="text-label-sm text-text-muted">
                      Product from demo database*
                    </span>
                    <select
                      value={selectedProductKey}
                      disabled={!personaSelection || productsLoading}
                      onChange={(event) => handleDemoProductSelection(event.target.value)}
                      className="mt-2 h-11 w-full rounded-md border border-border bg-surface-1 px-3 text-body-md text-text-primary outline-none transition-colors hover:border-border-strong focus:border-primary focus:shadow-[0_0_0_3px_var(--color-primary-light)] disabled:cursor-not-allowed disabled:text-text-muted"
                    >
                      <option value="">
                        {!personaSelection
                          ? "Select a demo customer first"
                          : productsLoading
                            ? "Loading products..."
                            : "Select a product"}
                      </option>
                      {demoProducts.map((item) => (
                        <option key={productOptionKey(item)} value={productOptionKey(item)}>
                          {(item.title || item.parent_asin).slice(0, 80)}
                        </option>
                      ))}
                    </select>
                  </label>

                  {!demoProducts.length && !productsError && !productsLoading && (
                    <p className="rounded-lg bg-surface-0 px-3 py-2 text-body-xs text-text-secondary">
                      Click Load unseen products to populate the product list.
                    </p>
                  )}

                  {productsError && <p className="text-body-sm text-error-text">{productsError}</p>}

                  {selectedProductKey && (
                    <div className="rounded-lg border border-border bg-surface-0 p-3 text-body-sm text-text-secondary">
                      <p className="font-semibold text-text-primary">{product.title}</p>
                      <div className="mt-2 grid gap-1 text-xs">
                        <span>ASIN: {product.parent_asin}</span>
                        {product.main_category && <span>Subcategory: {product.main_category}</span>}
                        {product.store && <span>Store: {product.store}</span>}
                        {typeof product.price === "number" && <span>Price: ${product.price.toFixed(2)}</span>}
                        {typeof product.average_rating === "number" && (
                          <span>Average rating: {product.average_rating.toFixed(1)} / 5</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="block">
                    <span className="text-label-sm text-text-muted">
                      Product title*
                    </span>
                    <Input
                      value={product.title}
                      onChange={(event) =>
                        setProduct((current) => ({ ...current, title: event.target.value }))
                      }
                      placeholder="Foam Massage Roller"
                      className="mt-2"
                    />
                  </label>

                  <label className="block">
                    <span className="text-label-sm text-text-muted">
                      Category*
                    </span>
                    <select
                      value={product.category}
                      onChange={(event) =>
                        setProduct((current) => ({ ...current, category: event.target.value as DemoCategory }))
                      }
                      className="mt-2 h-10 w-full rounded-md border border-border bg-surface-1 px-3 text-body-md text-text-primary outline-none transition-colors hover:border-border-strong focus:border-primary focus:shadow-[0_0_0_3px_var(--color-primary-light)]"
                    >
                      {DEMO_CATEGORIES.map((category) => (
                        <option key={category.value} value={category.value}>
                          {category.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="block">
                    <span className="text-label-sm text-text-muted">
                      Price
                    </span>
                    <Input
                      type="number"
                      step="0.01"
                      value={product.price ?? ""}
                      onChange={(event) =>
                        setProduct((current) => ({
                          ...current,
                          price: event.target.value ? Number(event.target.value) : undefined,
                        }))
                      }
                      placeholder="49.99"
                      className="mt-2"
                    />
                  </label>

                  <label className="block">
                    <span className="text-label-sm text-text-muted">
                      Features
                    </span>
                    <Textarea
                      value={featuresText}
                      onChange={(event) => setFeaturesText(event.target.value)}
                      rows={3}
                      placeholder={"EVA foam construction\nHigh-density ridges\nPortable size"}
                      className="mt-2 resize-none"
                    />
                  </label>

                  <label className="block md:col-span-2">
                    <span className="text-label-sm text-text-muted">
                      Description
                    </span>
                    <Textarea
                      value={product.description}
                      onChange={(event) =>
                        setProduct((current) => ({ ...current, description: event.target.value }))
                      }
                      rows={2}
                      className="mt-2 resize-none"
                    />
                  </label>
                </div>
              )}

              <Button
                type="button"
                disabled={!canSimulate || simulationLoading}
                onClick={() => void handleSimulation()}
                className="w-full"
              >
                {simulationLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Thinking...
                  </>
                ) : (
                  "Simulate review"
                )}
              </Button>
            </div>
          ) : (
            <div className="command-card space-y-4 p-5">
              <div>
                <p className="font-display text-heading-md text-text-primary">
                  Your request <span className="text-text-muted">(optional)</span>
                </p>
                <p className="mt-1 text-body-sm text-text-secondary">
                  A request is helpful, but the persona can drive recommendations on its own.
                </p>
              </div>

              <Textarea
                value={requestText}
                onChange={(event) => setRequestText(event.target.value)}
                rows={2}
                placeholder={"What are you looking for? (optional)\nLeave empty - your persona is enough."}
                className="resize-none"
              />

              <label className="block">
                <span className="text-label-sm text-text-muted">
                  Max recommendations
                </span>
                <select
                  value={recommendationLimit}
                  onChange={(event) => setRecommendationLimit(Number(event.target.value))}
                  className="mt-2 h-10 w-full rounded-md border border-border bg-surface-1 px-3 text-body-md text-text-primary outline-none transition-colors hover:border-border-strong focus:border-primary focus:shadow-[0_0_0_3px_var(--color-primary-light)]"
                >
                  {Array.from({ length: 10 }, (_, index) => index + 1).map((limit) => (
                    <option key={limit} value={limit}>
                      {limit}
                    </option>
                  ))}
                </select>
              </label>
              <p className="text-body-xs text-text-muted">A request is not required.</p>

              <Button
                type="button"
                disabled={!canRecommend || recommendationLoading}
                onClick={() => void handleRecommendations()}
                className="w-full"
              >
                {recommendationLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Finding matches...
                  </>
                ) : (
                  "Get recommendations"
                )}
              </Button>
            </div>
          )}
        </div>

        <section className="mt-6">
            {activeTab === "simulation" ? (
              <div>
                {simulationError && (
                  <div className="mb-5 rounded-lg border border-border-error bg-error-light px-4 py-3 text-body-sm font-medium text-error-text">
                    {simulationError}
                  </div>
                )}
                {simulationResult ? (
                  <SimulationResultPanel result={simulationResult} onReset={() => setSimulationResult(null)} />
                ) : (
                  <EmptyState
                    title="Your simulated review will appear here."
                    description="Select a user and enter product details."
                  />
                )}
              </div>
            ) : (
              <div>
                {recommendationError && (
                  <div className="mb-5 rounded-lg border border-border-error bg-error-light px-4 py-3 text-body-sm font-medium text-error-text">
                    {recommendationError}
                  </div>
                )}
                {recommendationResult ? (
                  <RecommendationResults
                    result={recommendationResult}
                    refineText={refineText}
                    setRefineText={setRefineText}
                    refining={refining}
                    onRefine={() => void handleRefine()}
                    conversation={conversation}
                  />
                ) : (
                  <EmptyState
                    title="Recommendations will appear here."
                    description="Select a persona, then let the engine recommend products using customer behaviour."
                  />
                )}
              </div>
            )}
        </section>

        <div className="mt-10 flex items-center justify-center">
          <a
            href="/auth/signup"
            className="inline-flex items-center gap-2 text-body-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            Run this on your own customer reviews
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>
      </section>
    </main>
  );
}
