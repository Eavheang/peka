"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { STEPS, WORKSPACE_TABS } from "@/constants/landing";

function renderStepContent(step: (typeof STEPS)[number], index: number, isTrigger = false) {
  return (
    <>
      <p className="font-mono text-xs uppercase tracking-widest text-primary">{step.tag}</p>
      {index === 0 ? (
        <h1
          id={isTrigger ? "hero-title" : undefined}
          className="max-w-3xl text-6xl font-bold leading-none tracking-tight text-foreground md:text-8xl"
        >
          {step.title}
        </h1>
      ) : (
        <h2
          id={isTrigger ? `hero-step-${index + 1}-title` : undefined}
          className="max-w-3xl text-6xl font-bold leading-none tracking-tight text-foreground md:text-8xl"
        >
          {step.title}
        </h2>
      )}
      <p className="max-w-xl text-lg leading-normal text-copy">{step.description}</p>

      {step.cta ? (
        <nav aria-label="Landing actions" className="flex flex-wrap gap-3">
          <Link
            className={cn(buttonVariants({ variant: "default", size: "lg" }), "rounded-lg")}
            href="/sign-in"
          >
            Start with Peka -&gt;
          </Link>
        </nav>
      ) : (
        <p className="font-mono text-xs text-muted">
          Local-first retrieval · Role-aware sources · Optional cloud model
        </p>
      )}
    </>
  );
}

export function PublicHero() {
  const [activeStep, setActiveStep] = useState(0);
  const stepRefs = useRef<Array<HTMLElement | null>>([]);

  useEffect(() => {
    let frame = 0;

    const updateActiveStep = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const viewportCenter = window.innerHeight / 2;
        let closestStep = 0;
        let closestDistance = Number.POSITIVE_INFINITY;

        stepRefs.current.forEach((step, index) => {
          if (!step) return;

          const rect = step.getBoundingClientRect();
          const distance = Math.abs(rect.top + rect.height / 2 - viewportCenter);

          if (distance < closestDistance) {
            closestStep = index;
            closestDistance = distance;
          }
        });

        setActiveStep((currentStep) => (currentStep === closestStep ? currentStep : closestStep));
      });
    };

    updateActiveStep();
    window.addEventListener("scroll", updateActiveStep, { passive: true });
    window.addEventListener("resize", updateActiveStep);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", updateActiveStep);
      window.removeEventListener("resize", updateActiveStep);
    };
  }, []);

  const step = STEPS[activeStep];

  return (
    <section
      aria-labelledby="hero-title"
      className="mx-auto grid min-h-dvh w-full items-center gap-12 px-6 lg:grid-cols-2 lg:gap-16"
    >
      <div className="relative lg:min-h-[calc(3*(100dvh-6rem))]">
        <div className="sticky top-24 z-10 hidden h-[calc(100dvh-6rem)] max-w-2xl flex-col justify-center gap-5 lg:flex">
          {renderStepContent(step, activeStep)}
        </div>
        <div className="lg:-mt-[calc(100dvh-6rem)]">
          {STEPS.map((item, index) => (
            <article
              key={item.tag}
              ref={(node) => {
                stepRefs.current[index] = node;
              }}
              aria-labelledby={index === 0 ? "hero-title" : `hero-step-${index + 1}-title`}
              className="flex min-h-[calc(100dvh-6rem)] max-w-2xl flex-col justify-center gap-5 py-16 lg:opacity-0"
            >
              {renderStepContent(item, index, true)}
            </article>
          ))}
        </div>
      </div>

      <div className="relative order-first self-start lg:order-last lg:min-h-[calc(3*(100dvh-6rem))]">
        <div className="sticky top-24 lg:flex lg:h-[calc(100dvh-6rem)] lg:flex-col lg:justify-center">
          <section
            aria-label="Peka chat preview"
            className="rotate-1 rounded-2xl bg-panel p-4.5 text-panel-foreground shadow-2xl"
          >
            <p className="absolute -top-8 right-0 font-mono text-xs text-muted">
              A small window into the workspace ↗
            </p>
            <header className="flex items-center justify-between border-b border-panel-foreground/15 pb-4.5">
              <strong className="tracking-tight">peka</strong>
              <p className="flex items-center gap-2 font-mono text-xs text-success">
                <Badge
                  aria-label="Knowledge base active"
                  className="border-success/40 text-success"
                  variant="outline"
                >
                  <span aria-hidden="true" className="size-1.5 rounded-full bg-success" />
                  ACTIVE
                </Badge>
              </p>
            </header>
            <section className="grid min-h-95 md:grid-cols-4">
              <aside className="hidden border-r border-panel-foreground/15 py-5 pr-4 md:col-span-1 md:block">
                <p className="mb-4 font-mono text-xs uppercase tracking-widest text-panel-foreground/70">
                  Workspace
                </p>
                <ul className="grid gap-1 text-xs text-panel-foreground/75">
                  {WORKSPACE_TABS.map((tab) => (
                    <li
                      key={tab}
                      className={cn(
                        "rounded-md px-2.5 py-2",
                        step.activeTab === tab
                          ? "bg-panel-foreground/10 text-panel-foreground"
                          : "text-panel-foreground/75",
                      )}
                    >
                      {tab}
                    </li>
                  ))}
                </ul>
                <p className="mb-3 mt-7 font-mono text-xs uppercase tracking-widest text-panel-foreground/70">
                  Recent
                </p>
                <ul className="grid gap-2 text-xs text-panel-foreground/75">
                  <li>Q3 planning notes</li>
                  <li>Onboarding checklist</li>
                </ul>
              </aside>
              <section className="flex min-h-91.25 flex-col justify-between px-4.5 py-6 md:col-span-3 md:px-6.5">
                <article className="flex flex-col gap-6" aria-live="polite">
                  <h2 className="text-xl font-semibold tracking-tight">What can I find for you?</h2>
                  <p className="ml-auto max-w-sm rounded-lg bg-panel-foreground/10 px-3.5 py-3 text-xs leading-normal text-panel-foreground/80">
                    {step.query}
                  </p>
                  <section className="flex max-w-lg flex-col gap-3">
                    <p className="text-xs leading-relaxed text-panel-foreground/90">
                      {step.response}
                    </p>
                    <cite className="w-fit rounded bg-panel-foreground/10 px-2 py-1.5 font-mono text-xs not-italic text-success">
                      {step.citation}
                    </cite>
                  </section>
                </article>
                <p className="rounded-lg border border-panel-foreground/20 px-3 py-3 text-xs text-panel-foreground/60">
                  Ask about your knowledge base ↗
                </p>
              </section>
            </section>
          </section>
        </div>
      </div>
    </section>
  );
}
