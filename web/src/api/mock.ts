import type {
  CookKgApi,
  AnswerResponse,
  GraphNeighborhood,
  RecipeDetail,
  RecommendationResponse,
} from "./types";

type MockScenario = "success" | "empty" | "error" | "graph-error" | "answer-error" | "answer-empty";
type MockOptions = { delayMs?: number; scenario?: MockScenario };

const commit = "2b19c9e9ee926fd925a68207a57582a338813f9c";
const source = (path: string) =>
  `https://github.com/Anduin2017/HowToCook/blob/${commit}/${path}`;

const recipes: Record<string, RecipeDetail> = {
  "dishes/breakfast/空气炸锅面包片.md": {
    id: "dishes/breakfast/空气炸锅面包片.md",
    name: "空气炸锅面包片",
    source_url: source("dishes/breakfast/空气炸锅面包片.md"),
    category: "早餐",
    difficulty: 1,
    ingredients: [
      { name: "面包片", requirement: "required", quantity_raw: ["面包片 2 片"] },
      { name: "黄油", requirement: "required", quantity_raw: ["黄油 10 g"] },
    ],
    steps: "在面包片表面均匀涂抹黄油。放入空气炸锅，按菜谱温度烤至表面酥脆。",
  },
  "dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md": {
    id: "dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md",
    name: "洋葱炒鸡蛋",
    source_url: source("dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md"),
    category: "素菜",
    difficulty: 2,
    ingredients: [
      { name: "鸡蛋", requirement: "required", quantity_raw: ["鸡蛋 2 个"] },
      { name: "洋葱", requirement: "required", quantity_raw: ["洋葱 50 g"] },
      { name: "葱", requirement: "required", quantity_raw: ["葱 半根"] },
      { name: "食用油", requirement: "required", quantity_raw: ["食用油 50 ml"] },
    ],
    steps: "鸡蛋与洋葱片、盐搅拌。起锅烧油后煎炒，最后加入料酒并撒葱花。",
  },
  "dishes/breakfast/鸡蛋三明治.md": {
    id: "dishes/breakfast/鸡蛋三明治.md",
    name: "鸡蛋三明治",
    source_url: source("dishes/breakfast/鸡蛋三明治.md"),
    category: "早餐",
    difficulty: 2,
    ingredients: [
      { name: "鸡蛋", requirement: "required", quantity_raw: ["鸡蛋 1 个"] },
      { name: "吐司", requirement: "required", quantity_raw: ["吐司 2 片"] },
      { name: "培根", requirement: "required", quantity_raw: ["培根 2 片"] },
      { name: "蛋黄酱", requirement: "required", quantity_raw: ["蛋黄酱 20 g"] },
      { name: "酸黄瓜", requirement: "optional", quantity_raw: [] },
    ],
    steps: "煮熟鸡蛋并捣碎，与蛋黄酱、盐和黑胡椒混合。煎熟培根后夹入吐司。",
  },
  "dishes/meat_dish/小炒肉.md": {
    id: "dishes/meat_dish/小炒肉.md",
    name: "小炒肉",
    source_url: source("dishes/meat_dish/小炒肉.md"),
    category: "荤菜",
    difficulty: 3,
    ingredients: [
      { name: "小米椒", requirement: "required", quantity_raw: ["小米椒 2 个"] },
      { name: "猪肉", requirement: "required", quantity_raw: ["猪肉 200 g"] },
    ],
    steps: "猪肉切片，与小米椒一起炒熟。",
  },
};

const success: RecommendationResponse = {
  plans: [
    {
      id: "plan-1",
      rank: 1,
      recipes: [
        recipes["dishes/breakfast/空气炸锅面包片.md"],
        recipes["dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md"],
      ].map(({ id, name, source_url }) => ({ id, name, source_url })),
      to_buy: ["葱"],
      covered: ["鸡蛋", "洋葱", "面包片"],
      omitted_optional: [],
    },
    {
      id: "plan-2",
      rank: 2,
      recipes: [
        recipes["dishes/breakfast/鸡蛋三明治.md"],
        recipes["dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md"],
      ].map(({ id, name, source_url }) => ({ id, name, source_url })),
      to_buy: ["培根", "蛋黄酱"],
      covered: ["鸡蛋", "洋葱", "面包片"],
      omitted_optional: ["酸黄瓜"],
    },
  ],
  reason: null,
  candidate_count: 8,
  normalized_input: {
    have: ["鸡蛋", "洋葱", "面包片"],
    pantry: ["盐", "食用油", "黄油", "料酒"],
    exclude: ["辣椒"],
  },
  excluded_ingredients: ["辣椒", "小米椒", "朝天椒", "青椒"],
  explanations: [
    {
      id: "exclude-xiaochao",
      kind: "excluded_required",
      message: "小炒肉必需使用小米椒；小米椒属于用户排除的辣椒类别。",
      path: [
        { id: "r:dishes/meat_dish/小炒肉.md", label: "小炒肉", kind: "recipe" },
        { id: "ingredient:小米椒", label: "小米椒", kind: "ingredient" },
        { id: "category:辣椒", label: "辣椒", kind: "category" },
      ],
      edges: [
        {
          source: "r:dishes/meat_dish/小炒肉.md",
          target: "ingredient:小米椒",
          relation: "REQUIRES",
          evidence: ["HowToCook 原料章节"],
        },
        {
          source: "ingredient:小米椒",
          target: "category:辣椒",
          relation: "IS_A",
          evidence: ["CookKG taxonomy review 2026-09-09"],
        },
      ],
    },
  ],
};

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

function graphFor(recipeId: string, exclude: string[] = []): GraphNeighborhood {
  const recipe = recipes[recipeId];
  if (!recipe) throw new Error("没有找到这道菜的图谱数据");
  const ingredientNodes = recipe.ingredients.map((item) => ({
    id: `ingredient:${item.name}`,
    label: item.name,
    kind: "ingredient" as const,
    excluded: exclude.includes("辣椒") && item.name === "小米椒",
  }));
  const pepper = recipe.ingredients.some((item) => item.name === "小米椒");
  return {
    recipe_id: recipeId,
    nodes: [
      { id: `recipe:${recipeId}`, label: recipe.name, kind: "recipe" },
      ...ingredientNodes,
      ...(pepper
        ? [{ id: "category:辣椒", label: "辣椒", kind: "category" as const, excluded: true }]
        : []),
      { id: "tool:炒锅", label: "炒锅", kind: "tool" },
    ],
    edges: [
      ...recipe.ingredients.map((item, index) => ({
        id: `edge:${index}`,
        source: `recipe:${recipeId}`,
        target: `ingredient:${item.name}`,
        relation: item.requirement === "optional" ? ("OPTIONALLY_USES" as const) : ("REQUIRES" as const),
        evidence: ["HowToCook 原料章节"],
        excluded: exclude.includes("辣椒") && item.name === "小米椒",
      })),
      ...(pepper
        ? [{
            id: "edge:category",
            source: "ingredient:小米椒",
            target: "category:辣椒",
            relation: "IS_A" as const,
            evidence: ["CookKG taxonomy review 2026-09-09"],
            excluded: true,
          }]
        : []),
      {
        id: "edge:tool",
        source: `recipe:${recipeId}`,
        target: "tool:炒锅",
        relation: "REQUIRES_TOOL",
        evidence: [],
      },
    ],
  };
}

function answerFor(question: string): AnswerResponse {
  if (question.includes("空气炸锅面包片")) {
    return {
      answer: "空气炸锅面包片使用 200°C 烘烤 5 分钟。[E1]",
      retriever: "vector",
      route_reason: "问题主要询问单道菜的原文事实或步骤",
      insufficient_evidence: false,
      citations: [{
        evidence_id: "E1",
        record_id: "ev-air-fryer-step",
        recipe_id: "dishes/breakfast/空气炸锅面包片.md",
        text: "菜谱“空气炸锅面包片”的操作步骤：3. 200°C 烘烤 5 分钟",
        source_url: source("dishes/breakfast/空气炸锅面包片.md"),
        line_start: 24,
        line_end: 24,
      }],
    };
  }
  if (question.includes("洋葱炒鸡蛋") && question.includes("几个鸡蛋")) {
    return {
      answer: "洋葱炒鸡蛋需要鸡蛋 2 个。[E1]",
      retriever: "vector",
      route_reason: "问题主要询问单道菜的原文事实或步骤",
      insufficient_evidence: false,
      citations: [{
        evidence_id: "E1",
        record_id: "ev-onion-egg-quantity",
        recipe_id: "dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md",
        text: "菜谱“洋葱炒鸡蛋”的必需食材：鸡蛋 2 个。",
        source_url: source("dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md"),
        line_start: 12,
        line_end: 12,
      }],
    };
  }
  if (question.includes("小炒肉") && question.includes("必需食材")) {
    return {
      answer: "小炒肉的必需食材包括五花肉、小米椒和朝天椒等。[E1][E2][E3]",
      retriever: "vector_cypher",
      route_reason: "问题需要从文本证据扩展到图谱关系",
      insufficient_evidence: false,
      citations: [
        {
          evidence_id: "E1", record_id: "ev-xiaochao-pork", recipe_id: "dishes/meat_dish/小炒肉.md",
          text: "菜谱“小炒肉”的必需食材：五花肉 500g。", source_url: source("dishes/meat_dish/小炒肉.md"), line_start: 10, line_end: 10,
        },
        {
          evidence_id: "E2", record_id: "ev-xiaochao-millet-pepper", recipe_id: "dishes/meat_dish/小炒肉.md",
          text: "菜谱“小炒肉”的必需食材：小米椒 4 颗。", source_url: source("dishes/meat_dish/小炒肉.md"), line_start: 12, line_end: 12,
        },
        {
          evidence_id: "E3", record_id: "ev-xiaochao-chili", recipe_id: "dishes/meat_dish/小炒肉.md",
          text: "菜谱“小炒肉”的必需食材：朝天椒 4 条。", source_url: source("dishes/meat_dish/小炒肉.md"), line_start: 11, line_end: 11,
        },
      ],
    };
  }
  if (question.includes("哪些菜") && question.includes("鸡蛋")) {
    return {
      answer: "当前证据中，美式炒蛋、鸡蛋三明治、洋葱炒鸡蛋和莴笋叶煎饼都使用鸡蛋。[E1][E2][E3][E4]",
      retriever: "hybrid_cypher",
      route_reason: "问题需要跨菜谱或跨实体关系检索",
      insufficient_evidence: false,
      citations: [
        { evidence_id: "E1", record_id: "ev-american-eggs", recipe_id: "dishes/breakfast/美式炒蛋.md", text: "菜谱“美式炒蛋”的必需食材：鸡蛋。", source_url: source("dishes/breakfast/美式炒蛋.md"), line_start: 11, line_end: 11 },
        { evidence_id: "E2", record_id: "ev-sandwich-eggs", recipe_id: "dishes/breakfast/鸡蛋三明治.md", text: "菜谱“鸡蛋三明治”的必需食材：鸡蛋 1 个。", source_url: source("dishes/breakfast/鸡蛋三明治.md"), line_start: 11, line_end: 11 },
        { evidence_id: "E3", record_id: "ev-onion-eggs", recipe_id: "dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md", text: "菜谱“洋葱炒鸡蛋”的必需食材：鸡蛋 2 个。", source_url: source("dishes/vegetable_dish/洋葱炒鸡蛋/洋葱炒鸡蛋.md"), line_start: 12, line_end: 12 },
        { evidence_id: "E4", record_id: "ev-lettuce-eggs", recipe_id: "dishes/vegetable_dish/莴笋叶煎饼.md", text: "菜谱“莴笋叶煎饼”的必需食材：鸡蛋。", source_url: source("dishes/vegetable_dish/莴笋叶煎饼.md"), line_start: 12, line_end: 12 },
      ],
    };
  }
  return {
    answer: "小炒肉必需使用小米椒，而小米椒属于辣椒类别。[E1][E2]",
    retriever: "hybrid_cypher",
    route_reason: "问题同时涉及菜谱、食材和类别关系",
    insufficient_evidence: false,
    citations: [
      {
        evidence_id: "E1", record_id: "ev-xiaochao-pepper", recipe_id: "dishes/meat_dish/小炒肉.md",
        text: "小米椒 4 颗", source_url: source("dishes/meat_dish/小炒肉.md"), line_start: 12, line_end: 12,
      },
      {
        evidence_id: "E2", record_id: "ev-pepper-category", recipe_id: "dishes/meat_dish/小炒肉.md",
        text: "小米椒属于辣椒类别。", source_url: source("dishes/meat_dish/小炒肉.md"), line_start: 12, line_end: 12,
      },
    ],
  };
}

export function createMockApi(options: MockOptions = {}): CookKgApi {
  const { delayMs = 350, scenario = "success" } = options;
  return {
    async answer(input, signal) {
      await wait(delayMs, signal);
      if (scenario === "answer-error") throw new Error("问答服务暂时不可用");
      const response = scenario === "answer-empty"
        ? {
            answer: "当前证据不足，无法可靠回答。", retriever: "vector" as const,
            route_reason: "问题主要询问单道菜的原文事实或步骤", insufficient_evidence: true, citations: [],
          }
        : answerFor(input.question);
      return response;
    },
    async recommend(_input, signal) {
      await wait(delayMs, signal);
      if (scenario === "error") throw new Error("演示推荐服务暂时不可用");
      if (scenario === "empty") {
        return { ...success, plans: [], reason: "没有满足当前约束的菜单组合" };
      }
      return structuredClone(success);
    },
    async getRecipe(recipeId, signal) {
      await wait(delayMs, signal);
      const recipe = recipes[recipeId];
      if (!recipe) throw new Error("没有找到菜谱详情");
      return structuredClone(recipe);
    },
    async getNeighborhood(recipeId, options = {}, signal) {
      await wait(delayMs, signal);
      if (scenario === "graph-error") throw new Error("图谱服务暂时不可用");
      return graphFor(recipeId, options.exclude);
    },
  };
}
