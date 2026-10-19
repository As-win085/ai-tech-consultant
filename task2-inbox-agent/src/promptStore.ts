import { createHash } from 'crypto';
import { existsSync, readFileSync } from 'fs';
import { join, resolve } from 'path';

export const PROMPTS_DIR = resolve(__dirname, '..', 'prompts');
export const ACTIVE_FILE = 'active.json';
export const SCHEMA_ID = 'prompt/v1';

const REQUIRED_KEYS = ['name', 'version', 'schema', 'date', 'changelog'] as const;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export class PromptStoreError extends Error {}

export class PromptManifestError extends PromptStoreError {
  constructor(message: string) {
    super(message);
    this.name = 'PromptManifestError';
  }
}

export class PromptVersionMissing extends PromptStoreError {
  constructor(message: string) {
    super(message);
    this.name = 'PromptVersionMissing';
  }
}

export class PromptSchemaError extends PromptStoreError {
  constructor(message: string) {
    super(message);
    this.name = 'PromptSchemaError';
  }
}

export interface LoadedPrompt {
  name: string;
  version: number;
  text: string;
  sha256: string;
  filePath: string;
  ref: string;
}

export interface PromptReportBlock {
  name: string;
  version: number;
  sha256: string;
  file: string;
}

function positiveInt(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1;
}

export function loadPrompt(name: string, promptsDir: string = PROMPTS_DIR): LoadedPrompt {
  const manifestPath = join(promptsDir, ACTIVE_FILE);
  if (!existsSync(manifestPath)) {
    throw new PromptManifestError(`Prompt manifest not found: ${manifestPath}`);
  }
  let manifest: unknown;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  } catch {
    throw new PromptManifestError(`Prompt manifest is not valid JSON: ${manifestPath}`);
  }
  if (manifest === null || typeof manifest !== 'object' || Array.isArray(manifest) ||
      Object.keys(manifest as Record<string, unknown>).length === 0) {
    throw new PromptManifestError(`Prompt manifest is not a non-empty object: ${manifestPath}`);
  }
  const entries = manifest as Record<string, unknown>;
  if (!Object.prototype.hasOwnProperty.call(entries, name)) {
    throw new PromptManifestError(`No active version for prompt "${name}" in ${manifestPath}`);
  }
  const version = entries[name];
  if (!positiveInt(version)) {
    throw new PromptManifestError(
      `Active version for prompt "${name}" must be a positive integer, got ${JSON.stringify(version)}`,
    );
  }
  const filePath = join(promptsDir, `${name}.v${version}.md`);
  if (!existsSync(filePath)) {
    throw new PromptVersionMissing(`Prompt file not found: ${filePath}`);
  }
  const raw = readFileSync(filePath, 'utf8').replace(/\r\n/g, '\n');
  if (!raw.startsWith('---\n')) {
    throw new PromptSchemaError(`Prompt file is missing the opening front matter fence: ${filePath}`);
  }
  const lines = raw.split('\n');
  let close = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i] === '---') {
      close = i;
      break;
    }
  }
  if (close === -1) {
    throw new PromptSchemaError(`Prompt file is missing the closing front matter fence: ${filePath}`);
  }
  const meta: Record<string, string> = {};
  for (const line of lines.slice(1, close)) {
    const idx = line.indexOf(':');
    if (idx === -1) {
      throw new PromptSchemaError(`Malformed front matter line "${line}" in ${filePath}`);
    }
    meta[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  }
  const missing = REQUIRED_KEYS.filter((key) => !(key in meta));
  if (missing.length > 0) {
    throw new PromptSchemaError(`Front matter missing key(s): ${missing.join(', ')} in ${filePath}`);
  }
  if (meta.name !== name) {
    throw new PromptSchemaError(`Front matter name "${meta.name}" does not match file name "${name}" in ${filePath}`);
  }
  if (meta.schema !== SCHEMA_ID) {
    throw new PromptSchemaError(`Unsupported schema "${meta.schema}" (expected "${SCHEMA_ID}") in ${filePath}`);
  }
  if (!DATE_RE.test(meta.date)) {
    throw new PromptSchemaError(`Front matter date "${meta.date}" is not YYYY-MM-DD in ${filePath}`);
  }
  const fileVersion = Number(meta.version);
  if (!positiveInt(fileVersion)) {
    throw new PromptSchemaError(`Front matter version "${meta.version}" is not a positive integer in ${filePath}`);
  }
  if (fileVersion !== version) {
    throw new PromptSchemaError(
      `Front matter version ${fileVersion} does not match manifest version ${version} in ${filePath}`,
    );
  }
  let body = lines.slice(close + 1).join('\n');
  if (body.endsWith('\n')) {
    body = body.slice(0, -1);
  }
  if (body.length === 0) {
    throw new PromptSchemaError(`Prompt body is empty in ${filePath}`);
  }
  return {
    name,
    version,
    text: body,
    sha256: createHash('sha256').update(body, 'utf8').digest('hex'),
    filePath,
    ref: `${name}/v${version}`,
  };
}

export function promptReport(name: string, promptsDir: string = PROMPTS_DIR): PromptReportBlock {
  const prompt = loadPrompt(name, promptsDir);
  return {
    name: prompt.name,
    version: prompt.version,
    sha256: prompt.sha256,
    file: `prompts/${prompt.name}.v${prompt.version}.md`,
  };
}
