import 'next-auth'

declare module 'next-auth' {
  interface Session {
    accessToken: string
    refreshToken?: string
    expiresAt?: number
    idToken: string
    scope?: string
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string
    refreshToken?: string
    expiresAt?: number
    idToken?: string
    scope?: string
  }
}