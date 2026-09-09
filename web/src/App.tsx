import { useEffect, useRef, useState } from "react";

import type { CookKgApi, RecommendationRequest, RecommendationResponse } from "./api/types";
import { ApiHttpError } from "./api/client";
import { PlanCard } from "./components/PlanCard";
import { PlannerForm } from "./components/PlannerForm";

type Props = { api: CookKgApi; isMock: boolean };
type RequestState = "idle" | "loading" | "success" | "error";

export function App({ api, isMock }: Props) {
  const [status, setStatus] = useState<RequestState>("idle");
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [lastRequest, setLastRequest] = useState<RecommendationRequest | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const run = async (request: RecommendationRequest) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLastRequest(request);
    setStatus("loading");
    setError(null);
    setErrorStatus(null);
    try {
      const next = await api.recommend(request, controller.signal);
      setResult(next);
      setStatus("success");
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "推荐服务暂时不可用");
      setErrorStatus(reason instanceof ApiHttpError ? reason.status : null);
      setStatus("error");
    }
  };

  const primaryPlan = result?.plans[0];

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-6 py-4 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-blue-600 text-sm font-bold text-white">
              CK
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight text-slate-950">CookKG 菜单规划器</h1>
              <p className="text-xs text-slate-500">知识图谱约束推荐 · 联合补购优化</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-500 sm:inline-flex">
              HowToCook 固定快照
            </span>
            {isMock ? (
              <span className="rounded-lg bg-violet-50 px-2.5 py-1.5 text-xs font-semibold text-violet-700">
                演示数据
              </span>
            ) : (
              <span className="rounded-lg bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-700">
                实时数据
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1440px] gap-6 px-6 py-7 lg:grid-cols-[360px_minmax(0,1fr)] lg:px-8">
        <aside className="self-start rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:sticky lg:top-6">
          <PlannerForm isLoading={status === "loading"} onSubmit={run} />
        </aside>

        <section aria-live="polite" className="min-w-0 space-y-5">
          {status === "idle" ? <InitialState /> : null}
          {status === "loading" ? <LoadingState /> : null}
          {status === "error" ? (
            <ErrorState
              detail={error}
              invalidInput={errorStatus === 422}
              onRetry={() => {
                if (lastRequest) void run(lastRequest);
              }}
            />
          ) : null}
          {status === "success" && result && !result.plans.length ? (
            <EmptyState reason={result.reason} />
          ) : null}
          {status === "success" && result && primaryPlan ? (
            <>
              <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
                <Metric label="可行候选" value={`${result.candidate_count} 道`} />
                <Metric label="最少补购" tone="amber" value={`${primaryPlan.to_buy.length} 种`} />
                <Metric label="库存利用" tone="green" value={`${primaryPlan.covered.length} 种`} />
                <Metric label="约束检查" tone="blue" value="满足全部约束" />
              </div>
              {result.explanations.length ? (
                <div className="rounded-2xl border border-red-100 bg-red-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-red-600">图谱约束解释</p>
                  {result.explanations.map((item) => (
                    <p className="mt-1 text-sm leading-6 text-red-800" key={item.id}>
                      {item.message}
                    </p>
                  ))}
                </div>
              ) : null}
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">推荐结果</p>
                  <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">找到 {result.plans.length} 组菜单</h2>
                </div>
                <p className="text-xs text-slate-500">按补购少、库存利用多排序</p>
              </div>
              <div className="space-y-4">
                {result.plans.map((plan) => (
                  <PlanCard
                    api={api}
                    exclude={result.normalized_input.exclude}
                    explanations={result.explanations}
                    key={plan.id}
                    plan={plan}
                  />
                ))}
              </div>
            </>
          ) : null}
        </section>
      </main>
    </div>
  );
}

function Metric({ label, tone = "slate", value }: { label: string; tone?: string; value: string }) {
  const colors: Record<string, string> = {
    slate: "text-slate-900",
    amber: "text-amber-700",
    green: "text-emerald-700",
    blue: "text-blue-700",
  };
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={`mt-2 text-xl font-semibold ${colors[tone]}`}>{value}</p>
    </div>
  );
}

function InitialState() {
  return (
    <div className="grid min-h-[520px] place-items-center rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
      <div className="max-w-md">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-blue-50 text-xl text-blue-700" aria-hidden="true">⌘</span>
        <h2 className="mt-5 text-2xl font-semibold tracking-tight text-slate-950">从冰箱库存开始规划</h2>
        <p className="mt-3 text-sm leading-6 text-slate-500">填写已有食材和限制条件，系统会检查忌口关系，组合多道菜并合并计算补购清单。</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2 text-xs text-slate-600">
          <span className="rounded-lg bg-slate-100 px-2.5 py-1.5">层级忌口推理</span>
          <span className="rounded-lg bg-slate-100 px-2.5 py-1.5">联合补购优化</span>
          <span className="rounded-lg bg-slate-100 px-2.5 py-1.5">原文可追溯</span>
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4" role="status">
      <p className="sr-only">正在生成菜单方案</p>
      {[0, 1, 2].map((item) => (
        <div className="h-36 animate-pulse rounded-2xl border border-slate-200 bg-white" key={item} />
      ))}
    </div>
  );
}

function EmptyState({ reason }: { reason: string | null }) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center">
      <p className="text-lg font-semibold text-amber-900">{reason || "没有可行菜单"}</p>
      <p className="mt-2 text-sm text-amber-700">系统没有修改你的条件。可以自行调整补购上限或排除项后重新提交。</p>
    </div>
  );
}

function ErrorState({
  detail,
  invalidInput,
  onRetry,
}: {
  detail: string | null;
  invalidInput: boolean;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center" role="alert">
      <p className="text-lg font-semibold text-red-900">
        {invalidInput ? "输入条件有误" : "服务连接失败"}
      </p>
      <p className="mt-2 text-sm text-red-700">{detail || "请检查服务状态后重试。"}</p>
      {invalidInput ? null : (
        <button className="mt-5 rounded-xl bg-red-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-400" onClick={onRetry} type="button">
          重试上次请求
        </button>
      )}
    </div>
  );
}
