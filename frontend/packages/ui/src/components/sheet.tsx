import { Dialog } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "../lib/cn";

// Menu coulissant de la Gestion sous 900 px (`.drawer` et `.scrim` des maquettes, M7) : se ferme
// en touchant à côté, avec Échap ou après un choix ; le focus reste dans le menu ouvert.
export const Sheet = Dialog.Root;
export const SheetTrigger = Dialog.Trigger;
export const SheetClose = Dialog.Close;

type SheetContentProps = ComponentProps<typeof Dialog.Content> & {
  title: string;
  children: ReactNode;
};

export function SheetContent({ title, className, children, ...props }: SheetContentProps) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 animate-fade-in bg-[rgba(26,34,51,.55)]" />
      <Dialog.Content
        aria-describedby={undefined}
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[292px] max-w-[85vw] animate-drawer-in flex-col gap-0.5 overflow-y-auto bg-basalt px-3 py-4 text-basalt-ink focus:outline-none",
          className,
        )}
        {...props}
      >
        <Dialog.Title className="sr-only">{title}</Dialog.Title>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  );
}

// Fenêtre de dialogue (`.overlay` `.dialog` des maquettes).
export const DialogRoot = Dialog.Root;
export const DialogClose = Dialog.Close;

type DialogContentProps = ComponentProps<typeof Dialog.Content> & {
  title: ReactNode;
  description?: ReactNode;
  footer?: ReactNode;
};

export function DialogContent({
  title,
  description,
  footer,
  className,
  children,
  ...props
}: DialogContentProps) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 animate-fade-in bg-[rgba(26,34,51,.45)]" />
      <Dialog.Content
        {...(description ? {} : { "aria-describedby": undefined })}
        className={cn(
          "fixed top-1/2 left-1/2 z-50 max-h-[90vh] w-[min(620px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[14px] bg-card shadow-[0_20px_60px_rgba(0,0,0,.25)] focus:outline-none",
          className,
        )}
        {...props}
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <Dialog.Title className="text-lg font-bold">{title}</Dialog.Title>
        </div>
        <div className="flex flex-col gap-3 px-5 py-[18px]">
          {description && (
            <Dialog.Description className="text-sm text-ink-2">{description}</Dialog.Description>
          )}
          {children}
        </div>
        {footer && (
          <div className="flex flex-wrap justify-end gap-2.5 border-t border-line px-5 py-3.5">
            {footer}
          </div>
        )}
      </Dialog.Content>
    </Dialog.Portal>
  );
}
