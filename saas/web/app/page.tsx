'use client'

import Link from 'next/link'
import { signIn, signOut, useSession } from 'next-auth/react'

export default function LandingPage() {
  const { data: session, status } = useSession()

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-semibold">images2slides</h1>
      <p className="mt-2 text-gray-600">Upload infographics and generate an editable Google Slides deck.</p>

      <div className="mt-6 flex gap-3">
        {status === 'authenticated' ? (
          <>
            <Link className="rounded bg-black px-4 py-2 text-white" href="/app">Go to app</Link>
            <button className="rounded border px-4 py-2" onClick={() => signOut()}>Sign out</button>
          </>
        ) : (
          <button className="rounded bg-black px-4 py-2 text-white" onClick={() => signIn('google')}>
            Sign in with Google
          </button>
        )}
      </div>

      <div className="mt-10 rounded border p-4 text-sm text-gray-600">
        <div>Required Google scopes:</div>
        <ul className="ml-5 list-disc">
          <li>Google Slides: presentations</li>
          <li>Drive: drive.file</li>
        </ul>
      </div>
    </main>
  )
}
