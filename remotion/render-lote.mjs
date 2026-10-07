// Renderiza um lote de elementos (editor/remotion_fx.py) num único bundle + navegador.
// Uso: node render-lote.mjs <lote.json>   — {itens: [{props, saida}], concorrencia}
// Saída: ProRes 4444 com canal alfa (fundo transparente) para o FFmpeg sobrepor.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, selectComposition } from "@remotion/renderer";
import { existsSync, readFileSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const dir = path.dirname(fileURLToPath(import.meta.url));
const lote = JSON.parse(readFileSync(process.argv[2], "utf-8"));
const headless = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const browserExecutable = existsSync(headless) ? headless : null;

const serveUrl = await bundle({ entryPoint: path.join(dir, "src/index.ts") });
const browser = await openBrowser("chrome", { browserExecutable });
for (const it of lote.itens) {
  const composition = await selectComposition({ serveUrl, id: "Elemento", inputProps: it.props, puppeteerInstance: browser, browserExecutable });
  await renderMedia({
    composition, serveUrl, inputProps: it.props, outputLocation: it.saida, puppeteerInstance: browser, browserExecutable,
    codec: "prores", proResProfile: "4444", imageFormat: "png", pixelFormat: "yuva444p10le",
    concurrency: lote.concorrencia ?? null, logLevel: "error",
  });
  console.log("ok", it.saida);
}
await browser.close({ silent: true });
