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

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
        // Stay on signup if the SaaS API cannot confirm organisation state yet.
      }
    });
    return () => {
      mounted = false;
    };
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (!fullName.trim() || !email.trim() || password.length < 8) {
      setError("Enter your name, email, and a password with 8 or more characters.");
      return;
    }

    setLoading(true);
    const supabase = createBrowserClient();
    const { data, error: signUpError } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: {
        data: {
          full_name: fullName.trim(),
        },
      },
    });
    setLoading(false);

    if (signUpError) {
      setError(signUpError.message);
      return;
    }

    if (!data.session) {
      setNotice("Account created. Check your email to confirm your account, then log in.");
      return;
    }

    try {
      const result = await getMyOrganisation(data.session.access_token);
      router.replace(result.organisation ? "/dashboard" : "/onboarding");
      router.refresh();
    } catch (orgError) {
      setError(orgError instanceof Error ? orgError.message : "We could not check your organisation yet. Try again.");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <section className="w-full max-w-[420px] rounded-xl border border-border bg-surface p-8 shadow-sm">
        <div className="flex justify-center">
          <Logo />
        </div>

        <div className="mt-8 text-center">
          <h1 className="font-display text-2xl font-semibold text-text-primary">Create your account</h1>
          <p className="mt-2 text-sm text-text-secondary">Start understanding your customers.</p>
        </div>

        <form className="mt-8 space-y-5" onSubmit={(event) => void handleSubmit(event)}>
          <label className="block">
            <span className="text-sm font-medium text-text-primary">Full name</span>
            <Input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
              className="violet-focus-ring mt-2"
              placeholder="Ada Merchant"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-text-primary">Email</span>
            <Input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              className="violet-focus-ring mt-2"
              placeholder="you@store.com"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-text-primary">Password</span>
            <div className="relative mt-2">
              <Input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={8}
                className="violet-focus-ring pr-11"
                placeholder="8 or more characters"
              />
              <button
                type="button"
                className="violet-focus-ring absolute right-2 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-text-muted hover:text-text-primary"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <p className="mt-2 text-xs text-text-muted">8 or more characters</p>
          </label>

          <Button
            type="submit"
            disabled={loading}
            className="violet-focus-ring h-11 w-full bg-primary text-white hover:bg-primary-hover"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating account...
              </>
            ) : (
              "Create account"
            )}
          </Button>

          {error && <p className="text-sm font-medium text-error">{error}</p>}
          {notice && <p className="text-sm font-medium text-success">{notice}</p>}
        </form>

        <p className="mt-6 text-center text-sm text-text-secondary">
          Already have an account?{" "}
          <Link href="/auth/login" className="font-semibold text-primary underline-offset-4 hover:underline">
            Log in
          </Link>
        </p>
      </section>
    </main>
  );
}
