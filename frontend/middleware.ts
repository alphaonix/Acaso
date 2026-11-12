import { NextResponse, type NextRequest } from "next/server";

// Barreira de navegacao: sem cookie de sessao, so /login. A validade real do token e checada pela API (401 -> /login).
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (pathname === "/login") return NextResponse.next();
  if (!req.cookies.has("sessao")) return NextResponse.redirect(new URL("/login", req.url));
  if (pathname === "/") return NextResponse.redirect(new URL("/visao-geral", req.url));
  return NextResponse.next();
}

export const config = { matcher: ["/((?!api|_next|.*\\..*).*)"] };
