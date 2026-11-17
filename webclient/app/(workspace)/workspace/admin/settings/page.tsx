"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import {
  useProviderSettings,
  useSaveProviderSettings,
  useTestProvider,
} from "@/services/providerSettings";
import { useServerStatus } from "@/services/status";
import { getApiErrorMessage } from "@/utils/api-error";

import DriveSync from "./_partials/driveSync";
import SettingsSection, { FIELD_LABEL, SECTION_GRID } from "./_partials/settingsSection";

const KEEP_KEY_HINT = "Saved. Leave blank to keep it.";

export default function WorkspaceSettingsPage() {
  const [form, setForm] = useState({
    llm_base_url: "",
    llm_model: "",
    llm_api_key: "",
    exa_base_url: "https://api.exa.ai",
    exa_api_key: "",
  });
  const settings = useProviderSettings();
  const save = useSaveProviderSettings();
  const test = useTestProvider();
  const { offline } = useServerStatus();
  const providerSettings = settings.data;

  useEffect(() => {
    if (!settings.data) return;
    setForm((current) => ({
      ...current,
      llm_base_url: settings.data.llm_base_url,
      llm_model: settings.data.llm_model,
      exa_base_url: settings.data.exa_base_url,
    }));
  }, [settings.data]);

  async function testConnection(provider: "llm" | "exa") {
    const name = provider === "llm" ? "Language model" : "Exa";
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

  const field = (key: keyof typeof form) => ({
    name: key,
    value: form[key],
    onChange: (event: React.ChangeEvent<HTMLInputElement>) =>
      setForm({ ...form, [key]: event.target.value }),
  });

  return (
    <div className="flex flex-col gap-12">
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
        <form
          className="flex flex-col gap-12"
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate(
              {
                ...form,
                llm_api_key: form.llm_api_key || undefined,
                exa_api_key: form.exa_api_key || undefined,
              },
              {
                onSuccess: () => {
                  setForm((current) => ({ ...current, llm_api_key: "", exa_api_key: "" }));
                  toast.add({ title: "Provider settings saved.", type: "success" });
                },
                onError: (error) =>
                  toast.add({
                    title: getApiErrorMessage(error, "Unable to save provider settings."),
                    type: "error",
                  }),
              },
            );
          }}
        >
          <SettingsSection
            title="Language model"
            description="The OpenAI-compatible server PEKA uses to answer questions for everyone in the workspace."
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
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={test.isPending}
                onClick={() => void testConnection("llm")}
              >
                Test connection
              </Button>
              <span className="text-xs text-muted">Tests the saved settings.</span>
            </div>
          </SettingsSection>

          <SettingsSection
            title="Web search"
            description="Exa lets PEKA search the web when the knowledge base has no answer. Needs internet."
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
                placeholder={providerSettings.exa_configured ? "••••••••" : "Enter your Exa API key…"}
                {...field("exa_api_key")}
              />
              {providerSettings.exa_configured && (
                <span className="text-xs font-normal text-muted">{KEEP_KEY_HINT}</span>
              )}
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={test.isPending}
                aria-disabled={offline || undefined}
                onClick={() =>
                  offline
                    ? toast.add({
                        title: "Exa needs internet. PEKA is offline, so the test can’t reach it.",
                        type: "warning",
                      })
                    : void testConnection("exa")
                }
              >
                Test connection
              </Button>
              <span className="text-xs text-muted">Tests the saved settings.</span>
            </div>
          </SettingsSection>

          <div className={`${SECTION_GRID} border-t border-border pt-6`}>
            <div />
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "Saving…" : "Save provider settings"}
              </Button>
              <span className="text-xs text-muted">Saves the language model and web search.</span>
            </div>
          </div>
        </form>
      )}
      <DriveSync />
    </div>
  );
}
