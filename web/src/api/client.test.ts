import { describe, expect, it, vi } from "vitest";

import {
  ApiContractError,
  ApiHttpError,
  createHttpApi,
  parseAgentResponse,
  parseRecommendationResponse,
} from "./client";
import { createMockApi } from "./mock";

describe("recommendation API contract", () => {
  it("parses a planner response from the controlled agent", () => {
    const result = parseAgentResponse({
      mode: "planner",
      answer: "已完成均衡规划。",
      route_reason: "包含菜单约束",
      normalized_terms: [
        { raw: "番茄", canonical: "西红柿", field: "have", source: "alias" },
      ],
      tool_trace: [
        { tool: "plan_menu", status: "success", summary: "完成菜单规划" },
      ],
      recommendation: {
        plans: [],
        reason: "没有满足当前约束的菜单组合",
        candidate_count: 0,
        normalized_input: { have: ["西红柿"], pantry: [], exclude: [] },
        excluded_ingredients: [],
        explanations: [],
      },
      citations: [],
      retriever: null,
      insufficient_evidence: false,
      clarification_question: null,
    });

    expect(result.mode).toBe("planner");
    expect(result.normalized_terms[0].canonical).toBe("西红柿");
  });

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
              diversity: {
                categories: ["vegetable_dish"],
                repeated_core_ingredients: [],
                same_category_pairs: 0,
                max_ingredient_similarity: 0,
                category_count: 1,
                summary: "单道菜",
              },
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

  it("serializes graph limit and repeated exclusion parameters", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ recipe_id: "dishes/a.md", nodes: [], edges: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const api = createHttpApi("http://localhost:8000/", fetcher);

    await api.getNeighborhood(
      "dishes/a.md",
      { limit: 20, exclude: ["辣椒", "花生"] },
    );

    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/graph/neighborhood?recipe_id=dishes%2Fa.md&limit=20&exclude=%E8%BE%A3%E6%A4%92&exclude=%E8%8A%B1%E7%94%9F",
      expect.objectContaining({ signal: undefined }),
    );
  });

  it("surfaces FastAPI validation messages for 422 responses", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [
            {
              loc: ["body"],
              msg: "Value error, 西红柿归一化后同时出现在可用与排除条件",
              type: "value_error",
            },
          ],
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );
    const api = createHttpApi("http://localhost:8000", fetcher);

    await expect(
      api.recommend({
        have: ["番茄"],
        pantry: [],
        exclude: ["西红柿"],
        count: 1,
        max_buy: 0,
        limit: 5,
      }),
    ).rejects.toEqual(
      expect.objectContaining({
        status: 422,
        message: "西红柿归一化后同时出现在可用与排除条件",
      }),
    );
  });
});
