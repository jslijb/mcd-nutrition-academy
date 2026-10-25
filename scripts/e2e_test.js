const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const outDir = process.argv[2];
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });

  const url = 'file:///' + path.resolve(outDir, 'index.html').replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });
  console.log('入口页标题:', await page.title());

  // 点开始按钮
  await page.click('a.cta');
  await page.waitForLoadState('load');
  console.log('进入课程页:', await page.title());

  // 逐课作答：每课点正确答案
  for (let i = 0; i < 6; i++) {
    const lesson = page.locator('.lesson').nth(i);
    const right = lesson.locator('.opt.right');
    // 正确答案在渲染后才标 class，先从 LESSONS 里读
    const answer = await page.evaluate((idx) => LESSONS[idx].quiz.answer, i);
    await lesson.locator('.opt', { hasText: answer }).first().click();
    await page.waitForTimeout(150);
    const nextBtn = lesson.locator('.next');
    if (await nextBtn.isVisible()) {
      await nextBtn.click();
      await page.waitForTimeout(200);
    }
  }

  const progText = await page.locator('#pt').innerText();
  console.log('通关提示:', progText);

  const link = page.locator('a.certlink');
  console.log('结业证链接数量:', await link.count());
  if (await link.count()) {
    const href = await link.getAttribute('href');
    console.log('结业证链接:', href);
    await link.click();
    await page.waitForLoadState('load');
    console.log('结业证页标题:', await page.title());
    const hasRadar = await page.locator('.radarbox svg').count();
    console.log('雷达图渲染:', hasRadar > 0 ? 'OK' : 'MISSING');
  }

  console.log('JS 错误:', errors.length ? errors : '无');
  await browser.close();
})();
