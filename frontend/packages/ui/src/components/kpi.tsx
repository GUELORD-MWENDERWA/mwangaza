import type { ReactNode } from "react";

import { cn } from "../lib/cn";
import { Card } from "./card";

const tones = { ok: "text-ok", warn: "text-warn", due: "text-due" };

/** `.kpi` des maquettes : libellé, grand chiffre tabulaire, précision en dessous. */
export function Kpi({
  label,
  value,
  sub,
  tone,
  className,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: keyof typeof tones;
  className?: string;
}) {
  return (
    <Card className={cn("px-[18px] py-4", className)}>
      <p className="text-sm text-ink-2">{label}</p>
      <p className={cn("mt-1 text-2xl font-bold tabular-nums", tone && tones[tone])}>{value}</p>
      {sub && <p className="mt-0.5 text-sm break-words text-ink-3">{sub}</p>}
    </Card>
  );
}
