#!/usr/bin/env node

const baseUrl = process.env.STUDIO_BASE_URL || 'http://localhost:3002';
const studioUrl = new URL('/studio', baseUrl);

const htmlRes = await fetch(studioUrl);
if (!htmlRes.ok) {
  fail(`GET ${studioUrl.href} returned ${htmlRes.status}`);
}

const html = await htmlRes.text();
if (!html.includes('CineForge Agent Studio') && !html.includes('CineJelly Autonomous')) {
  fail(`GET ${studioUrl.href} did not look like this repo's Studio app.`);
}
const cssHref = firstStylesheetHref(html);
if (!cssHref) {
  fail('No stylesheet link found in /studio HTML.');
}

const cssUrl = new URL(cssHref, studioUrl);
const cssRes = await fetch(cssUrl);
if (!cssRes.ok) {
  fail(`GET ${cssUrl.href} returned ${cssRes.status}. Restart Next dev server if this follows next build.`);
}

const css = await cssRes.text();
const requiredFragments = [
  '.bg-canvas',
  '.text-text',
  '.rounded-sheet',
  '.min-h-\\[150px\\]',
  '.w-full',
];
const missing = requiredFragments.filter((fragment) => !css.includes(fragment));
if (css.length < 5000 || missing.length > 0) {
  fail(`Studio stylesheet looks incomplete. length=${css.length}; missing=${missing.join(', ') || 'none'}`);
}

console.log(`PASS studio runtime CSS guard: ${cssUrl.pathname} loaded (${css.length} bytes).`);

function firstStylesheetHref(htmlText) {
  const match = htmlText.match(/<link[^>]+rel=["']stylesheet["'][^>]+href=["']([^"']+)["']/i)
    || htmlText.match(/<link[^>]+href=["']([^"']+)["'][^>]+rel=["']stylesheet["']/i);
  return match?.[1] || '';
}

function fail(message) {
  console.error(`FAIL studio runtime CSS guard: ${message}`);
  process.exit(1);
}
