import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const url = process.argv[2] || "http://127.0.0.1:8893/activities/role-toolbox/";
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH || undefined,
  args: ["--no-sandbox"]
});

try {
  for (const width of [320, 390, 768, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, acceptDownloads: true });
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(url).origin });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    const response = await page.goto(url, { waitUntil: "networkidle" });
    assert.equal(response.status(), 200);
    assert.match(await page.title(), /CPS Evidence Toolbox/);
    assert.equal(await page.locator("#source-label").innerText(), "SYNTHETIC / AUTHORED");
    assert.equal(await page.locator("#fact").inputValue(), "");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `horizontal overflow at ${width}px`);

    const policy = page.locator("#policy");
    await policy.selectOption("deny-all");
    assert.match(await page.locator("#policy-result").innerText(), /Write.*BLOCKED.*Ordinary read.*BLOCKED/s);
    await policy.selectOption("deny-write");
    assert.match(await page.locator("#policy-result").innerText(), /Write.*BLOCKED.*Ordinary read.*ALLOWED/s);
    await policy.selectOption("deny-client");
    assert.match(await page.locator("#policy-result").innerText(), /Write.*BLOCKED.*Ordinary read.*ALLOWED/s);

    for (const role of ["network", "program", "operator", "integrator"]) {
      await page.locator(`[data-role="${role}"]`).click();
      assert.equal(await page.locator(`[data-role="${role}"]`).getAttribute("aria-pressed"), "true");
      assert.ok((await page.locator("#question").innerText()).length > 10);
      assert.ok((await page.locator("#first-action").innerText()).length > 10);
      assert.ok((await page.locator("#today-tool").innerText()).length > 10);
      assert.ok((await page.locator("#future-tool").innerText()).length > 10);
    }
    await page.locator('[data-role="program"]').click();
    await page.locator("#symbol").selectOption("condition");
    assert.match(await page.locator("#symbol-result").innerText(), /downstream path/);
    await page.locator('[data-role="operator"]').click();
    await page.locator("#max-age").selectOption("45");
    assert.match(await page.locator("#age-result").innerText(), /still not physical proof/);
    await page.locator("#max-age").selectOption("5");
    assert.match(await page.locator("#age-result").innerText(), /STALE/);

    await page.locator('[data-role="network"]').click();
    await page.locator("#copy").click();
    assert.match(await page.locator("#saved").innerText(), /Add a fact, citation, and limit/);
    assert.equal(await page.evaluate(() => document.activeElement.id), "fact");
    await page.locator("#fact").fill("Packet #6 is a normal protocol reply.");
    await page.locator("#citation").fill("Packet #6");
    await page.locator("#limit").fill("It does not prove actuation.");
    await page.locator("#copy").click();
    await page.waitForFunction(() => document.getElementById("saved").textContent === "Handoff copied");
    assert.match(await page.locator("#saved").innerText(), /Handoff copied/);
    assert.match(await page.evaluate(() => navigator.clipboard.readText()), /Packet #6 is a normal protocol reply/);
    await page.reload({ waitUntil: "networkidle" });
    assert.equal(await page.locator("#fact").inputValue(), "Packet #6 is a normal protocol reply.");
    assert.equal(await page.locator("#policy").inputValue(), "deny-client");
    await page.locator('[data-role="program"]').click();
    assert.equal(await page.locator("#symbol").inputValue(), "condition");
    await page.locator('[data-role="network"]').click();

    await page.locator("#implementation").selectOption("hw3");
    assert.match(await page.locator("#source-label").innerText(), /LIVE SOFTWARE CONTROLLER/);
    assert.match(await page.locator("#source-description").innerText(), /does not read or control/);
    const hw3Links = await page.locator('a[href="https://hw3pilot-lgarcia.xdc.sphere-testbed.net/jupyter/substation/"]').count();
    assert.ok(hw3Links >= 1);
    await page.locator("#fact").fill("My HW3 app trace shows a request.");
    await page.locator("#implementation").selectOption("fixture");
    assert.equal(await page.locator("#fact").inputValue(), "Packet #6 is a normal protocol reply.");
    await page.locator("#implementation").selectOption("hw3");
    assert.equal(await page.locator("#fact").inputValue(), "My HW3 app trace shows a request.");
    await page.locator("#team-claim").fill("Only the cited software run is supported.");
    await page.locator("#next-test").fill("Check actual model position.");

    const downloadPromise = page.waitForEvent("download");
    await page.locator("#export").click();
    const download = await downloadPromise;
    assert.equal(download.suggestedFilename(), "cs6494-toolbox-notes.json");
    const file = await download.path();
    const { readFile } = await import("node:fs/promises");
    const exported = JSON.parse(await readFile(file, "utf8"));
    assert.equal(exported.practiceOnly, true);
    assert.equal(exported.notes.hw3.network.fact, "My HW3 app trace shows a request.");
    assert.equal(exported.teamClaim, "Only the cited software run is supported.");
    assert.deepEqual(errors, [], `browser errors at ${width}px`);
    console.log(`PASS ${width}px: roles, boundaries, tools, notes, export, layout`);
    await context.close();
  }
} finally {
  await browser.close();
}
