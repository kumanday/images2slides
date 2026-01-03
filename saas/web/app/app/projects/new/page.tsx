'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { createProject, PageSize } from '@/lib/api'

export default function NewProjectPage() {
  const router = useRouter()
  const [title, setTitle] = useState('')
  const [pageSize, setPageSize] = useState<PageSize>('16:9')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onCreate() {
    setError(null)
    setBusy(true)
    try {
      const project = await createProject(title || 'Untitled project', pageSize)
      router.push(`/app/projects/${project.id}`)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold">New project</h1>

      {error && <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>}

      <div className="mt-6 grid gap-4">
        <label className="grid gap-1">
          <span className="text-sm text-gray-700">Title</span>
          <input className="rounded border px-3 py-2" value={title} onChange={e => setTitle(e.target.value)} />
        </label>

        <label className="grid gap-1">
          <span className="text-sm text-gray-700">Page size</span>
          <select className="rounded border px-3 py-2" value={pageSize} onChange={e => setPageSize(e.target.value as PageSize)}>
            <option value="16:9">16:9</option>
            <option value="16:10">16:10</option>
            <option value="4:3">4:3</option>
          </select>
        </label>

        <button disabled={busy} className="rounded bg-black px-4 py-2 text-white disabled:opacity-50" onClick={onCreate}>
          {busy ? 'Creating…' : 'Create'}
        </button>
      </div>
    </main>
  )
}
