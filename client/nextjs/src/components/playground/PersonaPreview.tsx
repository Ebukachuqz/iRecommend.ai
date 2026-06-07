"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Star } from "lucide-react";

import { cn } from "@/lib/utils";

type PersonaPreviewProps = {
  persona: Record<string, unknown> | string;
  averageRating?: number | null;
  defaultOpen?: boolean;
};

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String).filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function pickPersonaField(persona: Record<string, unknown>, path: string[]) {
  let current: unknown = persona;
  for (const key of path) {
    current = asRecord(current)[key];
  }
  return current;
}

function getTone(persona: Record<string, unknown> | string) {
  if (typeof persona === "string") {
    return "described in text";
  }
  return (
    pickPersonaField(persona, ["writing_style", "tone"]) ||
    pickPersonaField(persona, ["tone"]) ||
    "unknown"
  );
}

function getAverageRating(persona: Record<string, unknown> | string, fallback?: number | null) {
  if (typeof fallback === "number") {
    return fallback;
  }
  if (typeof persona === "string") {
    return null;
  }
  const value =
    pickPersonaField(persona, ["rating_behavior", "average_rating"]) ||
    pickPersonaField(persona, ["average_rating"]);
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function getTopValues(persona: Record<string, unknown> | string) {
  if (typeof persona === "string") {
    return ["plain-text persona", "behavioural context"];
  }
  return (
    asArray(pickPersonaField(persona, ["preferences", "what_they_value"]))
      .concat(asArray(pickPersonaField(persona, ["values"])))
      .slice(0, 2)
  );
}

function getTopComplaints(persona: Record<string, unknown> | string) {
  if (typeof persona === "string") {
    return ["not extracted yet"];
  }
  return (
    asArray(pickPersonaField(persona, ["preferences", "common_complaints"]))
      .concat(asArray(pickPersonaField(persona, ["complaints"])))
      .slice(0, 2)
  );
}

function starsForRating(value: number | null) {
  if (value === null) {
    return "n/a";
  }
  const rounded = Math.max(1, Math.min(5, Math.round(value)));
  return "★".repeat(rounded) + "☆".repeat(5 - rounded);
}

export function PersonaPreview({
  persona,
  averageRating,
  defaultOpen = false,
}: PersonaPreviewProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [showJson, setShowJson] = useState(false);
  const rating = getAverageRating(persona, averageRating);
  const values = getTopValues(persona);
  const complaints = getTopComplaints(persona);

  return (
    <div className="command-card overflow-hidden">
      <button
        type="button"
        className="violet-focus-ring flex w-full items-center justify-between border-0 bg-surface px-4 py-3 text-left"
        onClick={() => setOpen((value) => !value)}
      >
        <div>
          <p className="text-sm font-semibold text-text-primary">Persona preview</p>
          <p className="text-xs text-text-secondary">What this customer values and notices</p>
        </div>
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
      </button>

      {open && (
        <div className="space-y-4 border-t border-border px-4 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
                Tone
              </p>
              <p className="mt-1 text-sm font-medium text-text-primary">{String(getTone(persona))}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
                Avg rating
              </p>
              <p className="mt-1 flex items-center gap-2 text-sm font-medium text-warning">
                <Star className="h-4 w-4 fill-current" />
                {starsForRating(rating)}
                {rating !== null && <span className="text-text-secondary">{rating.toFixed(1)}</span>}
              </p>
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
              Top values
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(values.length ? values : ["not available"]).map((item) => (
                <span
                  key={item}
                  className="rounded-full border border-primary/20 bg-primary-light px-2.5 py-1 text-xs font-medium text-primary"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
              Top complaints
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(complaints.length ? complaints : ["not available"]).map((item) => (
                <span
                  key={item}
                  className="rounded-full border border-border bg-soft-surface px-2.5 py-1 text-xs font-medium text-text-secondary"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <button
            type="button"
            className={cn(
              "text-xs font-semibold text-primary underline-offset-4 hover:underline",
              showJson && "text-primary-hover",
            )}
            onClick={() => setShowJson((value) => !value)}
          >
            {showJson ? "Hide full JSON" : "View full JSON"}
          </button>

          {showJson && (
            <pre className="max-h-72 overflow-auto rounded-lg bg-soft-surface p-3 text-xs leading-5 text-text-secondary">
              {typeof persona === "string" ? persona : JSON.stringify(persona, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
