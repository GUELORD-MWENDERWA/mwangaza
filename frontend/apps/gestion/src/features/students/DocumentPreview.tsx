import { Card, cn } from "@mwangaza/ui";
import { useEffect, useRef, useState } from "react";

/** Largeur d'une page A4 à l'écran (96 ppp). */
const A4_WIDTH = 794;

/** Aperçu d'un document imprimable : le HTML que le serveur met aussi en PDF (M11). Plus étroit
 *  qu'une page A4 (téléphone), le document garde sa mise en page et s'affiche réduit, comme dans
 *  les maquettes, au lieu de se tasser sur la largeur de l'écran. */
export function DocumentPreview({ title, src }: { title: string; src: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setScale(Math.min(1, entry.contentRect.width / A4_WIDTH));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const reduced = scale < 1;
  return (
    <Card className="overflow-hidden p-0">
      {/* Réduit, le document est posé en absolu : sa largeur A4 n'élargit pas la carte. */}
      <div ref={box} className="relative h-[75vh] min-h-[480px] w-full overflow-hidden">
        <iframe
          title={title}
          src={src}
          className={cn(
            "block h-full w-full origin-top-left bg-white",
            reduced && "absolute top-0 left-0",
          )}
          style={
            reduced
              ? {
                  width: A4_WIDTH,
                  height: `${100 / scale}%`,
                  transform: `scale(${scale})`,
                }
              : undefined
          }
        />
      </div>
    </Card>
  );
}
