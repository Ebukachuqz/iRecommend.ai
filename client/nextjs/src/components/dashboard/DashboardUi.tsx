"use client";

import { Copy, Star } from "lucide-react";

import { cn } from "@/lib/utils";
import type { CountItem } from "@/lib/saas-api";

export function Stars({ rating }: { rating: number }) {
  const rounded = Math.max(1, Math.min(5, Math.round(rating || 0)));
  return (
    <span className="inline-flex items-center gap-1 text-warning">
      {Array.from({ length: 5 }).map((_, index) => (
        <Star key={index} className={cn("h-4 w-4", index < rounded ? "fill-current" : "opacity-25")} />
      ))}
    </span>
  );
}

export function StrictnessBadge({ value }: { value?: string | null }) {
  const normalized = (value || "moderate").toLowerCase();
  const className =
    normalized === "strict"
      ? "border-error/30 bg-error/10 text-error"
      : normalized === "generous"
        ? "border-success/30 bg-success/10 text-success"
        : "border-warning/30 bg-warning/10 text-warning";
  return (
    <span className={cn("inline-flex rounded-full border px-2 py-1 text-xs font-semibold capitalize", className)}>
      {normalized}
    </span>
  );
}

export function InsightBars({
  items,
  tone = "violet",
}: {
  items: CountItem[];
  tone?: "violet" | "red";
}) {
  const max = Math.max(...items.map((item) => item.count), 1);
  if (!items.length) {
    return <p className="text-sm text-text-secondary">Not enough persona evidence yet.</p>;
  }
  return (
    <div className="space-y-4">
      {items.map((item) => {
        const percent = Math.max(8, Math.round((item.count / max) * 100));
        return (
          <div key={item.label}>
            <div className="flex items-center justify-between gap-4 text-sm">
              <span className="font-medium text-text-primary">{item.label}</span>
              <span className="text-text-muted">{item.count}</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-soft-surface">
              <div
                className={cn(
                  "h-full rounded-full",
                  tone === "red"
                    ? "bg-gradient-to-r from-error to-red-400"
                    : "bg-gradient-to-r from-primary to-violet-500",
                )}
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function TruncatedCustomerId({ customerId }: { customerId: string }) {
  return (
    <span className="group inline-flex items-center gap-2 font-mono text-sm text-text-primary">
      {customerId.length > 10 ? `${customerId.slice(0, 10)}...` : customerId}
      <button
        type="button"
        className="opacity-0 transition group-hover:opacity-100"
        onClick={(event) => {
          event.preventDefault();
          void navigator.clipboard.writeText(customerId);
        }}
        aria-label="Copy customer ID"
      >
        <Copy className="h-3.5 w-3.5 text-text-muted" />
      </button>
    </span>
  );
}

export function relativeTime(value?: string | null) {
  if (!value) {
    return "No upload yet";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Recently";
  }
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) {
    return "Just now";
  }
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
