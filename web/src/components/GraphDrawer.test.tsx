import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { createMockApi } from "../api/mock";
import type { Explanation, MenuPlan } from "../api/types";
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

const explanations: Explanation[] = [
  {
    id: "exclude-small-pepper",
    kind: "excluded_required",
    message: "小炒肉必需使用小米椒。",
    path: [
      {
        id: "r:dishes/meat_dish/小炒肉.md",
        label: "小炒肉",
        kind: "recipe",
      },
      { id: "i:小米椒", label: "小米椒", kind: "ingredient" },
      { id: "c:辣椒", label: "辣椒", kind: "category" },
    ],
    edges: [
      {
        source: "r:dishes/meat/小炒肉.md",
        target: "i:小米椒",
        relation: "REQUIRES",
        evidence: ["ingredients:1"],
      },
      {
        source: "i:小米椒",
        target: "c:辣椒",
        relation: "IS_A",
        evidence: ["reviewed taxonomy"],
      },
    ],
  },
];

describe("GraphDrawer", () => {
  it("loads one recipe graph at a time and restores trigger focus", async () => {
    const user = userEvent.setup();
    const api = createMockApi({ delayMs: 0 });
    const getNeighborhood = vi.spyOn(api, "getNeighborhood");
    render(<GraphDrawer api={api} exclude={["辣椒"]} explanations={[]} plan={plan} />);
    const trigger = screen.getByRole("button", { name: "查看方案 1 图谱解释" });

    await user.click(trigger);

    expect(await screen.findByRole("dialog", { name: "方案 1 知识图谱" })).toBeInTheDocument();
    fireEvent.click(await screen.findByText("面包片"));
    expect(screen.getByText("节点类型：食材")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "洋葱炒鸡蛋" }));
    expect(await screen.findByText("食用油")).toBeInTheDocument();
    expect(getNeighborhood).toHaveBeenCalledWith(
      plan.recipes[1].id,
      { limit: 30, exclude: ["辣椒"] },
      expect.any(AbortSignal),
    );

    await user.keyboard("{Escape}");
    expect(trigger).toHaveFocus();
  });

  it("keeps the drawer usable when the graph endpoint fails", async () => {
    const user = userEvent.setup();
    render(
      <GraphDrawer
        api={createMockApi({ delayMs: 0, scenario: "graph-error" })}
        exclude={[]}
        explanations={[]}
        plan={plan}
      />,
    );

    await user.click(screen.getByRole("button", { name: "查看方案 1 图谱解释" }));

    expect(await screen.findByText("图谱服务暂时不可用")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关闭图谱" })).toBeInTheDocument();
  });

  it("offers rejected recipes as exclusion-path tabs", async () => {
    const user = userEvent.setup();
    const api = createMockApi({ delayMs: 0 });
    const getNeighborhood = vi.spyOn(api, "getNeighborhood");
    render(
      <GraphDrawer api={api} exclude={["辣椒"]} explanations={explanations} plan={plan} />,
    );

    await user.click(screen.getByRole("button", { name: "查看方案 1 图谱解释" }));
    await user.click(screen.getByRole("button", { name: "小炒肉（已排除）" }));

    expect(await screen.findByText("小米椒")).toBeInTheDocument();
    expect(getNeighborhood).toHaveBeenCalledWith(
      "dishes/meat_dish/小炒肉.md",
      { limit: 30, exclude: ["辣椒"] },
      expect.any(AbortSignal),
    );
  });
});
