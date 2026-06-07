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
