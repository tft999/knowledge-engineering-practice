import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { createMockApi } from "./api/mock";
import { App } from "./App";

describe("CookKG planner page", () => {
  it("runs the demo flow and presents ranked plans with evidence", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 0 })} isMock />);

    expect(screen.getByText("演示数据")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "载入演示示例" }));
    await user.click(screen.getByRole("button", { name: "生成菜单方案" }));

    expect(await screen.findByText("空气炸锅面包片")).toBeInTheDocument();
    expect(screen.getByText("8 道")).toBeInTheDocument();
    expect(screen.getByText("1 种")).toBeInTheDocument();
    expect(screen.getByText("3 种")).toBeInTheDocument();
    expect(screen.getByText("满足全部约束")).toBeInTheDocument();
    expect(screen.getByText(/小炒肉必需使用小米椒/)).toBeInTheDocument();

    const source = screen.getAllByRole("link", { name: "查看原文" })[0];
    expect(source).toHaveAttribute("target", "_blank");
    expect(source).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("loads recipe details without replacing the menu", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 20 })} isMock />);
    await user.click(screen.getByRole("button", { name: "载入演示示例" }));
    await user.click(screen.getByRole("button", { name: "生成菜单方案" }));
    await screen.findByText("空气炸锅面包片");

    await user.click(screen.getAllByRole("button", { name: "查看洋葱炒鸡蛋详情" })[0]);

    expect(await screen.findByText("原料与用量")).toBeInTheDocument();
    expect(screen.getByText("鸡蛋 2 个")).toBeInTheDocument();
    expect(screen.getByText("空气炸锅面包片")).toBeInTheDocument();
  });

  it("shows an explicit business empty state", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 0, scenario: "empty" })} isMock />);
    await user.click(screen.getByRole("button", { name: "生成菜单方案" }));

    expect(await screen.findByText("没有满足当前约束的菜单组合")).toBeInTheDocument();
    expect(screen.queryByText("服务连接失败")).not.toBeInTheDocument();
  });

  it("keeps the form and offers retry after a service error", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 0, scenario: "error" })} isMock />);
    await user.click(screen.getByRole("button", { name: "载入演示示例" }));
    await user.click(screen.getByRole("button", { name: "生成菜单方案" }));

    expect(await screen.findByText("服务连接失败")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试上次请求" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除鸡蛋" })).toBeInTheDocument();
  });
});
