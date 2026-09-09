import { createHttpApi } from "./client";
import { createMockApi } from "./mock";

const useMocks = import.meta.env.VITE_USE_MOCKS !== "false";
const scenario = import.meta.env.VITE_MOCK_SCENARIO as
  | "success"
  | "empty"
  | "error"
  | "graph-error"
  | undefined;

export const api = useMocks
  ? createMockApi({ scenario: scenario || "success" })
  : createHttpApi(import.meta.env.VITE_API_BASE_URL || "http://localhost:8000");

export const isMockApi = useMocks;
