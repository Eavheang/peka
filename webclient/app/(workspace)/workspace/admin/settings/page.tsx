"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import {
  type ProviderSettings,
  type ProviderSettingsUpdate,
  useProviderSettings,
  useSaveProviderSettings,
  useTestProvider,
} from "@/services/providerSettings";
import { useServerStatus } from "@/services/status";
import { getApiErrorMessage } from "@/utils/api-error";

import DriveSync from "./_partials/driveSync";
import SettingsSection, { FIELD_LABEL } from "./_partials/settingsSection";

type Provider = "llm" | "exa";
type ProviderForm = Required<ProviderSettingsUpdate>;

const KEEP_KEY_HINT = "Saved. Leave blank to keep it.";
const PROVIDERS = {
  llm: { name: "Language model", fields: ["llm_base_url", "llm_model", "llm_api_key"] },
  exa: { name: "Web search", fields: ["exa_base_url", "exa_api_key"] },
} as const;

function savedForm(saved: ProviderSettings | undefined): ProviderForm {
  return {
    llm_base_url: saved?.llm_base_url ?? "",
    llm_model: saved?.llm_model ?? "",
    llm_api_key: "",
    exa_base_url: saved?.exa_base_url ?? "https://api.exa.ai",
    exa_api_key: "",
  };
}

export default function WorkspaceSettingsPage() {
  // Only unsaved edits; saving one card clears its own and leaves the other card's edits alone.
  const [draft, setDraft] = useState<Partial<ProviderForm>>({});
  const settings = useProviderSettings();
  const saveLlm = useSaveProviderSettings();
  const saveExa = useSaveProviderSettings();
  const test = useTestProvider();
  const { offline } = useServerStatus();
  const providerSettings = settings.data;
  const form = { ...savedForm(providerSettings), ...draft };

  function saveProvider(provider: Provider) {
    const { name, fields } = PROVIDERS[provider];
    // The other card's saved values go along unchanged; a blank API key keeps the saved one.
    const edits = Object.fromEntries(fields.map((key) => [key, form[key]]));
    const { llm_api_key, exa_api_key, ...urls } = { ...savedForm(providerSettings), ...edits };
    const payload: ProviderSettingsUpdate = {
      ...urls,
      llm_api_key: llm_api_key || undefined,
      exa_api_key: exa_api_key || undefined,
    };
    (provider === "llm" ? saveLlm : saveExa).mutate(payload, {
      onSuccess: () => {
        setDraft((current) => {
          const rest = { ...current };
          for (const key of fields) delete rest[key];
          return rest;
        });
        toast.add({ title: `${name} saved.`, type: "success" });
      },
      onError: (error) =>
        toast.add({
          title: getApiErrorMessage(error, `Unable to save the ${name.toLowerCase()} settings.`),
          type: "error",
        }),
    });
  }

  async function testConnection(provider: Provider) {
    const { name } = PROVIDERS[provider];
    try {
      const { ok, status, message } = await test.mutateAsync(provider);
      toast.add({
        title: `${name}: ${message}${status ? ` (HTTP ${status})` : ""}`,
        type: ok ? "success" : "error",
      });
    } catch {
      toast.add({
        title: `${name}: Unable to run the connection test. Check the server is running.`,
        type: "error",
      });
    }
  }

  const field = (key: keyof ProviderForm) => ({
    name: key,
    value: form[key],
    onChange: (event: React.ChangeEvent<HTMLInputElement>) =>
      setDraft((current) => ({ ...current, [key]: event.target.value })),
  });

  const testButton = (provider: Provider, onClick: () => void) => (
    <>
      <Button
        type="button"
        variant="outline"
        disabled={test.isPending}
        aria-disabled={(provider === "exa" && offline) || undefined}
        onClick={onClick}
      >
        Test connection
      </Button>
      <span className="text-xs text-muted">Tests the saved settings.</span>
    </>
  );

  return (
    <div className="flex flex-col gap-6">
      {settings.isLoading ? (
        <div
          role="status"
          aria-label="Loading workspace settings"
          className="h-64 animate-pulse rounded-xl bg-secondary motion-reduce:animate-none"
        />
      ) : settings.isError || !providerSettings ? (
        <p className="text-sm text-danger" role="alert">
          Unable to load workspace settings. Refresh the page to try again.
        </p>
      ) : (
        <>
          <SettingsSection
            title="Language model"
            description="The OpenAI-compatible server PEKA uses to answer questions for everyone in the workspace."
            onSubmit={() => saveProvider("llm")}
            actions={
              <>
                <Button type="submit" disabled={saveLlm.isPending}>
                  {saveLlm.isPending ? "Saving…" : "Save language model"}
                </Button>
                {testButton("llm", () => void testConnection("llm"))}
              </>
            }
          >
            <label className={FIELD_LABEL}>
              Base URL
              <Input
                required
                type="url"
                autoComplete="off"
                spellCheck={false}
                placeholder="e.g. http://llama:8080/v1"
                {...field("llm_base_url")}
              />
            </label>
            <label className={FIELD_LABEL}>
              Model
              <Input
                required
                autoComplete="off"
                spellCheck={false}
                placeholder="e.g. local"
                {...field("llm_model")}
              />
            </label>
            <label className={FIELD_LABEL}>
              API key
              <Input
                type="password"
                autoComplete="new-password"
                placeholder={providerSettings.llm_configured ? "••••••••" : "Enter an API key…"}
                {...field("llm_api_key")}
              />
              {providerSettings.llm_configured && (
                <span className="text-xs font-normal text-muted">{KEEP_KEY_HINT}</span>
              )}
            </label>
          </SettingsSection>

          <SettingsSection
            title="Web search"
            description="Exa lets PEKA search the web when the knowledge base has no answer. Needs internet."
            onSubmit={() => saveProvider("exa")}
            actions={
              <>
                <Button type="submit" disabled={saveExa.isPending}>
                  {saveExa.isPending ? "Saving…" : "Save web search"}
                </Button>
                {testButton("exa", () =>
                  offline
                    ? toast.add({
                        title: "Exa needs internet. PEKA is offline, so the test can’t reach it.",
                        type: "warning",
                      })
                    : void testConnection("exa"),
                )}
              </>
            }
          >
            <label className={FIELD_LABEL}>
              Base URL
              <Input
                required
                type="url"
                autoComplete="off"
                spellCheck={false}
                {...field("exa_base_url")}
              />
            </label>
            <label className={FIELD_LABEL}>
              API key
              <Input
                type="password"
                autoComplete="new-password"
                placeholder={
                  providerSettings.exa_configured ? "••••••••" : "Enter your Exa API key…"
                }
                {...field("exa_api_key")}
              />
              {providerSettings.exa_configured && (
                <span className="text-xs font-normal text-muted">{KEEP_KEY_HINT}</span>
              )}
            </label>
          </SettingsSection>
        </>
      )}
      <DriveSync />
    </div>
  );
}
