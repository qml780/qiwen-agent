const { chromium } = require("C:/Users/qml/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

(async () => {
  const browser = await chromium.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 }, locale: "zh-CN" });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });

  await page.goto("http://127.0.0.1:3000/knowledge", { waitUntil: "networkidle" });
  const allCount = await page.locator(".library-entry").count();
  if (allCount !== 44) throw new Error(`知识条数应为 44，实际为 ${allCount}`);
  await page.getByRole("button", { name: "材料基础", exact: true }).click();
  const materialCount = await page.locator(".library-entry").count();
  if (materialCount !== 5) throw new Error(`材料基础应为 5 条，实际为 ${materialCount}`);
  const firstImageFilter = await page.locator(".library-entry img").first().evaluate(node => getComputedStyle(node).filter);
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/knowledge-v2/01-分类筛选-材料基础.png", fullPage: true });

  const detailIds = ["MAT-001", "HAR-001", "TEC-001", "HIS-001", "REG-001"];
  for (let i = 0; i < detailIds.length; i++) {
    await page.goto(`http://127.0.0.1:3000/knowledge/${detailIds[i]}`, { waitUntil: "networkidle" });
    await page.getByText("核心事实", { exact: true }).waitFor();
    await page.getByText("参考资料", { exact: true }).waitFor();
    await page.screenshot({ path: `D:/游戏agent/qiwen-verify/evidence/knowledge-v2/${String(i + 2).padStart(2, "0")}-${detailIds[i]}-详情.png`, fullPage: true });
  }

  await page.goto("http://127.0.0.1:3000/studio?project=b64bc982-740e-403c-af2c-1c3a55f1f009", { waitUntil: "networkidle" });
  const imageInput = page.locator('input[type="file"][accept^="image/"]');
  await imageInput.setInputFiles("D:/游戏agent/qiwen-verify/apps/web/public/curated/彩色卡通-层漆碗道具.png");
  await page.locator(".pending-attachments span").first().waitFor();
  const documentInput = page.locator('input[type="file"][accept^=".json"]');
  await documentInput.setInputFiles("E:/漆vr游戏/QIWEN_知识库V2_Codex执行说明.md");
  await page.waitForFunction(() => document.querySelectorAll(".pending-attachments > span").length === 2);
  await page.getByRole("button", { name: /按参考图生成/ }).waitFor();
  const visualFilter = await page.locator(".visual-grid img").first().evaluate(node => getComputedStyle(node).filter);
  await page.screenshot({ path: "D:/游戏agent/qiwen-verify/evidence/聊天附件与彩色参考图生成.png", fullPage: true });

  console.log(JSON.stringify({ allCount, materialCount, firstImageFilter, visualFilter, imageAttachmentVisible: true, documentAttachmentVisible: true, referenceButtonVisible: true, errors }, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
