import * as Dialog from "@radix-ui/react-dialog";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";
import "@xyflow/react/dist/style.css";

import type { CookKgApi, GraphNeighborhood, GraphNode, MenuPlan } from "../api/types";

type Props = { api: CookKgApi; plan: MenuPlan };

const kindLabels: Record<GraphNode["kind"], string> = {
  recipe: "菜谱",
  ingredient: "食材",
  category: "食材类别",
  tool: "工具",
};

const nodeColors: Record<GraphNode["kind"], { background: string; border: string; color: string }> = {
  recipe: { background: "#eff6ff", border: "#2563eb", color: "#1e3a8a" },
  ingredient: { background: "#ecfdf5", border: "#10b981", color: "#065f46" },
  category: { background: "#f5f3ff", border: "#8b5cf6", color: "#5b21b6" },
  tool: { background: "#f8fafc", border: "#94a3b8", color: "#334155" },
};

function graphElements(graph: GraphNeighborhood): { nodes: Node[]; edges: Edge[] } {
  const rows: Record<GraphNode["kind"], number> = {
    recipe: 0,
    ingredient: 0,
    category: 0,
    tool: 0,
  };
  const x: Record<GraphNode["kind"], number> = {
    recipe: 0,
    ingredient: 240,
    category: 480,
    tool: 240,
  };
  const nodes = graph.nodes.map((node): Node => {
    const row = rows[node.kind]++;
    const toolOffset = node.kind === "tool" ? 320 : 0;
    return {
      id: node.id,
      data: { label: node.label, kind: node.kind },
      position: { x: x[node.kind], y: row * 92 + toolOffset },
      style: {
        ...nodeColors[node.kind],
        borderWidth: node.excluded ? 2 : 1,
        borderColor: node.excluded ? "#dc2626" : nodeColors[node.kind].border,
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 600,
        padding: "10px 12px",
        width: 150,
      },
    };
  });
  const edges = graph.edges.map((edge): Edge => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.relation,
    markerEnd: { type: MarkerType.ArrowClosed },
    style: {
      stroke: edge.excluded ? "#dc2626" : "#64748b",
      strokeWidth: edge.excluded ? 2 : 1.25,
      strokeDasharray: edge.relation === "OPTIONALLY_USES" ? "6 4" : undefined,
    },
    labelStyle: { fill: edge.excluded ? "#b91c1c" : "#475569", fontSize: 9 },
  }));
  return { nodes, edges };
}

export function GraphDrawer({ api, plan }: Props) {
  const [open, setOpen] = useState(false);
  const [recipeId, setRecipeId] = useState(plan.recipes[0]?.id || "");
  const [graph, setGraph] = useState<GraphNeighborhood | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<{ label: string; kind: GraphNode["kind"] } | null>(null);

  useEffect(() => {
    if (!open || !recipeId) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setGraph(null);
    setSelected(null);
    api
      .getNeighborhood(recipeId, 30, controller.signal)
      .then(setGraph)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "图谱加载失败");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [api, open, recipeId]);

  const elements = useMemo(() => (graph ? graphElements(graph) : null), [graph]);

  return (
    <Dialog.Root onOpenChange={setOpen} open={open}>
      <Dialog.Trigger asChild>
        <button
          className="rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 hover:border-blue-300 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-300"
          type="button"
        >
          查看方案 {plan.rank} 图谱解释
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/30 data-[state=open]:animate-in" />
        <Dialog.Content
          aria-describedby="graph-description"
          className="fixed inset-y-0 right-0 z-50 flex w-[min(640px,92vw)] flex-col border-l border-slate-200 bg-white shadow-2xl focus:outline-none"
        >
          <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
            <div>
              <Dialog.Title className="text-lg font-semibold text-slate-950">
                方案 {plan.rank} 知识图谱
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-slate-500" id="graph-description">
                查看菜谱、食材、类别和工具之间的审核关系。
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                aria-label="关闭图谱"
                className="grid h-9 w-9 place-items-center rounded-lg border border-slate-200 text-xl text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-300"
                type="button"
              >
                ×
              </button>
            </Dialog.Close>
          </div>

          <div className="flex gap-2 overflow-x-auto border-b border-slate-200 px-5 py-3">
            {plan.recipes.map((recipe) => (
              <button
                aria-pressed={recipeId === recipe.id}
                className={`shrink-0 rounded-lg px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-300 ${
                  recipeId === recipe.id
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
                key={recipe.id}
                onClick={() => setRecipeId(recipe.id)}
                type="button"
              >
                {recipe.name}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-3 border-b border-slate-100 px-5 py-2.5 text-[11px] text-slate-500">
            <span>● 菜谱</span><span className="text-emerald-700">● 食材</span>
            <span className="text-violet-700">● 类别</span><span>● 工具</span>
            <span>— 必需</span><span>-- 可选</span>
          </div>

          <div className="relative min-h-0 flex-1 bg-slate-50">
            {loading ? <div className="absolute inset-0 z-10 grid place-items-center text-sm text-slate-500">正在加载图谱…</div> : null}
            {error ? (
              <div className="absolute inset-0 z-10 grid place-items-center p-8 text-center">
                <div><p className="font-semibold text-red-800">图谱服务暂时不可用</p><p className="mt-2 text-sm text-red-600">详情：{error}</p></div>
              </div>
            ) : null}
            {elements ? (
              <ReactFlow
                edges={elements.edges}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                nodes={elements.nodes}
                nodesDraggable
                onNodeClick={(_, node) =>
                  setSelected({
                    label: String(node.data.label),
                    kind: node.data.kind as GraphNode["kind"],
                  })
                }
              >
                <Background color="#cbd5e1" gap={18} size={1} />
                <Controls showInteractive={false} />
              </ReactFlow>
            ) : null}
          </div>

          {selected ? (
            <div className="border-t border-slate-200 bg-white px-5 py-3 text-sm">
              <span className="font-semibold text-slate-900">{selected.label}</span>
              <span className="ml-3 text-slate-500">节点类型：{kindLabels[selected.kind]}</span>
            </div>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
