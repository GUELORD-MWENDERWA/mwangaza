import type { ReactNode } from "react";

import { Button } from "./button";
import { DialogClose, DialogContent, DialogRoot } from "./sheet";

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  pending?: boolean;
  destructive?: boolean;
};

/** Confirmation d'une action (désactiver, supprimer, réinitialiser) : Échap ou « Annuler » ferme
 *  sans rien faire ; le bouton est bloqué pendant l'envoi (pas de double clic). */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  children,
  confirmLabel,
  cancelLabel,
  onConfirm,
  pending,
  destructive,
}: ConfirmDialogProps) {
  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={title}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{cancelLabel}</Button>
            </DialogClose>
            <Button
              variant={destructive ? "destructive" : "default"}
              disabled={pending}
              onClick={onConfirm}
            >
              {confirmLabel}
            </Button>
          </>
        }
      >
        {children}
      </DialogContent>
    </DialogRoot>
  );
}
