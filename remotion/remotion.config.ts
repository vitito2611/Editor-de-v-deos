/**
 * Note: When using the Node.JS APIs, the config file
 * doesn't apply. Instead, pass options directly to the APIs.
 *
 * All configuration options: https://remotion.dev/docs/config
 */

import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);

// Ambiente de nuvem: usa o Chromium headless já instalado (o download automático do Remotion
// é bloqueado pela rede). Em outra máquina, se o caminho não existir, o Remotion baixa o seu.
import { existsSync, readdirSync } from "fs";
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
if (existsSync(headless)) {
  Config.setBrowserExecutable(headless);
}
