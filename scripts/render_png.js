// Render an HTML file to PNG/JPEG with Playwright (Chromium).
// Usage: node render_png.js <input.html> <output.png> [width] [height] [quality]
const { chromium } = require('playwright');

(async () => {
  const [input, output, w, h, q] = process.argv.slice(2);
  if (!input || !output) {
    console.error('usage: node render_png.js <input.html> <output.png> [width] [height] [quality]');
    process.exit(1);
  }
  const width = parseInt(w || '1080', 10);
  const height = parseInt(h || '1350', 10);
  const quality = parseInt(q || '88', 10);
  const isJpeg = /\.jpe?g$/i.test(output);

  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width, height },
    deviceScaleFactor: 1,
  });
  await page.goto('file:///' + input.replace(/\\/g, '/'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  await page.screenshot({
    path: output,
    fullPage: true,
    ...(isJpeg ? { type: 'jpeg', quality } : { type: 'png' }),
  });
  await browser.close();
  console.log('wrote ' + output);
})().catch((e) => {
  console.error('render failed:', e.message);
  process.exit(1);
});
