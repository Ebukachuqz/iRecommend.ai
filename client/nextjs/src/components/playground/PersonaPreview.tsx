"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { Stars } from "@/components/dashboard/DashboardUi";

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
        className="flex w-full items-center justify-between border-0 bg-surface-1 px-4 py-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        onClick={() => setOpen((value) => !value)}
      >
        <div>
          <p className="text-body-sm font-semibold text-text-primary">Persona preview</p>
          <p className="text-body-xs text-text-secondary">What this customer values and notices</p>
        </div>
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
      </button>

      {open && (
        <div className="space-y-4 border-t border-border px-4 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-label-sm text-text-muted">
                Tone
              </p>
              <p className="mt-1 text-body-sm font-medium text-text-primary">{String(getTone(persona))}</p>
            </div>
            <div>
              <p className="text-label-sm text-text-muted">
                Avg rating
              </p>
              <p className="mt-1 flex items-center gap-2 text-body-sm font-medium text-warning">
                {rating === null ? "n/a" : <Stars rating={rating} />}
                {rating !== null && <span className="font-mono text-mono-sm text-text-secondary">{rating.toFixed(1)}</span>}
              </p>
            </div>
          </div>

          <div>
            <p className="text-label-sm text-text-muted">
              Top values
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(values.length ? values : ["not available"]).map((item) => (
                <span
                  key={item}
                  className="inline-flex h-5 items-center rounded-full border border-border bg-surface-0 px-2 text-label-sm text-text-secondary"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="text-label-sm text-text-muted">
              Top complaints
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(complaints.length ? complaints : ["not available"]).map((item) => (
                <span
                  key={item}
                  className="inline-flex h-5 items-center rounded-full border border-border bg-surface-0 px-2 text-label-sm text-text-secondary"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <button
            type="button"
            className={cn(
              "text-body-xs font-semibold text-primary underline-offset-4 hover:underline",
              showJson && "text-primary-hover",
            )}
            onClick={() => setShowJson((value) => !value)}
          >
            {showJson ? "Hide full JSON" : "View full JSON"}
          </button>

          {showJson && (
            <pre className="max-h-72 overflow-auto rounded-lg bg-surface-0 p-3 text-mono-sm text-text-secondary">
              {typeof persona === "string" ? persona : JSON.stringify(persona, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
