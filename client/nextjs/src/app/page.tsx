import Link from "next/link";
import { ArrowRight, BarChart3, FileSpreadsheet, Rocket, Upload, Users } from "lucide-react";

import { HeroMetrics } from "@/components/landing/HeroMetrics";
import { Navbar } from "@/components/layout/Navbar";

const steps = [
  {
    number: "01",
    title: "Upload your data",
    description: "Connect a CSV of your customer reviews. We detect your columns and guide you through the mapping.",
    icon: Upload,
  },
  {
    number: "02",
    title: "Personas are built",
    description: "Understand why customers buy, complain, compare, and hesitate.",
    icon: Users,
  },
  {
    number: "03",
    title: "Simulate decisions",
    description: "Test launch ideas against real customer behaviour before inventory is committed.",
    icon: BarChart3,
  },
];

const integrations = [
  { label: "CSV", active: true },
  { label: "Shopify", active: false },
  { label: "WooCommerce", active: false },
  { label: "API", active: false },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-text-primary">
      <Navbar />

      <section className="bg-background px-4 py-24 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl items-center gap-16 lg:grid-cols-2">
          <div>
            <p className="text-label-lg uppercase text-primary">Customer Intelligence for Modern Merchants</p>
            <h1 className="mt-5 font-display text-display-md text-text-primary sm:text-display-xl">
              Know your customers before they tell you.
            </h1>
            <p className="mt-6 max-w-xl text-body-xl text-text-secondary">
              iRecommend turns customer review data into behavioural personas, launch simulations, and recommendation intelligence that helps merchants make clearer product decisions.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/playground"
                className="btn-press inline-flex h-11 items-center justify-center rounded-md bg-primary px-5 text-body-sm font-medium text-text-inverse hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                Try the Playground
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
              <Link
                href="/auth/signup"
                className="btn-press inline-flex h-11 items-center justify-center rounded-md border border-border bg-surface-1 px-5 text-body-sm font-medium text-text-primary hover:border-border-strong hover:bg-surface-0"
              >
                Get started free
              </Link>
            </div>
            <p className="mt-3 text-body-xs text-text-muted">No account needed for the Playground</p>
          </div>

          <div className="command-card p-8">
            <HeroMetrics />
            <div className="mt-8 border-t border-border pt-6">
              <p className="text-label-md uppercase text-text-muted">What the engine models</p>
              <ul className="mt-4 space-y-3 text-body-md text-text-secondary">
                <li>Customer values and repeated buying signals</li>
                <li>Complaint patterns and quality expectations</li>
                <li>Rating strictness and likely launch reaction</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-surface-1 px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-2xl">
            <p className="text-label-md uppercase text-text-muted">How it works</p>
            <h2 className="mt-3 font-display text-display-sm text-text-primary sm:text-display-md">
              From raw reviews to clear customer intelligence.
            </h2>
          </div>

          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {steps.map((step) => {
              const Icon = step.icon;
              return (
                <article key={step.title} className="command-card p-6">
                  <div className="flex items-start justify-between">
                    <span className="font-mono text-mono-md text-text-muted">{step.number}</span>
                    <span className="flex h-10 w-10 items-center justify-center rounded-md bg-primary-light text-primary">
                      <Icon className="h-5 w-5" />
                    </span>
                  </div>
                  <h3 className="mt-8 font-display text-heading-lg text-text-primary">{step.title}</h3>
                  <p className="mt-3 text-body-md text-text-secondary">{step.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="bg-background px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl items-center gap-10 lg:grid-cols-2">
          <div>
            <p className="text-label-md uppercase text-primary">Product Launch Simulator</p>
            <h2 className="mt-4 font-display text-display-sm text-text-primary sm:text-display-md">Test before you invest.</h2>
            <p className="mt-5 max-w-xl text-body-lg text-text-secondary">
              Enter a product you have not launched. iRecommend simulates how your existing customers would react: predicted rating, likely complaints, likely praises, and what the response means for your launch.
            </p>
            <Link href="/dashboard/simulator" className="mt-6 inline-flex items-center text-body-sm font-medium text-primary underline-offset-4 hover:underline">
              See it in the simulator
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </div>

          <div className="command-card p-6">
            <div className="flex items-start justify-between gap-4 border-b border-border pb-5">
              <div>
                <p className="text-label-md uppercase text-text-muted">Launch question</p>
                <h3 className="mt-2 font-display text-heading-xl text-text-primary">Will customers trust this product?</h3>
              </div>
              <Rocket className="h-6 w-6 text-primary" />
            </div>
            <div className="mt-6 grid gap-4">
              <div className="rounded-lg border border-border bg-surface-0 p-5">
                <p className="text-label-md uppercase text-text-muted">Likely praise</p>
                <p className="mt-2 text-body-md text-text-primary">Practical value and ease of use are clear.</p>
              </div>
              <div className="rounded-lg border border-border bg-surface-0 p-5">
                <p className="text-label-md uppercase text-text-muted">Likely concern</p>
                <p className="mt-2 text-body-md text-text-primary">Customers need proof that quality holds up.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-surface-1 px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl text-center">
          <h2 className="font-display text-display-sm text-text-primary">Today, CSV. Tomorrow, your entire stack.</h2>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            {integrations.map((item) => (
              <div
                key={item.label}
                className={
                  item.active
                    ? "inline-flex h-9 items-center gap-2 rounded-full bg-primary-light px-4 text-label-sm uppercase text-primary"
                    : "inline-flex h-9 items-center gap-2 rounded-full border border-border bg-surface-1 px-4 text-label-sm uppercase text-text-muted"
                }
              >
                <FileSpreadsheet className="h-4 w-4" />
                {item.label}
                {!item.active ? <span className="text-label-sm text-text-disabled">soon</span> : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-background px-4 py-20 sm:px-6 lg:px-8">
        <div className="command-card mx-auto max-w-4xl p-8 text-center sm:p-12">
          <h2 className="font-display text-display-sm text-text-primary sm:text-display-md">Ready to understand your customers?</h2>
          <p className="mx-auto mt-4 max-w-xl text-body-md text-text-secondary">Takes 5 minutes. Upload a CSV and start turning feedback into customer intelligence.</p>
          <Link
            href="/auth/signup"
            className="btn-press mt-8 inline-flex h-11 items-center justify-center rounded-md bg-primary px-5 text-body-sm font-medium text-text-inverse hover:bg-primary-hover"
          >
            Start for free
          </Link>
        </div>
      </section>

      <footer className="border-t border-border bg-surface-1 px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-6">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <Link href="/" className="flex items-center gap-2" aria-label="iRecommend home">
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary font-display text-heading-sm text-text-inverse">
                i
              </span>
              <span className="font-display text-heading-md text-text-primary">Recommend</span>
            </Link>
            <div className="flex items-center gap-5 text-body-sm text-text-secondary">
              <Link href="/playground" className="hover:text-text-primary">Playground</Link>
              <Link href="/auth/signup" className="hover:text-text-primary">Get started</Link>
            </div>
          </div>
          <p className="text-center text-body-xs text-text-muted">(c) 2026 iRecommend</p>
        </div>
      </footer>
    </main>
  );
}
