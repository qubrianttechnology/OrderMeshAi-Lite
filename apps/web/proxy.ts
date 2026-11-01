import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const configured = process.env.ORDERMESH_APP_ORIGIN;
  if (!configured || !["GET", "HEAD"].includes(request.method))
    return NextResponse.next();
  let target: URL;
  try {
    target = new URL(configured);
  } catch {
    return NextResponse.next();
  }
  if (target.protocol !== "https:" || target.username || target.password)
    return NextResponse.next();
  const host = (
    request.headers.get("x-forwarded-host") ||
    request.headers.get("host") ||
    ""
  )
    .split(",")[0]
    .trim()
    .split(":")[0]
    .toLowerCase();
  if (!["localhost", "127.0.0.1"].includes(host)) return NextResponse.next();
  target.pathname = request.nextUrl.pathname;
  target.search = request.nextUrl.search;
  target.hash = "";
  const response = NextResponse.redirect(target, 307);
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export const config = {
  matcher: ["/", "/sign-in", "/sign-up", "/dashboard/:path*"],
};
