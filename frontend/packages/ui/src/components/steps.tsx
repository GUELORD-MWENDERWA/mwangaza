import { cn } from "../lib/cn";

type Step = { label: string; state: "done" | "current" | "todo" };

/** `.steps` des maquettes : fait = vert avec ✓, en cours = lac. */
export function Steps({ steps, className }: { steps: Step[]; className?: string }) {
  return (
    <ol className={cn("flex", className)}>
      {steps.map((step, index) => (
        <li
          key={step.label}
          aria-current={step.state === "current" ? "step" : undefined}
          className={cn(
            "flex flex-1 items-center gap-2.5 text-[.9rem] font-bold after:mr-2.5 after:h-0.5 after:flex-1 after:bg-line after:content-[''] last:after:hidden",
            step.state === "done" && "text-ok",
            step.state === "current" && "text-lake",
            step.state === "todo" && "text-ink-3",
          )}
        >
          <span
            className={cn(
              "grid size-7 shrink-0 place-items-center rounded-full border-2",
              step.state === "done" && "border-ok bg-ok text-white",
              step.state === "current" && "border-lake bg-lake text-white",
              step.state === "todo" && "border-line bg-card",
            )}
            aria-hidden="true"
          >
            {step.state === "done" ? "✓" : index + 1}
          </span>
          {step.label}
        </li>
      ))}
    </ol>
  );
}
