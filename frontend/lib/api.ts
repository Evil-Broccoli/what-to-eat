export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";

export type Source = {
  recipe_id: string;
  recipe_name: string;
  category: string;
  difficulty: string;
  score: number;
};

export type ChatResponse = {
  answer: string;
  strategy: string;
  sources: Source[];
};

export type RecipeSummary = {
  id: string;
  name: string;
  category: string;
  difficulty: string;
  source: string;
  description: string;
};

export type Ingredient = {
  name: string;
  amount?: string | null;
  required: boolean;
};

export type RecipeDetail = RecipeSummary & {
  ingredients: Ingredient[];
  steps: string[];
  sections: Record<string, string>;
  related: RecipeSummary[];
};

export type RecipeListResponse = {
  items: RecipeSummary[];
  total: number;
};

export type IndexStatus = {
  neo4j: boolean;
  milvus: boolean;
  recipe_count: number;
  chunk_count: number;
  last_build?: string | null;
};

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}

export async function chat(query: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    throw new Error(`Chat failed: ${response.status}`);
  }
  return response.json();
}
