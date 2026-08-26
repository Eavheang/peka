"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowLeft, ArrowRight, Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
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

  function submit({ rememberMe, ...credentials }: SignInFormValues) {
    login.mutate(credentials, {
      onSuccess: (tokens) => {
        storeAuthTokens(tokens, rememberMe);
        router.push("/workspace");
      },
    });
  }

  return (
    <main className="grid min-h-screen bg-background lg:grid-cols-[1fr_0.85fr]">
      <section className="flex flex-col justify-between bg-panel px-[5vw] py-10 text-panel-foreground">
        <div className="flex items-center gap-2 text-xl font-bold tracking-[-0.06em]">
          <span className="grid size-7 place-items-center rounded-full bg-background">
            <Image
              className="size-5 "
              src="/peka.svg"
              alt=""
              width={20}
              height={20}
            />
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
            <input
              className="rounded-lg border border-border bg-background px-3.5 py-3 text-foreground outline-none focus:border-primary focus:ring-4 focus:ring-primary/15"
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
              <input
                className="w-full rounded-lg border border-border bg-background px-3.5 py-3 pr-11 text-foreground outline-none focus:border-primary focus:ring-4 focus:ring-primary/15"
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
          <label className="mt-2 inline-flex items-center gap-2 text-sm text-muted" htmlFor="remember-me">
            <input
              className="size-4 accent-primary"
              id="remember-me"
              type="checkbox"
              {...register("rememberMe")}
            />
            Remember me
          </label>
          {login.isError && <p className="mt-1 text-xs text-danger">Invalid email or password.</p>}
          <Button className="mt-5 w-full" type="submit" disabled={login.isPending}>
            {login.isPending ? (
              "Signing in..."
            ) : (
              <>
                Continue <ArrowRight aria-hidden="true" size={16} />
              </>
            )}
          </Button>
          <button
            className="mt-6 inline-flex items-center gap-1 border-0 bg-transparent p-0 text-sm text-muted hover:text-primary"
            type="button"
            onClick={() => router.push("/")}
          >
            <ArrowLeft aria-hidden="true" size={15} />
            Back to peka
          </button>
        </form>
      </section>
    </main>
  );
}
