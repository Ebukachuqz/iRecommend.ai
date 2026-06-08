"use client";

import Papa from "papaparse";
import { AlertCircle, CheckCircle2, Download, FileText, Loader2, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { ColumnMapper } from "@/components/uploads/ColumnMapper";
import { productOptionalFields, productRequiredFields } from "@/components/uploads/ReviewCsvUploadFlow";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  getUploadStatus,
  uploadProductsCsv,
  type UploadStatus,
} from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

type ProductCsvUploadFlowProps = {
  orgId: string;
  onComplete?: (status: UploadStatus) => void;
};

type FlowStep = "select" | "map" | "confirm" | "processing" | "complete" | "failed";

async function getAccessToken() {
  const supabase = createBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    throw new Error("Log in again before uploading your product catalog.");
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

export function ProductCsvUploadFlow({ orgId, onComplete }: ProductCsvUploadFlowProps) {
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
        setDetectedColumns(result.meta.fields || []);
        setPreviewRows(result.data || []);
        setStep("map");
      },
      error: () => setError("Could not read this CSV. Check the file and try again."),
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
      toast.loading("Uploading product catalog...", { id: "product-upload" });
      const result = await uploadProductsCsv(token, orgId, file, mapping);
      setUploadId(result.upload_id);
      setStep("processing");
      toast.success("Product catalog upload started.", { id: "product-upload" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to upload product catalog.";
      setError(message);
      toast.error(message, { id: "product-upload" });
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
          toast.success("Product catalog uploaded.");
          onComplete?.(nextStatus);
        }
        if (nextStatus.status === "failed") {
          setStep("failed");
          toast.error("Product catalog upload failed.");
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Unable to fetch upload status.";
          setError(message);
          toast.error(message);
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
          requiredFields={productRequiredFields}
          optionalFields={productOptionalFields}
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
          <h3 className="font-display text-xl font-semibold text-text-primary">Ready to upload catalog</h3>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {rowEstimate.toLocaleString()} products are ready. Unmapped columns are kept as extra fields when your SaaS table has that optional column.
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
            Upload product catalog
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
              step === "complete" ? "bg-success" : step === "failed" ? "bg-error" : "animate-pulse bg-primary"
            }`}
          />
          <p className="text-sm font-semibold text-text-primary">
            {step === "complete" ? "Done" : step === "failed" ? "Upload failed" : "Processing your catalog..."}
          </p>
        </div>
        <h3 className="mt-5 font-display text-2xl font-semibold text-text-primary">
          We are saving your product catalog for simulator autofill.
        </h3>
        <Progress className="mt-6" value={progressValue} />
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Metric label="Rows processed" value={`${(status?.processed_rows || 0).toLocaleString()} of ${(status?.total_rows || rowEstimate).toLocaleString()}`} />
          <Metric label="Products saved" value={`${status?.processing_summary.valid_rows || 0}`} />
          <Metric label="Skipped rows" value={`${status?.processing_summary.skipped_invalid_rows || 0}`} />
        </div>
        {step === "complete" ? (
          <div className="aurora-panel mt-6 p-5">
            <CheckCircle2 className="h-6 w-6 text-white" />
            <p className="mt-3 font-display text-xl font-semibold text-white">
              {status?.processing_summary.valid_rows || 0} products added to your catalog.
            </p>
            <p className="mt-2 text-sm text-white/80">You can now select these products inside the launch simulator.</p>
          </div>
        ) : null}
        {step === "failed" ? (
          <div className="mt-6 rounded-xl border border-error/30 bg-error/5 p-4 text-sm text-error">
            {status?.error_message || error || "Processing failed. Try uploading again."}
          </div>
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
        <h3 className="mt-4 font-display text-xl font-semibold text-text-primary">Drag your product catalog CSV here</h3>
        <p className="mt-2 text-sm leading-6 text-text-secondary">
          Or click to browse. Product catalog upload is optional and only helps the simulator prefill product details.
        </p>
      </div>
      <a className="inline-flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline" href="/sample-data/product_catalog_sample.csv" download>
        <Download className="h-4 w-4" />
        Download sample products CSV
      </a>
      {error ? <ErrorMessage message={error} /> : null}
    </div>
  );
}

function UploadHeader({ rowEstimate, fileName }: { rowEstimate: number; fileName: string }) {
  return (
    <div className="rounded-2xl border border-border bg-soft-surface p-4">
      <p className="text-sm font-semibold text-text-primary">{fileName}</p>
      <p className="mt-1 text-sm text-text-secondary">Estimated rows: {rowEstimate.toLocaleString()}</p>
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
