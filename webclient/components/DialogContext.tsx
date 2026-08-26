"use client";

import type { FormEventHandler, ReactNode } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

type DialogContextProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  onSubmit?: FormEventHandler<HTMLFormElement>;
};

export default function DialogContext({
  open,
  onOpenChange,
  title,
  description,
  children,
  onSubmit,
}: DialogContextProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[calc(100%-2rem)] max-w-md gap-0 overflow-hidden rounded-2xl border-border bg-panel p-0 text-panel-foreground shadow-2xl">
        <div className="p-6">
          <DialogTitle className="text-lg font-semibold tracking-tight text-panel-foreground">
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription className="mt-2 text-sm leading-6 text-panel-foreground/70">
              {description}
            </DialogDescription>
          )}
        </div>
        <form className="grid gap-3 border-t border-panel-foreground/15 p-6" onSubmit={onSubmit}>
          {children}
        </form>
      </DialogContent>
    </Dialog>
  );
}
