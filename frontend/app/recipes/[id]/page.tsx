import Link from "next/link";
import { notFound } from "next/navigation";

import { RecipeDetail, apiGet } from "@/lib/api";

type Props = {
  params: Promise<{ id: string }>;
};

export default async function RecipeDetailPage({ params }: Props) {
  const { id } = await params;
  let recipe: RecipeDetail;
  try {
    recipe = await apiGet<RecipeDetail>(`/recipes/${id}`);
  } catch {
    notFound();
  }

  return (
    <>
      <header className="pageHeader">
        <div>
          <h1 className="pageTitle">{recipe.name}</h1>
          <p className="pageLead">{recipe.description || "从本地菜谱库解析生成的菜谱详情。"}</p>
        </div>
        <div className="meta">
          <span className="tag">{recipe.category}</span>
          <span className="tag">{recipe.difficulty}</span>
        </div>
      </header>
      <div className="recipeDetail">
        <section className="panel contentBlock">
          <h2>食材</h2>
          {recipe.ingredients.length ? (
            <ul className="stepList">
              {recipe.ingredients.map((item, index) => (
                <li key={`${item.name}-${index}`}>
                  {item.name}
                  {item.amount ? `：${item.amount}` : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty">没有解析到结构化食材。</p>
          )}

          <h2>步骤</h2>
          {recipe.steps.length ? (
            <ol className="stepList">
              {recipe.steps.map((step, index) => (
                <li key={`${index}-${step}`}>{step}</li>
              ))}
            </ol>
          ) : (
            <p className="empty">没有解析到结构化步骤。</p>
          )}
        </section>
        <aside className="sideStack">
          <section className="panel contentBlock">
            <h2>相似菜谱</h2>
            <div className="sourceList">
              {recipe.related.map((item) => (
                <Link className="sourceCard" href={`/recipes/${item.id}`} key={item.id}>
                  <h3>{item.name}</h3>
                  <div className="meta">
                    <span>{item.category}</span>
                    <span>{item.difficulty}</span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}
