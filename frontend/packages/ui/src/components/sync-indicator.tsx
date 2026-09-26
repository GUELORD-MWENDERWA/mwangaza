import { cn } from "../lib/cn";

/** `.sync` des maquettes : toujours visible en haut de la Gestion. En 1.6 : en ligne ou non ;
 *  opérations en attente et dernière synchronisation avec la 3.4. */
export function SyncIndicator({
  online,
  label,
  className,
}: {
  online: boolean;
  label: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={cn(
        "flex items-center gap-2 rounded-full px-3 py-1.5 text-sm whitespace-nowrap",
        online ? "bg-ok-50 text-ok" : "bg-warn-50 text-warn",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn("size-[9px] rounded-full", online ? "bg-ok" : "bg-warn")}
      />
      {label}
    </div>
  );
}
