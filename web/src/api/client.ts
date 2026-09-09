import type {
  CookKgApi,
  GraphEdge,
  GraphNeighborhood,
  GraphNode,
  MenuPlan,
  RecipeDetail,
  RecommendationRequest,
  RecommendationResponse,
} from "./types";

type JsonRecord = Record<string, unknown>;

export class ApiContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiContractError";
  }
}

export class ApiHttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiHttpError";
  }
}

function record(value: unknown, label: string): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ApiContractError(`${label} 必须是对象`);
  }
  return value as JsonRecord;
}

function text(value: unknown, label: string): string {
  if (typeof value !== "string") throw new ApiContractError(`${label} 必须是字符串`);
  return value;
}

function number(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ApiContractError(`${label} 必须是数字`);
  }
  return value;
}

function strings(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new ApiContractError(`${label} 必须是字符串数组`);
  }
  return value as string[];
}

function array(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new ApiContractError(`${label} 必须是数组`);
  return value;
}

function parsePlan(value: unknown): MenuPlan {
  const item = record(value, "plan");
  return {
    id: text(item.id, "plan.id"),
    rank: number(item.rank, "plan.rank"),
    recipes: array(item.recipes, "plan.recipes").map((recipeValue) => {
      const recipe = record(recipeValue, "recipe");
      return {
        id: text(recipe.id, "recipe.id"),
        name: text(recipe.name, "recipe.name"),
        source_url: text(recipe.source_url, "recipe.source_url"),
      };
    }),
    to_buy: strings(item.to_buy, "plan.to_buy"),
    covered: strings(item.covered, "plan.covered"),
    omitted_optional: strings(item.omitted_optional, "plan.omitted_optional"),
  };
}

export function parseRecommendationResponse(value: unknown): RecommendationResponse {
  const item = record(value, "recommendation response");
  const normalized = record(item.normalized_input, "normalized_input");
  const explanations = array(item.explanations, "explanations").map((raw) => {
    const explanation = record(raw, "explanation");
    const kind = text(explanation.kind, "explanation.kind");
    if (!["excluded_required", "omitted_optional", "normalization"].includes(kind)) {
      throw new ApiContractError("explanation.kind 无效");
    }
    return {
      id: text(explanation.id, "explanation.id"),
      kind: kind as "excluded_required" | "omitted_optional" | "normalization",
      message: text(explanation.message, "explanation.message"),
      path: array(explanation.path, "explanation.path").map((rawNode) => {
        const node = record(rawNode, "explanation.path node");
        const nodeKind = text(node.kind, "node.kind");
        if (!["recipe", "ingredient", "category", "tool"].includes(nodeKind)) {
          throw new ApiContractError("node.kind 无效");
        }
        return {
          id: text(node.id, "node.id"),
          label: text(node.label, "node.label"),
          kind: nodeKind as "recipe" | "ingredient" | "category" | "tool",
        };
      }),
    };
  });
  const reason = item.reason;
  if (reason !== null && typeof reason !== "string") {
    throw new ApiContractError("reason 必须是字符串或 null");
  }
  return {
    plans: array(item.plans, "plans").map(parsePlan),
    reason,
    candidate_count: number(item.candidate_count, "candidate_count"),
    normalized_input: {
      have: strings(normalized.have, "normalized_input.have"),
      pantry: strings(normalized.pantry, "normalized_input.pantry"),
      exclude: strings(normalized.exclude, "normalized_input.exclude"),
    },
    excluded_ingredients: strings(item.excluded_ingredients, "excluded_ingredients"),
    explanations,
  };
}

export function parseRecipeDetail(value: unknown): RecipeDetail {
  const item = record(value, "recipe detail");
  const difficulty = item.difficulty;
  if (difficulty !== null && typeof difficulty !== "number") {
    throw new ApiContractError("difficulty 必须是数字或 null");
  }
  return {
    id: text(item.id, "recipe.id"),
    name: text(item.name, "recipe.name"),
    source_url: text(item.source_url, "recipe.source_url"),
    category: text(item.category, "recipe.category"),
    difficulty,
    ingredients: array(item.ingredients, "recipe.ingredients").map((raw) => {
      const ingredient = record(raw, "ingredient");
      const requirement = text(ingredient.requirement, "ingredient.requirement");
      if (!["required", "optional", "one_of"].includes(requirement)) {
        throw new ApiContractError("ingredient.requirement 无效");
      }
      return {
        name: text(ingredient.name, "ingredient.name"),
        requirement: requirement as "required" | "optional" | "one_of",
        quantity_raw: strings(ingredient.quantity_raw, "ingredient.quantity_raw"),
      };
    }),
    steps: text(item.steps, "recipe.steps"),
  };
}

export function parseGraphNeighborhood(value: unknown): GraphNeighborhood {
  const item = record(value, "graph neighborhood");
  return {
    recipe_id: text(item.recipe_id, "graph.recipe_id"),
    nodes: array(item.nodes, "graph.nodes").map((raw): GraphNode => {
      const node = record(raw, "graph node");
      const kind = text(node.kind, "graph node.kind");
      if (!["recipe", "ingredient", "category", "tool"].includes(kind)) {
        throw new ApiContractError("graph node.kind 无效");
      }
      return {
        id: text(node.id, "graph node.id"),
        label: text(node.label, "graph node.label"),
        kind: kind as GraphNode["kind"],
        excluded: node.excluded === true,
      };
    }),
    edges: array(item.edges, "graph.edges").map((raw): GraphEdge => {
      const edge = record(raw, "graph edge");
      const relation = text(edge.relation, "graph edge.relation");
      if (
        ![
          "REQUIRES",
          "OPTIONALLY_USES",
          "ONE_OF",
          "IS_A",
          "SUBCLASS_OF",
          "REQUIRES_TOOL",
        ].includes(relation)
      ) {
        throw new ApiContractError("graph edge.relation 无效");
      }
      return {
        id: text(edge.id, "graph edge.id"),
        source: text(edge.source, "graph edge.source"),
        target: text(edge.target, "graph edge.target"),
        relation: relation as GraphEdge["relation"],
        excluded: edge.excluded === true,
      };
    }),
  };
}

async function responseJson(response: Response): Promise<unknown> {
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = record(await response.json(), "error response");
      if (typeof body.detail === "string") message = body.detail;
      if (Array.isArray(body.detail)) {
        const validation = body.detail.find(
          (item) =>
            typeof item === "object" &&
            item !== null &&
            typeof (item as JsonRecord).msg === "string",
        ) as JsonRecord | undefined;
        if (validation) {
          message = (validation.msg as string).replace(/^Value error,\s*/, "");
        }
      }
    } catch {
      // Keep the stable status message for non-JSON errors.
    }
    throw new ApiHttpError(response.status, message);
  }
  return response.json();
}

export function createHttpApi(baseUrl: string, fetcher: typeof fetch = fetch): CookKgApi {
  const base = baseUrl.replace(/\/$/, "");
  return {
    async recommend(input, signal) {
      const response = await fetcher(`${base}/api/v1/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
        signal,
      });
      return parseRecommendationResponse(await responseJson(response));
    },
    async getRecipe(recipeId, signal) {
      const response = await fetcher(
        `${base}/api/v1/recipes/${encodeURIComponent(recipeId)}`,
        { signal },
      );
      return parseRecipeDetail(await responseJson(response));
    },
    async getNeighborhood(recipeId, options = {}, signal) {
      const query = new URLSearchParams({
        recipe_id: recipeId,
        limit: String(options.limit ?? 30),
      });
      for (const ingredient of options.exclude ?? []) query.append("exclude", ingredient);
      const response = await fetcher(`${base}/api/v1/graph/neighborhood?${query}`, {
        signal,
      });
      return parseGraphNeighborhood(await responseJson(response));
    },
  };
}
