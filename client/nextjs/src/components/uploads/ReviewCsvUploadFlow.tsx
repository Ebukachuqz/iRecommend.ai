"use client";

import Papa from "papaparse";
import { AlertCircle, CheckCircle2, Download, FileText, Loader2, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ColumnMapper, type FieldDef } from "@/components/uploads/ColumnMapper";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  getUploadStatus,
  uploadReviewsCsv,
  type UploadStatus,
} from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

type ReviewCsvUploadFlowProps = {
  orgId: string;
  onComplete?: (status: UploadStatus) => void;
};

const reviewRequiredFields: FieldDef[] = [
  { key: "customer_id", label: "Customer ID", description: "Unique identifier per customer" },
  { key: "rating", label: "Rating (1-5)", description: "Numeric star rating" },
  { key: "review_text", label: "Review Text", description: "The written review" },
];

const reviewOptionalFields: FieldDef[] = [
  { key: "product_name", label: "Product Name", description: "Name of the reviewed product" },
  { key: "category", label: "Category", description: "Product category" },
  { key: "date", label: "Date", description: "When the review was written" },
];

export const productRequiredFields: FieldDef[] = [
  { key: "product_name", label: "Product Name", description: "Name of the product" },
  { key: "category", label: "Category", description: "Product category" },
];

export const productOptionalFields: FieldDef[] = [
  { key: "product_id", label: "Product ID", description: "Unique product identifier" },
  { key: "price", label: "Price", description: "Product price (numeric)" },
  { key: "description", label: "Description", description: "Product description text" },
  { key: "features", label: "Features", description: "Comma-separated feature list" },
];

type FlowStep = "select" | "map" | "confirm" | "processing" | "complete" | "failed";

async function getAccessToken() {
  const supabase = createBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    throw new Error("Log in again before uploading customer reviews.");
  }
  return session.access_token;
}

function estimateRows(file: File) {
  return new Promise<number>((resolve) => {
    Papa.parse(file, {
      skipEmptyLines: true,
      complete: (result) => {
        const rows = Array.isArray(result.data) ? result.data.length : 0;
        resolve(Math.max(rows - 1, 0));
      },
      error: () => resolve(0),
    });
  });
}

export function ReviewCsvUploadFlow({ orgId, onComplete }: ReviewCsvUploadFlowProps) {
  const [step, setStep] = useState<FlowStep>("select");
  const [file, setFile] = useState<File | null>(null);
  const [detectedColumns, setDetectedColumns] = useState<string[]>([]);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [rowEstimate, setRowEstimate] = useState(0);
  const [mapping, setMapping] = useState<Record<string, string> | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const progressValue = useMemo(() => {
    if (!status?.total_rows) {
      return 0;
    }
    return Math.min(100, Math.round((status.processed_rows / status.total_rows) * 100));
  }, [status]);

  async function handleFile(selectedFile: File) {
    if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
      setError("Upload a CSV file.");
      return;
    }
    setError(null);
    setFile(selectedFile);
    const rows = await estimateRows(selectedFile);
    setRowEstimate(rows);
    Papa.parse<Record<string, unknown>>(selectedFile, {
      header: true,
      preview: 3,
      skipEmptyLines: true,
      complete: (result) => {
        const columns = result.meta.fields || [];
        setDetectedColumns(columns);
        setPreviewRows(result.data || []);
        setStep("map");
      },
      error: () => {
        setError("Could not read this CSV. Check the file and try again.");
      },
    });
  }

  async function startUpload() {
    if (!file || !mapping) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const token = await getAccessToken();
      const result = await uploadReviewsCsv(token, orgId, file, mapping);
      setUploadId(result.upload_id);
      setStep("processing");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload customer reviews.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!uploadId || step !== "processing") {
      return;
    }
    let cancelled = false;

    async function poll() {
      try {
        const token = await getAccessToken();
        const nextStatus = await getUploadStatus(token, uploadId as string);
        if (cancelled) {
          return;
        }
        setStatus(nextStatus);
        if (nextStatus.status === "complete") {
          setStep("complete");
          onComplete?.(nextStatus);
        }
        if (nextStatus.status === "failed") {
          setStep("failed");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to fetch upload status.");
        }
      }
    }

    void poll();
    const interval = window.setInterval(() => void poll(), 10000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [onComplete, step, uploadId]);

  if (step === "map" && file) {
    return (
      <div className="space-y-6">
        <UploadHeader rowEstimate={rowEstimate} fileName={file.name} />
        <ColumnMapper
          detectedColumns={detectedColumns}
          previewRows={previewRows}
          requiredFields={reviewRequiredFields}
          optionalFields={reviewOptionalFields}
          onMappingComplete={(nextMapping) => {
            setMapping(nextMapping);
            setStep("confirm");
          }}
        />
        {error ? <ErrorMessage message={error} /> : null}
      </div>
    );
  }

  if (step === "confirm" && file && mapping) {
    return (
      <div className="space-y-6">
        <UploadHeader rowEstimate={rowEstimate} fileName={file.name} />
        <div className="command-card p-5">
          <h3 className="font-display text-xl font-semibold text-text-primary">
            Ready to upload
          </h3>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {rowEstimate.toLocaleString()} rows are ready. We will preserve unmapped columns as extra fields.
          </p>
          <div className="mt-4 grid gap-2 text-sm text-text-secondary">
            {Object.entries(mapping)
              .filter(([, value]) => value !== "skip")
              .map(([column, value]) => (
                <div key={column} className="flex justify-between rounded-lg bg-soft-surface px-3 py-2">
                  <span>{column}</span>
                  <span className="font-semibold text-primary">{value}</span>
                </div>
              ))}
          </div>
          <Button
            type="button"
            disabled={loading}
            onClick={() => void startUpload()}
            className="violet-focus-ring mt-6 h-11 w-full bg-primary text-white hover:bg-primary-hover"
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
            Upload and generate personas
          </Button>
        </div>
        {error ? <ErrorMessage message={error} /> : null}
      </div>
    );
  }

  if (step === "processing" || step === "complete" || step === "failed") {
    return (
      <div className="command-card p-6">
        <div className="flex items-center gap-3">
          <span
            className={`h-3 w-3 rounded-full ${
              step === "complete"
                ? "bg-success"
                : step === "failed"
                  ? "bg-error"
                  : "animate-pulse bg-primary"
            }`}
          />
          <p className="text-sm font-semibold text-text-primary">
            {step === "complete"
              ? "Done"
              : step === "failed"
                ? "Upload failed"
                : "Processing your data..."}
          </p>
        </div>
        <h3 className="mt-5 font-display text-2xl font-semibold text-text-primary">
          We are turning your reviews into customer personas.
        </h3>
        <Progress className="mt-6" value={progressValue} />
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Metric label="Rows processed" value={`${(status?.processed_rows || 0).toLocaleString()} of ${(status?.total_rows || rowEstimate).toLocaleString()}`} />
          <Metric label="Customers detected" value={`${status?.processing_summary.customers_detected || 0}`} />
          <Metric label="Personas generated" value={`${status?.personas_generated || 0}`} />
        </div>
        <div className="mt-4 grid gap-2 text-xs text-text-muted sm:grid-cols-3">
          <span>Valid rows: {status?.processing_summary.valid_rows || 0}</span>
          <span>Skipped invalid rows: {status?.processing_summary.skipped_invalid_rows || 0}</span>
          <span>Skipped customers: {status?.processing_summary.skipped_insufficient_reviews || 0}</span>
        </div>
        {step === "complete" ? (
          <div className="aurora-panel mt-6 p-5">
            <CheckCircle2 className="h-6 w-6 text-white" />
            <p className="mt-3 font-display text-xl font-semibold text-white">
              {status?.personas_generated || 0} customer personas built successfully.
            </p>
            <p className="mt-2 text-sm text-white/80">
              Your customer intelligence workspace is ready for the next step.
            </p>
          </div>
        ) : null}
        {step === "failed" ? (
          <div className="mt-6 rounded-xl border border-error/30 bg-error/5 p-4 text-sm text-error">
            {status?.error_message || error || "Processing failed. Try uploading again."}
          </div>
        ) : null}
        {status?.processing_summary.error_samples?.length ? (
          <details className="mt-5 text-sm text-text-secondary">
            <summary className="cursor-pointer font-semibold text-text-primary">Processing notes</summary>
            <ul className="mt-3 list-disc space-y-1 pl-5">
              {status.processing_summary.error_samples.map((sample, index) => (
                <li key={`${sample}-${index}`}>{sample}</li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div
        className="violet-glow-card cursor-pointer rounded-2xl border border-dashed border-primary/30 p-8 text-center"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const selected = event.dataTransfer.files?.[0];
          if (selected) {
            void handleFile(selected);
          }
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(event) => {
            const selected = event.target.files?.[0];
            if (selected) {
              void handleFile(selected);
            }
          }}
        />
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary-light text-primary">
          <FileText className="h-6 w-6" />
        </div>
        <h3 className="mt-4 font-display text-xl font-semibold text-text-primary">
          Drag your customer reviews CSV here
        </h3>
        <p className="mt-2 text-sm leading-6 text-text-secondary">
          Or click to browse. We will guide you through mapping your columns before anything is processed.
        </p>
      </div>
      <div className="flex flex-wrap gap-3 text-sm">
        <a className="inline-flex items-center gap-2 font-semibold text-primary underline-offset-4 hover:underline" href="/sample-data/customer_reviews_sample.csv" download>
          <Download className="h-4 w-4" />
          Download sample reviews CSV
        </a>
        <a className="inline-flex items-center gap-2 font-semibold text-text-secondary underline-offset-4 hover:text-primary hover:underline" href="/sample-data/product_catalog_sample.csv" download>
          <Download className="h-4 w-4" />
          Download sample products CSV
        </a>
      </div>
      {error ? <ErrorMessage message={error} /> : null}
    </div>
  );
}

function UploadHeader({ rowEstimate, fileName }: { rowEstimate: number; fileName: string }) {
  return (
    <div className="rounded-2xl border border-border bg-soft-surface p-4">
      <p className="text-sm font-semibold text-text-primary">{fileName}</p>
      <p className="mt-1 text-sm text-text-secondary">
        Estimated rows: {rowEstimate.toLocaleString()}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">{label}</p>
      <p className="mt-2 font-display text-xl font-semibold text-text-primary">{value}</p>
    </div>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-error/30 bg-error/5 p-4 text-sm text-error">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <p>{message}</p>
    </div>
  );
}
