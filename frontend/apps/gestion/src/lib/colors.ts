// Couleur de l'école (décision Q8) : aperçu pendant la saisie, même calcul que le serveur
// (`backend/apps/schools/colors.py`), qui reste seul juge à l'enregistrement. Texte blanc ou encre,
// le plus lisible des deux, avec un contraste d'au moins 4,5 : 1 ; sinon, teinte voisine proposée.
export const WHITE = "#FFFFFF";
export const INK = "#101828";
export const MIN_CONTRAST = 4.5;

const HEX = /^#([0-9A-F]{3}|[0-9A-F]{6})$/;

/** `#RRGGBB` en majuscules (accepte `#rgb`) ; `null` pour tout autre format. */
export function normalizeColor(value: string): string | null {
  const color = value.trim().toUpperCase();
  if (!HEX.test(color)) return null;
  if (color.length === 4) {
    return `#${[...color.slice(1)].map((digit) => digit + digit).join("")}`;
  }
  return color;
}

function rgb(color: string): [number, number, number] {
  return [1, 3, 5].map((start) => parseInt(color.slice(start, start + 2), 16)) as [
    number,
    number,
    number,
  ];
}

function linear(channel: number) {
  const c = channel / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(color: string) {
  const [red, green, blue] = rgb(color).map(linear) as [number, number, number];
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

export function contrast(first: string, second: string) {
  const [light, dark] = [luminance(first), luminance(second)].sort((a, b) => b - a) as [
    number,
    number,
  ];
  return (light + 0.05) / (dark + 0.05);
}

/** Blanc ou encre, le plus lisible des deux s'il atteint 4,5 : 1 ; sinon `null`. */
export function textColor(color: string): string | null {
  const best = contrast(color, WHITE) >= contrast(color, INK) ? WHITE : INK;
  return contrast(color, best) >= MIN_CONTRAST ? best : null;
}

// `colorsys` de Python, pour proposer exactement la même teinte que le serveur.
const mod1 = (value: number) => ((value % 1) + 1) % 1;

function rgbToHls(r: number, g: number, b: number): [number, number, number] {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const lightness = (max + min) / 2;
  if (max === min) return [0, lightness, 0];
  const range = max - min;
  const saturation = lightness <= 0.5 ? range / (max + min) : range / (2 - max - min);
  const [rc, gc, bc] = [(max - r) / range, (max - g) / range, (max - b) / range];
  const hue = r === max ? bc - gc : g === max ? 2 + rc - bc : 4 + gc - rc;
  return [mod1(hue / 6), lightness, saturation];
}

function channel(m1: number, m2: number, hue: number) {
  const h = mod1(hue);
  if (h < 1 / 6) return m1 + (m2 - m1) * h * 6;
  if (h < 0.5) return m2;
  if (h < 2 / 3) return m1 + (m2 - m1) * (2 / 3 - h) * 6;
  return m1;
}

function hlsToRgb(hue: number, lightness: number, saturation: number) {
  if (saturation === 0) return [lightness, lightness, lightness];
  const m2 =
    lightness <= 0.5
      ? lightness * (1 + saturation)
      : lightness + saturation - lightness * saturation;
  const m1 = 2 * lightness - m2;
  return [channel(m1, m2, hue + 1 / 3), channel(m1, m2, hue), channel(m1, m2, hue - 1 / 3)];
}

/** Arrondi de Python (moitié vers le pair). */
function roundHalfEven(value: number) {
  const rounded = Math.round(value);
  return Math.abs(value % 1) === 0.5 && rounded % 2 !== 0 ? rounded - 1 : rounded;
}

/** La couleur si elle est lisible ; sinon la plus proche de même teinte (plus sombre d'abord). */
export function nearbyReadable(color: string): string {
  if (textColor(color)) return color;
  const [hue, lightness, saturation] = rgbToHls(
    ...(rgb(color).map((c) => c / 255) as [number, number, number]),
  );
  for (let step = 1; step <= 200; step++) {
    for (const candidate of [lightness - step / 200, lightness + step / 200]) {
      if (candidate < 0 || candidate > 1) continue;
      const hex = hlsToRgb(hue, candidate, saturation)
        .map((c) =>
          roundHalfEven(c * 255)
            .toString(16)
            .toUpperCase()
            .padStart(2, "0"),
        )
        .join("");
      if (textColor(`#${hex}`)) return `#${hex}`;
    }
  }
  return "#0B5FCC";
}
