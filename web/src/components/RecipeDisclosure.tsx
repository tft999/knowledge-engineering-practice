import { useEffect, useState } from "react";

import type { CookKgApi, RecipeDetail, RecipeSummary } from "../api/types";

type Props = { api: CookKgApi; recipe: RecipeSummary };

export function RecipeDisclosure({ api, recipe }: Props) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<RecipeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || detail) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    api
      .getRecipe(recipe.id, controller.signal)
      .then(setDetail)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "菜谱详情加载失败");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [api, detail, open, recipe.id]);

  return (
    <div>
      <button
        aria-expanded={open}
        className="text-xs font-semibold text-blue-700 hover:text-blue-900 focus:outline-none focus:ring-2 focus:ring-blue-300"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        {open ? "收起" : "查看"}{recipe.name}详情
      </button>
      {open ? (
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
          {loading ? <p className="text-sm text-slate-500">正在加载菜谱详情…</p> : null}
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          {detail ? (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2 text-xs text-slate-600">
                <span className="rounded-md bg-white px-2 py-1">类别：{detail.category}</span>
                <span className="rounded-md bg-white px-2 py-1">
                  难度：{detail.difficulty === null ? "未标注" : `${detail.difficulty} 星`}
                </span>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-slate-900">原料与用量</h4>
                <ul className="mt-2 grid gap-1 text-sm text-slate-600 sm:grid-cols-2">
                  {detail.ingredients.map((ingredient) => (
                    <li className="flex gap-2" key={`${recipe.id}:${ingredient.name}`}>
                      <span aria-hidden="true">•</span>
                      <span>
                        {ingredient.quantity_raw[0] || ingredient.name}
                        {ingredient.requirement === "optional" ? "（可选）" : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-slate-900">操作摘要</h4>
                <p className="mt-2 text-sm leading-6 text-slate-600">{detail.steps}</p>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
