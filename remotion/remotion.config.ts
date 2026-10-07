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
import { existsSync } from "fs";
const headless = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
if (existsSync(headless)) {
  Config.setBrowserExecutable(headless);
}
