import { copyFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = dirname(__dirname);

const source = join(projectRoot, "electron", "preload.cjs");
const targetDir = join(projectRoot, "dist-electron", "electron");
const target = join(targetDir, "preload.cjs");

await mkdir(targetDir, { recursive: true });
await copyFile(source, target);
console.log(`[copy-preload] Copied ${source} -> ${target}`);
