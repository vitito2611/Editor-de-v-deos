// Renderiza um lote de elementos (editor/remotion_fx.py) num único bundle + navegador.
// Uso: node render-lote.mjs <lote.json>   — {itens: [{props, saida}], concorrencia}
// Saída: ProRes 4444 com canal alfa (fundo transparente) para o FFmpeg sobrepor.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, selectComposition } from "@remotion/renderer";
import { existsSync, readFileSync, readdirSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const dir = path.dirname(fileURLToPath(import.meta.url));
const lote = JSON.parse(readFileSync(process.argv[2], "utf-8"));
const headless = (() => {   // Chromium headless do ambiente (qualquer versão do Playwright em /opt/pw-browsers)
  try {
    for (const d of readdirSync("/opt/pw-browsers").filter((x) => x.startsWith("chromium_headless_shell-")).sort().reverse())
      for (const sub of ["chrome-linux", "chrome-headless-shell-linux64"]) {
        const f = `/opt/pw-browsers/${d}/${sub}/` + (sub === "chrome-linux" ? "headless_shell" : "chrome-headless-shell");
        if (existsSync(f)) return f;
      }
  } catch { /* fora da nuvem */ }
  return "";
})();
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
