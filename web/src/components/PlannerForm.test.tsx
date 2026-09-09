import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { PlannerForm } from "./PlannerForm";

describe("PlannerForm", () => {
  it("loads the agreed demo example and submits it", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PlannerForm isLoading={false} onSubmit={onSubmit} />);

    expect(screen.getByRole("button", { name: "2 道" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByLabelText("最多补购种类")).toHaveValue("2");

    await user.click(screen.getByRole("button", { name: "载入演示示例" }));
    await user.click(screen.getByRole("button", { name: "生成菜单方案" }));

    expect(onSubmit).toHaveBeenCalledWith({
      have: ["鸡蛋", "洋葱", "面包片"],
      pantry: ["盐", "食用油", "黄油", "料酒"],
      exclude: ["辣椒"],
      count: 2,
      max_buy: 2,
      limit: 5,
    });
  });

  it("blocks exact conflicts between available and excluded ingredients", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PlannerForm isLoading={false} onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("已有食材"), "鸡蛋{Enter}");
    await user.type(screen.getByLabelText("排除食材或类别"), "鸡蛋{Enter}");
    await user.click(screen.getByRole("button", { name: "生成菜单方案" }));

    expect(screen.getByRole("alert")).toHaveTextContent("鸡蛋同时出现在可用和排除条件中");
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
