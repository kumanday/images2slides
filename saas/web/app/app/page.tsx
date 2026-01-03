'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { signOut, useSession } from 'next-auth/react'
import { getProjects, Project } from '@/lib/api'

export default function DashboardPage() {
  const { status } = useSession()
  const [projects, setProjects] = useState<Project[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (status !== 'authenticated') return
    getProjects().then(setProjects).catch(e => setError(e.message))
  }, [status])

  if (status === 'loading') return <div className="p-8">Loading…</div>

  if (status !== 'authenticated') {
    return (
      <div className="p-8">
        <Link className="underline" href="/">Go sign in</Link>
      </div>
    )
  }

  return (
    <main className="mx-auto max-w-4xl p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Projects</h1>
        <div className="flex gap-3">
          <Link className="rounded bg-black px-4 py-2 text-white" href="/app/projects/new">New project</Link>
          <button className="rounded border px-4 py-2" onClick={() => signOut()}>Sign out</button>
        </div>
      </div>

      {error && <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>}

      <div className="mt-6 grid gap-3">
        {projects.map(p => (
          <Link key={p.id} href={`/app/projects/${p.id}`} className="rounded border p-4 hover:bg-gray-50">
            <div className="font-medium">{p.title}</div>
            <div className="text-sm text-gray-600">{p.images?.length || 0} images · page {p.page_size}</div>
          </Link>
        ))}
        {projects.length === 0 && !error && (
          <div className="rounded border p-6 text-gray-600">No projects yet.</div>
        )}
      </div>
    </main>
  )
}
