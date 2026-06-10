"use client";

import Link from "next/link";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { useDashboardOrg } from "@/components/dashboard/DashboardOrgContext";
import { Stars, StrictnessBadge, TruncatedCustomerId } from "@/components/dashboard/DashboardUi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  getDashboardCustomers,
  type DashboardCustomerSummary,
  type DashboardCustomersResponse,
} from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

export default function CustomersPage() {
  const { orgId } = useDashboardOrg();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<DashboardCustomersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [search]);

  useEffect(() => {
    let mounted = true;
    async function loadCustomers() {
      setLoading(true);
      setError(null);
      try {
        const supabase = createBrowserClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) {
          throw new Error("Log in again to view customers.");
        }
        const nextData = await getDashboardCustomers(session.access_token, orgId, {
          page,
          perPage: 20,
          search,
        });
        if (mounted) {
          setData(nextData);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Unable to load customers.");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    void loadCustomers();
    return () => {
      mounted = false;
    };
  }, [orgId, page, search]);

  const totalPages = Math.max(1, Math.ceil((data?.total || 0) / 20));

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-label-lg text-primary">Customer profiles</p>
          <h1 className="mt-2 font-display text-display-md text-text-primary">Customer Profiles</h1>
          <p className="mt-2 text-body-md text-text-secondary">
            {(data?.total || 0).toLocaleString()} customers with personas
          </p>
        </div>
        <label className="relative block w-full max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search customer ID..."
          className="h-11 pl-10"
          />
        </label>
      </header>

      <section className="command-card overflow-hidden p-0">
        {loading ? (
          <CustomerSkeleton />
        ) : error ? (
          <p className="p-6 text-body-sm text-error-text">{error}</p>
        ) : (
          <CustomerTable customers={data?.customers || []} />
        )}
      </section>

      <div className="flex items-center justify-between">
        <Button
          type="button"
          variant="outline"
          disabled={page <= 1}
          onClick={() => setPage((current) => Math.max(1, current - 1))}
        >
          <ChevronLeft className="mr-2 h-4 w-4" />
          Previous
        </Button>
        <p className="text-sm text-text-secondary">
          Page {page} of {totalPages}
        </p>
        <Button
          type="button"
          variant="outline"
          disabled={page >= totalPages}
          onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
        >
          Next
          <ChevronRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function CustomerTable({ customers }: { customers: DashboardCustomerSummary[] }) {
  if (!customers.length) {
    return <p className="p-6 text-body-sm text-text-secondary">No customers yet. Upload a CSV to get started.</p>;
  }
  return (
    <table className="min-w-full text-left text-body-md">
      <thead className="bg-surface-0 text-label-md text-text-muted">
        <tr>
          <th className="px-4 py-3">Customer ID</th>
          <th className="px-4 py-3">Reviews</th>
          <th className="px-4 py-3">Avg Rating</th>
          <th className="px-4 py-3">Strictness</th>
          <th className="px-4 py-3">Top value</th>
          <th className="px-4 py-3">Top category</th>
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
            <td className="px-4 py-4 text-text-secondary">{customer.top_category || "Unknown"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CustomerSkeleton() {
  return (
    <div className="space-y-3 p-5">
      {[0, 1, 2, 3, 4].map((item) => (
        <div key={item} className="skeleton-shimmer h-11 rounded-md" />
      ))}
    </div>
  );
}
