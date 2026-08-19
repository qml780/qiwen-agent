const { chromium } = require("C:/Users/qml/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

(async () => {
  const browser = await chromium.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 }, locale: "zh-CN" });
  const page = await context.newPage();
  const errors = [];
  const failed = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  page.on("requestfailed", request => failed.push(`${request.method()} ${request.url()} ${request.failure()?.errorText}`));

  await page.goto("http://127.0.0.1:3000/studio?project=f20e6701-775f-4461-8669-8aba2b711e5a", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "我的素材", exact: true }).click();
  await page.getByRole("button", { name: "图像", exact: true }).click();

  const curatedCards = page.locator(".asset-item").filter({ hasText: "彩色卡通" });
  if (await curatedCards.count() !== 4) throw new Error("精选彩色素材数量不是 4");
  await page.waitForFunction(() => {
    const images = Array.from(document.querySelectorAll(".asset-item img")).filter(img => img.alt.includes("彩色卡通"));
    return images.length === 4 && images.every(img => img.complete && img.naturalWidth > 0);
  });
  const curatedThumbnails = await curatedCards.locator("img").evaluateAll(nodes => nodes.map(node => ({ alt: node.alt, width: node.naturalWidth, height: node.naturalHeight, filter: getComputedStyle(node).filter })));

  const card = page.getByRole("button", { name: /彩色卡通 · 漆林采集关卡/ }).first();
  await card.waitFor({ state: "visible" });
  const thumbnail = card.locator("img");
  await page.waitForFunction(() => Array.from(document.images).some(img => img.alt.includes("彩色卡通 · 漆林采集关卡") && img.complete && img.naturalWidth > 0));
  const thumbnailState = await thumbnail.evaluate(node => ({ width: node.naturalWidth, height: node.naturalHeight, filter: getComputedStyle(node).filter }));
  await card.click();
  await page.getByText("彩色卡通 · 漆林采集关卡", { exact: true }).last().waitFor();

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "预览大图", exact: true }).click();
  const popup = await popupPromise;
  await popup.waitForLoadState("domcontentloaded");
  const preview = await popup.evaluate(() => ({ images: document.images.length, title: document.title }));
  await popup.close();
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/彩色卡通素材库-精选预置.png", fullPage: true });

  await page.getByRole("button", { name: "加入项目并使用", exact: true }).click();
  await page.getByRole("button", { name: "当前项目", exact: true }).waitFor();
  const usedCard = page.getByRole("button", { name: /彩色卡通 · 漆林采集关卡.*正在使用/ }).first();
  await usedCard.waitFor({ state: "visible" });
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/彩色卡通素材库-可选择可使用.png", fullPage: true });

  console.log(JSON.stringify({ curatedThumbnails, thumbnailState, preview, used: await usedCard.innerText(), errors, failed }, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
