"use client";

import { useEffect, useMemo, useState } from "react";
import { BadgeCheck, ChevronDown, Database, FileJson, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { PersonaPreview } from "@/components/playground/PersonaPreview";
import {
  DEMO_CATEGORIES,
  type DemoCategory,
  type PersonaSelection,
  type UserSummary,
  getPersona,
  listDemoUsers,
  parsePersona,
} from "@/lib/prototype-api";

type PersonaSelectorProps = {
  value: PersonaSelection | null;
  onChange: (selection: PersonaSelection | null) => void;
};

type SelectorMode = "demo" | "custom";

const categoryLabels = Object.fromEntries(
  DEMO_CATEGORIES.map((category) => [category.value, category.label]),
) as Record<DemoCategory, string>;

function userOptionKey(user: UserSummary) {
  return `${user.user_id}|||${user.category}`;
}

export function PersonaSelector({ value, onChange }: PersonaSelectorProps) {
  const [mode, setMode] = useState<SelectorMode>("demo");
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [selectedUserKey, setSelectedUserKey] = useState("");
  const [personaLoading, setPersonaLoading] = useState(false);
  const [personaError, setPersonaError] = useState<string | null>(null);
  const [rawPersona, setRawPersona] = useState("");
  const [customCategory, setCustomCategory] = useState<DemoCategory>("Electronics");
  const [parseLoading, setParseLoading] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setUsersLoading(true);
    listDemoUsers()
      .then((rows) => {
        if (!mounted) {
          return;
        }
        setUsers(rows);
        setUsersError(rows.length ? null : "No demo personas were returned by the prototype API.");
      })
      .catch((error) => {
        if (!mounted) {
          return;
        }
        setUsersError(error instanceof Error ? error.message : "Unable to load demo users.");
      })
      .finally(() => {
        if (mounted) {
          setUsersLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const selectedUser = useMemo(
    () => users.find((user) => userOptionKey(user) === selectedUserKey),
    [selectedUserKey, users],
  );

  async function handleDemoSelection(nextKey: string) {
    setSelectedUserKey(nextKey);
    setPersonaError(null);
    onChange(null);

    const user = users.find((row) => userOptionKey(row) === nextKey);
    if (!user) {
      return;
    }

    setPersonaLoading(true);
    try {
      const personaRow = await getPersona(user.user_id, user.category);
      onChange({
        mode: "demo",
        userId: user.user_id,
        category: user.category as DemoCategory,
        persona: personaRow.persona || {},
        personaRow,
      });
    } catch (error) {
      setPersonaError(error instanceof Error ? error.message : "Unable to load that persona.");
    } finally {
      setPersonaLoading(false);
    }
  }

  async function handleParsePersona() {
    const text = rawPersona.trim();
    setParseError(null);
    if (!text) {
      setParseError("Paste a persona description first.");
      return;
    }

    setParseLoading(true);
    try {
      const persona = await parsePersona(text);
      onChange({
        mode: "custom",
        category: customCategory,
        persona,
      });
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "Unable to parse persona.");
    } finally {
      setParseLoading(false);
    }
  }

  const activeSelection = value?.mode === mode ? value : null;

  return (
    <div className="command-card p-4">
      <div>
        <p className="text-sm font-semibold text-text-primary">Customer persona</p>
        <p className="mt-1 text-xs text-text-secondary">
          Choose demo behaviour or paste your own customer profile.
        </p>
      </div>

      <div className="mt-4 grid grid-cols-2 rounded-xl border border-border bg-soft-surface p-1">
        <button
          type="button"
          onClick={() => setMode("demo")}
          className={`violet-focus-ring flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${
            mode === "demo"
              ? "bg-surface text-primary shadow-sm"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          <Database className="h-4 w-4" />
          Demo database
        </button>
        <button
          type="button"
          onClick={() => setMode("custom")}
          className={`violet-focus-ring flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${
            mode === "custom"
              ? "bg-surface text-primary shadow-sm"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          <FileJson className="h-4 w-4" />
          Paste your own
        </button>
      </div>

      {mode === "demo" ? (
        <div className="mt-4 space-y-4">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
              Demo user
            </span>
            <div className="relative mt-2">
              <select
                value={selectedUserKey}
                disabled={usersLoading}
                onChange={(event) => void handleDemoSelection(event.target.value)}
                className="violet-focus-ring h-11 w-full appearance-none rounded-lg border border-border bg-surface px-3 pr-9 text-sm text-text-primary outline-none disabled:cursor-not-allowed disabled:text-text-muted"
              >
                <option value="">
                  {usersLoading ? "Loading demo customers..." : "Select a demo customer"}
                </option>
                {users.map((user) => (
                  <option key={userOptionKey(user)} value={userOptionKey(user)}>
                    {user.user_id} - {categoryLabels[user.category as DemoCategory] || user.category}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-text-muted" />
            </div>
          </label>

          {selectedUser && (
            <p className="rounded-lg bg-primary-light px-3 py-2 text-xs font-medium text-primary">
              Demo data selected from {categoryLabels[selectedUser.category as DemoCategory] || selectedUser.category}.
            </p>
          )}

          {usersError && <p className="text-sm text-error">{usersError}</p>}
          {personaError && <p className="text-sm text-error">{personaError}</p>}
          {personaLoading && (
            <p className="flex items-center gap-2 text-sm text-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading persona...
            </p>
          )}
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
              Persona text
            </span>
            <Textarea
              value={rawPersona}
              onChange={(event) => setRawPersona(event.target.value)}
              rows={5}
              placeholder={
                'Paste a persona as JSON, or describe a user in plain text.\nExample: "A detail-oriented reviewer who values build quality and rarely gives 5 stars. Buys mostly electronics."'
              }
              className="violet-focus-ring mt-2 resize-none"
            />
          </label>

          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
              Demo category context
            </span>
            <div className="relative mt-2">
              <select
                value={customCategory}
                onChange={(event) => setCustomCategory(event.target.value as DemoCategory)}
                className="violet-focus-ring h-11 w-full appearance-none rounded-lg border border-border bg-surface px-3 pr-9 text-sm text-text-primary outline-none"
              >
                {DEMO_CATEGORIES.map((category) => (
                  <option key={category.value} value={category.value}>
                    {category.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-text-muted" />
            </div>
          </label>

          <Button
            type="button"
            onClick={() => void handleParsePersona()}
            disabled={parseLoading}
            className="violet-focus-ring w-full bg-primary text-white hover:bg-primary-hover"
          >
            {parseLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Parsing...
              </>
            ) : (
              "Parse persona"
            )}
          </Button>

          {parseError && <p className="text-sm text-error">{parseError}</p>}
          {activeSelection?.mode === "custom" && (
            <p className="inline-flex items-center gap-2 rounded-full bg-primary-light px-3 py-1 text-xs font-semibold text-primary">
              <BadgeCheck className="h-3.5 w-3.5" />
              Ready
            </p>
          )}
        </div>
      )}

      {activeSelection && (
        <div className="mt-4">
          <PersonaPreview
            persona={activeSelection.persona}
            averageRating={activeSelection.personaRow?.average_rating}
          />
        </div>
      )}
    </div>
  );
}
