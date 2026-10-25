/**
 * 分步骤截图，为合成 GIF 准备帧素材。
 * 用法: node scripts/capture_frames.js <baseUrl> <outDir>
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.argv[2];
const OUT = path.resolve(process.argv[3]);

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1080, height: 900 } });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let n = 0;
  const shot = async (tag) => {
    n += 1;
    const f = path.join(OUT, `f${String(n).padStart(2, '0')}_${tag}.png`);
    await page.screenshot({ path: f });
    console.log('FRAME', f);
  };

  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 60000 });
  await sleep(1200);

  // 入口页 -> 点 CTA 进入课程页
  const cta = page.locator('a.cta');
  if (await cta.count()) {
    await shot('landing');
    await cta.first().click();
    await page.waitForLoadState('load');
    await sleep(900);
  }
  await shot('course_top');

  for (let i = 0; i < 6; i++) {
    const lesson = page.locator('.lesson').nth(i);
    await lesson.scrollIntoViewIfNeeded().catch(() => {});
    await sleep(400);

    if (i === 0) await shot('lesson1');

    const answer = await page.evaluate((idx) => LESSONS[idx].quiz.answer, i);
    // 先点一个错的，展示红叉反馈
    const opts = lesson.locator('.opt');
    const cnt = await opts.count();
    let wrongIdx = -1;
    for (let k = 0; k < cnt; k++) {
      const t = (await opts.nth(k).innerText()).trim();
      if (t !== answer) { wrongIdx = k; break; }
    }
    if (i === 0 && wrongIdx >= 0) {
      await opts.nth(wrongIdx).click().catch(() => {});
      await sleep(500);
      await shot('wrong_answer');
    }

    await lesson.locator('.opt', { hasText: answer }).first().click().catch(() => {});
    await sleep(600);
    if (i === 0) await shot('right_answer');
    if (i === 2) await shot('mid_progress');

    const nextBtn = lesson.locator('.next');
    if (await nextBtn.isVisible().catch(() => false)) {
      await nextBtn.click().catch(() => {});
      await sleep(500);
    }
  }

  // 通关状态
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(400);
  await shot('course_done');

  // 结业证页
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(500);
  const doneInfo = await page.evaluate(() => ({
    done: typeof done !== 'undefined' ? done.size : null,
    cert: document.querySelectorAll('a.certlink').length,
    href: document.querySelector('a.certlink') ? document.querySelector('a.certlink').getAttribute('href') : null,
  }));
  console.log('DONE_STATE', JSON.stringify(doneInfo));
  const certHref = doneInfo.href || 'certificate.html';
  {
    const certUrl = new URL(certHref, page.url()).toString();
    console.log('CERT_URL', certUrl);
    await page.goto(certUrl, { waitUntil: 'networkidle', timeout: 60000 });
    await sleep(1200);
    await shot('certificate');

    // 滚到雷达图
    await page.evaluate(() => {
      const el = document.querySelector('.radarbox') || document.querySelector('svg');
      if (el) el.scrollIntoView({ block: 'center' });
    });
    await sleep(600);
    await shot('radar');
  }

  console.log('TOTAL_FRAMES', n);
  await browser.close();
})();
