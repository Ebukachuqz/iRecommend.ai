export const BACKEND_API_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

const OFFLINE_MESSAGE = "Backend API is offline. Start it with: uvicorn app.api.main:app --reload --port 8000.";

export type Organisation = {
  id: string;
  name: string;
  market_context?: string | null;
  owner_id?: string | null;
  created_at?: string | null;
};

type MyOrganisationResponse = {
  organisation: Organisation | null;
};

type OrganisationCreateResponse = {
  org_id: string;
  name: string;
};

type SuccessResponse = {
  success: boolean;
};

export type UploadProcessingSummary = {
  customers_detected?: number;
  valid_rows?: number;
  skipped_invalid_rows?: number;
  skipped_insufficient_reviews?: number;
  failed_personas?: number;
  error_samples?: string[];
};

export type UploadStatus = {
  upload_id: string;
  upload_type: string;
  status: "pending" | "processing" | "complete" | "failed";
  total_rows: number;
  processed_rows: number;
  personas_generated: number;
  error_message?: string | null;
  processing_summary: UploadProcessingSummary;
};

export type UploadCreateResponse = {
  upload_id: string;
  total_rows: number;
};

export type OrganisationSummary = {
  persona_count: number;
  review_count: number;
  latest_upload: Record<string, unknown> | null;
  latest_upload_status: string | null;
};

export type CountItem = {
  label: string;
  count: number;
};

export type DashboardOverview = {
  total_personas: number;
  avg_strictness?: string | null;
  top_values: string[];
  top_values_counts: CountItem[];
  top_complaints: string[];
  top_complaints_counts: CountItem[];
  categories_covered: string[];
  categories_covered_counts: CountItem[];
  last_upload_at?: string | null;
};

export type DashboardCustomerSummary = {
  customer_id: string;
  review_count: number;
  avg_rating: number;
  strictness: string;
  top_values: string[];
  top_category?: string | null;
};

export type DashboardCustomersResponse = {
  customers: DashboardCustomerSummary[];
  total: number;
  page: number;
  per_page: number;
};

export type DashboardCustomerProfile = {
  customer_id: string;
  persona: Record<string, unknown>;
  review_count: number;
};

export type MerchantSimulationProduct = {
  title: string;
  category: string;
  price?: number | null;
  features?: string[];
  description?: string | null;
};

export type MerchantCatalogProduct = {
  id?: string | null;
  product_id?: string | null;
  product_name: string;
  category: string;
  price?: number | null;
  description?: string | null;
  features: string[];
};

export type MerchantProductsResponse = {
  products: MerchantCatalogProduct[];
};

export type MerchantSimulationResult = {
  customer_id: string;
  product_title?: string | null;
  final_predicted_rating: number;
  simulated_review_title: string;
  simulated_review_text: string;
  confidence?: number | null;
  reasoning_summary?: string | null;
  evidence_used?: string[];
};

export type MerchantBulkSimulationResult = {
  simulations: MerchantSimulationResult[];
  avg_predicted_rating: number;
  pct_4_plus: number;
  pct_3_or_below: number;
  top_praises: string[];
  top_concerns: string[];
  interpretation: string;
};

export class SaasApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SaasApiError";
  }
}

async function requestSaas<T>(path: string, accessToken: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BACKEND_API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
        ...(init?.headers || {}),
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new SaasApiError("This request took too long. Try again with a smaller sample, or load the sample result.");
    }
    throw new SaasApiError(OFFLINE_MESSAGE);
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
          : "SaaS API request failed.";
    throw new SaasApiError(detail);
  }

  return payload as T;
}

async function requestSaasForm<T>(path: string, accessToken: string, body: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BACKEND_API_URL}${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
      body,
    });
  } catch {
    throw new SaasApiError(OFFLINE_MESSAGE);
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
          : "SaaS API request failed.";
    throw new SaasApiError(detail);
  }

  return payload as T;
}

export async function getMyOrganisation(accessToken: string): Promise<MyOrganisationResponse> {
  return requestSaas<MyOrganisationResponse>("/saas/me/organisation", accessToken);
}

export async function createOrganisation(
  accessToken: string,
  name: string,
): Promise<OrganisationCreateResponse> {
  return requestSaas<OrganisationCreateResponse>("/saas/organisations", accessToken, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function updateOrganisationSettings(
  accessToken: string,
  orgId: string,
  marketContext: string,
): Promise<SuccessResponse> {
  return requestSaas<SuccessResponse>(`/saas/organisations/${encodeURIComponent(orgId)}/settings`, accessToken, {
    method: "PATCH",
    body: JSON.stringify({ market_context: marketContext }),
  });
}

export async function getOrganisationSummary(
  accessToken: string,
  orgId: string,
): Promise<OrganisationSummary> {
  return requestSaas<OrganisationSummary>(`/saas/organisations/${encodeURIComponent(orgId)}/summary`, accessToken);
}

export async function uploadReviewsCsv(
  accessToken: string,
  orgId: string,
  file: File,
  columnMapping: Record<string, string>,
): Promise<UploadCreateResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("org_id", orgId);
  formData.append("column_mapping", JSON.stringify(columnMapping));
  return requestSaasForm<UploadCreateResponse>("/saas/uploads/reviews", accessToken, formData);
}

export async function uploadProductsCsv(
  accessToken: string,
  orgId: string,
  file: File,
  columnMapping: Record<string, string>,
): Promise<UploadCreateResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("org_id", orgId);
  formData.append("column_mapping", JSON.stringify(columnMapping));
  return requestSaasForm<UploadCreateResponse>("/saas/uploads/products", accessToken, formData);
}

export async function getUploadStatus(accessToken: string, uploadId: string): Promise<UploadStatus> {
  return requestSaas<UploadStatus>(`/saas/uploads/${encodeURIComponent(uploadId)}/status`, accessToken);
}

export async function getDashboardOverview(accessToken: string, orgId: string): Promise<DashboardOverview> {
  return requestSaas<DashboardOverview>(`/saas/organisations/${encodeURIComponent(orgId)}/overview`, accessToken);
}

export async function getDashboardCustomers(
  accessToken: string,
  orgId: string,
  options: { page?: number; perPage?: number; search?: string } = {},
): Promise<DashboardCustomersResponse> {
  const params = new URLSearchParams();
  params.set("page", String(options.page || 1));
  params.set("per_page", String(options.perPage || 20));
  if (options.search?.trim()) {
    params.set("search", options.search.trim());
  }
  return requestSaas<DashboardCustomersResponse>(
    `/saas/organisations/${encodeURIComponent(orgId)}/customers?${params.toString()}`,
    accessToken,
  );
}

export async function getDashboardCustomer(
  accessToken: string,
  orgId: string,
  customerId: string,
): Promise<DashboardCustomerProfile> {
  return requestSaas<DashboardCustomerProfile>(
    `/saas/organisations/${encodeURIComponent(orgId)}/customers/${encodeURIComponent(customerId)}`,
    accessToken,
  );
}

export async function simulateMerchantCustomer(
  accessToken: string,
  orgId: string,
  customerId: string,
  product: MerchantSimulationProduct,
): Promise<MerchantSimulationResult> {
  return requestSaas<MerchantSimulationResult>(`/saas/organisations/${encodeURIComponent(orgId)}/simulate`, accessToken, {
    method: "POST",
    body: JSON.stringify({ customer_id: customerId, product }),
  });
}

export async function getMerchantProducts(
  accessToken: string,
  orgId: string,
): Promise<MerchantProductsResponse> {
  return requestSaas<MerchantProductsResponse>(`/saas/organisations/${encodeURIComponent(orgId)}/products`, accessToken);
}

export async function simulateMerchantLaunchBulk(
  accessToken: string,
  orgId: string,
  payload: {
    product: MerchantSimulationProduct;
    customer_ids?: string[] | null;
    sample_size?: number;
  },
): Promise<MerchantBulkSimulationResult> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 90000);
  try {
    return await requestSaas<MerchantBulkSimulationResult>(
      `/saas/organisations/${encodeURIComponent(orgId)}/simulate/bulk`,
      accessToken,
      {
        method: "POST",
        body: JSON.stringify(payload),
        signal: controller.signal,
      },
    );
  } finally {
    window.clearTimeout(timeout);
  }
}
