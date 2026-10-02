"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { useChangePassword, useGetCurrentUser, useUpdateProfile } from "@/services/auth";
import { endSession, getStoredToken } from "@/utils/auth-storage";
import { THEMES, type ThemeId, getTheme, setTheme } from "@/utils/theme";

type ProfileForm = { display_name: string };
type PasswordForm = { current_password: string; new_password: string; confirm_password: string };
type SettingsSection = "profile" | "security" | "appearance";

export default function ProfileSettingsPage() {
  const [token, setToken] = useState("");
  const [activeSection, setActiveSection] = useState<SettingsSection>("profile");
  const [passwordError, setPasswordError] = useState("");
  const [theme, setThemeState] = useState<ThemeId>("clay");
  const me = useGetCurrentUser(token);
  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();
  const profileForm = useForm<ProfileForm>({ defaultValues: { display_name: "" } });
  const passwordForm = useForm<PasswordForm>({
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  useEffect(() => setToken(getStoredToken("peka_access_token") ?? ""), []);
  useEffect(() => setThemeState(getTheme()), []);

  function chooseTheme(id: ThemeId) {
    setTheme(id);
    setThemeState(id);
  }
  useEffect(() => {
    if (me.data) profileForm.reset({ display_name: me.data.display_name });
  }, [me.data, profileForm]);

  function submitProfile(values: ProfileForm) {
    updateProfile.mutate(
      { display_name: values.display_name },
      {
        onSuccess: (user) => {
          profileForm.reset({ display_name: user.display_name });
          toast.add({ title: "Profile saved.", type: "success" });
        },
        onError: () => toast.add({ title: "Unable to save your profile.", type: "error" }),
      },
    );
  }

  function submitPassword({ current_password, new_password }: PasswordForm) {
    setPasswordError("");
    changePassword.mutate(
      { current_password, new_password },
      {
        onSuccess: () => {
          toast.add({
            title: "Password updated. Sign in with your new password.",
            type: "success",
          });
          // Let the toast be read before the full page load that ends the session.
          window.setTimeout(endSession, 1500);
        },
        onError: () => setPasswordError("Current password is incorrect or the change failed."),
      },
    );
  }

  if (!me.data) return <section className="p-6 text-sm text-muted">Loading profile…</section>;

  return (
    <section className="mx-auto max-w-6xl space-y-8 p-6 lg:p-10">
      <header className="max-w-2xl">
        <p className="text-sm font-medium text-primary">Your account</p>
        <h1 className="mt-2 text-2xl font-semibold">Account settings</h1>
        <p className="mt-2 text-sm text-muted">
          Manage your profile and sign-in details. These changes affect only your account.
        </p>
      </header>

      <div className="grid gap-8 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="space-y-5">
          <nav aria-label="Account settings sections" className="grid gap-1">
            {(
              [
                ["profile", "Profile", "Name and account details"],
                ["security", "Security", "Password and sessions"],
                ["appearance", "Appearance", "Theme for this browser"],
              ] as const
            ).map(([id, label, hint]) => (
              <button
                key={id}
                aria-pressed={activeSection === id}
                className={`rounded-lg border px-4 py-3 text-left text-sm font-medium transition-colors ${
                  activeSection === id
                    ? "border-border bg-background text-foreground"
                    : "border-transparent text-foreground hover:bg-secondary"
                }`}
                type="button"
                onClick={() => setActiveSection(id)}
              >
                {label}
                <span className="mt-1 block text-xs font-normal text-muted">{hint}</span>
              </button>
            ))}
          </nav>
          {me.data.role === "admin" && (
            <div className="rounded-xl border border-border bg-secondary/50 p-4">
              <p className="text-sm font-semibold">Workspace settings</p>
              <p className="mt-1 text-xs leading-5 text-muted">
                Manage shared AI and search provider configuration for everyone.
              </p>
              <Link
                className="mt-4 inline-flex h-9 w-full items-center justify-center rounded-lg border border-border bg-background px-3 text-sm font-medium hover:bg-secondary"
                href="/workspace/admin/settings"
              >
                Open workspace settings
              </Link>
            </div>
          )}
        </aside>

        <div className="min-w-0 space-y-6">
          {activeSection === "appearance" ? (
            <section
              id="appearance"
              className="rounded-xl border border-border bg-background p-5 sm:p-7"
            >
              <div className="mb-6 border-b border-border pb-5">
                <h2 className="text-lg font-semibold">Appearance</h2>
                <p className="mt-1 text-sm text-muted">
                  Pick a theme. It applies right away and is saved on this browser.
                </p>
              </div>
              <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-2">
                {THEMES.map((option) => (
                  <button
                    key={option.id}
                    role="radio"
                    aria-checked={theme === option.id}
                    className={`flex items-center gap-4 rounded-lg border p-4 text-left transition-colors ${
                      theme === option.id
                        ? "border-primary ring-1 ring-primary"
                        : "border-border hover:bg-secondary"
                    }`}
                    type="button"
                    onClick={() => chooseTheme(option.id)}
                  >
                    <span className="flex shrink-0 overflow-hidden rounded-md border border-border">
                      {option.swatch.map((color) => (
                        <span key={color} className="size-6" style={{ background: color }} />
                      ))}
                    </span>
                    <span>
                      <span className="block text-sm font-medium">{option.label}</span>
                      <span className="block text-xs text-muted">{option.description}</span>
                    </span>
                  </button>
                ))}
              </div>
            </section>
          ) : activeSection === "profile" ? (
            <section
              id="profile"
              className="rounded-xl border border-border bg-background p-5 sm:p-7"
            >
              <div className="mb-6 border-b border-border pb-5">
                <h2 className="text-lg font-semibold">Profile</h2>
                <p className="mt-1 text-sm text-muted">
                  This information identifies you in the workspace.
                </p>
              </div>
              <div className="mb-6 grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-xs font-medium text-muted">Email</p>
                  <p className="mt-1 text-sm">{me.data.email}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-muted">Role</p>
                  <p className="mt-1 text-sm capitalize">{me.data.role}</p>
                </div>
              </div>
              <form
                className="grid max-w-xl gap-4"
                onSubmit={profileForm.handleSubmit(submitProfile)}
              >
                <label className="grid gap-2 text-sm font-medium" htmlFor="display-name">
                  Display name
                  <Input
                    id="display-name"
                    maxLength={100}
                    autoComplete="name"
                    {...profileForm.register("display_name", {
                      required: true,
                      minLength: 1,
                      maxLength: 100,
                    })}
                  />
                </label>
                <div className="flex flex-wrap items-center gap-4">
                  <Button
                    type="submit"
                    disabled={updateProfile.isPending || !profileForm.formState.isDirty}
                  >
                    {updateProfile.isPending ? "Saving…" : "Save profile"}
                  </Button>
                </div>
              </form>
            </section>
          ) : (
            <section
              id="security"
              className="scroll-mt-6 rounded-xl border border-border bg-background p-5 sm:p-7"
            >
              <div className="mb-6 border-b border-border pb-5">
                <h2 className="text-lg font-semibold">Security</h2>
                <p className="mt-1 text-sm text-muted">
                  Choose a strong password you do not use for other accounts.
                </p>
              </div>
              <form
                className="grid max-w-xl gap-4"
                onSubmit={passwordForm.handleSubmit(submitPassword)}
              >
                <label className="grid gap-2 text-sm font-medium" htmlFor="current-password">
                  Current password
                  <Input
                    id="current-password"
                    type="password"
                    autoComplete="current-password"
                    {...passwordForm.register("current_password", { required: true })}
                  />
                </label>
                <label className="grid gap-2 text-sm font-medium" htmlFor="new-password">
                  New password
                  <Input
                    id="new-password"
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    {...passwordForm.register("new_password", {
                      required: true,
                      minLength: 12,
                      deps: ["confirm_password"],
                    })}
                  />
                  <span className="text-xs font-normal text-muted">
                    Use at least 12 characters.
                  </span>
                </label>
                <label className="grid gap-2 text-sm font-medium" htmlFor="confirm-password">
                  Confirm new password
                  <Input
                    id="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    {...passwordForm.register("confirm_password", {
                      required: true,
                      validate: (value) =>
                        value === passwordForm.getValues("new_password") ||
                        "Passwords do not match",
                    })}
                  />
                </label>
                {passwordForm.formState.errors.confirm_password && (
                  <p role="alert" className="text-sm text-danger">
                    {passwordForm.formState.errors.confirm_password.message}
                  </p>
                )}
                {passwordError && (
                  <p role="alert" className="text-sm text-danger">
                    {passwordError}
                  </p>
                )}
                <p className="text-xs text-muted">
                  You’ll be signed out on all devices after changing your password.
                </p>
                <Button
                  className="justify-self-start"
                  type="submit"
                  disabled={changePassword.isPending}
                >
                  {changePassword.isPending ? "Updating password…" : "Update password"}
                </Button>
              </form>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}
