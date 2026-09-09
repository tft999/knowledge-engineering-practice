import { useState } from "react";

type Props = {
  id: string;
  label: string;
  description?: string;
  placeholder?: string;
  tone?: "default" | "danger";
  value: string[];
  onChange: (value: string[]) => void;
};

function unique(values: string[]): string[] {
  return [...new Set(values.map((item) => item.trim()).filter(Boolean))];
}

export function IngredientTagInput({
  id,
  label,
  description,
  placeholder = "输入后按 Enter",
  tone = "default",
  value,
  onChange,
}: Props) {
  const [draft, setDraft] = useState("");

  const commit = (raw: string) => {
    const incoming = raw.split(/[,，]/);
    const next = unique([...value, ...incoming]);
    if (next.length !== value.length) onChange(next);
    setDraft("");
  };

  return (
    <div className="space-y-2">
      <div>
        <label className="text-sm font-semibold text-slate-800" htmlFor={id}>
          {label}
        </label>
        {description ? <p className="mt-0.5 text-xs text-slate-500">{description}</p> : null}
      </div>
      <div
        className={`flex min-h-12 flex-wrap items-center gap-1.5 rounded-xl border bg-white px-2.5 py-2 shadow-sm transition focus-within:ring-2 ${
          tone === "danger"
            ? "border-red-200 focus-within:border-red-400 focus-within:ring-red-100"
            : "border-slate-200 focus-within:border-blue-500 focus-within:ring-blue-100"
        }`}
      >
        {value.map((item) => (
          <span
            className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium ${
              tone === "danger" ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-700"
            }`}
            key={item}
          >
            {item}
            <button
              aria-label={`删除${item}`}
              className="rounded px-0.5 text-current opacity-60 hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-blue-400"
              onClick={() => onChange(value.filter((current) => current !== item))}
              type="button"
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="min-w-28 flex-1 border-0 bg-transparent px-1 py-1 text-sm text-slate-900 outline-none placeholder:text-slate-400"
          id={id}
          onBlur={() => {
            if (draft.trim()) commit(draft);
          }}
          onChange={(event) => {
            const next = event.target.value;
            if (/[,，]/.test(next)) commit(next);
            else setDraft(next);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              if (draft.trim()) commit(draft);
            } else if (event.key === "Backspace" && !draft && value.length) {
              onChange(value.slice(0, -1));
            }
          }}
          placeholder={value.length ? "继续添加" : placeholder}
          value={draft}
        />
      </div>
    </div>
  );
}
