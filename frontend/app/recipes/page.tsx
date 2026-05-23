import Link from "next/link";

import { RecipeFilters } from "@/components/RecipeFilters";
import { RecipeListResponse, apiGet } from "@/lib/api";

type Props = {
  searchParams: Promise<Record<string, string | undefined>>;
};

export default async function RecipesPage({ searchParams }: Props) {
  const params = await searchParams;
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.category) query.set("category", params.category);
  if (params.difficulty) query.set("difficulty", params.difficulty);
  query.set("limit", "80");

  let data: RecipeListResponse = { items: [], total: 0 };
  let error: string | null = null;
  try {
    data = await apiGet<RecipeListResponse>(`/recipes?${query.toString()}`);
  } catch (err) {
    error = err instanceof Error ? err.message : "加载失败";
  }

  return (
    <>
      <header className="pageHeader">
        <div>
          <h1 className="pageTitle">菜谱库</h1>
          <p className="pageLead">浏览从 Markdown 菜谱库解析出的结构化菜谱。</p>
        </div>
        <div className="meta">
          <span className="tag">{data.total} 道菜</span>
        </div>
      </header>
      <RecipeFilters />
      {error ? <p className="errorText">{error}</p> : null}
      <section className="recipeGrid">
        {data.items.map((recipe) => (
          <Link className="recipeCard" href={`/recipes/${recipe.id}`} key={recipe.id}>
            <h3>{recipe.name}</h3>
            <p className="pageLead">{recipe.description || "暂无简介"}</p>
            <div className="meta">
              <span>{recipe.category}</span>
              <span>{recipe.difficulty}</span>
            </div>
          </Link>
        ))}
      </section>
    </>
  );
}
