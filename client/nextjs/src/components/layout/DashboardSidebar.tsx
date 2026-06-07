"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Lock,
  LogOut,
  PieChart,
  Rocket,
  Upload,
  Users,
} from "lucide-react";
import { createBrowserClient } from "@supabase/ssr";

import { cn } from "@/lib/utils";
import { Logo } from "@/components/layout/Navbar";

type DashboardSidebarProps = {
  orgName?: string | null;
  userEmail?: string | null;
};

const navItems = [
  {
    label: "Overview",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "Customers",
    href: "/dashboard/customers",
    icon: Users,
  },
  {
    label: "Upload data",
    href: "/dashboard/upload",
    icon: Upload,
  },
  {
    label: "Segments",
    href: "/dashboard/segments",
    icon: PieChart,
    locked: true,
  },
  {
    label: "Launch Simulator",
    href: "/dashboard/simulator",
    icon: Rocket,
  },
];

export function DashboardSidebar({
  orgName = "Demo organisation",
  userEmail = "merchant@example.com",
}: DashboardSidebarProps) {
  const router = useRouter();

  async function handleLogout() {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    if (supabaseUrl && supabaseAnonKey) {
      const supabase = createBrowserClient(supabaseUrl, supabaseAnonKey);
      await supabase.auth.signOut();
    }

    router.push("/");
  }

  return (
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-border bg-soft-surface">
      <div className="flex h-16 items-center border-b border-border px-5">
        <Logo />
      </div>

      <nav className="flex-1 space-y-1 px-3 py-5">
        {navItems.map((item) => {
          const Icon = item.icon;
          const className = cn(
            "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
            item.locked
              ? "cursor-not-allowed text-text-muted"
              : "text-text-secondary hover:bg-primary-light hover:text-primary hover:shadow-[0_10px_24px_rgba(91,33,182,0.08)]",
          );

          if (item.locked) {
            return (
              <div
                key={item.label}
                className={className}
                title="Customer segmentation — coming soon"
                aria-disabled="true"
              >
                <Icon className="h-4 w-4" />
                <span className="flex-1 truncate">{item.label}</span>
                <span className="inline-flex items-center gap-1 rounded-full border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-muted">
                  <Lock className="h-3 w-3" />
                </span>
              </div>
            );
          }

          return (
            <Link key={item.label} href={item.href} className={className}>
              <Icon className="h-4 w-4" />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border p-4">
        <div className="mb-3 min-w-0">
          <p className="truncate text-sm font-semibold text-text-primary">{orgName}</p>
          <p className="truncate text-xs text-text-secondary">{userEmail}</p>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="violet-focus-ring flex w-full items-center justify-center gap-2 rounded-lg border bg-surface px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:border-primary-light hover:bg-primary-light hover:text-primary"
        >
          <LogOut className="h-4 w-4" />
          Log out
        </button>
      </div>
    </aside>
  );
}
