import Image from "next/image";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PublicNavigation() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background">
      <nav
        aria-label="Primary navigation"
        className="flex h-18.5 items-center justify-between px-6"
      >
        <Link
          aria-label="Peka home"
          className="inline-flex items-center gap-2 text-2xl font-bold tracking-tight text-foreground"
          href="/"
        >
          <Image src="/peka.svg" alt="" aria-hidden="true" width={22} height={22} />
          peka
        </Link>
        <div className="flex items-center gap-4">
          <Link className={cn(buttonVariants({ variant: "default", size: "sm" }))} href="/workspace">
            Open workspace
          </Link>
        </div>
      </nav>
    </header>
  );
}
