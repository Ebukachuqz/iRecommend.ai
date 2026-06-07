export const SAAS_API_URL =
  process.env.NEXT_PUBLIC_SAAS_API_URL?.replace(/\/$/, "") || "http://localhost:8001";

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

export class SaasApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SaasApiError";
  }
}

async function requestSaas<T>(path: string, accessToken: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${SAAS_API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
        ...(init?.headers || {}),
      },
    });
  } catch {
    throw new SaasApiError("SaaS API is offline. Start it with: uvicorn app.saas.main:app --reload --port 8001.");
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
    response = await fetch(`${SAAS_API_URL}${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
      body,
    });
  } catch {
    throw new SaasApiError("SaaS API is offline. Start it with: uvicorn app.saas.main:app --reload --port 8001.");
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

export async function getUploadStatus(accessToken: string, uploadId: string): Promise<UploadStatus> {
  return requestSaas<UploadStatus>(`/saas/uploads/${encodeURIComponent(uploadId)}/status`, accessToken);
}
