const { chromium } = require("C:/Users/qml/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

(async () => {
  const browser = await chromium.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 }, locale: "zh-CN" });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("http://127.0.0.1:3000/studio?project=05101e28-80ba-40b1-b0b1-014deec863bf", { waitUntil: "networkidle" });

  const twoD = page.getByRole("button", { name: /^2D 游戏/ });
  const threeD = page.getByRole("button", { name: /^3D 游戏/ });
  await twoD.waitFor();
  await threeD.waitFor();

  await threeD.click();
  await page.getByRole("button", { name: /^按当前提示词生成画面$/ }).waitFor();
  const threeDSelected = await threeD.evaluate(element => element.classList.contains("active"));
  if (!threeDSelected) throw new Error("3D 游戏制作方式未能选中");

  await twoD.click();
  const editor = page.getByLabel("画面提示词");
  await editor.waitFor();
  await editor.fill("彩色卡通二维横版游戏，朱红漆碗、青绿色漆林、金色纹样，角色轮廓清晰，适合二维精灵切分。");
  const button = page.getByRole("button", { name: "按当前提示词生成画面", exact: true });
  if (!(await button.isEnabled())) throw new Error("生成按钮未在选择 2D 并编辑提示词后启用");
  const twoDSelected = await twoD.evaluate(element => element.classList.contains("active"));
  if (!twoDSelected) throw new Error("2D 游戏制作方式未能选中");

  const body = await page.locator("body").innerText();
  const forbidden = ["米醋", "深度求索", "混元", "腾讯 MPS", "API", "gpt-", "已连接"];
  const visibleForbidden = forbidden.filter(item => body.includes(item));
  if (visibleForbidden.length) throw new Error(`界面仍显示服务或模型名称：${visibleForbidden.join("、")}`);
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/2D与3D制作方式选择.png", fullPage: true });
  console.log(JSON.stringify({ modeChoices: 2, twoDSelected, threeDSelected, promptEditable: true, generationButtonEnabled: true, visibleForbidden, errors }, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
