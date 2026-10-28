"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { useGetCurrentUser } from "@/services/auth";
import {
  useProviderSettings,
  useSaveProviderSettings,
  useTestProvider,
} from "@/services/providerSettings";
import { getStoredToken } from "@/utils/auth-storage";

export default function ProviderSettingsPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [form, setForm] = useState({
    llm_base_url: "",
    llm_model: "",
    llm_api_key: "",
    exa_base_url: "https://api.exa.ai",
    exa_api_key: "",
  });
  const me = useGetCurrentUser(token);
  const settings = useProviderSettings();
  const save = useSaveProviderSettings();
  const test = useTestProvider();
  const providerSettings = settings.data;

  useEffect(() => setToken(getStoredToken("peka_access_token") ?? ""), []);
  useEffect(() => {
    if (me.data && me.data.role !== "admin") router.replace("/workspace");
  }, [me.data, router]);
  useEffect(() => {
    if (!settings.data) return;
    setForm((current) => ({
      ...current,
      llm_base_url: settings.data.llm_base_url,
      llm_model: settings.data.llm_model,
      exa_base_url: settings.data.exa_base_url,
    }));
  }, [settings.data]);

  if (!me.data || me.data.role !== "admin") return null;
  const inputClass =
    "w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground";

  async function testConnection(provider: "llm" | "exa") {
    try {
      const { ok, status, message } = await test.mutateAsync(provider);
      toast.add({
        title: `${provider.toUpperCase()}: ${message}${status ? ` (HTTP ${status})` : ""}`,
        type: ok ? "success" : "error",
      });
    } catch {
      toast.add({
        title: `${provider.toUpperCase()}: Unable to run connection test.`,
        type: "error",
      });
    }
  }

  return (
    <section className="mx-auto max-w-3xl space-y-8 p-6 lg:p-10">
      <div>
        <Button
          className="border-border"
          type="button"
          variant="outline"
          onClick={() => router.push("/workspace/admin")}
        >
          <ArrowLeft aria-hidden="true" />
          Back
        </Button>
        <h1 className="mt-3 text-2xl font-semibold">Provider settings</h1>
        <p className="mt-1 text-sm text-muted">
          Configure workspace-wide LLM and web search access.
        </p>
      </div>
      {settings.isLoading ? (
        <p className="text-sm text-muted">Loading provider settings…</p>
      ) : settings.isError || !providerSettings ? (
        <p className="text-sm text-danger">Unable to load provider settings.</p>
      ) : (
        <>
          <form
            className="space-y-6"
            onSubmit={(event) => {
              event.preventDefault();
              save.mutate(
                {
                  ...form,
                  llm_api_key: form.llm_api_key || undefined,
                  exa_api_key: form.exa_api_key || undefined,
                },
                {
                  onSuccess: () =>
                    toast.add({ title: "Settings saved.", type: "success" }),
                  onError: () =>
                    toast.add({
                      title: "Unable to save provider settings.",
                      type: "error",
                    }),
                },
              );
            }}
          >
            <fieldset className="space-y-4 rounded-xl border border-border p-5">
              <legend className="px-2 font-semibold">LLM provider</legend>
              <label className="block space-y-1 text-sm">
                OpenAI-compatible base URL
                <input
                  required
                  className={inputClass}
                  value={form.llm_base_url}
                  onChange={(e) =>
                    setForm({ ...form, llm_base_url: e.target.value })
                  }
                />
              </label>
              <label className="block space-y-1 text-sm">
                Model
                <input
                  required
                  className={inputClass}
                  value={form.llm_model}
                  onChange={(e) =>
                    setForm({ ...form, llm_model: e.target.value })
                  }
                />
              </label>
              <label className="block space-y-1 text-sm">
                API key{" "}
                {providerSettings.llm_configured && (
                  <span className="text-muted">
                    (saved; leave blank to keep)
                  </span>
                )}
                <input
                  type="password"
                  autoComplete="new-password"
                  placeholder={
                    providerSettings.llm_configured
                      ? "••••••••"
                      : "Enter API key"
                  }
                  className={inputClass}
                  value={form.llm_api_key}
                  onChange={(e) =>
                    setForm({ ...form, llm_api_key: e.target.value })
                  }
                />
              </label>
              <Button
                type="button"
                variant="outline"
                disabled={test.isPending}
                onClick={() => void testConnection("llm")}
              >
                Test LLM connection
              </Button>
            </fieldset>
            <fieldset className="space-y-4 rounded-xl border border-border p-5">
              <legend className="px-2 font-semibold">Exa web search</legend>
              <label className="block space-y-1 text-sm">
                Base URL
                <input
                  required
                  className={inputClass}
                  value={form.exa_base_url}
                  onChange={(e) =>
                    setForm({ ...form, exa_base_url: e.target.value })
                  }
                />
              </label>
              <label className="block space-y-1 text-sm">
                API key{" "}
                {providerSettings.exa_configured && (
                  <span className="text-muted">
                    (saved; leave blank to keep)
                  </span>
                )}
                <input
                  type="password"
                  autoComplete="new-password"
                  placeholder={
                    providerSettings.exa_configured
                      ? "••••••••"
                      : "Enter API key"
                  }
                  className={inputClass}
                  value={form.exa_api_key}
                  onChange={(e) =>
                    setForm({ ...form, exa_api_key: e.target.value })
                  }
                />
              </label>
              <Button
                type="button"
                variant="outline"
                disabled={test.isPending}
                onClick={() => void testConnection("exa")}
              >
                Test Exa connection
              </Button>
            </fieldset>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save settings"}
            </Button>
          </form>
        </>
      )}
    </section>
  );
}
