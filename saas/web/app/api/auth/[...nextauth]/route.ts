import NextAuth from "next-auth"
import GoogleProvider from "next-auth/providers/google"
import { API_URL } from "@/lib/api"

const handler = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
      authorization: {
        params: {
          scope: "openid email profile https://www.googleapis.com/auth/presentations https://www.googleapis.com/auth/drive.file",
        },
      },
    }),
  ],
  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === "google" && account?.id_token) {
        // Send ID token and access token to backend for verification
        try {
          const response = await fetch(`${API_URL}/api/v1/auth/google`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              id_token: account.id_token,
              access_token: account.access_token,
              refresh_token: account.refresh_token,
              expires_in: account.expires_at ? account.expires_at - Math.floor(Date.now() / 1000) : undefined,
            }),
          })

          if (!response.ok) {
            console.error("Backend auth failed")
            return false
          }

          const backendUser = await response.json()
          // Store backend user ID in session
          user.id = backendUser.id.toString()
          return true
        } catch (error) {
          console.error("Auth error:", error)
          return false
        }
      }
      return false
    },
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string
      }
      return session
    },
  },
  pages: {
    signIn: "/",
    error: "/",
  },
})

export { handler as GET, handler as POST }
