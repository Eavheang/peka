import { type FormEvent, type ReactNode, useId } from "react";

export const FIELD_LABEL = "flex flex-col gap-1.5 text-sm font-medium";

/** One feature per card: its own fields and its own save, so saving one never touches another. */
export default function SettingsSection({
  title,
  description,
  onSubmit,
  actions,
  children,
}: {
  title: string;
  description: string;
  onSubmit: () => void;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="overflow-hidden rounded-xl border border-border">
      <form
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <div className="flex flex-col gap-5 p-5 sm:p-6">
          <div>
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            <p className="mt-1 max-w-prose text-sm text-pretty text-muted">{description}</p>
          </div>
          <div className="flex min-w-0 flex-col gap-4">{children}</div>
        </div>
        {actions && (
          <div className="flex flex-wrap items-center gap-3 border-t border-border bg-secondary/40 px-5 py-3 sm:px-6">
            {actions}
          </div>
        )}
      </form>
    </section>
  );
}
