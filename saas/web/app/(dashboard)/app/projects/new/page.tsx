'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createProject, PageSize } from '@/lib/api'

export default function NewProjectPage() {
  const router = useRouter()
  const [title, setTitle] = useState('')
  const [pageSize, setPageSize] = useState<PageSize>('16:9')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) {
      setError('Title is required')
      return
    }

    try {
      setLoading(true)
      setError(null)
      const project = await createProject(title.trim(), pageSize)
      router.push(`/app/projects/${project.id}`)
    } catch (err) {
      setError('Failed to create project')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-2xl font-bold mb-8">Create New Project</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="p-4 bg-red-100 text-red-700 rounded-lg">{error}</div>
        )}

        <div>
          <label htmlFor="title" className="block text-sm font-medium mb-2">
            Project Title
          </label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="My Infographic Presentation"
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label htmlFor="pageSize" className="block text-sm font-medium mb-2">
            Slide Size
          </label>
          <select
            id="pageSize"
            value={pageSize}
            onChange={(e) => setPageSize(e.target.value as PageSize)}
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="16:9">Widescreen 16:9</option>
            <option value="16:10">Widescreen 16:10</option>
            <option value="4:3">Standard 4:3</option>
          </select>
        </div>

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {loading ? 'Creating...' : 'Create Project'}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}