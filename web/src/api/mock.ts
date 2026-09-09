import type {
  CookKgApi,
  GraphNeighborhood,
  RecipeDetail,
  RecommendationResponse,
} from "./types";

type MockScenario = "success" | "empty" | "error" | "graph-error";
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
        { id: "recipe:小炒肉", label: "小炒肉", kind: "recipe" },
        { id: "ingredient:小米椒", label: "小米椒", kind: "ingredient" },
        { id: "category:辣椒", label: "辣椒", kind: "category" },
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

function graphFor(recipeId: string): GraphNeighborhood {
  const recipe = recipes[recipeId];
  if (!recipe) throw new Error("没有找到这道菜的图谱数据");
  const ingredientNodes = recipe.ingredients.map((item) => ({
    id: `ingredient:${item.name}`,
    label: item.name,
    kind: "ingredient" as const,
  }));
  return {
    recipe_id: recipeId,
    nodes: [
      { id: `recipe:${recipeId}`, label: recipe.name, kind: "recipe" },
      ...ingredientNodes,
      { id: "category:家常菜", label: "家常菜", kind: "category" },
      { id: "tool:炒锅", label: "炒锅", kind: "tool" },
    ],
    edges: [
      ...recipe.ingredients.map((item, index) => ({
        id: `edge:${index}`,
        source: `recipe:${recipeId}`,
        target: `ingredient:${item.name}`,
        relation: item.requirement === "optional" ? ("OPTIONALLY_USES" as const) : ("REQUIRES" as const),
      })),
      {
        id: "edge:category",
        source: ingredientNodes[0].id,
        target: "category:家常菜",
        relation: "IS_A",
      },
      {
        id: "edge:tool",
        source: `recipe:${recipeId}`,
        target: "tool:炒锅",
        relation: "REQUIRES_TOOL",
      },
    ],
  };
}

export function createMockApi(options: MockOptions = {}): CookKgApi {
  const { delayMs = 350, scenario = "success" } = options;
  return {
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
    async getNeighborhood(recipeId, _limit = 30, signal) {
      await wait(delayMs, signal);
      if (scenario === "graph-error") throw new Error("图谱服务暂时不可用");
      return graphFor(recipeId);
    },
  };
}
