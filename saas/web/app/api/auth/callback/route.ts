import { getServerSession } from 'next-auth'
import { authOptions } from '../../[...nextauth]/route'
import { NextResponse } from 'next/server'
import { API_URL } from '@/lib/api'

export async function GET() {
  const session = await getServerSession(authOptions)
  
  if (session?.accessToken && session?.user) {
    try {
      // Sync user to backend and get access token
      const response = await fetch(`${API_URL}/api/v1/auth/google`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id_token: session.user.id,
          access_token: session.accessToken,
          expires_at: session.expiresAt,
        }),
      })
      
      if (response.ok) {
        const data = await response.json()
        // Store the backend access token in localStorage on the client
      }
    } catch (error) {
      console.error('Failed to sync with backend:', error)
    }
  }
  
  return NextResponse.redirect(new URL('/app', process.env.NEXTAUTH_URL || 'http://localhost:3000'))
}
