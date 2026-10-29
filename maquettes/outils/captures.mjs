// Captures PNG des maquettes avec Chrome sans interface (protocole DevTools, aucune dépendance).
// Usage : node maquettes/outils/captures.mjs [fichier.html …]   (sans argument : toutes les maquettes)
//         node maquettes/outils/captures.mjs --logo   (PNG du logo, fond transparent, depuis maquettes/assets/logo/mwangaza-*.svg)
// Bureau : 1440 px de large, page entière (toutes les applications : le portail aussi, 2026-10-14). Téléphone : 390 px, densité 1 (assez pour lire la mise en page, léger dans Git).
// Site public (`site/`, WEB.1a) : aussi la tablette, 820 px (`captures/tablet/`), et en WebP (photos : un PNG pèserait ~1,5 Mo).
// Chaque capture est contrôlée : un élément qui dépasse de l'écran (hors conteneur qui défile) est signalé
// et la commande sort en erreur (code 2) — une maquette qui déborde n'est pas finie.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname, basename, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CHROME = process.env.CHROME ?? "google-chrome";

function pages(args) {
  if (args.length) {
    const files = args.map((a) => resolve(a));
    // Chemin faux : s'arrêter, plutôt que d'enregistrer la page d'erreur du navigateur.
    const missing = files.filter((f) => !f.endsWith(".html") || !existsSync(f));
    if (missing.length) throw new Error(`Maquette introuvable : ${missing.join(", ")}`);
    return files;
  }
  const out = [];
  for (const app of ["gestion", "portail", "console", "site"]) {
    for (const f of readdirSync(join(ROOT, app)).sort()) if (f.endsWith(".html")) out.push(join(ROOT, app, f));
  }
  return out;
}

function targets(file) {
  const app = basename(dirname(file));
  const name = basename(file, ".html");
  const t = [];
  t.push({ kind: "desktop", width: 1440, height: 900, scale: 1 });
  if (app === "site") t.push({ kind: "tablet", width: 820, height: 1180, scale: 1 });
  t.push({ kind: "mobile", width: 390, height: 844, scale: 1 });
  const ext = app === "site" ? "webp" : "png";
  return t.map((x) => ({ ...x, ext, out: join(ROOT, "captures", x.kind, `${app}-${name}.${ext}`) }));
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const LOGO_ONLY = process.argv[2] === "--logo";

// PNG du logo (BRAND.1) : hauteur en pixels par fichier, fond transparent, rendu exact de Chrome.
const LOGO_PNG = { "mwangaza-symbole": [16, 32, 512, 1024], "mwangaza-symbole-inverse": [512], "mwangaza-symbole-mono": [512],
  "mwangaza-logo": [256], "mwangaza-logo-inverse": [256], "mwangaza-logo-mono": [256],
  "mwangaza-logotype": [192], "mwangaza-logotype-inverse": [192], "mwangaza-logotype-mono": [192] };

async function logoPng(send, sessionId) {
  const dir = join(ROOT, "assets", "logo");
  mkdirSync(join(dir, "png"), { recursive: true });
  await send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } }, sessionId);
  for (const [name, heights] of Object.entries(LOGO_PNG)) {
    const file = join(dir, `${name}.svg`);
    const [w, h] = readFileSync(file, "utf8").match(/viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"/).slice(1).map(Number);
    for (const px of heights) {
      const scale = px / h;
      const width = Math.ceil(w), height = Math.ceil(h);
      await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: scale, mobile: false }, sessionId);
      await send("Page.navigate", { url: pathToFileURL(file).href }, sessionId);
      await sleep(200);
      const { data } = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: w, height: h, scale: 1 } }, sessionId);
      const out = join(dir, "png", `${name}-${px}.png`);
      writeFileSync(out, Buffer.from(data, "base64"));
      console.log(`${relative(ROOT, out)}  ${Math.round(w * scale)}×${px}`);
    }
  }
}

// Éléments qui dépassent à droite de l'écran sans être dans un conteneur qui défile (3 au plus).
const OVERFLOW = `(() => {
  const w = window.innerWidth, out = [];
  for (const el of document.body.querySelectorAll("*")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.right <= w + 1) continue;
    let p = el.parentElement;
    while (p && p !== document.body && !["auto", "scroll", "hidden"].includes(getComputedStyle(p).overflowX)) p = p.parentElement;
    if (p && p !== document.body) continue;
    const cls = typeof el.className === "string" ? el.className.trim().split(/\\s+/).slice(0, 2).join(".") : "";
    out.push(el.tagName.toLowerCase() + (cls ? "." + cls : "") + " +" + Math.round(r.right - w) + " px");
  }
  return out.slice(0, 3);
})()`;

async function main() {
  const profile = mkdtempSync(join(tmpdir(), "mwangaza-captures-"));
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
    "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });
  const wsUrl = await new Promise((ok, ko) => {
    let buf = "";
    chrome.stderr.on("data", (d) => {
      buf += d;
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) ok(m[1]);
    });
    chrome.on("exit", () => ko(new Error("Chrome s'est arrêté")));
  });
  const ws = new WebSocket(wsUrl);
  await new Promise((ok) => ws.addEventListener("open", ok, { once: true }));
  let id = 0;
  const waiting = new Map();
  ws.addEventListener("message", (e) => {
    const msg = JSON.parse(e.data);
    if (msg.id && waiting.has(msg.id)) {
      const { ok, ko } = waiting.get(msg.id);
      waiting.delete(msg.id);
      msg.error ? ko(new Error(msg.error.message)) : ok(msg.result);
    }
  });
  const send = (method, params = {}, sessionId) =>
    new Promise((ok, ko) => {
      const n = ++id;
      waiting.set(n, { ok, ko });
      ws.send(JSON.stringify({ id: n, method, params, sessionId }));
    });

  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  await send("Page.enable", {}, sessionId);

  if (LOGO_ONLY) await logoPng(send, sessionId);
  const overflows = [];
  for (const file of LOGO_ONLY ? [] : pages(process.argv.slice(2))) {
    for (const t of targets(file)) {
      await send("Emulation.setDeviceMetricsOverride",
        { width: t.width, height: t.height, deviceScaleFactor: t.scale, mobile: t.kind !== "desktop" }, sessionId);
      await send("Page.navigate", { url: pathToFileURL(file).href }, sessionId);
      await sleep(300);
      await send("Runtime.evaluate", { expression: "document.fonts.ready.then(() => true)", awaitPromise: true }, sessionId);
      await sleep(150);
      const { result } = await send("Runtime.evaluate",
        { expression: "Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)", returnByValue: true }, sessionId);
      const height = Math.max(t.height, Math.ceil(result.value));
      const { result: over } = await send("Runtime.evaluate", { expression: OVERFLOW, returnByValue: true }, sessionId);
      if (over.value.length) overflows.push(`${relative(ROOT, file)} (${t.width} px) : ${over.value.join(", ")}`);
      await send("Emulation.setDeviceMetricsOverride",
        { width: t.width, height, deviceScaleFactor: t.scale, mobile: t.kind !== "desktop" }, sessionId);
      await sleep(150);
      const { data } = await send("Page.captureScreenshot",
        { format: t.ext, ...(t.ext === "webp" ? { quality: 82 } : {}), clip: { x: 0, y: 0, width: t.width, height, scale: 1 }, captureBeyondViewport: true }, sessionId);
      writeFileSync(t.out, Buffer.from(data, "base64"));
      console.log(`${relative(ROOT, t.out)}  ${t.width * t.scale}×${height * t.scale}`);
    }
  }
  ws.close();
  const exited = new Promise((ok) => chrome.once("exit", ok));
  chrome.kill();
  await exited;
  await sleep(500); // les sous-processus de Chrome écrivent encore quelques instants dans le profil
  if (overflows.length) {
    console.error(`\n✘ ${overflows.length} capture(s) qui débordent de l'écran :`);
    for (const o of overflows) console.error(`  ${o}`);
    process.exitCode = 2;
  }
  try {
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 });
  } catch {
    console.warn(`Profil temporaire non supprimé : ${profile}`);
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
