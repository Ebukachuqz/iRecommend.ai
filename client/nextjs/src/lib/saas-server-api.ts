import { BACKEND_API_URL, type Organisation } from "@/lib/saas-api";

type MyOrganisationResponse = {
  organisation: Organisation | null;
};

export async function getMyOrganisationServer(accessToken: string): Promise<MyOrganisationResponse> {
  const response = await fetch(`${BACKEND_API_URL}/saas/me/organisation`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to verify organisation setup.");
  }

  return response.json() as Promise<MyOrganisationResponse>;
}
