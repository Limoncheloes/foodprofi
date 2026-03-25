import { NextRequest, NextResponse } from "next/server"

export function middleware(request: NextRequest) {
  // Route protection is handled client-side via useAuth() hook.
  // Middleware is intentionally minimal for MVP — no server-side token check
  // because tokens are stored in localStorage (not cookies).
  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
}
