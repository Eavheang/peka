"use client";

import axios from "axios";
import { Controller, useForm } from "react-hook-form";
import { toast } from "@/components/ui/toast";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { InvitationResponse, UserRole } from "@/interface/auth";
import { useInviteUser } from "@/services/user";

type InviteUserValues = { email: string; role: UserRole };
type InviteUserProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvited: (invitation: InvitationResponse) => void;
};

export default function InviteUser({ open, onOpenChange, onInvited }: InviteUserProps) {
  const inviteUser = useInviteUser();
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<InviteUserValues>({
    defaultValues: { email: "", role: "staff" },
  });

  function close(nextOpen: boolean) {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  }

  function submit(values: InviteUserValues) {
    inviteUser.mutate(values, {
      onSuccess: (invitation) => {
        close(false);
        onInvited(invitation);
      },
      onError: (error) => {
        const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
        toast.add({
          title: typeof detail === "string" ? detail : "Unable to send invitation.",
          type: "error",
        });
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="w-[calc(100%-2rem)] max-w-md gap-0 overflow-hidden rounded-2xl border-border bg-panel p-0 text-panel-foreground shadow-2xl">
        <div className="p-6">
          <DialogTitle className="text-lg font-semibold tracking-tight text-panel-foreground">
            Invite user
          </DialogTitle>
          <DialogDescription className="mt-2 text-sm leading-6 text-panel-foreground/70">
            They receive a link to choose their own password and are signed in automatically.
          </DialogDescription>
        </div>
        <form
          className="grid gap-3 border-t border-panel-foreground/15 p-6"
          onSubmit={handleSubmit(submit)}
        >
          <Input
            type="email"
            aria-label="Email"
            placeholder="Email"
            autoComplete="off"
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={errors.email ? "invite-email-error" : undefined}
            {...register("email", { required: "Email is required." })}
          />
          {errors.email && (
            <p id="invite-email-error" role="alert" className="text-sm text-panel-danger">
              {errors.email.message}
            </p>
          )}
          <Controller
            control={control}
            name="role"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger aria-label="Role">
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>Role</SelectLabel>
                    <SelectItem value="staff">Staff</SelectItem>
                    <SelectItem value="senior">Senior</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            )}
          />
          <Button
            className="mt-2 px-5 py-3 text-base"
            disabled={inviteUser.isPending}
            type="submit"
          >
            {inviteUser.isPending ? "Sending..." : "Send invitation"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
