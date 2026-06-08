"use client";

import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

const navLinkClass =
  "text-body-sm font-medium text-text-secondary transition-colors duration-150 hover:text-text-primary";

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2" aria-label="iRecommend home">
      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary font-display text-heading-sm text-text-inverse">
        i
      </span>
      <span className="font-display text-heading-md text-text-primary">
        Recommend
      </span>
    </Link>
  );
}

export function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 h-16 border-b border-border bg-surface-1">
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
            className="btn-press rounded-md px-3 py-2 text-body-sm font-medium text-text-secondary transition-colors hover:bg-surface-0 hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            Log in
          </Link>
          <Link
            href="/auth/signup"
            className="btn-press rounded-md bg-primary px-4 py-2 text-body-sm font-medium text-text-inverse transition-colors hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            Get started
          </Link>
        </div>

        <button
          type="button"
          className="btn-press inline-flex h-10 w-10 items-center justify-center rounded-md border border-border bg-surface-1 text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      <div
        className={cn(
          "fixed inset-x-0 top-16 z-40 border-b border-border bg-surface-1 px-4 py-4 transition md:hidden",
          open ? "translate-y-0 opacity-100" : "pointer-events-none -translate-y-2 opacity-0",
        )}
      >
        <nav className="flex flex-col gap-2">
          <Link href="/playground" className="rounded-md px-3 py-3 text-body-sm font-medium text-text-primary">
            Playground
          </Link>
          <Link href="/auth/login" className="rounded-md px-3 py-3 text-body-sm font-medium text-text-secondary">
            Log in
          </Link>
          <Link
            href="/auth/signup"
            className="rounded-md bg-primary px-3 py-3 text-center text-body-sm font-medium text-text-inverse"
          >
            Get started
          </Link>
        </nav>
      </div>
    </header>
  );
}

export { Logo };
