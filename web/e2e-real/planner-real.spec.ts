import { expect, test } from "@playwright/test";

test("plans a menu and explains a hierarchical exclusion with the real API", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("实时数据")).toBeVisible();

  await page.getByRole("button", { name: "载入演示示例" }).click();
  await page.getByRole("button", { name: "生成菜单方案" }).click();

  await expect(page.getByRole("heading", { name: /找到 \d+ 组菜单/ })).toBeVisible();
  const firstPlan = page.locator("article").first();
  await expect(firstPlan).toContainText("空气炸锅面包片 + 洋葱炒鸡蛋");
  await expect(firstPlan).toContainText("补购 1 种");
  await expect(firstPlan.getByText("葱", { exact: true })).toBeVisible();
  await expect(page.getByText(/小炒肉.*小米椒/).first()).toBeVisible();

  await firstPlan.getByRole("button", { name: "查看洋葱炒鸡蛋详情" }).click();
  await expect(firstPlan.getByText("原料与用量")).toBeVisible();

  await firstPlan.getByRole("button", { name: "查看方案 1 图谱解释" }).click();
  const dialog = page.getByRole("dialog", { name: "方案 1 知识图谱" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "小炒肉（已排除）" }).click();
  await expect(dialog.getByText("小米椒", { exact: true })).toBeVisible();
  await expect(dialog.getByText("辣椒", { exact: true })).toBeVisible();

  const excludedPepper = dialog.locator(".react-flow__node", { hasText: "小米椒" });
  await expect(excludedPepper).toHaveCSS("border-color", "rgb(220, 38, 38)");
});
