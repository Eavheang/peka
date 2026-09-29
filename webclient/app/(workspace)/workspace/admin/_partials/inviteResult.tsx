"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import type { InvitationResponse } from "@/interface/auth";

type InviteResultProps = { invitation: InvitationResponse | null; onClose: () => void };

export default function InviteResult({ invitation, onClose }: InviteResultProps) {
  async function copyLink() {
    if (!invitation) return;
    try {
      await navigator.clipboard.writeText(invitation.invite_url);
      toast.add({ title: "Invitation link copied.", type: "success" });
    } catch {
      toast.add({ title: "Unable to copy. Select the link and copy it manually.", type: "error" });
    }
  }

  const expires = invitation ? new Date(invitation.expires_at).toLocaleDateString() : "";

  return (
    <Dialog open={invitation !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[calc(100%-2rem)] max-w-md gap-0 overflow-hidden rounded-2xl border-border bg-panel p-0 text-panel-foreground shadow-2xl">
        <div className="p-6">
          <DialogTitle className="text-lg font-semibold tracking-tight text-panel-foreground">
            {invitation?.email_sent ? "Invitation sent" : "Invitation created, email not sent"}
          </DialogTitle>
          <DialogDescription className="mt-2 text-sm leading-6 text-panel-foreground/70">
            {invitation?.email_sent
              ? `We emailed ${invitation.email}. The link works until ${expires}.`
              : `Email is not configured or could not be delivered. Copy this link and send it to ${invitation?.email}. It works until ${expires}.`}
          </DialogDescription>
        </div>
        <div className="grid gap-3 border-t border-panel-foreground/15 p-6">
          <Input
            aria-label="Invitation link"
            readOnly
            value={invitation?.invite_url ?? ""}
            onFocus={(event) => event.currentTarget.select()}
          />
          <div className="flex justify-end gap-3">
            <Button
              className="border-panel-foreground/20 bg-transparent px-4 py-2 text-panel-foreground hover:text-panel-foreground"
              onClick={onClose}
              type="button"
              variant="outline"
            >
              Done
            </Button>
            <Button className="px-4 py-2" onClick={copyLink} type="button">
              Copy link
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
