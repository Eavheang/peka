"use client";

import { useMemo } from "react";
import { Progress } from "@/components/ui/progress";
import { useDeleteFile, useListFiles, useRetryFile, downloadFile } from "@/services/files";
import { KnowledgeTable } from "./_partials/table";
import { Upload } from "./_partials/upload";

export default function KnowledgePage() {
  const files = useListFiles();
  const retry = useRetryFile();
  const remove = useDeleteFile();
  const sources = files.data ?? [];
  const counts = useMemo(
    () => ({
      indexed: sources.filter((file) => file.okf_status === "completed").length,
      active: sources.filter(
        (file) => file.okf_status === "queued" || file.okf_status === "processing",
      ).length,
      failed: sources.filter((file) => file.okf_status === "failed").length,
    }),
    [sources],
  );
  const aggregateProgress = sources.length
    ? Math.round((counts.indexed / sources.length) * 100)
    : 0;

  return (
    <section className="mx-auto max-w-7xl space-y-8 p-6 lg:p-10">
      <header className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
        <div className="max-w-2xl">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-primary">
            Workspace knowledge
          </p>
          <h1>Knowledge library</h1>
          <p className="mt-3 text-base text-copy">
            Keep workspace answers grounded in your team&apos;s documents. Upload sources, monitor
            indexing, and manage access in one place.
          </p>
        </div>
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "Total sources", value: sources.length, detail: "Uploaded documents" },
          { label: "Indexing now", value: counts.active, detail: "Being prepared for chat" },
          { label: "Needs attention", value: counts.failed, detail: "Failed uploads" },
        ].map((stat) => (
          <div className="rounded-2xl border border-border bg-secondary/60 p-5" key={stat.label}>
            <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight">{stat.value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{stat.detail}</p>
          </div>
        ))}
      </div>

      <Upload />

      <div className="space-y-4">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              Source management
            </p>
            <h2 className="mt-2 text-2xl">Your sources</h2>
            <p className="mt-1 text-sm text-copy">
              {counts.indexed} of {sources.length} sources indexed and ready for chat
            </p>
          </div>
          <div className="flex items-center gap-3 sm:w-56">
            <Progress value={aggregateProgress} />
            <span className="text-sm font-semibold text-muted-foreground">
              {aggregateProgress}%
            </span>
          </div>
        </div>
        <KnowledgeTable
          onDownload={downloadFile}
          onRemove={(id) => remove.mutate(id)}
          onRetry={(id) => retry.mutate(id)}
          sources={sources}
        />
      </div>
    </section>
  );
}
