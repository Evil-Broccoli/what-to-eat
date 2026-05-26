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

export type RebuildResponse = IndexStatus & {
  message: string;
  failed_sources: string[];
};

export type StreamChatHandlers = {
  onMeta?: (meta: Pick<ChatResponse, "strategy" | "sources">) => void;
  onToken?: (content: string) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
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
  llm_configured: boolean;
  llm_model?: string | null;
  embedding_configured: boolean;
  embedding_model?: string | null;
  embedding_dimension?: number | null;
  degraded_services: string[];
};

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "API 请求失败"));
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
    throw new Error(await responseErrorMessage(response, "问答请求失败"));
  }
  return response.json();
}

export async function streamChat(query: string, handlers: StreamChatHandlers): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, stream: true }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "流式问答请求失败"));
  }
  if (!response.body) {
    throw new Error("Chat stream is not readable");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = readSseBuffer(buffer, handlers);
  }

  buffer += decoder.decode();
  readSseBuffer(`${buffer}\n\n`, handlers);
}

export async function rebuildIndex(): Promise<RebuildResponse> {
  const response = await fetch(`${API_BASE_URL}/index/rebuild`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "索引重建失败"));
  }
  return response.json();
}

async function responseErrorMessage(response: Response, fallback: string): Promise<string> {
  const text = await response.text();
  if (!text) return `${fallback}: ${response.status}`;

  try {
    const payload = JSON.parse(text) as { detail?: unknown; message?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item: unknown) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String((item as { msg?: unknown }).msg)
            : JSON.stringify(item),
        )
        .join("；");
    }
    if (typeof payload.message === "string") {
      return payload.message;
    }
  } catch {
    return text;
  }

  return `${fallback}: ${response.status}`;
}

function readSseBuffer(buffer: string, handlers: StreamChatHandlers): string {
  let normalized = buffer.replace(/\r\n/g, "\n");
  let boundary = normalized.indexOf("\n\n");
  while (boundary >= 0) {
    const rawEvent = normalized.slice(0, boundary);
    normalized = normalized.slice(boundary + 2);
    dispatchSseEvent(rawEvent, handlers);
    boundary = normalized.indexOf("\n\n");
  }
  return normalized;
}

function dispatchSseEvent(rawEvent: string, handlers: StreamChatHandlers) {
  if (!rawEvent.trim()) return;

  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  const data = dataLines.join("\n");
  const payload = data ? JSON.parse(data) : {};
  if (eventName === "meta") {
    handlers.onMeta?.(payload as Pick<ChatResponse, "strategy" | "sources">);
  } else if (eventName === "token") {
    handlers.onToken?.(String(payload.content ?? ""));
  } else if (eventName === "error") {
    handlers.onError?.(String(payload.message ?? "问答生成失败"));
  } else if (eventName === "done") {
    handlers.onDone?.();
  }
}
