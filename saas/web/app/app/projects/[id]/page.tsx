'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { API_URL, Project, Job } from '@/lib/api'

interface ProjectPageProps {
  params: {
    id: string
  }
}

export default function ProjectPage({ params }: ProjectPageProps) {
  const router = useRouter()
  const { id } = params
  
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [job, setJob] = useState<Job | null>(null)
  const [jobPolling, setJobPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchProject()
  }, [id])

  useEffect(() => {
    if (job && job.status !== 'succeeded' && job.status !== 'failed') {
      setJobPolling(true)
      const interval = setInterval(() => {
        fetchJob()
      }, 3000)
      return () => {
        clearInterval(interval)
        setJobPolling(false)
      }
    }
  }, [job?.id])

  const fetchProject = async () => {
    try {
      const accessToken = localStorage.getItem('access_token')
      const res = await fetch(`${API_URL}/api/v1/projects/${id}`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      })
      
      if (!res.ok) {
        throw new Error('Failed to fetch project')
      }
      
      const data = await res.json()
      setProject(data)
      
      // Check for existing job
      if (data.jobs && data.jobs.length > 0) {
        const latestJob = data.jobs[0]
        if (latestJob.status === 'queued' || latestJob.status === 'running') {
          setJob(latestJob)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load project')
    } finally {
      setLoading(false)
    }
  }

  const fetchJob = async () => {
    if (!job) return
    
    try {
      const accessToken = localStorage.getItem('access_token')
      const res = await fetch(`${API_URL}/api/v1/jobs/${job.id}`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      })
      
      if (res.ok) {
        const data = await res.json()
        setJob(data)
      }
    } catch (err) {
      console.error('Failed to fetch job status:', err)
    }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    setError(null)

    try {
      const accessToken = localStorage.getItem('access_token')
      
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const formData = new FormData()
        formData.append('file', file)
        
        // Get presigned URL (simplified - in production use actual S3/GCS)
        const presignedRes = await fetch(`${API_URL}/api/v1/projects/${id}/images`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            original_filename: file.name,
            storage_path: `/uploads/${id}/${file.name}`,
            mime_type: file.type,
          }),
        })
        
        if (!presignedRes.ok) {
          throw new Error('Failed to prepare upload')
        }
      }
      
      // Refresh project
      fetchProject()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleCreateJob = async () => {
    setError(null)
    
    try {
      const accessToken = localStorage.getItem('access_token')
      const res = await fetch(`${API_URL}/api/v1/projects/${id}/jobs`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      })
      
      if (!res.ok) {
        throw new Error('Failed to create job')
      }
      
      const newJob = await res.json()
      setJob(newJob)
      fetchProject()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create job')
    }
  }

  const handleDeleteImage = async (imageId: number) => {
    if (!confirm('Delete this image?')) return
    
    try {
      const accessToken = localStorage.getItem('access_token')
      const res = await fetch(`${API_URL}/api/v1/projects/${id}/images/${imageId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      })
      
      if (res.ok) {
        fetchProject()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete image')
    }
  }

  if (loading) {
    return <div className="min-h-screen bg-gray-50 flex items-center justify-center">Loading...</div>
  }

  if (error && !project) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-red-600">{error}</div>
      </div>
    )
  }

  if (!project) {
    return <div className="min-h-screen bg-gray-50 flex items-center justify-center">Project not found</div>
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/app" className="text-gray-500 hover:text-gray-700">
                ← Back
              </Link>
              <div>
                <h1 className="text-xl font-bold text-gray-900">{project.title}</h1>
                <p className="text-sm text-gray-500">
                  {project.images.length} image{project.images.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
            
            {job && (
              <div className="flex items-center gap-2">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  job.status === 'queued' ? 'bg-yellow-100 text-yellow-800' :
                  job.status === 'running' ? 'bg-blue-100 text-blue-800' :
                  job.status === 'succeeded' ? 'bg-green-100 text-green-800' :
                  'bg-red-100 text-red-800'
                }`}>
                  {job.status}
                </span>
                {job.status === 'succeeded' && job.presentation_url && (
                  <a
                    href={job.presentation_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1 bg-primary-600 text-white rounded-full text-sm font-medium hover:bg-primary-700"
                  >
                    Open in Slides →
                  </a>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {error && (
          <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm mb-4">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Images Panel */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold">Images</h2>
                <label className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 cursor-pointer">
                  {uploading ? 'Uploading...' : '+ Add Images'}
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={handleUpload}
                    className="hidden"
                    disabled={uploading}
                  />
                </label>
              </div>

              {project.images.length === 0 ? (
                <div className="text-center py-8 border-2 border-dashed border-gray-300 rounded-lg">
                  <p className="text-gray-500">No images yet</p>
                  <p className="text-sm text-gray-400">Upload images to start creating your slides</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {project.images
                    .sort((a, b) => a.ordinal - b.ordinal)
                    .map((image) => (
                    <div key={image.id} className="relative group">
                      <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
                        {/* Use placeholder for local development */}
                        <div className="w-full h-full flex items-center justify-center text-gray-400">
                          {image.original_filename}
                        </div>
                      </div>
                      <button
                        onClick={() => handleDeleteImage(image.id)}
                        className="absolute top-2 right-2 p-1 bg-red-600 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete image"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                      <p className="mt-1 text-xs text-gray-500 truncate">{image.original_filename}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Job Progress */}
            {job && job.events && job.events.length > 0 && (
              <div className="bg-white rounded-lg shadow p-6 mt-6">
                <h2 className="text-lg font-semibold mb-4">Processing Progress</h2>
                <div className="space-y-3">
                  {job.events.map((event) => (
                    <div key={event.id} className="flex items-center gap-3">
                      <span className={`w-3 h-3 rounded-full ${
                        event.status === 'completed' ? 'bg-green-500' :
                        event.status === 'failed' ? 'bg-red-500' :
                        'bg-yellow-500 animate-pulse'
                      }`} />
                      <span className="flex-1 text-sm">{event.step}</span>
                      <span className={`text-xs ${
                        event.status === 'completed' ? 'text-green-600' :
                        event.status === 'failed' ? 'text-red-600' :
                        'text-gray-500'
                      }`}>
                        {event.status}
                      </span>
                      {event.duration_seconds && (
                        <span className="text-xs text-gray-400">
                          {event.duration_seconds.toFixed(1)}s
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Settings & Actions */}
          <div>
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">Settings</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Page Size
                  </label>
                  <p className="text-gray-900">
                    {project.page_size === 'standard_16_9' ? '16:9 Widescreen' :
                     project.page_size === 'standard_4_3' ? '4:3 Standard' :
                     '16:10 Widescreen'}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6 mt-6">
              <h2 className="text-lg font-semibold mb-4">Generate Slides</h2>
              
              {!job || job.status === 'succeeded' || job.status === 'failed' ? (
                <button
                  onClick={handleCreateJob}
                  disabled={project.images.length === 0}
                  className="w-full px-4 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {job?.status === 'failed' ? 'Retry Generation' : 'Generate Slides'}
                </button>
              ) : (
                <div className="text-center py-2">
                  <p className="text-gray-500">Generation in progress...</p>
                </div>
              )}
              
              {project.images.length === 0 && (
                <p className="text-sm text-gray-500 mt-2">
                  Add at least one image to generate slides
                </p>
              )}
              
              {job?.error_message && (
                <div className="mt-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
                  {job.error_message}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
