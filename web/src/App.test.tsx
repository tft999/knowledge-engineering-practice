import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ApiHttpError } from "./api/client";
import { createMockApi } from "./api/mock";
import { App } from "./App";

describe("CookKG planner page", () => {
  it("accepts a hard-constraint question in the agent view", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 0 })} isMock />);

    await user.click(screen.getByRole("button", { name: "智能问答" }));
    await user.click(screen.getByRole("button", { name: /约束.*我有鸡蛋/ }));
    await user.click(screen.getByRole("button", { name: "交给 CookKG Agent" }));

    expect((await screen.findAllByText("均衡推荐")).length).toBeGreaterThan(0);
    expect(screen.getByText(/辣的.*辣椒/)).toBeInTheDocument();
    expect(screen.getAllByText(/没有重复核心食材/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("早餐").length).toBeGreaterThan(0);
    expect(screen.getAllByText("素菜").length).toBeGreaterThan(0);
  });

  it("answers greetings without showing irrelevant evidence", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 0 })} isMock />);

    await user.click(screen.getByRole("button", { name: "智能问答" }));
    await user.click(screen.getByRole("button", { name: /帮助.*你好/ }));
    await user.click(screen.getByRole("button", { name: "交给 CookKG Agent" }));

    expect(await screen.findByText("使用帮助")).toBeInTheDocument();
    expect(screen.getByText(/我可以规划约束菜单/)).toBeInTheDocument();
    expect(screen.queryByText("引用证据")).not.toBeInTheDocument();
  });

  it("shows a clarification for an unknown ingredient", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 0 })} isMock />);

    await user.click(screen.getByRole("button", { name: "智能问答" }));
    const question = screen.getByRole("textbox", { name: "问题" });
    await user.clear(question);
    await user.type(question, "我有神秘果，推荐两道菜");
    await user.click(screen.getByRole("button", { name: "交给 CookKG Agent" }));

    expect(await screen.findByText("需要确认")).toBeInTheDocument();
    expect(screen.getByText(/无法识别.*神秘果/)).toBeInTheDocument();
  });

  it("answers with a routed retriever and traceable citations", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 0 })} isMock />);

    await user.click(screen.getByRole("button", { name: "智能问答" }));
    await user.click(screen.getByRole("button", { name: "交给 CookKG Agent" }));

    expect(await screen.findByText("HybridCypher")).toBeInTheDocument();
    expect(screen.getByText(/美式炒蛋、鸡蛋三明治、洋葱炒鸡蛋/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "跳转到证据 E1" })).toHaveAttribute(
      "href", "#citation-E1"
    );
    const source = screen.getAllByRole("link", { name: "查看固定版本原文" })[0];
    expect(source).toHaveAttribute("target", "_blank");
    expect(source).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("offers demo questions for different retrieval paths", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 0 })} isMock />);

    await user.click(screen.getByRole("button", { name: "智能问答" }));
    await user.click(screen.getByRole("button", { name: /步骤.*空气炸锅面包片/ }));
    await user.click(screen.getByRole("button", { name: "交给 CookKG Agent" }));

    expect(await screen.findByText("Vector")).toBeInTheDocument();
    expect(screen.getAllByText(/200°C 烘烤 5 分钟/)).toHaveLength(2);
  });

  it("shows an explicit insufficient-evidence state", async () => {
    const user = userEvent.setup();
    render(<App api={createMockApi({ delayMs: 0, scenario: "answer-empty" })} isMock />);
    await user.click(screen.getByRole("button", { name: "智能问答" }));
    await user.click(screen.getByRole("button", { name: "交给 CookKG Agent" }));
    expect(await screen.findByText(/证据不足：系统拒绝/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "查看固定版本原文" })).not.toBeInTheDocument();
  });

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

  it("distinguishes invalid constraints from a network failure", async () => {
    const user = userEvent.setup();
    const api = createMockApi({ delayMs: 0 });
    api.recommend = async () => {
      throw new ApiHttpError(422, "西红柿归一化后同时出现在可用与排除条件");
    };
    render(<App api={api} isMock={false} />);

    await user.click(screen.getByRole("button", { name: "生成菜单方案" }));

    expect(await screen.findByText("输入条件有误")).toBeInTheDocument();
    expect(screen.getByText(/西红柿归一化后/)).toBeInTheDocument();
    expect(screen.queryByText("服务连接失败")).not.toBeInTheDocument();
  });
});
