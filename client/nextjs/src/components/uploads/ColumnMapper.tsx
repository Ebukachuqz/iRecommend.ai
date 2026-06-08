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
        <h3 className="font-display text-heading-lg text-text-primary">
          Map your columns
        </h3>
        <p className="mt-2 text-body-sm text-text-secondary">
          We found {detectedColumns.length} columns in your file. Tell us what each column means.
        </p>
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-surface-1">
        <div className="grid grid-cols-12 border-b border-border bg-surface-0 px-4 py-3 text-label-md text-text-muted">
          <span className="col-span-5">Your column name</span>
          <span className="col-span-2 text-center"> </span>
          <span className="col-span-5">Maps to</span>
        </div>
        {detectedColumns.map((column) => (
          <div key={column} className="grid grid-cols-12 items-center gap-3 border-b border-border px-4 py-3 last:border-b-0">
            <code className="col-span-5 truncate rounded-md bg-surface-0 px-3 py-2 text-mono-md text-text-secondary">
              {column}
            </code>
            <span className="col-span-2 text-center text-text-muted">-&gt;</span>
            <select
              value={mapping[column] || SKIP_VALUE}
              onChange={(event) => updateColumn(column, event.target.value)}
              className="violet-focus-ring col-span-5 h-9 rounded-md border border-border bg-surface-1 px-3 text-body-md text-text-primary outline-none hover:border-border-strong"
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

      <div className="grid gap-3 rounded-lg border border-border bg-surface-0 p-4 text-body-sm text-text-secondary">
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
                  {!mapped ? <span className="text-error-text">Required</span> : null}
                </p>
                <p>{field.description}</p>
              </div>
            </div>
          );
        })}
        {extraColumns.length ? (
          <p className="border-t border-border pt-3 text-body-xs text-text-muted">
            {extraColumns.length} unmapped column{extraColumns.length === 1 ? "" : "s"} will be preserved in extra fields.
          </p>
        ) : null}
      </div>

      <div>
        <h4 className="text-body-sm font-semibold text-text-primary">
          Preview (first 3 rows after mapping)
        </h4>
        <div className="mt-3 overflow-x-auto rounded-lg border border-border bg-surface-1">
          <table className="min-w-full text-left text-body-md">
            <thead className="bg-surface-0 text-label-md text-text-muted">
              <tr>
                {[...requiredFields, ...optionalFields]
                  .filter((field) => Object.values(mapping).includes(field.key))
                  .map((field) => (
                    <th key={field.key} className="px-3 py-3">
                      {field.label}
                    </th>
                  ))}
                <th className="px-3 py-3">Extra fields</th>
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
                          <td key={field.key} className="max-w-xs truncate px-3 py-3 text-text-secondary">
                            {sourceColumn ? String(row[sourceColumn] ?? "") : ""}
                          </td>
                        );
                      })}
                    <td className="max-w-xs truncate px-3 py-3 text-text-muted">
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
        className="h-11 w-full"
      >
        Confirm mapping
      </Button>
    </div>
  );
}
