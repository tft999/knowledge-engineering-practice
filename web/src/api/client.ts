import type {
  CookKgApi,
  AgentResponse,
  AnswerResponse,
  GraphEdge,
  GraphNeighborhood,
  GraphNode,
  MenuPlan,
  RecipeDetail,
  RecommendationRequest,
  RecommendationResponse,
} from "./types";

const retrieverNames = ["vector", "vector_cypher", "hybrid", "hybrid_cypher"] as const;

export function parseAnswerResponse(value: unknown): AnswerResponse {
  const item = record(value, "answer response");
  const retriever = text(item.retriever, "answer.retriever");
  if (!retrieverNames.includes(retriever as (typeof retrieverNames)[number])) {
    throw new ApiContractError("answer.retriever 无效");
  }
  if (typeof item.insufficient_evidence !== "boolean") {
    throw new ApiContractError("answer.insufficient_evidence 必须是布尔值");
  }
  return {
    answer: text(item.answer, "answer.answer"),
    retriever: retriever as AnswerResponse["retriever"],
    route_reason: text(item.route_reason, "answer.route_reason"),
    insufficient_evidence: item.insufficient_evidence,
    citations: array(item.citations, "answer.citations").map((raw) => {
      const citation = record(raw, "citation");
      return {
        evidence_id: text(citation.evidence_id, "citation.evidence_id"),
        record_id: text(citation.record_id, "citation.record_id"),
        recipe_id: text(citation.recipe_id, "citation.recipe_id"),
        text: text(citation.text, "citation.text"),
        source_url: text(citation.source_url, "citation.source_url"),
        line_start: number(citation.line_start, "citation.line_start"),
        line_end: number(citation.line_end, "citation.line_end"),
      };
    }),
  };
}

export function parseAgentResponse(value: unknown): AgentResponse {
  const item = record(value, "agent response");
  const mode = text(item.mode, "agent.mode");
  if (!["help", "planner", "graphrag", "clarification"].includes(mode)) {
    throw new ApiContractError("agent.mode 无效");
  }
  const retrieverValue = item.retriever;
  if (
    retrieverValue !== null &&
    (!retrieverNames.includes(retrieverValue as (typeof retrieverNames)[number]))
  ) {
    throw new ApiContractError("agent.retriever 无效");
  }
  const clarification = item.clarification_question;
  if (clarification !== null && typeof clarification !== "string") {
    throw new ApiContractError("agent.clarification_question 必须是字符串或 null");
  }
  if (typeof item.insufficient_evidence !== "boolean") {
    throw new ApiContractError("agent.insufficient_evidence 必须是布尔值");
  }
  const recommendation = item.recommendation;
  return {
    mode: mode as AgentResponse["mode"],
    answer: text(item.answer, "agent.answer"),
    route_reason: text(item.route_reason, "agent.route_reason"),
    normalized_terms: array(item.normalized_terms, "agent.normalized_terms").map((raw) => {
      const term = record(raw, "normalized term");
      const field = text(term.field, "normalized term.field");
      const source = text(term.source, "normalized term.source");
      if (!["have", "pantry", "exclude"].includes(field)) {
        throw new ApiContractError("normalized term.field 无效");
      }
      if (!["exact", "alias", "entity_linker", "category_linker"].includes(source)) {
        throw new ApiContractError("normalized term.source 无效");
      }
      return {
        raw: text(term.raw, "normalized term.raw"),
        canonical: text(term.canonical, "normalized term.canonical"),
        field: field as AgentResponse["normalized_terms"][number]["field"],
        source: source as AgentResponse["normalized_terms"][number]["source"],
      };
    }),
    tool_trace: array(item.tool_trace, "agent.tool_trace").map((raw) => {
      const trace = record(raw, "tool trace");
      const tool = text(trace.tool, "tool trace.tool");
      const status = text(trace.status, "tool trace.status");
      if (!["plan_menu", "answer_knowledge"].includes(tool)) {
        throw new ApiContractError("tool trace.tool 无效");
      }
      if (!["success", "empty"].includes(status)) {
        throw new ApiContractError("tool trace.status 无效");
      }
      return {
        tool: tool as AgentResponse["tool_trace"][number]["tool"],
        status: status as AgentResponse["tool_trace"][number]["status"],
        summary: text(trace.summary, "tool trace.summary"),
      };
    }),
    recommendation:
      recommendation === null ? null : parseRecommendationResponse(recommendation),
    citations: parseAnswerResponse({
      answer: item.answer,
      citations: item.citations,
      retriever: retrieverValue ?? "vector",
      route_reason: item.route_reason,
      insufficient_evidence: item.insufficient_evidence,
    }).citations,
    retriever: retrieverValue as AgentResponse["retriever"],
    insufficient_evidence: item.insufficient_evidence,
    clarification_question: clarification,
  };
}

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
  const diversity = record(item.diversity, "plan.diversity");
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
    diversity: {
      categories: strings(diversity.categories, "plan.diversity.categories"),
      repeated_core_ingredients: strings(
        diversity.repeated_core_ingredients,
        "plan.diversity.repeated_core_ingredients",
      ),
      same_category_pairs: number(
        diversity.same_category_pairs,
        "plan.diversity.same_category_pairs",
      ),
      max_ingredient_similarity: number(
        diversity.max_ingredient_similarity,
        "plan.diversity.max_ingredient_similarity",
      ),
      category_count: number(diversity.category_count, "plan.diversity.category_count"),
      summary: text(diversity.summary, "plan.diversity.summary"),
    },
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
      edges: array(explanation.edges, "explanation.edges").map((rawEdge) => {
        const edge = record(rawEdge, "explanation edge");
        const relation = text(edge.relation, "explanation edge.relation");
        if (!["REQUIRES", "OPTIONALLY_USES", "IS_A", "SUBCLASS_OF"].includes(relation)) {
          throw new ApiContractError("explanation edge.relation 无效");
        }
        return {
          source: text(edge.source, "explanation edge.source"),
          target: text(edge.target, "explanation edge.target"),
          relation: relation as "REQUIRES" | "OPTIONALLY_USES" | "IS_A" | "SUBCLASS_OF",
          evidence: strings(edge.evidence, "explanation edge.evidence"),
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
        evidence: strings(edge.evidence, "graph edge.evidence"),
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
    async agent(input, signal) {
      const response = await fetcher(`${base}/api/v1/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
        signal,
      });
      return parseAgentResponse(await responseJson(response));
    },
    async answer(input, signal) {
      const response = await fetcher(`${base}/api/v1/answers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
        signal,
      });
      return parseAnswerResponse(await responseJson(response));
    },
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
