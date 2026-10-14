import { cn } from "../lib/cn";

const tones = {
  ok: ["bg-ok-50 text-ok", "bg-ok"],
  warn: ["bg-warn-50 text-warn", "bg-warn"],
  due: ["bg-due-50 text-due", "bg-due"],
} as const;

/** `.sync` des maquettes : toujours visible en haut de la Gestion. `ok` : en ligne ; `warn` :
 *  hors ligne ; `due` : opérations refusées par le serveur. */
export function SyncIndicator({
  tone,
  label,
  className,
}: {
  tone: keyof typeof tones;
  label: string;
  className?: string;
}) {
  const [box, dot] = tones[tone];
  return (
    <div
      role="status"
      className={cn(
        "flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold whitespace-nowrap",
        box,
        className,
      )}
    >
      <span aria-hidden="true" className={cn("size-[9px] shrink-0 rounded-full", dot)} />
      {label}
    </div>
  );
}
