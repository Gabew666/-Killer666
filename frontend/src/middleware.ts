import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;
  if (path === "/") return NextResponse.redirect(new URL("/study", request.url));
  if (path.startsWith("/session/")) {
    return NextResponse.redirect(new URL(path.replace("/session/", "/study/session/"), request.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/", "/session/:path*"] };
