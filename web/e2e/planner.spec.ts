import { expect, test } from "@playwright/test";

test("completes the CookKG demo flow without horizontal overflow", async ({ context, page }) => {
  await page.goto("/");
  await expect(page.getByText("演示数据")).toBeVisible();

  await page.getByRole("button", { name: "载入演示示例" }).click();
  await page.getByRole("button", { name: "生成菜单方案" }).click();

  await expect(page.getByRole("heading", { name: "找到 2 组菜单" })).toBeVisible();
  await expect(page.getByText("空气炸锅面包片").first()).toBeVisible();
  await expect(page.getByText("补购 1 种")).toBeVisible();

  await page.getByRole("button", { name: "查看洋葱炒鸡蛋详情" }).first().click();
  await expect(page.getByText("原料与用量").first()).toBeVisible();

  await page.getByRole("button", { name: "查看方案 1 图谱解释" }).click();
  await expect(page.getByRole("dialog", { name: "方案 1 知识图谱" })).toBeVisible();
  await page
    .getByRole("dialog", { name: "方案 1 知识图谱" })
    .getByRole("button", { name: "洋葱炒鸡蛋", exact: true })
    .click();
  await expect(page.getByText("食用油").last()).toBeVisible();
  await page.getByRole("button", { name: "关闭图谱" }).click();

  await context.route("https://github.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/html", body: "<title>HowToCook source</title>" }),
  );
  const popupPromise = context.waitForEvent("page");
  await page.getByRole("link", { name: "查看原文" }).first().click();
  const popup = await popupPromise;
  await expect(popup).toHaveTitle("HowToCook source");

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
});

test("answers a graph question and opens its fixed source evidence", async ({ context, page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "智能问答" }).click();
  await page.getByRole("button", { name: "交给 CookKG Agent" }).click();
  await expect(page.getByText("HybridCypher")).toBeVisible();
  await expect(page.getByText(/美式炒蛋、鸡蛋三明治、洋葱炒鸡蛋/)).toBeVisible();
  await expect(page.getByRole("link", { name: "跳转到证据 E1" })).toBeVisible();

  await context.route("https://github.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/html", body: "<title>Evidence source</title>" }),
  );
  const popupPromise = context.waitForEvent("page");
  await page.getByRole("link", { name: "查看固定版本原文" }).first().click();
  await expect(await popupPromise).toHaveTitle("Evidence source");
});
