import { FormEvent, useEffect, useRef, useState } from "react";

import type { AnswerResponse, CookKgApi, RetrieverName } from "../api/types";

type State = "idle" | "loading" | "success" | "error";

const labels: Record<RetrieverName, string> = {
  vector: "Vector",
  vector_cypher: "VectorCypher",
  hybrid: "Hybrid",
  hybrid_cypher: "HybridCypher",
};

const demoQuestions = [
  { label: "步骤", question: "空气炸锅面包片要用多少度、烤多久？" },
  { label: "用量", question: "洋葱炒鸡蛋需要几个鸡蛋？" },
  { label: "组成", question: "小炒肉需要哪些必需食材？" },
  { label: "关联", question: "哪些菜都使用鸡蛋？" },
] as const;

export function AnswerPanel({ api }: { api: CookKgApi }) {
  const [question, setQuestion] = useState("哪些菜都使用鸡蛋？");
  const [state, setState] = useState<State>("idle");
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  async function ask(event?: FormEvent) {
    event?.preventDefault();
    if (!question.trim()) return;
    controller.current?.abort();
    controller.current = new AbortController();
    setState("loading");
    setError("");
    try {
      setResult(await api.answer({ question: question.trim(), retriever: "auto", top_k: 5 }, controller.current.signal));
      setState("success");
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "问答服务暂时不可用");
      setState("error");
    }
  }

  return (
    <section className="space-y-5">
      <form className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" onSubmit={ask}>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-blue-700">GraphRAG 菜谱问答</p>
        <h2 className="mt-2 text-2xl font-semibold text-slate-950">从图关系和菜谱原文中寻找答案</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">系统自动选择检索器。硬约束菜单仍由确定性算法处理。</p>
        <div className="mt-5">
          <p className="text-sm font-medium text-slate-800">演示问题</p>
          <div className="mt-2 flex flex-wrap gap-2" aria-label="演示问题">
            {demoQuestions.map((item) => (
              <button
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs text-slate-700 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-200"
                key={item.question}
                onClick={() => setQuestion(item.question)}
                type="button"
              >
                <span className="mr-1 font-semibold text-blue-700">{item.label}</span>
                {item.question}
              </button>
            ))}
          </div>
        </div>
        <label className="mt-5 block text-sm font-medium text-slate-800" htmlFor="question">问题</label>
        <textarea
          className="mt-2 min-h-28 w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          id="question"
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="例如：哪些菜都使用鸡蛋？"
          value={question}
        />
        <button className="mt-3 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60" disabled={state === "loading" || !question.trim()} type="submit">
          {state === "loading" ? "正在检索证据…" : "查询知识库"}
        </button>
      </form>

      {state === "error" ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6" role="alert">
          <p className="font-semibold text-red-900">问答服务不可用</p>
          <p className="mt-1 text-sm text-red-700">{error}</p>
          <button className="mt-4 rounded-lg border border-red-300 px-3 py-2 text-sm font-semibold text-red-800" onClick={() => void ask()} type="button">重试</button>
        </div>
      ) : null}

      {state === "success" && result ? (
        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-lg bg-violet-50 px-2.5 py-1.5 font-semibold text-violet-700">{labels[result.retriever]}</span>
            <span className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-slate-600">{result.route_reason}</span>
          </div>
          <h3 className="mt-5 text-sm font-semibold text-slate-500">回答</h3>
          <p className="mt-2 whitespace-pre-wrap text-base leading-7 text-slate-900">
            <AnswerText answer={result.answer} />
          </p>
          {result.insufficient_evidence ? (
            <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-800">证据不足：系统拒绝生成无来源结论。</p>
          ) : null}
          {result.citations.length ? (
            <div className="mt-6 border-t border-slate-100 pt-5">
              <h3 className="font-semibold text-slate-900">引用证据</h3>
              <div className="mt-3 space-y-3">
                {result.citations.map((citation) => (
                  <div className="rounded-xl border border-slate-200 p-4" id={`citation-${citation.evidence_id}`} key={citation.record_id}>
                    <div className="flex items-center justify-between gap-3">
                      <strong className="text-sm text-blue-700">[{citation.evidence_id}]</strong>
                      <a className="text-xs font-semibold text-blue-700 hover:underline" href={`${citation.source_url}#L${citation.line_start}`} rel="noopener noreferrer" target="_blank">查看固定版本原文</a>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-700">{citation.text}</p>
                    <p className="mt-2 text-xs text-slate-400">{citation.recipe_id} · 第 {citation.line_start}–{citation.line_end} 行</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </article>
      ) : null}
    </section>
  );
}

function AnswerText({ answer }: { answer: string }) {
  return answer.split(/(\[E\d+\])/g).map((part, index) => {
    const marker = part.match(/^\[(E\d+)\]$/)?.[1];
    return marker ? (
      <a
        aria-label={`跳转到证据 ${marker}`}
        className="font-semibold text-blue-700 underline decoration-blue-300 underline-offset-2"
        href={`#citation-${marker}`}
        key={`${marker}-${index}`}
      >
        [{marker}]
      </a>
    ) : (
      part
    );
  });
}
