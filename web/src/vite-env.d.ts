/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_USE_MOCKS?: string;
  readonly VITE_MOCK_SCENARIO?: "success" | "empty" | "error" | "graph-error";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
