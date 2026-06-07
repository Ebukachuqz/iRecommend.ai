"use client";

import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

const navLinkClass =
  "text-sm font-medium text-text-secondary transition-colors hover:text-text-primary";

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2" aria-label="iRecommend home">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary font-display text-lg font-bold text-white">
        i
      </span>
      <span className="font-display text-lg font-semibold tracking-tight text-text-primary">
        Recommend
      </span>
    </Link>
  );
}

export function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 h-16 border-b border-border bg-surface/95 backdrop-blur">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Logo />

        <nav className="hidden items-center md:flex">
          <Link href="/playground" className={navLinkClass}>
            Playground
          </Link>
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <Link
            href="/auth/login"
            className="violet-focus-ring rounded-lg px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
          >
            Log in
          </Link>
          <Link
            href="/auth/signup"
            className="violet-focus-ring rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-hover"
          >
            Get started
          </Link>
        </div>

        <button
          type="button"
          className="violet-focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border bg-surface text-text-primary md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      <div
        className={cn(
          "fixed inset-x-0 top-16 z-40 border-b border-border bg-surface px-4 py-4 shadow-sm transition md:hidden",
          open ? "translate-y-0 opacity-100" : "pointer-events-none -translate-y-2 opacity-0",
        )}
      >
        <nav className="flex flex-col gap-2">
          <Link href="/playground" className="rounded-lg px-3 py-3 text-sm font-medium text-text-primary">
            Playground
          </Link>
          <Link href="/auth/login" className="rounded-lg px-3 py-3 text-sm font-medium text-text-secondary">
            Log in
          </Link>
          <Link
            href="/auth/signup"
            className="rounded-lg bg-primary px-3 py-3 text-center text-sm font-semibold text-white"
          >
            Get started
          </Link>
        </nav>
      </div>
    </header>
  );
}

export { Logo };
