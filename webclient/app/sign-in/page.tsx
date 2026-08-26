"use client";

import Image from "next/image";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import type { LoginFormValues } from "@/interface/auth";
import { useLogin } from "@/services/auth";

export default function SignInPage() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>();
  const login = useLogin();

  function submit(values: LoginFormValues) {
    login.mutate(values, {
      onSuccess: (tokens) => {
        sessionStorage.setItem("peka_access_token", tokens.access_token);
        sessionStorage.setItem("peka_refresh_token", tokens.refresh_token);
        document.cookie = `peka_access_token=${encodeURIComponent(tokens.access_token)}; Max-Age=${tokens.expires_in}; Path=/; SameSite=Lax`;
        router.push("/workspace");
      },
    });
  }

  return (
    <main className="grid min-h-screen bg-background lg:grid-cols-[1fr_0.85fr]">
      <section className="flex flex-col justify-between bg-panel px-[5vw] py-10 text-panel-foreground">
        <div className="flex items-center gap-2 text-xl font-bold tracking-[-0.06em]">
          <span className="grid size-7 place-items-center rounded-full bg-primary">
            <Image
              className="size-5 brightness-0 invert"
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
            <input
              className="rounded-lg border border-border bg-background px-3.5 py-3 text-foreground outline-none focus:border-primary focus:ring-4 focus:ring-primary/15"
              id="password"
              type="password"
              placeholder="Your password"
              autoComplete="current-password"
              {...register("password", { required: "Password is required" })}
            />
            <small className="min-h-4 text-xs text-danger">{errors.password?.message}</small>
          </div>
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
