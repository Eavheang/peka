"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import { ArrowLeft, ArrowRight, Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import type { LoginFormValues } from "@/interface/auth";
import { useLogin } from "@/services/auth";
import { storeAuthTokens } from "@/utils/auth-storage";

type SignInFormValues = LoginFormValues & {
  rememberMe: boolean;
};

export default function SignInPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignInFormValues>({
    defaultValues: { rememberMe: false },
  });
  const login = useLogin();
  const queryClient = useQueryClient();
  function submit({ rememberMe, ...credentials }: SignInFormValues) {
    login.mutate(credentials, {
      onSuccess: (tokens) => {
        // Drop cached profile and chat data so a different user never sees the previous user's.
        queryClient.clear();
        storeAuthTokens(tokens, rememberMe);
        toast.add({ title: "Signed in.", type: "success" });
        // Full page load, not router.push: a prefetch of /workspace made while signed out is cached
        // as a redirect to /sign-in, which would bounce the user straight back here.
        const next = new URL(
          new URLSearchParams(window.location.search).get("next") ?? "/workspace",
          window.location.origin,
        );
        window.location.assign(
          next.origin === window.location.origin ? next.pathname + next.search : "/workspace",
        );
      },
      onError: () => toast.add({ title: "Invalid email or password.", type: "error" }),
    });
  }

  return (
    <main className="grid min-h-screen bg-background lg:grid-cols-[1fr_0.85fr]">
      <section className="hidden flex-col justify-between bg-panel px-[5vw] py-10 text-panel-foreground lg:flex">
        <div className="flex items-center gap-2 text-xl font-bold tracking-[-0.06em]">
          <span className="grid size-7 place-items-center rounded-full bg-background">
            <Image className="size-5 " src="/peka.svg" alt="" width={20} height={20} />
          </span>
          peka
        </div>
        <blockquote className="my-16 max-w-xl text-[clamp(2.375rem,5vw,4.0625rem)] leading-[0.97] tracking-[-0.08em]">
          Good answers start with <em className="text-success not-italic">the right context.</em>
        </blockquote>
        <footer className="font-mono text-[11px] text-[#9ba19a]">
          LOCAL RETRIEVAL / EXPLAINABLE RESPONSES / LESS GUESSING
        </footer>
      </section>
      <section className="grid place-items-center px-7 py-8">
        <form className="w-full max-w-xl" onSubmit={handleSubmit(submit)}>
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-primary">Welcome back</p>
          <h1 className="mt-3 text-[34px] leading-none tracking-[-0.07em]">
            Enter your workspace.
          </h1>
          <p className="mb-7 mt-2 max-w-sm text-muted">
            Sign in to continue with your organisation&apos;s private knowledge base.
          </p>
          <div className="mt-4 grid gap-2">
            <label className="text-xs font-bold" htmlFor="email">
              Work email
            </label>
            <Input
              className="rounded-lg px-3.5 py-3"
              id="email"
              type="email"
              placeholder="you@company.com"
              autoComplete="email"
              {...register("email", { required: "Email is required" })}
            />
            <small className="min-h-4 text-xs text-danger">{errors.email?.message}</small>
          </div>
          <div className="mt-1 grid gap-2">
            <label className="text-xs font-bold" htmlFor="password">
              Password
            </label>
            <div className="relative">
              <Input
                className="w-full rounded-lg px-3.5 py-3 pr-11"
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Your password"
                autoComplete="current-password"
                {...register("password", { required: "Password is required" })}
              />
              <button
                className="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted hover:text-foreground"
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                title={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword((visible) => !visible)}
              >
                {showPassword ? (
                  <EyeOff aria-hidden="true" size={17} />
                ) : (
                  <Eye aria-hidden="true" size={17} />
                )}
              </button>
            </div>
            <small className="min-h-4 text-xs text-danger">{errors.password?.message}</small>
          </div>
          <label
            className="mt-2 inline-flex items-center gap-2 text-sm text-muted"
            htmlFor="remember-me"
          >
            <Input
              className="size-4 h-4 w-4 rounded accent-primary p-0 shadow-none"
              id="remember-me"
              type="checkbox"
              {...register("rememberMe")}
            />
            Remember me
          </label>
          {login.isError && <p className="mt-1 text-xs text-danger">Invalid email or password.</p>}
          <Button className="mt-5 w-full" type="submit" disabled={login.isPending} size="lg">
            {login.isPending ? (
              "Signing in..."
            ) : (
              <>
                Continue <ArrowRight aria-hidden="true" size={16} />
              </>
            )}
          </Button>
          <Button
            className="mt-6 inline-flex h-auto items-center gap-1 border-0 bg-transparent p-0 text-sm text-muted hover:bg-transparent hover:text-primary"
            type="button"
            variant="outline"
            onClick={() => router.push("/")}
          >
            <ArrowLeft aria-hidden="true" size={15} />
            Back to peka
          </Button>
        </form>
      </section>
    </main>
  );
}
