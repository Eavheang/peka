"use client";

import { Button, Card } from "@heroui/react";
import { Globe3D, type GlobeMarker } from "@/components/ui/3d-globe";

const globeMarkers: GlobeMarker[] = [
  { lat: 40.7128, lng: -74.006, src: "https://assets.aceternity.com/avatars/1.webp", label: "New York" },
  { lat: 51.5074, lng: -0.1278, src: "https://assets.aceternity.com/avatars/2.webp", label: "London" },
  { lat: 35.6762, lng: 139.6503, src: "https://assets.aceternity.com/avatars/3.webp", label: "Tokyo" },
  { lat: -33.8688, lng: 151.2093, src: "https://assets.aceternity.com/avatars/4.webp", label: "Sydney" },
  { lat: 48.8566, lng: 2.3522, src: "https://assets.aceternity.com/avatars/5.webp", label: "Paris" },
  { lat: 1.3521, lng: 103.8198, src: "https://assets.aceternity.com/avatars/6.webp", label: "Singapore" },
];

const features = [
  {
    icon: "✦",
    title: "Meet anywhere",
    description: "Find people, ideas, and opportunities beyond your usual circle.",
  },
  {
    icon: "↗",
    title: "Move faster",
    description: "Turn a quick introduction into your next meaningful connection.",
  },
  {
    icon: "◎",
    title: "Stay in sync",
    description: "Keep every conversation and collaboration moving forward.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen w-full overflow-hidden bg-background text-foreground transition-colors">
      <header className="mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-5 sm:px-8 lg:px-10">
        <a href="#top" className="flex items-center gap-2 text-lg font-bold tracking-tight">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-lg text-primary-foreground shadow-lg shadow-primary/20">P</span>
          PEKA
        </a>
         <div className="hidden items-center gap-8 text-sm text-muted md:flex">
          <a className="transition-colors hover:text-foreground" href="#how-it-works">How it works</a>
          <a className="transition-colors hover:text-foreground" href="#features">Features</a>
          <a className="transition-colors hover:text-foreground" href="#about">About</a>
        </div>
      </header>

      <section id="top" className="relative mx-auto grid w-full max-w-7xl items-center gap-14 px-5 pb-20 pt-12 sm:px-8 md:pb-28 md:pt-20 lg:grid-cols-[0.9fr_1.1fr] lg:px-10 lg:pt-28">
        <article className="relative z-10 max-w-2xl">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-default bg-surface px-3 py-1.5 text-xs font-medium text-muted shadow-sm">
            <span className="size-1.5 rounded-full bg-success" /> Built for people who think globally
          </div>
          <h1 className="max-w-xl text-5xl font-semibold tracking-[-0.055em] text-balance sm:text-6xl lg:text-7xl">
            Your next connection is <span className="text-primary">closer</span> than you think.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-muted sm:text-lg">
            PEKA makes it simple to discover people and possibilities that move your world forward.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button size="lg">Start exploring <span aria-hidden>→</span></Button>
            <Button size="lg" variant="secondary">See how it works</Button>
          </div>
          <aside className="mt-10 flex items-center gap-3 text-sm text-muted">
            <ul className="flex -space-x-2" aria-label="PEKA community members">
              {["#f2b5a7", "#91b8c8", "#d9c18d", "#b7a5ce"].map((color, index) => (
                <li key={color} className="size-8 rounded-full border-2 border-background" style={{ backgroundColor: color }} aria-label={`Community member ${index + 1}`} />
              ))}
            </ul>
            <span><strong className="text-foreground">12,000+</strong> people already exploring</span>
          </aside>
        </article>

        <section className="relative min-h-[clamp(28rem,70vw,37rem)] w-full" aria-label="PEKA global connections">
          <span className="absolute inset-8 rounded-[2.5rem] bg-primary/10 blur-3xl" aria-hidden />
          <Card className="absolute inset-0 overflow-hidden border-default/70 shadow-2xl shadow-primary/10 backdrop-blur-xl bg-background text-foreground" variant="tertiary">
            <article className="relative flex h-full flex-col justify-between gap-4 p-4 sm:p-8">
              <header className="flex items-center justify-between gap-3">
                <div><p className="text-xs font-medium text-muted">DISCOVER YOUR WORLD</p><p className="mt-1 text-xl font-semibold">People are waiting</p></div>
                <span className="rounded-full bg-success/15 px-3 py-1 text-xs font-medium text-success">Live now</span>
              </header>
              <figure className="relative mx-auto flex w-full flex-1 items-center justify-center overflow-hidden">
                <Globe3D
                  className="size-[min(78vw,24rem)] max-w-full sm:size-[min(42vw,26rem)]"
                  markers={globeMarkers}
                  config={{
                    atmosphereColor: "#4da6ff",
                    atmosphereIntensity: 1,
                    bumpScale: 5,
                    autoRotateSpeed: 0.3,
                    showAtmosphere: true,
                  }}
                />
              </figure>
              <footer className="flex items-center justify-between gap-3 rounded-2xl border border-default bg-background/70 p-3 backdrop-blur">
                <div><p className="text-xs text-muted">Connections nearby</p><p className="font-semibold">2,438 active today</p></div>
                <Button isIconOnly aria-label="Explore connections" size="sm">↗</Button>
              </footer>
            </article>
          </Card>
        </section>
      </section>

      <section id="features" className="w-full bg-background text-foreground">
        <div className="mx-auto grid w-full max-w-7xl gap-px px-5 sm:grid-cols-3 sm:px-8 lg:px-10 ">
          {features.map((feature) => (
            <Card key={feature.title} className="rounded-none border-0 bg-transparent py-8 shadow-none sm:py-12" variant="tertiary">
              <div className="mb-5 flex size-10 items-center justify-center rounded-xl bg-primary/10 text-lg text-primary">{feature.icon}</div>
              <h2 className="text-lg font-semibold">{feature.title}</h2>
              <p className="mt-2 max-w-xs text-sm leading-6 text-muted">{feature.description}</p>
            </Card>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="mx-auto w-full max-w-7xl px-5 py-20 sm:px-8 lg:px-10 lg:py-28">
        <div className="grid gap-10 rounded-[2rem] bg-primary px-6 py-12 text-primary-foreground sm:px-12 lg:grid-cols-[1fr_auto] lg:items-center lg:px-16">
          <div><p className="text-sm font-medium opacity-75">MAKE YOUR NEXT MOVE</p><h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">Good things happen when you look beyond the obvious.</h2></div>
          <Button className="bg-background text-foreground hover:bg-background/90" size="lg">Join PEKA <span aria-hidden>→</span></Button>
        </div>
      </section>

      <footer id="about" className="mx-auto flex w-full max-w-7xl flex-col gap-4 border-t border-default px-5 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-10">
        <span className="font-semibold text-foreground">PEKA</span><span>Connect with what comes next.</span><span>© 2026 PEKA</span>
      </footer>
    </main>
  );
}
