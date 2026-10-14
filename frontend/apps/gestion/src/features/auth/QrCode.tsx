import qrcode from "qrcode-generator";
import { useMemo } from "react";

/** QR code dessiné en SVG (net à toute taille, imprimable), sans image ni texte HTML injecté. */
export function QrCode({
  value,
  label,
  size = 176,
}: {
  value: string;
  label: string;
  size?: number;
}) {
  const { count, path } = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(value);
    qr.make();
    const modules = qr.getModuleCount();
    let d = "";
    for (let row = 0; row < modules; row += 1) {
      for (let col = 0; col < modules; col += 1) {
        if (qr.isDark(row, col)) d += `M${col} ${row}h1v1h-1z`;
      }
    }
    return { count: modules, path: d };
  }, [value]);
  const margin = 2;
  return (
    <svg
      role="img"
      aria-label={label}
      width={size}
      height={size}
      viewBox={`${-margin} ${-margin} ${count + 2 * margin} ${count + 2 * margin}`}
      shapeRendering="crispEdges"
      className="rounded-field bg-white"
    >
      <rect
        x={-margin}
        y={-margin}
        width={count + 2 * margin}
        height={count + 2 * margin}
        fill="#fff"
      />
      <path d={path} fill="#211D1A" />
    </svg>
  );
}
