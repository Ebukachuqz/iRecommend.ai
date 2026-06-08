"use client";

import { useEffect, useMemo, useState } from "react";
import { BadgeCheck, ChevronDown, Database, FileJson, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { PersonaPreview } from "@/components/playground/PersonaPreview";
import {
  DEMO_CATEGORIES,
  type DemoCategory,
  type PersonaSelection,
  type UserSummary,
  getPersona,
  listDemoUsersForCategory,
  parsePersona,
} from "@/lib/prototype-api";

type PersonaSelectorProps = {
  value: PersonaSelection | null;
  onChange: (selection: PersonaSelection | null) => void;
  allowColdStart?: boolean;
};

type SelectorMode = "demo" | "custom" | "cold_start";

const categoryLabels = Object.fromEntries(
  DEMO_CATEGORIES.map((category) => [category.value, category.label]),
) as Record<DemoCategory, string>;

function userOptionKey(user: UserSummary) {
  return `${user.user_id}|||${user.category}`;
}

export function PersonaSelector({ value, onChange, allowColdStart = false }: PersonaSelectorProps) {
  const [mode, setMode] = useState<SelectorMode>("demo");
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [usersLoaded, setUsersLoaded] = useState(false);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [demoCategory, setDemoCategory] = useState<DemoCategory>("Health_and_Household");
  const [userLimit, setUserLimit] = useState(20);
  const [selectedUserKey, setSelectedUserKey] = useState("");
  const [personaLoading, setPersonaLoading] = useState(false);
  const [personaError, setPersonaError] = useState<string | null>(null);
  const [rawPersona, setRawPersona] = useState("");
  const [customCategory, setCustomCategory] = useState<DemoCategory>("Electronics");
  const [coldStartCategory, setColdStartCategory] = useState<DemoCategory>("Health_and_Household");
  const [coldStartInterests, setColdStartInterests] = useState("");
  const [coldStartPriorities, setColdStartPriorities] = useState("");
  const [coldStartDislikes, setColdStartDislikes] = useState("");
  const [coldStartStrictness, setColdStartStrictness] = useState("");
  const [parseLoading, setParseLoading] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);

  async function handleLoadUsers() {
    setUsersLoading(true);
    setUsersLoaded(false);
    setUsersError(null);
    setPersonaError(null);
    setSelectedUserKey("");
    onChange(null);

    listDemoUsersForCategory(demoCategory, userLimit)
      .then((rows) => {
        setUsers(rows);
        setUsersLoaded(true);
        setUsersError(rows.length ? null : "No demo personas were returned by the prototype API.");
      })
      .catch((error) => {
        setUsers([]);
        setUsersError(error instanceof Error ? error.message : "Unable to load demo users.");
      })
      .finally(() => {
        setUsersLoading(false);
      });
  }

  const selectedUser = useMemo(
    () => users.find((user) => userOptionKey(user) === selectedUserKey),
    [selectedUserKey, users],
  );

  useEffect(() => {
    if (!allowColdStart && mode === "cold_start") {
      setMode("demo");
      onChange(null);
    }
  }, [allowColdStart, mode, onChange]);

  useEffect(() => {
    if (mode !== "cold_start") {
      return;
    }
    onChange({
      mode: "cold_start",
      category: coldStartCategory,
      onboardingAnswers: buildColdStartAnswers(),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    mode,
    coldStartCategory,
    coldStartInterests,
    coldStartPriorities,
    coldStartDislikes,
    coldStartStrictness,
  ]);

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

  function switchMode(nextMode: SelectorMode) {
    setMode(nextMode);
    onChange(null);
    if (nextMode === "cold_start") {
      onChange({
        mode: "cold_start",
        category: coldStartCategory,
        onboardingAnswers: buildColdStartAnswers(),
      });
    }
  }

  function commaTerms(value: string) {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function buildColdStartAnswers() {
    const answers: Record<string, unknown> = {};
    if (commaTerms(coldStartInterests).length) {
      answers.interests = commaTerms(coldStartInterests);
    }
    if (commaTerms(coldStartPriorities).length) {
      answers.priorities = commaTerms(coldStartPriorities);
    }
    if (commaTerms(coldStartDislikes).length) {
      answers.dislikes = commaTerms(coldStartDislikes);
    }
    if (coldStartStrictness) {
      answers.rating_strictness = coldStartStrictness;
    }
    return answers;
  }

  const activeSelection = value?.mode === mode ? value : null;
  const gridColumns = allowColdStart ? "grid-cols-3" : "grid-cols-2";

  return (
    <div className="command-card p-4">
      <div>
        <p className="text-body-sm font-semibold text-text-primary">Customer persona</p>
        <p className="mt-1 text-body-xs text-text-secondary">
          Choose demo behaviour or paste your own customer profile.
        </p>
      </div>

      <div className={`mt-4 grid ${gridColumns} rounded-md border border-border bg-surface-0 p-1`}>
        <button
          type="button"
          onClick={() => switchMode("demo")}
          className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-body-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
            mode === "demo"
              ? "bg-surface-1 text-primary"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          <Database className="h-4 w-4" />
          <span className="hidden sm:inline">Select from Database</span>
          <span className="sm:hidden">Database</span>
        </button>
        <button
          type="button"
          onClick={() => switchMode("custom")}
          className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-body-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
            mode === "custom"
              ? "bg-surface-1 text-primary"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          <FileJson className="h-4 w-4" />
          {allowColdStart ? "Custom Persona" : "Custom Input"}
        </button>
        {allowColdStart && (
          <button
            type="button"
            onClick={() => switchMode("cold_start")}
            className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-body-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
              mode === "cold_start"
                ? "bg-surface-1 text-primary"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            No Persona
          </button>
        )}
      </div>

      {mode === "demo" ? (
        <div className="mt-4 space-y-4">
          <label className="block">
            <span className="text-label-sm text-text-muted">
              Category
            </span>
            <div className="relative mt-2">
              <select
                value={demoCategory}
                onChange={(event) => {
                  setDemoCategory(event.target.value as DemoCategory);
                  setUsers([]);
                  setUsersLoaded(false);
                  setSelectedUserKey("");
                  onChange(null);
                }}
                className="h-11 w-full appearance-none rounded-md border border-border bg-surface-1 px-3 pr-9 text-body-md text-text-primary outline-none transition-colors hover:border-border-strong focus:border-primary focus:shadow-[0_0_0_3px_var(--color-primary-light)]"
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

          <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <label className="block">
              <span className="text-label-sm text-text-muted">
                Limit
              </span>
              <Input
                type="number"
                min={1}
                max={100}
                step={1}
                value={userLimit}
                onChange={(event) =>
                  setUserLimit(Math.max(1, Math.min(100, Number(event.target.value) || 1)))
                }
                className="mt-2"
              />
            </label>
            <Button
              type="button"
              variant="outline"
              disabled={usersLoading}
              onClick={() => void handleLoadUsers()}
              className="h-10"
            >
              {usersLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Loading...
                </>
              ) : (
                "Load users"
              )}
            </Button>
          </div>

          <label className="block">
            <span className="text-label-sm text-text-muted">
              Demo user
            </span>
            <div className="relative mt-2">
              <select
                value={selectedUserKey}
                disabled={usersLoading || !users.length}
                onChange={(event) => void handleDemoSelection(event.target.value)}
                className="h-11 w-full appearance-none rounded-md border border-border bg-surface-1 px-3 pr-9 text-body-md text-text-primary outline-none transition-colors hover:border-border-strong focus:border-primary focus:shadow-[0_0_0_3px_var(--color-primary-light)] disabled:cursor-not-allowed disabled:text-text-muted"
              >
                <option value="">
                  {usersLoading
                    ? "Loading demo customers..."
                    : users.length
                      ? "Select a demo customer"
                      : "Load users to begin"}
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
            <p className="rounded-lg bg-primary-light px-3 py-2 text-body-xs font-medium text-primary">
              Demo data selected from {categoryLabels[selectedUser.category as DemoCategory] || selectedUser.category}.
            </p>
          )}

          {!usersLoaded && !usersError && (
            <p className="rounded-lg bg-surface-0 px-3 py-2 text-body-xs text-text-secondary">
              Select a category and click Load users to begin.
            </p>
          )}

          {usersError && <p className="text-body-sm text-error-text">{usersError}</p>}
          {personaError && <p className="text-body-sm text-error-text">{personaError}</p>}
          {personaLoading && (
            <p className="flex items-center gap-2 text-body-sm text-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading persona...
            </p>
          )}
        </div>
      ) : mode === "custom" ? (
        <div className="mt-4 space-y-4">
          <label className="block">
            <span className="text-label-sm text-text-muted">
              Persona text
            </span>
            <Textarea
              value={rawPersona}
              onChange={(event) => setRawPersona(event.target.value)}
              rows={5}
              placeholder={
                'Paste a persona as JSON, or describe a user in plain text.\nExample: "A detail-oriented reviewer who values build quality and rarely gives 5 stars. Buys mostly electronics."'
              }
              className="mt-2 resize-none"
            />
          </label>

          <label className="block">
            <span className="text-label-sm text-text-muted">
              Demo category context
            </span>
            <div className="relative mt-2">
              <select
                value={customCategory}
                onChange={(event) => setCustomCategory(event.target.value as DemoCategory)}
                className="h-11 w-full appearance-none rounded-md border border-border bg-surface-1 px-3 pr-9 text-body-md text-text-primary outline-none transition-colors hover:border-border-strong focus:border-primary focus:shadow-[0_0_0_3px_var(--color-primary-light)]"
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
            className="w-full"
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

          {parseError && <p className="text-body-sm text-error-text">{parseError}</p>}
          {activeSelection?.mode === "custom" && (
            <p className="inline-flex h-5 items-center gap-2 rounded-full bg-primary-light px-2 text-label-sm text-primary">
              <BadgeCheck className="h-3.5 w-3.5" />
              Ready
            </p>
          )}
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <p className="rounded-lg bg-surface-0 px-3 py-2 text-body-sm text-text-secondary">
            No persona is required. Add optional starter signals, then describe what you are looking for in the request box.
          </p>

          <label className="block">
            <span className="text-label-sm text-text-muted">
              Category
            </span>
            <div className="relative mt-2">
              <select
                value={coldStartCategory}
                onChange={(event) => {
                  const nextCategory = event.target.value as DemoCategory;
                  setColdStartCategory(nextCategory);
                }}
                className="h-11 w-full appearance-none rounded-md border border-border bg-surface-1 px-3 pr-9 text-body-md text-text-primary outline-none transition-colors hover:border-border-strong focus:border-primary focus:shadow-[0_0_0_3px_var(--color-primary-light)]"
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

          <div className="grid gap-3 md:grid-cols-2">
            <Input
              value={coldStartInterests}
              onChange={(event) => {
                setColdStartInterests(event.target.value);
              }}
              placeholder="Interests: skincare, electronics"
            />
            <Input
              value={coldStartPriorities}
              onChange={(event) => {
                setColdStartPriorities(event.target.value);
              }}
              placeholder="Priorities: durable, affordable"
            />
            <Input
              value={coldStartDislikes}
              onChange={(event) => {
                setColdStartDislikes(event.target.value);
              }}
              placeholder="Avoid: flimsy build"
            />
            <select
              value={coldStartStrictness}
              onChange={(event) => {
                setColdStartStrictness(event.target.value);
              }}
              className="h-10 w-full rounded-md border border-border bg-surface-1 px-3 text-body-md text-text-primary outline-none transition-colors hover:border-border-strong focus:border-primary focus:shadow-[0_0_0_3px_var(--color-primary-light)]"
            >
              <option value="">Rating strictness</option>
              <option value="strict">Strict</option>
              <option value="moderate">Moderate</option>
              <option value="generous">Generous</option>
            </select>
          </div>
        </div>
      )}

      {activeSelection && activeSelection.mode !== "cold_start" && (
        <div className="mt-4">
          <PersonaPreview
            persona={activeSelection.persona || {}}
            averageRating={activeSelection.personaRow?.average_rating}
          />
        </div>
      )}
    </div>
  );
}
