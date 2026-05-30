import { NextRequest, NextResponse } from "next/server";

const DEFAULT_BACKEND = "https://backend-production-b399b.up.railway.app";

function resolveBackendRoot() {
  const configured =
    process.env.BACKEND_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    DEFAULT_BACKEND;

  return configured.replace(/\/api\/?$/, "").replace(/\/$/, "");
}

async function proxy(request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  const { path = [] } = await context.params;
  const backendRoot = resolveBackendRoot();
  const incomingUrl = new URL(request.url);
  const trailingSlash = incomingUrl.pathname.endsWith("/") ? "/" : "";
  const targetUrl = new URL(`${backendRoot}/${path.join("/")}${trailingSlash}`);
  targetUrl.search = incomingUrl.search;

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");
  headers.delete("origin");
  headers.delete("referer");

  const method = request.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();

  try {
    let response = await fetch(targetUrl, {
      method,
      headers,
      body,
      cache: "no-store",
    });

    if (response.status === 404 && !targetUrl.pathname.endsWith("/")) {
      targetUrl.pathname = `${targetUrl.pathname}/`;
      response = await fetch(targetUrl, {
        method,
        headers,
        body,
        cache: "no-store",
      });
    }

    const responseHeaders = new Headers(response.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("transfer-encoding");

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown proxy error";
    return NextResponse.json(
      { detail: `无法连接后端服务：${message}` },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
