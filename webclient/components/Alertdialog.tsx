"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

type AlertdialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  pending?: boolean;
};

export default function Alertdialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Okay",
  cancelLabel = "Cancel",
  onConfirm,
  pending = false,
}: AlertdialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[calc(100%-2rem)] max-w-md gap-0 overflow-hidden rounded-2xl border-border bg-panel p-0 text-panel-foreground shadow-2xl">
        <div className="p-6">
          <DialogTitle className="text-lg font-semibold tracking-tight text-panel-foreground">
            {title}
          </DialogTitle>
          <DialogDescription className="mt-2 text-sm leading-6 text-panel-foreground/70">
            {description}
          </DialogDescription>
        </div>
        <div className="flex items-center justify-end gap-3 border-t border-panel-foreground/15 bg-panel/90 px-6 py-4">
          <Button
            className="border-panel-foreground/20 bg-transparent px-4 py-2 text-panel-foreground hover:text-panel-foreground"
            onClick={() => onOpenChange(false)}
            type="button"
            variant="outline"
          >
            {cancelLabel}
          </Button>
          <Button
            className="bg-danger px-4 py-2 text-danger-foreground hover:bg-danger/90"
            disabled={pending}
            onClick={onConfirm}
            type="button"
          >
            {pending ? "Working..." : confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
