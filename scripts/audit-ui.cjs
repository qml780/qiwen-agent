const { chromium } = require("C:/Users/qml/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

(async () => {
  const browser = await chromium.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 }, locale: "zh-CN" });
  const consoleErrors = [];
  const failedRequests = [];
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("requestfailed", (request) => failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText}`));

  await page.goto("http://127.0.0.1:3000/", { waitUntil: "networkidle" });
  const home = {
    lang: await page.locator("html").getAttribute("lang"),
    title: await page.title(),
    background: await page.locator("body").evaluate((node) => getComputedStyle(node).backgroundColor),
    buttons: await page.getByRole("button").allTextContents(),
    links: await page.getByRole("link").allTextContents(),
  };
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/full-audit-主页.png", fullPage: true });

  await page.goto("http://127.0.0.1:3000/knowledge", { waitUntil: "networkidle" });
  const knowledge = {
    cards: await page.locator(".library-entry").count(),
    buttons: await page.getByRole("button").allTextContents(),
    bodyHasProviderName: /(米醋|深度求索|混元|腾讯|gpt-|API\s*已连接)/i.test(await page.locator("body").innerText()),
  };
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/full-audit-知识库.png", fullPage: true });

  await page.goto("http://127.0.0.1:3000/projects", { waitUntil: "networkidle" });
  const projects = {
    projectLinks: await page.locator('a[href*="/studio?project="]').count(),
    deleteButtons: await page.getByRole("button", { name: /删除/ }).count(),
    hasNewProjectPath: (await page.getByRole("link").allTextContents()).some((text) => /新建|知识/.test(text)),
  };
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/full-audit-项目列表.png", fullPage: true });

  await page.goto("http://127.0.0.1:3000/studio?project=658be659-07ff-4d41-8922-21729df0b56e", { waitUntil: "networkidle" });
  const studioText = await page.locator("body").innerText();
  const assetNameInputs = page.locator('input[aria-label^="素材名称"]');
  const assetNames = await assetNameInputs.evaluateAll((nodes) => nodes.map((node) => node.value));
  const studio = {
    headings: await page.getByRole("heading").allTextContents(),
    buttons: await page.getByRole("button").allTextContents(),
    fileInputs: await page.locator('input[type="file"]').count(),
    visibleProviderNames: ["米醋", "深度求索", "混元", "腾讯 MPS", "gpt-"].filter((name) => studioText.includes(name)),
    errorVisible: /暂时不可用|稍后重试|未完成/.test(studioText),
    independentAssetNames: assetNames,
    assetGenerateButtons: await page.getByRole("button", { name: "生成这一项" }).count(),
    currentStageShowsAssetDraft: studioText.includes("逐项生成游戏素材"),
    budgetDialogVisible: await page.getByRole("dialog").isVisible().catch(() => false),
    budgetDialogButtons: await page.getByRole("dialog").getByRole("button").allTextContents().catch(() => []),
  };
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/full-audit-工作台.png", fullPage: true });

  const musicTab = page.getByRole("button", { name: /音乐/ }).first();
  if (await musicTab.isEnabled()) {
    await musicTab.click();
    await page.waitForTimeout(500);
  }
  const music = {
    tracks: await page.locator(".audio-track").count(),
    trackBackgrounds: await page.locator(".audio-track").evaluateAll((nodes) => nodes.slice(0, 3).map((node) => getComputedStyle(node).backgroundColor)),
    audioBackgrounds: await page.locator(".audio-track audio").evaluateAll((nodes) => nodes.slice(0, 3).map((node) => getComputedStyle(node).backgroundColor)),
    visibleText: (await page.locator("main").innerText().catch(() => page.locator("body").innerText())).slice(0, 1200),
  };
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/full-audit-音乐阶段.png", fullPage: true });

  console.log(JSON.stringify({ home, knowledge, projects, studio, music, consoleErrors, failedRequests }, null, 2));
  await browser.close();
})().catch((error) => { console.error(error); process.exit(1); });
