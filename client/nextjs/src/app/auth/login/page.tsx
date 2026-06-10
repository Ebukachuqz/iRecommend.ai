"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { Logo } from "@/components/layout/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getMyOrganisation } from "@/lib/saas-api";
import { createBrowserClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const supabase = createBrowserClient();
    supabase.auth.getSession().then(async ({ data }) => {
      const session = data.session;
      if (!mounted || !session) {
        return;
      }
      try {
        const result = await getMyOrganisation(session.access_token);
        router.replace(result.organisation ? "/dashboard" : "/onboarding");
        router.refresh();
      } catch {
        // Stay on login if the SaaS API cannot confirm organisation state yet.
      }
    });
    return () => {
      mounted = false;
    };
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }

    setLoading(true);
    const supabase = createBrowserClient();
    const { data: loginData, error: loginError } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });

    if (loginError) {
      setLoading(false);
      setError(loginError.message);
      return;
    }

    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser();

    if (userError || !user) {
      setLoading(false);
      setError("Login succeeded, but we could not load your account. Try again.");
      return;
    }

    const accessToken = loginData.session?.access_token;
    if (!accessToken) {
      setLoading(false);
      setError("Login succeeded, but no session was returned. Try logging in again.");
      return;
    }

    try {
      const result = await getMyOrganisation(accessToken);
      setLoading(false);
      router.replace(result.organisation ? "/dashboard" : "/onboarding");
      router.refresh();
    } catch (orgError) {
      setLoading(false);
      setError(orgError instanceof Error ? orgError.message : "We could not check your organisation yet. Try again.");
      return;
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <section className="w-full max-w-md rounded-lg border border-border bg-surface-1 p-8">
        <div className="flex justify-center">
          <Logo />
        </div>

        <div className="mt-8 text-center">
          <h1 className="font-display text-heading-xl text-text-primary">Welcome back</h1>
          <p className="mt-2 text-body-sm text-text-secondary">Log in to your merchant dashboard.</p>
        </div>

        <form className="mt-8 space-y-5" onSubmit={(event) => void handleSubmit(event)}>
          <label className="block">
            <span className="text-body-sm font-medium text-text-primary">Email</span>
            <Input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              className="mt-2"
              placeholder="you@store.com"
            />
          </label>

          <label className="block">
            <span className="text-body-sm font-medium text-text-primary">Password</span>
            <div className="relative mt-2">
              <Input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                className="pr-11"
                placeholder="Your password"
              />
              <button
                type="button"
                className="absolute right-2 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-text-muted transition-colors hover:text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </label>

          <Button
            type="submit"
            disabled={loading}
            className="h-11 w-full"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Logging in...
              </>
            ) : (
              "Log in"
            )}
          </Button>

          {error && <p className="text-body-sm font-medium text-error-text">{error}</p>}
        </form>

        <p className="mt-6 text-center text-body-sm text-text-secondary">
          No account?{" "}
          <Link href="/auth/signup" className="font-semibold text-primary underline-offset-4 hover:underline">
            Get started
          </Link>
        </p>
      </section>
    </main>
  );
}
