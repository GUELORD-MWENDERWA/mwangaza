import { Card } from "@mwangaza/ui";

/** Aperçu d'un document imprimable : le HTML que le serveur met aussi en PDF (M11). */
export function DocumentPreview({ title, src }: { title: string; src: string }) {
  return (
    <Card className="overflow-hidden p-0">
      <iframe title={title} src={src} className="block h-[75vh] min-h-[480px] w-full bg-white" />
    </Card>
  );
}
