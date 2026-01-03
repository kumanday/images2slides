'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { getProjects, deleteProject, Project } from '@/lib/api'

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadProjects()
  }, [])

  async function loadProjects() {
    try {
      setLoading(true)
      setError(null)
      const data = await getProjects()
      setProjects(data)
    } catch (err) {
      setError('Failed to load projects')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(projectId: number) {
    if (!confirm('Are you sure you want to delete this project?')) return

    try {
      await deleteProject(projectId)
      setProjects(projects.filter((p) => p.id !== projectId))
    } catch (err) {
      console.error('Failed to delete project:', err)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-white"></div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-2xl font-bold">My Projects</h1>
        <Link
          href="/app/projects/new"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          New Project
        </Link>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-100 text-red-700 rounded-lg">{error}</div>
      )}

      {projects.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            You don&apos;t have any projects yet.
          </p>
          <Link
            href="/app/projects/new"
            className="text-blue-600 hover:underline"
          >
            Create your first project
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <div
              key={project.id}
              className="bg-white dark:bg-gray-800 rounded-lg shadow p-6"
            >
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-lg font-semibold truncate">{project.title}</h2>
                <span
                  className={`px-2 py-1 text-xs rounded ${
                    project.status === 'generated'
                      ? 'bg-green-100 text-green-800'
                      : project.status === 'archived'
                      ? 'bg-gray-100 text-gray-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}
                >
                  {project.status}
                </span>
              </div>

              <div className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                <p>{project.images.length} image(s)</p>
                <p>Page size: {project.page_size}</p>
                <p>
                  Updated: {new Date(project.updated_at).toLocaleDateString()}
                </p>
              </div>

              <div className="flex gap-2">
                <Link
                  href={`/app/projects/${project.id}`}
                  className="flex-1 text-center px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                >
                  Open
                </Link>
                <button
                  onClick={() => handleDelete(project.id)}
                  className="px-3 py-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}