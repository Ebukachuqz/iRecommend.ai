import { redirect } from "next/navigation";
import type { Metadata } from "next";

import { DashboardOrgProvider } from "@/components/dashboard/DashboardOrgContext";
import { DashboardSidebar } from "@/components/layout/DashboardSidebar";
import { getMyOrganisationServer } from "@/lib/saas-server-api";
import { createServerClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Dashboard",
};

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = createServerClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    redirect("/auth/login");
  }

  const result = await getMyOrganisationServer(session.access_token);
  if (!result.organisation) {
    redirect("/onboarding");
  }

  const userEmail = session.user.email || "merchant@example.com";

  return (
    <DashboardOrgProvider
      value={{
        orgId: result.organisation.id,
        orgName: result.organisation.name,
        userEmail,
      }}
    >
      <div className="min-h-screen bg-background lg:flex">
        <DashboardSidebar orgName={result.organisation.name} userEmail={userEmail} />
        <main className="min-w-0 flex-1 px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </DashboardOrgProvider>
  );
}
