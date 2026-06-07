"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";

export type FieldDef = {
  key: string;
  label: string;
  description: string;
};

type ColumnMapperProps = {
  detectedColumns: string[];
  previewRows?: Record<string, unknown>[];
  requiredFields: FieldDef[];
  optionalFields: FieldDef[];
  onMappingComplete: (mapping: Record<string, string>) => void;
};

const SKIP_VALUE = "skip";

const synonyms: Record<string, string[]> = {
  customer_id: ["customer", "customerid", "custid", "cust_id", "user", "userid", "user_id", "client"],
  rating: ["rating", "stars", "star", "score", "reviewrating"],
  review_text: ["review", "reviewtext", "review_text", "comment", "comments", "feedback", "text", "body"],
  product_name: ["product", "productname", "product_name", "item", "itemname", "title"],
  category: ["category", "cat", "department", "type"],
  date: ["date", "created", "createdat", "created_at", "reviewdate", "review_date"],
  product_id: ["productid", "product_id", "sku", "asin", "id"],
  price: ["price", "amount", "cost"],
  description: ["description", "desc", "details"],
  features: ["features", "feature", "attributes"],
};

function normalize(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function guessField(column: string, fields: FieldDef[]) {
  const normalizedColumn = normalize(column);
  for (const field of fields) {
    const candidates = [field.key, field.label, ...(synonyms[field.key] || [])].map(normalize);
    if (
      candidates.some(
        (candidate) =>
          normalizedColumn === candidate ||
          normalizedColumn.includes(candidate) ||
          candidate.includes(normalizedColumn),
      )
    ) {
      return field.key;
    }
  }
  return SKIP_VALUE;
}

export function ColumnMapper({
  detectedColumns,
  previewRows = [],
  requiredFields,
  optionalFields,
  onMappingComplete,
}: ColumnMapperProps) {
  const fields = useMemo(() => [...requiredFields, ...optionalFields], [requiredFields, optionalFields]);
  const [mapping, setMapping] = useState<Record<string, string>>({});

  useEffect(() => {
    const used = new Set<string>();
    const next: Record<string, string> = {};
    for (const column of detectedColumns) {
      const guessed = guessField(column, fields);
      if (guessed !== SKIP_VALUE && !used.has(guessed)) {
        next[column] = guessed;
        used.add(guessed);
      } else {
        next[column] = SKIP_VALUE;
      }
    }
    setMapping(next);
  }, [detectedColumns, fields]);

  const mappedRequired = new Set(Object.values(mapping));
  const missingRequired = requiredFields.filter((field) => !mappedRequired.has(field.key));
  const isComplete = missingRequired.length === 0;
  const extraColumns = detectedColumns.filter((column) => mapping[column] === SKIP_VALUE);

  function updateColumn(column: string, value: string) {
    setMapping((current) => {
      const next = { ...current, [column]: value };
      if (value !== SKIP_VALUE) {
        for (const otherColumn of Object.keys(next)) {
          if (otherColumn !== column && next[otherColumn] === value) {
            next[otherColumn] = SKIP_VALUE;
          }
        }
      }
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-display text-xl font-semibold text-text-primary">
          Map your columns
        </h3>
        <p className="mt-2 text-sm leading-6 text-text-secondary">
          We found {detectedColumns.length} columns in your file. Tell us what each column means.
        </p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-border bg-surface">
        <div className="grid grid-cols-[1fr_44px_1fr] border-b border-border bg-soft-surface px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
          <span>Your column name</span>
          <span className="text-center"> </span>
          <span>Maps to</span>
        </div>
        {detectedColumns.map((column) => (
          <div key={column} className="grid grid-cols-[1fr_44px_1fr] items-center gap-3 border-b border-border px-4 py-3 last:border-b-0">
            <code className="truncate rounded-lg bg-soft-surface px-3 py-2 text-sm text-text-secondary">
              {column}
            </code>
            <span className="text-center text-text-muted">→</span>
            <select
              value={mapping[column] || SKIP_VALUE}
              onChange={(event) => updateColumn(column, event.target.value)}
              className="violet-focus-ring h-10 rounded-lg border border-border bg-surface px-3 text-sm text-text-primary outline-none"
            >
              <option value={SKIP_VALUE}>Other / stored as extra field</option>
              {requiredFields.map((field) => (
                <option key={field.key} value={field.key}>
                  {field.label} *
                </option>
              ))}
              {optionalFields.map((field) => (
                <option key={field.key} value={field.key}>
                  {field.label}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>

      <div className="grid gap-3 rounded-2xl border border-border bg-soft-surface p-4 text-sm text-text-secondary">
        {requiredFields.map((field) => {
          const mapped = mappedRequired.has(field.key);
          return (
            <div key={field.key} className="flex items-start gap-3">
              {mapped ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-success" />
              ) : (
                <AlertCircle className="mt-0.5 h-4 w-4 text-error" />
              )}
              <div>
                <p className="font-semibold text-text-primary">
                  {field.label}{" "}
                  {!mapped ? <span className="text-error">Required</span> : null}
                </p>
                <p>{field.description}</p>
              </div>
            </div>
          );
        })}
        {extraColumns.length ? (
          <p className="border-t border-border pt-3 text-xs text-text-muted">
            {extraColumns.length} unmapped column{extraColumns.length === 1 ? "" : "s"} will be preserved in extra fields.
          </p>
        ) : null}
      </div>

      <div>
        <h4 className="text-sm font-semibold text-text-primary">
          Preview (first 3 rows after mapping)
        </h4>
        <div className="mt-3 overflow-x-auto rounded-2xl border border-border bg-surface">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-soft-surface text-xs uppercase tracking-[0.12em] text-text-muted">
              <tr>
                {[...requiredFields, ...optionalFields]
                  .filter((field) => Object.values(mapping).includes(field.key))
                  .map((field) => (
                    <th key={field.key} className="px-3 py-3 font-semibold">
                      {field.label}
                    </th>
                  ))}
                <th className="px-3 py-3 font-semibold">Extra fields</th>
              </tr>
            </thead>
            <tbody>
              {previewRows.slice(0, 3).map((row, index) => {
                const mappedColumns = new Set(
                  Object.entries(mapping)
                    .filter(([, field]) => field !== SKIP_VALUE)
                    .map(([column]) => column),
                );
                return (
                  <tr key={index} className="border-t border-border">
                    {[...requiredFields, ...optionalFields]
                      .filter((field) => Object.values(mapping).includes(field.key))
                      .map((field) => {
                        const sourceColumn = Object.entries(mapping).find(([, value]) => value === field.key)?.[0];
                        return (
                          <td key={field.key} className="max-w-[220px] truncate px-3 py-3 text-text-secondary">
                            {sourceColumn ? String(row[sourceColumn] ?? "") : ""}
                          </td>
                        );
                      })}
                    <td className="max-w-[220px] truncate px-3 py-3 text-text-muted">
                      {Object.keys(row).filter((column) => !mappedColumns.has(column)).join(", ") || "None"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <Button
        type="button"
        disabled={!isComplete}
        onClick={() => onMappingComplete(mapping)}
        className="violet-focus-ring h-11 w-full bg-primary text-white hover:bg-primary-hover"
      >
        Confirm mapping
      </Button>
    </div>
  );
}
