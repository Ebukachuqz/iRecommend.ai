"use client";

import Link from "next/link";
import { ChevronRight, Clock, Star, Tag, Upload, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { useDashboardOrg } from "@/components/dashboard/DashboardOrgContext";
import {
  InsightBars,
  relativeTime,
  Stars,
  StrictnessBadge,
  TruncatedCustomerId,
} from "@/components/dashboard/DashboardUi";
import { Button } from "@/components/ui/button";
import {
  getDashboardCustomers,
  getDashboardOverview,
  type DashboardCustomerSummary,
  type DashboardOverview,
} from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

function businessLabel(value?: string | null) {
  if (!value) {
    return "Not enough data";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export default function DashboardPage() {
  const { orgId, orgName } = useDashboardOrg();
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [customers, setCustomers] = useState<DashboardCustomerSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadDashboard() {
      setLoading(true);
      setError(null);
      try {
        const supabase = createBrowserClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) {
          throw new Error("Log in again to view your dashboard.");
        }
        const [nextOverview, nextCustomers] = await Promise.all([
          getDashboardOverview(session.access_token, orgId),
          getDashboardCustomers(session.access_token, orgId, { page: 1, perPage: 5 }),
        ]);
        if (mounted) {
          setOverview(nextOverview);
          setCustomers(nextCustomers.customers);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Unable to load dashboard.");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    void loadDashboard();
    return () => {
      mounted = false;
    };
  }, [orgId]);

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <section className="command-card p-8">
        <h1 className="font-display text-display-sm text-text-primary">Unable to load dashboard</h1>
        <p className="mt-3 text-body-sm text-error-text">{error}</p>
      </section>
    );
  }

  if (!overview || overview.total_personas === 0) {
    return (
      <section className="flex justify-center py-24">
        <div className="command-card max-w-2xl p-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-light text-primary">
            <Upload className="h-7 w-7" />
          </div>
          <h1 className="mt-6 font-display text-display-sm text-text-primary">
            No customer intelligence yet
          </h1>
          <p className="mt-3 text-body-sm text-text-secondary">
            Upload your review CSV and iRecommend will build behavioural personas from your customer feedback.
          </p>
          <Button
            render={<Link href="/dashboard/upload" />}
            className="mt-8"
          >
            Upload customer reviews
          </Button>
        </div>
      </section>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <header>
        <p className="text-label-lg text-primary">Customer intelligence</p>
        <h1 className="mt-2 font-display text-display-md text-text-primary">{orgName}</h1>
        <p className="mt-2 text-body-md text-text-secondary">Here&apos;s how your customer base looks.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={Users}
          label="Total customers with personas"
          value={overview.total_personas.toLocaleString()}
          explanation="Customers we understand well enough to simulate or recommend for."
        />
        <StatCard
          icon={Star}
          label="Avg rating strictness"
          value={businessLabel(overview.avg_strictness)}
          explanation="How hard your customers are to impress."
        />
        <StatCard
          icon={Tag}
          label="Categories covered"
          value={`${overview.categories_covered.length || 0}`}
          explanation="Product areas represented in your customer feedback."
          detail={overview.categories_covered.slice(0, 3).join(", ") || "No categories yet"}
        />
        <StatCard
          icon={Clock}
          label="Personas last updated"
          value={relativeTime(overview.last_upload_at)}
          explanation="How recently iRecommend refreshed this intelligence."
        />
      </section>

      <section className="grid gap-6 lg:grid-cols-5">
        <div className="command-card p-6 lg:col-span-3">
          <h2 className="font-display text-heading-xl text-text-primary">What your customers value</h2>
          <p className="mt-2 text-body-sm text-text-secondary">What your customers repeatedly praise or look for.</p>
          <div className="mt-6">
            <InsightBars items={overview.top_values_counts} />
          </div>
        </div>
        <div className="command-card p-6 lg:col-span-2">
          <h2 className="font-display text-heading-xl text-text-primary">Common complaints</h2>
          <p className="mt-2 text-body-sm text-text-secondary">What your customers repeatedly dislike or warn about.</p>
          <div className="mt-6">
            <InsightBars items={overview.top_complaints_counts} tone="red" />
          </div>
        </div>
      </section>

      <section className="command-card p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="font-display text-heading-xl text-text-primary">Recent customer profiles</h2>
            <p className="mt-2 text-body-sm text-text-secondary">Click any row to view their full persona.</p>
          </div>
          <Link href="/dashboard/customers" className="text-body-sm font-medium text-primary underline-offset-4 hover:underline">
            View all customers
          </Link>
        </div>
        <CustomerTable customers={customers} />
      </section>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  explanation,
  detail,
}: {
  icon: typeof Users;
  label: string;
  value: string;
  explanation: string;
  detail?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface-1 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-label-md text-text-muted">{label}</p>
          <p className="metric-number mt-3 font-display text-metric-lg text-text-primary">{value}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary-light text-primary">
          <Icon className="h-5 w-5" />
        </div>
      </div>
      <p className="mt-4 text-body-sm text-text-secondary">{explanation}</p>
      {detail ? <p className="mt-2 truncate text-body-xs text-text-muted">{detail}</p> : null}
    </div>
  );
}

function CustomerTable({ customers }: { customers: DashboardCustomerSummary[] }) {
  if (!customers.length) {
    return <p className="mt-6 text-body-sm text-text-secondary">No customer profiles found.</p>;
  }
  return (
    <div className="mt-6 overflow-hidden rounded-lg border border-border">
      <table className="min-w-full text-left text-body-md">
        <thead className="bg-surface-0 text-label-md text-text-muted">
          <tr>
            <th className="px-4 py-3">Customer ID</th>
            <th className="px-4 py-3">Reviews</th>
            <th className="px-4 py-3">Avg Rating</th>
            <th className="px-4 py-3">Strictness</th>
            <th className="px-4 py-3">Top value</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {customers.map((customer) => (
            <tr key={customer.customer_id} className="border-t border-surface-0 transition-colors duration-100 hover:bg-surface-0">
              <td className="px-4 py-4">
                <Link href={`/dashboard/customers/${encodeURIComponent(customer.customer_id)}`}>
                  <TruncatedCustomerId customerId={customer.customer_id} />
                </Link>
              </td>
              <td className="px-4 py-4 font-mono text-mono-md text-text-secondary">{customer.review_count}</td>
              <td className="px-4 py-4">
                <div className="flex items-center gap-2">
                  <Stars rating={customer.avg_rating} />
                  <span className="font-mono text-mono-md text-text-secondary">{customer.avg_rating.toFixed(1)}</span>
                </div>
              </td>
              <td className="px-4 py-4">
                <StrictnessBadge value={customer.strictness} />
              </td>
              <td className="px-4 py-4 text-text-secondary">{customer.top_values[0] || "No signal yet"}</td>
              <td className="px-4 py-4 text-right">
                <ChevronRight className="ml-auto h-4 w-4 text-text-muted" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <div className="skeleton-shimmer h-24 rounded-lg" />
      <div className="grid gap-4 md:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="skeleton-shimmer h-40 rounded-lg" />
        ))}
      </div>
      <div className="skeleton-shimmer h-80 rounded-lg" />
    </div>
  );
}
