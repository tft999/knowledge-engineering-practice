import { FormEvent, useState } from "react";

import type { RecommendationRequest } from "../api/types";
import { IngredientTagInput } from "./IngredientTagInput";

type Props = {
  isLoading: boolean;
  onSubmit: (request: RecommendationRequest) => void;
};

const demo: RecommendationRequest = {
  have: ["鸡蛋", "洋葱", "面包片"],
  pantry: ["盐", "食用油", "黄油", "料酒"],
  exclude: ["辣椒"],
  count: 2,
  max_buy: 2,
  limit: 5,
};

export function PlannerForm({ isLoading, onSubmit }: Props) {
  const [have, setHave] = useState<string[]>([]);
  const [pantry, setPantry] = useState<string[]>([]);
  const [exclude, setExclude] = useState<string[]>([]);
  const [count, setCount] = useState<1 | 2 | 3>(2);
  const [maxBuy, setMaxBuy] = useState(2);
  const [error, setError] = useState<string | null>(null);

  const loadDemo = () => {
    setHave(demo.have);
    setPantry(demo.pantry);
    setExclude(demo.exclude);
    setCount(demo.count);
    setMaxBuy(demo.max_buy);
    setError(null);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const available = new Set([...have, ...pantry]);
    const conflict = exclude.find((item) => available.has(item));
    if (conflict) {
      setError(`${conflict}同时出现在可用和排除条件中`);
      return;
    }
    setError(null);
    onSubmit({ have, pantry, exclude, count, max_buy: maxBuy, limit: 5 });
  };

  return (
    <form className="space-y-6" onSubmit={submit}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
            规划条件
          </p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">这一餐怎么安排？</h2>
        </div>
        <button
          className="shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:border-blue-300 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
          onClick={loadDemo}
          type="button"
        >
          载入演示示例
        </button>
      </div>

      <IngredientTagInput
        description="希望优先利用的冰箱库存"
        id="have"
        label="已有食材"
        onChange={setHave}
        placeholder="如：鸡蛋、洋葱"
        value={have}
      />
      <IngredientTagInput
        description="只有明确填写的调料才视为已有"
        id="pantry"
        label="常备调料"
        onChange={setPantry}
        placeholder="如：盐、食用油"
        value={pantry}
      />
      <IngredientTagInput
        description="可填写具体食材或食材类别"
        id="exclude"
        label="排除食材或类别"
        onChange={setExclude}
        placeholder="如：辣椒"
        tone="danger"
        value={exclude}
      />

      <fieldset>
        <legend className="text-sm font-semibold text-slate-800">计划菜数</legend>
        <div className="mt-2 grid grid-cols-3 gap-2">
          {([1, 2, 3] as const).map((value) => (
            <button
              aria-pressed={count === value}
              className={`rounded-xl border px-3 py-2.5 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-blue-300 ${
                count === value
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-blue-300"
              }`}
              key={value}
              onClick={() => setCount(value)}
              type="button"
            >
              {value} 道
            </button>
          ))}
        </div>
      </fieldset>

      <div>
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-slate-800" htmlFor="max-buy">
            最多补购种类
          </label>
          <span className="rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">
            {maxBuy} 种
          </span>
        </div>
        <input
          aria-label="最多补购种类"
          className="mt-3 h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-blue-600"
          id="max-buy"
          max="20"
          min="0"
          onChange={(event) => setMaxBuy(Number(event.target.value))}
          type="range"
          value={maxBuy}
        />
        <div className="mt-1 flex justify-between text-[11px] text-slate-400">
          <span>0</span>
          <span>20</span>
        </div>
      </div>

      {error ? (
        <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}

      <button
        className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 disabled:cursor-wait disabled:bg-blue-400"
        disabled={isLoading}
        type="submit"
      >
        {isLoading ? "正在计算可行菜单…" : "生成菜单方案"}
      </button>
    </form>
  );
}
