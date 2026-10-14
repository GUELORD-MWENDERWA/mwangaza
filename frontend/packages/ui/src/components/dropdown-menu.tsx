import { DropdownMenu as Menu } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// Liste déroulante (changement d'école, M2) : clavier et lecteur d'écran gérés par Radix.
export const DropdownMenu = Menu.Root;
export const DropdownMenuTrigger = Menu.Trigger;

export function DropdownMenuContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentProps<typeof Menu.Content>) {
  return (
    <Menu.Portal>
      <Menu.Content
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-[220px] rounded-field bg-card p-1 text-sm text-ink shadow-float",
          className,
        )}
        {...props}
      />
    </Menu.Portal>
  );
}

export function DropdownMenuItem({ className, ...props }: ComponentProps<typeof Menu.Item>) {
  return (
    <Menu.Item
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-[6px] px-[9px] py-[7px] outline-none select-none data-[disabled]:cursor-default data-[disabled]:opacity-55 data-[highlighted]:bg-lake-50",
        className,
      )}
      {...props}
    />
  );
}

export function DropdownMenuSeparator({ className }: { className?: string }) {
  return <Menu.Separator className={cn("my-1 h-px bg-line", className)} />;
}
