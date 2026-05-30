import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const outputPath = resolve(rootDir, 'public/build-info.json');

function run(command, fallback = '') {
  try {
    return execSync(command, {
      cwd: resolve(rootDir, '..'),
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return fallback;
  }
}

const commit = process.env.BUILD_COMMIT || run('git rev-parse --short=12 HEAD', 'unknown');
const branch = process.env.BUILD_BRANCH || run('git rev-parse --abbrev-ref HEAD', 'unknown');
const builtAt = process.env.BUILD_TIME || new Date().toISOString();
const buildId = process.env.BUILD_ID || `${builtAt.replace(/[-:.TZ]/g, '').slice(0, 14)}-${commit}`;

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(
  outputPath,
  `${JSON.stringify(
    {
      app: 'ai-bidding-workbench',
      buildId,
      commit,
      branch,
      builtAt,
    },
    null,
    2,
  )}\n`,
  'utf8',
);

console.log(`wrote public/build-info.json (${buildId})`);
