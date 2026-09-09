import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { createMockApi } from "../api/mock";
import type { MenuPlan } from "../api/types";
import { GraphDrawer } from "./GraphDrawer";

const plan: MenuPlan = {
  id: "plan-1",
  rank: 1,
  recipes: [
    {
      id: "dishes/breakfast/空气炸锅面包片.md",
      name: "空气炸锅面包片",
      source_url: "https://example.com/bread",
    },
    {
      id: "dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md",
      name: "洋葱炒鸡蛋",
      source_url: "https://example.com/egg",
    },
  ],
  to_buy: ["葱"],
  covered: ["鸡蛋", "洋葱", "面包片"],
  omitted_optional: [],
};

describe("GraphDrawer", () => {
  it("loads one recipe graph at a time and restores trigger focus", async () => {
    const user = userEvent.setup();
    render(<GraphDrawer api={createMockApi({ delayMs: 0 })} plan={plan} />);
    const trigger = screen.getByRole("button", { name: "查看方案 1 图谱解释" });

    await user.click(trigger);

    expect(await screen.findByRole("dialog", { name: "方案 1 知识图谱" })).toBeInTheDocument();
    fireEvent.click(await screen.findByText("面包片"));
    expect(screen.getByText("节点类型：食材")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "洋葱炒鸡蛋" }));
    expect(await screen.findByText("食用油")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(trigger).toHaveFocus();
  });

  it("keeps the drawer usable when the graph endpoint fails", async () => {
    const user = userEvent.setup();
    render(
      <GraphDrawer api={createMockApi({ delayMs: 0, scenario: "graph-error" })} plan={plan} />,
    );

    await user.click(screen.getByRole("button", { name: "查看方案 1 图谱解释" }));

    expect(await screen.findByText("图谱服务暂时不可用")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关闭图谱" })).toBeInTheDocument();
  });
});
