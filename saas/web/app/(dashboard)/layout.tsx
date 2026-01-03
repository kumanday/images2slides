'use client'

import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { oauthExchange } from '@/lib/api'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { data: session, status } = useSession()
  const router = useRouter()
  const [tokensSynced, setTokensSynced] = useState(false)

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/')
    }
  }, [status, router])

  // Sync OAuth tokens to backend
  useEffect(() => {
    if (session?.accessToken && session?.idToken && !tokensSynced) {
      oauthExchange(
        session.accessToken,
        session.refreshToken,
        session.expiresAt ? new Date(session.expiresAt * 1000).toISOString() : undefined,
        session.scope ? session.scope.split(' ') : []
      )
        .then(() => setTokensSynced(true))
        .catch((err) => console.error('Failed to sync tokens:', err))
    }
  }, [session, tokensSynced])

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-white"></div>
      </div>
    )
  }

  if (!session) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link href="/app" className="text-xl font-bold">
            images2slides
          </Link>
          
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600 dark:text-gray-300">
              {session.user?.email}
            </span>
            {session.user?.image && (
              <img
                src={session.user.image}
                alt="Profile"
                className="w-8 h-8 rounded-full"
              />
            )}
            <button
              onClick={() => signOut({ callbackUrl: '/' })}
              className="text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}