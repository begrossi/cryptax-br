import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";

// Server-side proxy to the FastAPI backend. Runs on the Node runtime (default
// for route handlers), so it can:
//   1. enforce the frontend session on every backend call, and
//   2. attach the shared API token the browser must never see.
// The more specific /api/auth/* routes take precedence over this catch-all.

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  }

  const url = `${BACKEND}/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const token = process.env.API_TOKEN;
  if (token) headers.set("x-api-token", token);

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const body = hasBody ? await req.text() : undefined;

  const res = await fetch(url, { method: req.method, headers, body });
  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") || "application/json",
    },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

async function handle(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export { handle as GET, handle as POST, handle as PATCH, handle as PUT, handle as DELETE };
