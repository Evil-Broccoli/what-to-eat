export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const internalApiBaseUrl = (process.env.INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");

function streamHeaders(contentType: string | null): HeadersInit {
  return {
    "Content-Type": contentType ?? "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  };
}

export async function POST(request: Request) {
  const upstreamResponse = await fetch(`${internalApiBaseUrl}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": request.headers.get("content-type") ?? "application/json",
      Accept: "text/event-stream",
    },
    body: await request.text(),
    cache: "no-store",
    signal: request.signal,
  });

  if (!upstreamResponse.body) {
    return new Response(await upstreamResponse.text(), {
      status: upstreamResponse.status,
      headers: streamHeaders(upstreamResponse.headers.get("content-type")),
    });
  }

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: streamHeaders(upstreamResponse.headers.get("content-type")),
  });
}
