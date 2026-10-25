const { chromium } = require('playwright');

(async () => {
  const url = process.argv[2];
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });

  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  console.log('入口页标题:', await page.title());

  await page.click('a.cta');
  await page.waitForLoadState('networkidle');
  console.log('课程页标题:', await page.title());

  for (let i = 0; i < 6; i++) {
    const lesson = page.locator('.lesson').nth(i);
    const answer = await page.evaluate((idx) => LESSONS[idx].quiz.answer, i);
    await lesson.locator('.opt', { hasText: answer }).first().click();
    await page.waitForTimeout(120);
    const nextBtn = lesson.locator('.next');
    if (await nextBtn.isVisible()) { await nextBtn.click(); await page.waitForTimeout(180); }
  }

  console.log('通关提示:', await page.locator('#pt').innerText());
  await page.locator('a.certlink').click();
  await page.waitForLoadState('networkidle');
  console.log('结业证页:', await page.title());
  console.log('雷达图:', (await page.locator('.radarbox svg').count()) > 0 ? 'OK' : 'MISSING');
  console.log('JS 错误:', errors.length ? errors : '无');
  await browser.close();
})();
