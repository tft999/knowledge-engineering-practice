import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { api, isMockApi } from "./api";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App api={api} isMock={isMockApi} />
  </StrictMode>,
);
