"use client";

import { useState } from "react";
import { Download, ExternalLink, LoaderCircle } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { Citation } from "@/interface/chat";
import { downloadCitation, useSourcePreview } from "@/services/chat";

export function SourcePreview({ citation, number }: { citation: Citation; number: number }) {
  const [open, setOpen] = useState(false);

  if (citation.url) {
    return (
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger className="text-left text-xs leading-5 text-copy hover:text-foreground hover:underline underline-offset-4">
          <span className="font-medium text-foreground">
            [{number}] {citation.title}
          </span>
        </DialogTrigger>
        <DialogContent className="max-h-[85dvh] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden bg-background text-foreground sm:max-w-2xl">
          <DialogHeader className="min-w-0 pr-8">
            <DialogTitle className="break-words leading-6 [overflow-wrap:anywhere]">
              {citation.title}
            </DialogTitle>
            <DialogDescription>Web source</DialogDescription>
          </DialogHeader>
          <div className="citation-scroll min-h-0 overflow-y-auto border-t border-border pt-4 pr-4">
            <CitationMarkdown
              content={citation.excerpt || "No preview excerpt is available for this source."}
            />
          </div>
          <a
            className="inline-flex w-fit items-center gap-2 text-sm font-medium text-primary hover:underline underline-offset-4"
            href={citation.url}
            rel="noreferrer"
            target="_blank"
          >
            Open original source
            <ExternalLink aria-hidden="true" size={14} />
          </a>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger className="text-left text-xs leading-5 text-copy hover:text-foreground hover:underline underline-offset-4">
        <span className="font-medium text-foreground">
          [{number}] {citation.title}
        </span>
        {citation.heading && ` · ${citation.heading}`}
      </DialogTrigger>
      <DialogContent className="max-h-[85dvh] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden bg-background text-foreground sm:max-w-3xl">
        <DialogHeader className="min-w-0 pr-8">
          <DialogTitle className="break-words leading-6 [overflow-wrap:anywhere]">
            {citation.title}
          </DialogTitle>
          <DialogDescription>
            {citation.heading || "Cited excerpt"}
          </DialogDescription>
        </DialogHeader>
        {open && <SourcePreviewContent citation={citation} />}
      </DialogContent>
    </Dialog>
  );
}

function SourcePreviewContent({ citation }: { citation: Citation }) {
  const preview = useSourcePreview(citation);
  const fileId = citation.file_id ?? preview.data?.file_id;
  const previewContent = preview.isPending ? (
    <div className="flex min-h-0 items-center gap-2 py-8 text-sm text-muted" role="status">
      <LoaderCircle aria-hidden="true" className="animate-spin" size={16} />
      Loading source excerpt…
    </div>
  ) : preview.isError ? (
    <div className="flex min-h-0 flex-col items-start gap-3 py-4">
      <p className="text-sm text-copy" role="alert">
        This excerpt could not be loaded. It may have changed, be unavailable, or no longer be
        accessible.
      </p>
      <Button variant="outline" onClick={() => preview.refetch()}>
        Try again
      </Button>
    </div>
  ) : (
    <div className="citation-scroll min-h-0 overflow-y-auto overscroll-contain border-t border-border pt-4 pr-4">
      <CitationMarkdown content={preview.data.content} />
    </div>
  );

  return (
    <>
      {previewContent}
      {fileId && <SourceDownloadButton fileId={fileId} filename={citation.title} />}
    </>
  );
}

function SourceDownloadButton({ fileId, filename }: { fileId: string; filename: string }) {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(false);

  async function handleDownload() {
    setIsDownloading(true);
    setDownloadError(false);
    try {
      await downloadCitation(fileId, filename);
    } catch {
      setDownloadError(true);
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
      <Button disabled={isDownloading} onClick={handleDownload} variant="outline">
        <Download aria-hidden="true" />
        {isDownloading ? "Preparing download…" : "Download original file"}
      </Button>
      {downloadError && (
        <p className="text-sm text-destructive" role="alert">
          The file could not be downloaded. Please try again.
        </p>
      )}
    </div>
  );
}

function CitationMarkdown({ content }: { content: string }) {
  return (
    <div className="break-words text-sm leading-7 text-copy [&_h1]:my-4 [&_h1]:text-xl [&_h2]:my-4 [&_h2]:text-lg [&_h3]:my-3 [&_h3]:text-base [&_p]:my-3 [&_p]:text-sm [&_p]:leading-7 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_li]:my-1 [&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-4 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-secondary [&_pre]:p-3 [&_code]:text-xs [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-border [&_th]:bg-secondary [&_th]:p-2 [&_th]:text-left [&_td]:border [&_td]:border-border [&_td]:p-2 [&_hr]:my-4 [&_hr]:border-border">
      <Markdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        disallowedElements={["img", "a"]}
        unwrapDisallowed
      >
        {cleanCitationExcerpt(content)}
      </Markdown>
    </div>
  );
}

function cleanCitationExcerpt(content: string): string {
  return content
    .replace(/^\s*(?:\.\.\.|…)\s*$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
