"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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
  const pathname = usePathname();

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
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-border bg-surface-1">
      <div className="flex h-16 items-center border-b border-border px-6">
        <Logo />
      </div>

      <nav className="flex-1 px-4 py-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/dashboard"
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          const className = cn(
            "mb-0.5 flex h-9 w-full items-center gap-2.5 rounded-md px-3 text-body-sm font-medium transition-colors duration-150",
            item.locked
              ? "cursor-not-allowed text-text-disabled"
              : isActive
                ? "bg-primary-light text-primary"
                : "text-text-secondary hover:bg-surface-0 hover:text-text-primary",
          );

          if (item.locked) {
            return (
              <div
                key={item.label}
                className={className}
                title="Customer segmentation - coming soon"
                aria-disabled="true"
              >
                <Icon className="h-4 w-4" />
                <span className="flex-1 truncate">{item.label}</span>
                <span className="inline-flex h-5 items-center gap-1 rounded-full border border-border px-2 text-label-sm text-text-disabled">
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
          <p className="truncate text-body-sm font-semibold text-text-primary">{orgName}</p>
          <p className="truncate text-body-xs text-text-muted">{userEmail}</p>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="btn-press flex h-9 w-full items-center justify-center gap-2 rounded-md border border-border bg-surface-1 px-3 text-body-sm font-medium text-text-secondary transition-colors hover:bg-surface-0 hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <LogOut className="h-4 w-4" />
          Log out
        </button>
      </div>
    </aside>
  );
}
