import { withAuth } from "next-auth/middleware"
import { NextResponse } from "next/server"

export default withAuth(
  function middleware(req) {
    const token = req.nextauth.token
    const isAuth = !!token
    const isAuthPage = req.nextUrl.pathname.startsWith('/app')
    const isApiRoute = req.nextUrl.pathname.startsWith('/api/')

    if (isAuthPage && !isAuth) {
      return NextResponse.redirect(new URL('/api/auth/signin', req.url))
    }

    if (!isAuthPage && isAuth && req.nextUrl.pathname === '/') {
      return NextResponse.redirect(new URL('/app', req.url))
    }

    return NextResponse.next()
  },
  {
    callbacks: {
      authorized: ({ token, req }) => {
        const isAuthPage = req.nextUrl.pathname.startsWith('/app')
        
        if (isAuthPage) {
          return !!token
        }
        return true
      },
    },
  }
)

export const config = {
  matcher: ["/app/:path*", "/api/v1/:path*"]
}
