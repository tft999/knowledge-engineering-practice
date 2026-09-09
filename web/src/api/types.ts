export type RecipeSummary = {
  id: string;
  name: string;
  source_url: string;
};

export type RecommendationRequest = {
  have: string[];
  pantry: string[];
  exclude: string[];
  count: 1 | 2 | 3;
  max_buy: number;
  limit: 5;
};

export type MenuPlan = {
  id: string;
  rank: number;
  recipes: RecipeSummary[];
  to_buy: string[];
  covered: string[];
  omitted_optional: string[];
};

export type NormalizedInput = {
  have: string[];
  pantry: string[];
  exclude: string[];
};

export type ExplanationNodeKind = "recipe" | "ingredient" | "category" | "tool";

export type Explanation = {
  id: string;
  kind: "excluded_required" | "omitted_optional" | "normalization";
  message: string;
  path: Array<{ id: string; label: string; kind: ExplanationNodeKind }>;
  edges: Array<{
    source: string;
    target: string;
    relation: "REQUIRES" | "OPTIONALLY_USES" | "IS_A" | "SUBCLASS_OF";
    evidence: string[];
  }>;
};

export type RecommendationResponse = {
  plans: MenuPlan[];
  reason: string | null;
  candidate_count: number;
  normalized_input: NormalizedInput;
  excluded_ingredients: string[];
  explanations: Explanation[];
};

export type RecipeIngredient = {
  name: string;
  requirement: "required" | "optional" | "one_of";
  quantity_raw: string[];
};

export type RecipeDetail = RecipeSummary & {
  category: string;
  difficulty: number | null;
  ingredients: RecipeIngredient[];
  steps: string;
};

export type GraphNode = {
  id: string;
  label: string;
  kind: ExplanationNodeKind;
  excluded?: boolean;
};

export type GraphRelation =
  | "REQUIRES"
  | "OPTIONALLY_USES"
  | "ONE_OF"
  | "IS_A"
  | "SUBCLASS_OF"
  | "REQUIRES_TOOL";

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relation: GraphRelation;
  evidence: string[];
  excluded?: boolean;
};

export type GraphNeighborhood = {
  recipe_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type GraphNeighborhoodOptions = {
  limit?: number;
  exclude?: string[];
};

export interface CookKgApi {
  recommend(
    input: RecommendationRequest,
    signal?: AbortSignal,
  ): Promise<RecommendationResponse>;
  getRecipe(recipeId: string, signal?: AbortSignal): Promise<RecipeDetail>;
  getNeighborhood(
    recipeId: string,
    options?: GraphNeighborhoodOptions,
    signal?: AbortSignal,
  ): Promise<GraphNeighborhood>;
}
