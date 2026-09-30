"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import Link from "next/link";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { useAcceptInvitation, useInvitationPreview } from "@/services/auth";
import { storeAuthTokens } from "@/utils/auth-storage";

type AcceptInviteValues = { display_name: string; password: string; confirm_password: string };

export default function AcceptInvitePage() {
  const queryClient = useQueryClient();
  // undefined until the URL is read; null when the link has no token.
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const preview = useInvitationPreview(token ?? null);
  const accept = useAcceptInvitation();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<AcceptInviteValues>({
    defaultValues: { display_name: "", password: "", confirm_password: "" },
  });

  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get("token");
    if (!value) {
      setToken((current) => current ?? null);
      return;
    }
    setToken(value);
    // Keep the one-time token out of the address bar and browser history.
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  function submit({ display_name, password }: AcceptInviteValues) {
    if (!token) return;
    accept.mutate(
      { token, display_name, password },
      {
        onSuccess: (tokens) => {
          // Drop cached data from any previous session in this tab.
          queryClient.clear();
          storeAuthTokens(tokens, false);
          toast.add({ title: "Welcome to PEKA.", type: "success" });
          // Full page load so a cached signed-out redirect for /workspace cannot bounce the user back.
          window.location.replace("/workspace");
        },
        onError: (error) => {
          const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
          toast.add({
            title:
              typeof detail === "string" ? detail : "Unable to finish setting up your account.",
            type: "error",
          });
        },
      },
    );
  }

  const checking = token === undefined || (Boolean(token) && preview.isPending);
  const invalid = token === null || preview.isError;

  return (
    <main className="grid min-h-screen place-items-center bg-background px-7 py-8">
      <div className="w-full max-w-md">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-primary">
          Welcome to peka
        </p>
        {checking ? (
          <p className="mt-3 text-muted" role="status">
            Checking your invitation…
          </p>
        ) : invalid || !preview.data ? (
          <div role="alert">
            <h1 className="mt-3 text-2xl leading-tight">This invitation can&apos;t be used.</h1>
            <p className="mb-6 mt-2 text-muted">
              The link is invalid, has expired or was already used. Ask your admin for a new
              invitation.
            </p>
            <Link className="text-sm text-primary hover:underline" href="/sign-in">
              Go to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit(submit)}>
            <h1 className="mt-3 text-2xl leading-tight">Set up your account</h1>
            <p className="mb-6 mt-2 text-muted">
              You were invited to join as <span className="capitalize">{preview.data.role}</span>.
              Choose a password to finish.
            </p>
            <div className="grid gap-4">
              <div className="grid gap-2">
                <label className="text-xs font-bold" htmlFor="invite-email">
                  Email
                </label>
                <Input id="invite-email" value={preview.data.email} readOnly />
              </div>
              <div className="grid gap-2">
                <label className="text-xs font-bold" htmlFor="display-name">
                  Your name
                </label>
                <Input
                  id="display-name"
                  autoComplete="name"
                  maxLength={100}
                  {...register("display_name", {
                    required: "Name is required",
                    validate: (value) => value.trim().length > 0 || "Name is required",
                  })}
                />
                <small className="min-h-4 text-xs text-danger">
                  {errors.display_name?.message}
                </small>
              </div>
              <div className="grid gap-2">
                <label className="text-xs font-bold" htmlFor="new-password">
                  Password
                </label>
                <Input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  {...register("password", {
                    required: "Password is required",
                    minLength: { value: 12, message: "Use at least 12 characters" },
                    deps: ["confirm_password"],
                  })}
                />
                <small className="min-h-4 text-xs text-danger">{errors.password?.message}</small>
              </div>
              <div className="grid gap-2">
                <label className="text-xs font-bold" htmlFor="confirm-password">
                  Confirm password
                </label>
                <Input
                  id="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  {...register("confirm_password", {
                    required: "Confirm your password",
                    validate: (value) =>
                      value === getValues("password") || "Passwords do not match",
                  })}
                />
                <small className="min-h-4 text-xs text-danger">
                  {errors.confirm_password?.message}
                </small>
              </div>
            </div>
            <Button className="mt-5 w-full" type="submit" disabled={accept.isPending} size="lg">
              {accept.isPending ? "Creating account..." : "Create account and sign in"}
            </Button>
          </form>
        )}
      </div>
    </main>
  );
}
