"use client";

import { useState } from "react";

import Alertdialog from "@/components/Alertdialog";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import type { InvitationResponse, InvitationSummary } from "@/interface/auth";
import { useListInvitations, useResendInvitation, useRevokeInvitation } from "@/services/user";

type PendingInvitationsProps = { onResent: (invitation: InvitationResponse) => void };

export default function PendingInvitations({ onResent }: PendingInvitationsProps) {
  const [revoking, setRevoking] = useState<InvitationSummary | null>(null);
  const invitations = useListInvitations();
  const resend = useResendInvitation();
  const revoke = useRevokeInvitation();

  function resendInvitation(invitation: InvitationSummary) {
    resend.mutate(invitation.id, {
      onSuccess: onResent,
      onError: () => toast.add({ title: "Unable to resend invitation.", type: "error" }),
    });
  }

  function revokeInvitation() {
    if (!revoking) return;
    revoke.mutate(revoking.id, {
      onSuccess: () =>
        toast.add({ title: `Invitation for ${revoking.email} revoked.`, type: "success" }),
      onError: () => toast.add({ title: "Unable to revoke invitation.", type: "error" }),
      onSettled: () => setRevoking(null),
    });
  }

  if (invitations.isError) {
    return <p className="text-sm text-danger">Unable to load pending invitations.</p>;
  }
  if (!invitations.data?.length) return null;

  return (
    <section aria-labelledby="pending-invitations" className="space-y-3">
      <h2 id="pending-invitations" className="text-lg font-semibold">
        Pending invitations
      </h2>
      <Alertdialog
        open={revoking !== null}
        onOpenChange={(open) => !open && setRevoking(null)}
        title="Revoke invitation?"
        description={`${revoking?.email ?? "This person"} will no longer be able to use their invitation link.`}
        confirmLabel="Revoke"
        onConfirm={revokeInvitation}
        pending={revoke.isPending}
      />
      <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-sm">
        <Table>
          <TableHeader className="bg-secondary/70">
            <TableRow className="border-border hover:bg-secondary/70">
              <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
                Email
              </TableHead>
              <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
                Role
              </TableHead>
              <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
                Expires
              </TableHead>
              <TableHead className="px-5 py-4 text-center text-xs uppercase tracking-[0.14em] text-muted">
                Actions
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invitations.data.map((invitation) => {
              const expired = new Date(invitation.expires_at) < new Date();
              return (
                <TableRow key={invitation.id} className="border-border hover:bg-secondary/40">
                  <TableCell className="px-5 py-4 font-medium text-foreground">
                    {invitation.email}
                  </TableCell>
                  <TableCell className="px-5 py-4 capitalize">{invitation.role}</TableCell>
                  <TableCell className="px-5 py-4">
                    {expired ? (
                      <span className="rounded-full bg-danger/15 px-2.5 py-1 text-xs font-medium text-danger">
                        Expired
                      </span>
                    ) : (
                      new Date(invitation.expires_at).toLocaleDateString()
                    )}
                  </TableCell>
                  <TableCell className="space-x-2 px-5 py-4 text-center">
                    <Button
                      className="border-border hover:bg-secondary"
                      disabled={resend.isPending}
                      onClick={() => resendInvitation(invitation)}
                      type="button"
                      variant="outline"
                    >
                      Resend
                    </Button>
                    <Button
                      className="px-4 py-2.5"
                      onClick={() => setRevoking(invitation)}
                      type="button"
                      variant="destructive"
                    >
                      Revoke
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}
