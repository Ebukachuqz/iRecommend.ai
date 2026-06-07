import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  FileSpreadsheet,
  Rocket,
  Upload,
  Users,
} from "lucide-react";

import { Navbar } from "@/components/layout/Navbar";
import { HeroMetrics } from "@/components/landing/HeroMetrics";

const steps = [
  {
    number: "01",
    title: "Upload your data",
    description:
      "Connect a CSV of your customer reviews. We detect your columns and guide you through the mapping.",
    icon: Upload,
  },
  {
    number: "02",
    title: "Personas are built",
    description:
      "Our LLM analyses each customer's behaviour: what they value, how strict they are, and what makes them complain.",
    icon: Users,
  },
  {
    number: "03",
    title: "Intelligence unlocked",
    description:
      "Simulate new product launches. Browse customer profiles. Power recommendations with real behavioural context.",
    icon: BarChart3,
  },
];

const integrations = [
  { label: "CSV", active: true },
  { label: "Shopify", active: false },
  { label: "WooCommerce", active: false },
  { label: "API", active: false },
];

const reactions = [
  "Likely buyer: Values comfort and notices build quality quickly.",
  "Cautious buyer: Would compare it against cheaper alternatives.",
  "Power user: Would praise ergonomics if the battery life holds up.",
];

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-text-primary">
      <Navbar />

      <section className="flex min-h-[calc(100vh-64px)] items-center bg-background px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-5xl">
          <div className="aurora-panel px-5 py-14 text-center shadow-[0_26px_80px_rgba(91,33,182,0.22)] sm:px-10 sm:py-16">
            <div className="relative z-10 mx-auto max-w-4xl">
          <p className="mb-5 text-[13px] font-bold uppercase tracking-[0.22em] text-white/80">
            Customer Intelligence for Modern Merchants
          </p>
          <h1 className="font-display text-[40px] font-bold leading-[1.05] tracking-tight text-white sm:text-6xl lg:text-[64px]">
            Know your customers.
            <br />
            <span className="inline-block border-b-[3px] border-white leading-[1.08]">
              Before
            </span>{" "}
            they tell you.
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-8 text-white/80">
            iRecommend builds behavioural personas from customer review data.
            Understand what your customers value, predict how they&apos;ll react
            to new products, and power recommendations that actually fit them.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/playground"
              className="inline-flex h-12 items-center justify-center rounded-lg bg-white px-6 text-sm font-semibold text-primary shadow-[0_12px_28px_rgba(17,24,39,0.18)] transition-colors hover:bg-primary-light"
            >
              Try the Playground
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
            <Link
              href="/auth/signup"
              className="inline-flex h-12 items-center justify-center rounded-lg border border-white/25 bg-white/10 px-6 text-sm font-semibold text-white transition-colors hover:bg-white/15"
            >
              Get started free
            </Link>
          </div>
          <p className="mt-3 text-xs font-medium text-white/70">
            No account needed for the Playground
          </p>

          <HeroMetrics />
            </div>
          </div>
        </div>
      </section>

      <section className="bg-surface px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <p className="text-sm font-medium text-text-muted">How it works</p>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
              From raw reviews to real insight.
            </h2>
          </div>

          <div className="mt-14 grid gap-5 md:grid-cols-3">
            {steps.map((step) => {
              const Icon = step.icon;
              return (
                <article
                  key={step.title}
                  className="command-card p-6"
                >
                  <div className="flex items-start justify-between">
                    <span className="font-display text-5xl font-bold text-primary">
                      {step.number}
                    </span>
                    <span className="flex h-11 w-11 items-center justify-center rounded-full bg-primary-light text-primary">
                      <Icon className="h-5 w-5" />
                    </span>
                  </div>
                  <h3 className="mt-8 font-display text-xl font-semibold text-text-primary">
                    {step.title}
                  </h3>
                  <p className="mt-3 leading-7 text-text-secondary">
                    {step.description}
                  </p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="bg-background px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-6xl items-center gap-10 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-primary">
              Product Launch Simulator
            </p>
            <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
              Test before you invest.
            </h2>
            <p className="mt-5 max-w-xl text-lg leading-8 text-text-secondary">
              Enter a product you haven&apos;t launched. iRecommend simulates
              how your existing customers would react: predicted rating, likely
              complaints, likely praises. Before a single unit is manufactured.
            </p>
            <Link
              href="/dashboard/simulator"
              className="mt-6 inline-flex items-center border-b border-primary pb-1 text-sm font-semibold text-primary"
            >
              See it in the simulator
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </div>

          <div className="violet-glow-card rounded-2xl p-5">
            <div className="flex items-start justify-between gap-4 border-b border-border pb-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Product
                </p>
                <h3 className="mt-2 font-display text-xl font-semibold text-text-primary">
                  Wireless Ergonomic Mouse - $49.99
                </h3>
              </div>
              <span className="rounded-full bg-primary-light px-3 py-1 text-xs font-semibold text-primary">
                Sample
              </span>
            </div>

            <div className="grid gap-4 py-5 sm:grid-cols-2">
              <div className="aurora-panel rounded-2xl p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-white/70">
                  Predicted rating
                </p>
                <p className="mt-2 text-2xl font-bold text-white">
                  ★★★★☆ <span className="text-white">4.1 / 5</span>
                </p>
              </div>
              <div className="command-card bg-soft-surface p-4 shadow-none">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
                  Launch read
                </p>
                <p className="mt-2 text-sm font-medium leading-6 text-text-secondary">
                  Strong fit for comfort-driven customers, with quality concerns
                  to fix before launch.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="command-card p-4 shadow-none">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-error">
                  Most likely complaint
                </p>
                <p className="mt-1 text-sm text-text-primary">
                  Scroll wheel feels cheap
                </p>
              </div>
              <div className="command-card p-4 shadow-none">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-success">
                  Most likely praise
                </p>
                <p className="mt-1 text-sm text-text-primary">
                  Comfortable for long sessions
                </p>
              </div>
            </div>

            <div className="mt-5 grid gap-3">
              {reactions.map((reaction) => (
                <blockquote
                  key={reaction}
                  className="rounded-lg bg-primary-light px-4 py-3 text-sm leading-6 text-text-primary"
                >
                  &ldquo;{reaction}&rdquo;
                </blockquote>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="bg-surface px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl text-center">
          <h2 className="font-display text-3xl font-bold tracking-tight text-text-primary">
            Today, CSV. Tomorrow, your entire stack.
          </h2>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            {integrations.map((item) => (
              <div
                key={item.label}
                className={
                  item.active
                    ? "violet-glow-card inline-flex items-center gap-2 rounded-full border-primary bg-primary-light px-4 py-2 text-sm font-semibold text-primary"
                    : "inline-flex items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-semibold text-text-muted"
                }
              >
                <FileSpreadsheet className="h-4 w-4" />
                {item.label}
                {!item.active && (
                  <span className="rounded-full bg-surface px-2 py-0.5 text-[10px] uppercase tracking-wide">
                    coming soon
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-background px-4 py-20 sm:px-6 lg:px-8">
        <div className="aurora-panel mx-auto max-w-4xl px-6 py-16 text-center shadow-[0_24px_70px_rgba(91,33,182,0.2)] sm:px-10">
          <div className="relative z-10">
          <Rocket className="mx-auto h-8 w-8" />
          <h2 className="mt-5 font-display text-3xl font-bold tracking-tight sm:text-4xl">
            Ready to understand your customers?
          </h2>
          <Link
            href="/auth/signup"
            className="mt-8 inline-flex h-12 items-center justify-center rounded-lg bg-white px-6 text-sm font-semibold text-primary transition-colors hover:bg-primary-light"
          >
            Start for free
          </Link>
          <p className="mt-4 text-sm text-white/80">
            Takes 5 minutes. Upload a CSV and go.
          </p>
          </div>
        </div>
      </section>

      <footer className="border-t border-border bg-surface px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-6">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <Link href="/" className="flex items-center gap-2" aria-label="iRecommend home">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary font-display text-lg font-bold text-white">
                i
              </span>
              <span className="font-display text-lg font-semibold text-text-primary">
                Recommend
              </span>
            </Link>
            <div className="flex items-center gap-5 text-sm font-medium text-text-secondary">
              <Link href="/playground" className="hover:text-text-primary">
                Playground
              </Link>
              <Link href="/auth/signup" className="hover:text-text-primary">
                Get started
              </Link>
            </div>
          </div>
          <p className="text-center text-xs text-text-muted">© 2026 iRecommend</p>
        </div>
      </footer>
    </main>
  );
}
