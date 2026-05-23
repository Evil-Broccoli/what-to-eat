"use client";

import { Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

const categories = ["", "荤菜", "素菜", "汤品", "甜品", "早餐", "主食", "水产", "调料", "饮品", "半成品"];
const difficulties = ["", "非常简单", "简单", "中等", "困难", "非常困难", "未知"];

export function RecipeFilters() {
  const router = useRouter();
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [category, setCategory] = useState(params.get("category") ?? "");
  const [difficulty, setDifficulty] = useState(params.get("difficulty") ?? "");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const next = new URLSearchParams();
    if (q) next.set("q", q);
    if (category) next.set("category", category);
    if (difficulty) next.set("difficulty", difficulty);
    router.push(`/recipes?${next.toString()}`);
  }

  return (
    <form className="filters" onSubmit={onSubmit}>
      <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="搜索菜名、食材或描述" />
      <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="分类">
        {categories.map((item) => (
          <option key={item || "all"} value={item}>
            {item || "全部分类"}
          </option>
        ))}
      </select>
      <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} aria-label="难度">
        {difficulties.map((item) => (
          <option key={item || "all"} value={item}>
            {item || "全部难度"}
          </option>
        ))}
      </select>
      <button className="primaryButton" type="submit">
        <Search size={18} />
        搜索
      </button>
    </form>
  );
}
