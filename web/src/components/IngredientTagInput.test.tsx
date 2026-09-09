import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { IngredientTagInput } from "./IngredientTagInput";

function Harness() {
  const [value, setValue] = useState<string[]>([]);
  return <IngredientTagInput id="have" label="已有食材" value={value} onChange={setValue} />;
}

describe("IngredientTagInput", () => {
  it("creates trimmed unique tags from enter and Chinese or English commas", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByLabelText("已有食材");

    await user.type(input, "鸡蛋， 洋葱,鸡蛋{Enter}");

    expect(screen.getByRole("button", { name: "删除鸡蛋" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除洋葱" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /删除/ })).toHaveLength(2);
  });

  it("removes the final tag with backspace when the text field is empty", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByLabelText("已有食材");
    await user.type(input, "鸡蛋{Enter}洋葱{Enter}");

    await user.type(input, "{Backspace}");

    expect(screen.queryByRole("button", { name: "删除洋葱" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除鸡蛋" })).toBeInTheDocument();
  });
});
