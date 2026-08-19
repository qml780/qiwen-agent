const { chromium } = require("C:/Users/qml/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

(async () => {
  const browser = await chromium.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, locale: "zh-CN" });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("http://127.0.0.1:3000/studio?project=dcd31586-d6b4-441a-bd76-cf9015f0422f", { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "逐项生成游戏素材" }).waitFor();
  const names = await page.locator('input[aria-label^="素材名称"]').count();
  const prompts = await page.locator('textarea[aria-label$="提示词"]').count();
  const generateButtons = await page.getByRole("button", { name: "生成这一项" }).count();
  if (names !== 5 || prompts !== 5 || generateButtons !== 5) throw new Error(`素材清单数量不正确：${names}/${prompts}/${generateButtons}`);
  const body = await page.locator("body").innerText();
  if (body.includes("匿名共创时间线") || body.includes("研究记录")) throw new Error("主界面仍显示研究记录");

  const firstAsset = page.locator(".asset-list .asset-item").first();
  await firstAsset.click();
  await page.getByRole("button", { name: "预览大图" }).click();
  await page.getByRole("dialog", { name: "图片预览" }).waitFor();
  await page.getByRole("button", { name: "关闭预览" }).click();
  if (await page.getByRole("dialog", { name: "图片预览" }).count()) throw new Error("图片预览弹窗无法关闭");
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/独立游戏素材清单.png", fullPage: true });
  console.log(JSON.stringify({ namedAssets: names, independentPrompts: prompts, independentGeneration: generateButtons, modalPreview: true, researchPanelHidden: true, errors }, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
