import type { ReactNode } from "react";

/** Two columns on wide screens: what a group is, then its controls. */
export const SECTION_GRID = "grid gap-5 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-10";
export const FIELD_LABEL = "flex flex-col gap-1.5 text-sm font-medium";

export default function SettingsSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className={SECTION_GRID}>
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-muted">{description}</p>
      </div>
      <div className="flex min-w-0 flex-col gap-4">{children}</div>
    </section>
  );
}
