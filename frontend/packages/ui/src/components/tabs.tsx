import { Tabs as TabsPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.tabs` des maquettes : onglet actif = texte et soulignement de 3 px couleur lac. Flèches du
// clavier pour passer d'un onglet à l'autre (Radix).
export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("flex gap-1 overflow-x-auto border-b border-line", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "-mb-px min-h-11 cursor-pointer border-b-3 border-transparent px-3.5 py-2.5 text-[.92rem] font-bold whitespace-nowrap text-ink-2 hover:text-ink focus-visible:bg-lake-50 focus-visible:outline-none data-[state=active]:border-lake data-[state=active]:text-lake",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn("mt-5 flex flex-col gap-5 focus-visible:outline-none", className)}
      {...props}
    />
  );
}
