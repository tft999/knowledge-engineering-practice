import { describe, expect, it, vi } from "vitest";

import { ApiContractError, createHttpApi, parseRecommendationResponse } from "./client";
import { createMockApi } from "./mock";

describe("recommendation API contract", () => {
  it("rejects a response without plans", () => {
    expect(() => parseRecommendationResponse({ candidate_count: 1 })).toThrow(
      ApiContractError,
    );
  });

  it("posts the target request and parses nested recipes", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          plans: [
            {
              id: "plan-1",
              rank: 1,
              recipes: [
                { id: "dishes/a.md", name: "示例菜", source_url: "https://example.com/a" },
              ],
              to_buy: ["葱"],
              covered: ["鸡蛋"],
              omitted_optional: [],
            },
          ],
          reason: null,
          candidate_count: 1,
          normalized_input: { have: ["鸡蛋"], pantry: [], exclude: [] },
          excluded_ingredients: [],
          explanations: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const api = createHttpApi("http://localhost:8000", fetcher);

    const result = await api.recommend({
      have: ["鸡蛋"],
      pantry: [],
      exclude: [],
      count: 1,
      max_buy: 2,
      limit: 5,
    });

    expect(result.plans[0].recipes[0].name).toBe("示例菜");
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/recommendations",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("provides deterministic success data through the mock contract", async () => {
    const api = createMockApi({ delayMs: 0 });
    const result = await api.recommend({
      have: ["鸡蛋", "洋葱", "面包片"],
      pantry: ["盐", "食用油", "黄油", "料酒"],
      exclude: ["辣椒"],
      count: 2,
      max_buy: 2,
      limit: 5,
    });

    expect(result.plans).toHaveLength(2);
    expect(result.excluded_ingredients).toContain("小米椒");
  });
});
