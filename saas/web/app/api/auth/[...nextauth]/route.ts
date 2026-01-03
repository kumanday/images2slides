import NextAuth, { NextAuthOptions } from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'

const apiBase = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
      authorization: {
        params: {
          scope: [
            'openid',
            'email',
            'profile',
            'https://www.googleapis.com/auth/presentations',
            'https://www.googleapis.com/auth/drive.file',
          ].join(' '),
          access_type: 'offline',
          prompt: 'consent',
        },
      },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        ;(token as any).accessToken = account.access_token
        ;(token as any).refreshToken = account.refresh_token
        ;(token as any).idToken = account.id_token
        ;(token as any).expiresAt = account.expires_at
        ;(token as any).scope = account.scope

        // Store OAuth tokens server-side for the worker.
        if (account.id_token && account.access_token) {
          try {
            const scopes = typeof account.scope === 'string' ? account.scope.split(' ') : []
            await fetch(`${apiBase}/api/v1/oauth/google/exchange`, {
              method: 'POST',
              headers: {
                Authorization: `Bearer ${account.id_token}`,
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                access_token: account.access_token,
                refresh_token: account.refresh_token,
                expires_at: account.expires_at ? new Date(account.expires_at * 1000).toISOString() : null,
                scopes,
              }),
            })
          } catch {
            // Best-effort only.
          }
        }
      }
      return token
    },
    async session({ session, token }) {
      ;(session as any).accessToken = (token as any).accessToken
      ;(session as any).idToken = (token as any).idToken
      ;(session as any).scope = (token as any).scope
      return session
    },
  },
}

const handler = NextAuth(authOptions)

export { handler as GET, handler as POST }
