import type { CookKgApi, MenuPlan } from "../api/types";
import { GraphDrawer } from "./GraphDrawer";
import { RecipeDisclosure } from "./RecipeDisclosure";

type Props = { api: CookKgApi; plan: MenuPlan };

function TagList({ empty, items, tone }: { empty: string; items: string[]; tone: string }) {
  if (!items.length) return <p className="mt-2 text-sm text-slate-400">{empty}</p>;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${tone}`} key={item}>
          {item}
        </span>
      ))}
    </div>
  );
}

export function PlanCard({ api, plan }: Props) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold text-blue-600">方案 {plan.rank}</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">
            {plan.recipes.map((recipe) => recipe.name).join(" + ")}
          </h3>
        </div>
        <span className="shrink-0 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-700">
          补购 {plan.to_buy.length} 种
        </span>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        <div>
          <p className="text-xs font-medium text-slate-500">需要补购</p>
          <TagList empty="无需补购" items={plan.to_buy} tone="bg-amber-50 text-amber-700" />
        </div>
        <div>
          <p className="text-xs font-medium text-slate-500">利用库存</p>
          <TagList empty="没有覆盖" items={plan.covered} tone="bg-emerald-50 text-emerald-700" />
        </div>
        <div>
          <p className="text-xs font-medium text-slate-500">省略可选项</p>
          <TagList
            empty="没有省略项"
            items={plan.omitted_optional}
            tone="bg-slate-100 text-slate-600"
          />
        </div>
      </div>

      <div className="mt-5 divide-y divide-slate-100 border-t border-slate-100">
        {plan.recipes.map((recipe) => (
          <div className="flex flex-wrap items-center justify-between gap-3 py-3" key={recipe.id}>
            <span className="text-sm font-medium text-slate-800">{recipe.name}</span>
            <div className="flex items-center gap-4">
              <RecipeDisclosure api={api} recipe={recipe} />
              <a
                className="text-xs font-semibold text-slate-500 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
                href={recipe.source_url}
                rel="noopener noreferrer"
                target="_blank"
              >
                查看原文
              </a>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-end border-t border-slate-100 pt-4">
        <GraphDrawer api={api} plan={plan} />
      </div>
    </article>
  );
}
