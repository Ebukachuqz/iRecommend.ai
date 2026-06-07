export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export const DEMO_CATEGORIES = [
  { value: "Electronics", label: "Electronics" },
  { value: "Health_and_Household", label: "Health & Household" },
  { value: "Beauty_and_Personal_Care", label: "Beauty & Personal Care" },
] as const;

export type DemoCategory = (typeof DEMO_CATEGORIES)[number]["value"];

export type PersonaRow = {
  user_id: string;
  category: string;
  persona?: Record<string, unknown>;
  review_count?: number | null;
  average_rating?: number | null;
  source_review_ids?: string[];
  persona_version?: string | null;
  model_name?: string | null;
  prompt_version?: string | null;
};

export type UserSummary = {
  user_id: string;
  category: string;
  review_count?: number | null;
  average_rating?: number | null;
  persona_version?: string | null;
};

export type PersonaSelection = {
  mode: "demo" | "custom";
  userId?: string;
  category: DemoCategory;
  persona: Record<string, unknown> | string;
  personaRow?: PersonaRow;
};

export type ProductInput = {
  parent_asin?: string;
  title: string;
  category: DemoCategory;
  main_category?: string | null;
  price?: number;
  features?: string[];
  description?: string;
  average_rating?: number | null;
  rating_number?: number | null;
  store?: string | null;
};

export type ProductSummary = {
  parent_asin: string;
  title?: string | null;
  main_category?: string | null;
  price?: number | null;
  average_rating?: number | null;
  rating_number?: number | null;
  store?: string | null;
};

export type SimulationResult = {
  product_title?: string | null;
  final_predicted_rating: number;
  simulated_review_title: string;
  simulated_review_text: string;
  confidence?: number | null;
  reasoning_summary?: string | null;
  evidence_used?: string[];
};

export type RecommendationItem = {
  parent_asin: string;
  rank: number;
  title?: string | null;
  reason: string;
  confidence?: number | null;
  evidence?: string[];
  score_breakdown?: Record<string, unknown>;
};

export type RecommendationResult = {
  user_id?: string | null;
  category: string;
  request?: string | null;
  recommendations: RecommendationItem[];
  candidate_count: number;
  session_id?: string | null;
};

class PrototypeApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "PrototypeApiError";
    this.status = status;
  }
}

function offlineMessage() {
  return "Prototype API is offline. Start the FastAPI backend on port 8000.";
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    });
  } catch {
    throw new PrototypeApiError(offlineMessage());
  }

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : typeof payload === "string"
          ? payload
          : "API request failed.";
    throw new PrototypeApiError(
      response.status >= 500 && detail.includes("<html") ? offlineMessage() : detail,
      response.status,
    );
  }

  return payload as T;
}

export async function checkPrototypeHealth() {
  return requestJson<{ status: string; service: string }>("/health");
}

export async function listDemoUsers(limit = 30): Promise<UserSummary[]> {
  const batches = await Promise.all(
    DEMO_CATEGORIES.map((category) =>
      requestJson<UserSummary[]>(
        `/users?category=${encodeURIComponent(category.value)}&limit=${limit}`,
      ).catch(() => []),
    ),
  );
  return batches.flat();
}

export async function getPersona(userId: string, category: string): Promise<PersonaRow> {
  return requestJson<PersonaRow>(
    `/users/${encodeURIComponent(userId)}/persona?category=${encodeURIComponent(category)}`,
  );
}

export async function listUnseenProducts(userId: string, limit = 50): Promise<ProductSummary[]> {
  return requestJson<ProductSummary[]>(
    `/users/${encodeURIComponent(userId)}/unseen-products?limit=${limit}`,
  );
}

export async function parsePersona(rawInput: string): Promise<Record<string, unknown> | string> {
  try {
    const response = await requestJson<{ persona?: Record<string, unknown>; parsed_persona?: Record<string, unknown> }>(
      "/personas/parse",
      {
        method: "POST",
        body: JSON.stringify({ raw_input: rawInput, input_format: "auto" }),
      },
    );
    return response.persona || response.parsed_persona || rawInput;
  } catch (error) {
    if (error instanceof PrototypeApiError && error.status === 404) {
      try {
        const parsed = JSON.parse(rawInput);
        return typeof parsed === "object" && parsed !== null ? parsed : rawInput;
      } catch {
        return rawInput;
      }
    }
    throw error;
  }
}

export async function simulateReview(selection: PersonaSelection, product: ProductInput) {
  return requestJson<SimulationResult>("/reviews/simulate", {
    method: "POST",
    body: JSON.stringify({
      user_id: selection.mode === "demo" ? selection.userId : undefined,
      category: product.category,
      parent_asin: product.parent_asin || "playground_custom_product",
      persona: selection.persona,
      product: {
        parent_asin: product.parent_asin || "playground_custom_product",
        title: product.title,
        category: product.category,
        main_category: product.main_category || product.category,
        price: product.price,
        features: product.features || [],
        description: product.description ? [product.description] : [],
        average_rating: product.average_rating ?? 4.2,
        rating_number: product.rating_number ?? 100,
        store: product.store || "Playground merchant",
        details: {},
      },
      context: { source: "nextjs_playground" },
    }),
  });
}

export async function getRecommendations(
  selection: PersonaSelection,
  requestText: string,
  sessionId?: string | null,
) {
  return requestJson<RecommendationResult>("/recommendations/generate", {
    method: "POST",
    body: JSON.stringify({
      user_id: selection.mode === "demo" ? selection.userId : undefined,
      category: selection.category,
      persona: selection.persona,
      request: requestText || null,
      limit: 5,
      session_id: sessionId || undefined,
      cold_start: selection.mode === "custom",
      context: { source: "nextjs_playground" },
    }),
  });
}

export async function refineRecommendations(
  sessionId: string,
  selection: PersonaSelection,
  message: string,
) {
  const payload =
    selection.mode === "demo"
      ? {
          user_id: selection.userId,
          category: selection.category,
          message,
          limit: 5,
        }
      : {
          persona: selection.persona,
          category: selection.category,
          request: message,
          limit: 5,
          session_id: sessionId,
          cold_start: true,
          context: { source: "nextjs_playground", refinement: true },
        };

  const path =
    selection.mode === "demo"
      ? `/sessions/${encodeURIComponent(sessionId)}/message`
      : "/recommendations/generate";

  return requestJson<RecommendationResult>(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export { PrototypeApiError };
