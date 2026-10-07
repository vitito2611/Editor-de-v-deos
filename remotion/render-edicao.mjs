// Render final da edição pelo Remotion (o mesmo que se vê no Studio/Player).
// Uso: node render-edicao.mjs <projeto.json> <saida.mp4> [crf]
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { existsSync, readFileSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const dir = path.dirname(fileURLToPath(import.meta.url));
const [, , projFile, saida, crf] = process.argv;
const props = JSON.parse(readFileSync(projFile, "utf-8"));
const headless = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const browserExecutable = existsSync(headless) ? headless : null;
const serveUrl = await bundle({ entryPoint: path.join(dir, "src/index.ts") });
const composition = await selectComposition({ serveUrl, id: "Edicao", inputProps: props, browserExecutable });
let ultimo = -1;
await renderMedia({
  composition, serveUrl, inputProps: props, outputLocation: saida, browserExecutable,
  codec: "h264", crf: Number(crf ?? 18), imageFormat: "jpeg", jpegQuality: 92, pixelFormat: "yuv420p",
  audioCodec: "aac", audioBitrate: "192k", x264Preset: "fast", logLevel: "error",
  concurrency: (await import("os")).cpus().length,
  onProgress: ({ progress }) => {
    const p = Math.floor(progress * 10);
    if (p !== ultimo) { ultimo = p; console.log(`progresso ${p * 10}%`); }
  },
});
console.log("ok", saida);
