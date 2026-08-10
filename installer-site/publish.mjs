// Uploads a built installer EXE to Vercel Blob and prints its real
// {url, sha256, size} as JSON — used by publish-installer-site.ps1 to
// fill in latest.json / index.html with real values (never guessed ones).
//
// Usage: node publish.mjs <path-to-exe> <version>
// Requires: BLOB_READ_WRITE_TOKEN in env (already in installer-site/.env.local)
import { put } from '@vercel/blob';
import { readFileSync } from 'fs';
import { createHash } from 'crypto';

const [, , filePath, version] = process.argv;
if (!filePath || !version) {
  console.error('Usage: node publish.mjs <path-to-exe> <version>');
  process.exit(1);
}

const buf = readFileSync(filePath);
const sha256 = createHash('sha256').update(buf).digest('hex');

const blob = await put(`releases/ONEVO-Connector-Setup-${version}.exe`, buf, {
  access: 'public',
  addRandomSuffix: true,
  token: process.env.BLOB_READ_WRITE_TOKEN,
  contentType: 'application/octet-stream',
});

console.log(JSON.stringify({ url: blob.url, sha256, size: buf.length }));
