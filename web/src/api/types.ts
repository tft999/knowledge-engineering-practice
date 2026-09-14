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
  diversity: {
    categories: string[];
    repeated_core_ingredients: string[];
    same_category_pairs: number;
    max_ingredient_similarity: number;
    category_count: number;
    summary: string;
  };
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

export type RetrieverName = "vector" | "vector_cypher" | "hybrid" | "hybrid_cypher";

export type AnswerRequest = {
  question: string;
  retriever: "auto" | RetrieverName;
  top_k: number;
};

export type Citation = {
  evidence_id: string;
  record_id: string;
  recipe_id: string;
  text: string;
  source_url: string;
  line_start: number;
  line_end: number;
};

export type AnswerResponse = {
  answer: string;
  citations: Citation[];
  retriever: RetrieverName;
  route_reason: string;
  insufficient_evidence: boolean;
};

export type AgentRequest = {
  question: string;
  top_k: number;
};

export type AgentMode = "help" | "planner" | "graphrag" | "clarification";

export type AgentResponse = {
  mode: AgentMode;
  answer: string;
  route_reason: string;
  normalized_terms: Array<{
    raw: string;
    canonical: string;
    field: "have" | "pantry" | "exclude";
    source: "exact" | "alias" | "entity_linker" | "category_linker";
  }>;
  tool_trace: Array<{
    tool: "plan_menu" | "answer_knowledge";
    status: "success" | "empty";
    summary: string;
  }>;
  recommendation: RecommendationResponse | null;
  citations: Citation[];
  retriever: RetrieverName | null;
  insufficient_evidence: boolean;
  clarification_question: string | null;
};

export interface CookKgApi {
  agent(input: AgentRequest, signal?: AbortSignal): Promise<AgentResponse>;
  answer(input: AnswerRequest, signal?: AbortSignal): Promise<AnswerResponse>;
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
