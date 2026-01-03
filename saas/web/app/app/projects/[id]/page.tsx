'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { getProject, uploadImage, deleteImage, createJob, getJobs, getJob, retryJob, type Project, type ProjectImage, type Job } from '@/lib/api'

export default function ProjectPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = parseInt(params.id as string)
  
  const [project, setProject] = useState<Project | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [currentJob, setCurrentJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    loadProject()
    loadJobs()
  }, [projectId])

  const loadProject = async () => {
    try {
      const data = await getProject(projectId)
      setProject(data)
    } catch (error) {
      console.error('Failed to load project:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadJobs = async () => {
    try {
      const data = await getJobs(projectId)
      setJobs(data)
      if (data.length > 0) {
        setCurrentJob(data[0])
        pollJobStatus(data[0].id)
      }
    } catch (error) {
      console.error('Failed to load jobs:', error)
    }
  }

  const pollJobStatus = async (jobId: number) => {
    const interval = setInterval(async () => {
      try {
        const job = await getJob(jobId)
        setCurrentJob(job)
        if (job.status === 'succeeded' || job.status === 'failed') {
          clearInterval(interval)
        }
      } catch (error) {
        console.error('Failed to poll job status:', error)
      }
    }, 2000)
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        await uploadImage(projectId, file)
      }
      await loadProject()
    } catch (error) {
      console.error('Failed to upload image:', error)
      alert('Failed to upload image')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleDeleteImage = async (imageId: number) => {
    if (!confirm('Are you sure you want to delete this image?')) return

    try {
      await deleteImage(projectId, imageId)
      await loadProject()
    } catch (error) {
      console.error('Failed to delete image:', error)
      alert('Failed to delete image')
    }
  }

  const handleGenerate = async () => {
    if (!project || project.images.length === 0) {
      alert('Please upload at least one image')
      return
    }

    try {
      const job = await createJob(projectId)
      setJobs([job, ...jobs])
      setCurrentJob(job)
      pollJobStatus(job.id)
    } catch (error) {
      console.error('Failed to create job:', error)
      alert('Failed to create job')
    }
  }

  const handleRetry = async () => {
    if (!currentJob) return

    try {
      const newJob = await retryJob(currentJob.id)
      setJobs([newJob, ...jobs])
      setCurrentJob(newJob)
      pollJobStatus(newJob.id)
    } catch (error) {
      console.error('Failed to retry job:', error)
      alert('Failed to retry job')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-600">Loading...</div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{project?.title}</h1>
          <a href="/app" className="text-blue-600 hover:text-blue-700">
            ← Back to projects
          </a>
        </div>
        <button
          onClick={handleGenerate}
          disabled={!project || project.images.length === 0 || currentJob?.status === 'running'}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {currentJob?.status === 'running' ? 'Processing...' : 'Generate Slides'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Upload Images</h2>
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            <input
              type="file"
              multiple
              accept="image/png,image/jpeg,image/webp"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              <div className="text-4xl mb-2">📤</div>
              <p className="text-gray-600">
                {uploading ? 'Uploading...' : 'Click to upload or drag and drop'}
              </p>
            </label>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Images ({project?.images.length || 0})</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {project?.images.map((image) => (
              <div key={image.id} className="relative group">
                <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden">
                  <img
                    src={`/api/images/${image.id}`}
                    alt={image.original_filename}
                    className="w-full h-full object-cover"
                  />
                </div>
                <button
                  onClick={() => handleDeleteImage(image.id)}
                  className="absolute top-2 right-2 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  ×
                </button>
                <div className="absolute bottom-2 left-2 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded">
                  {image.ordinal}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {currentJob && (
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Job Status</h2>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Status:</span>
              <span className={`font-semibold ${
                currentJob.status === 'succeeded' ? 'text-green-600' :
                currentJob.status === 'failed' ? 'text-red-600' :
                currentJob.status === 'running' ? 'text-blue-600' :
                'text-gray-600'
              }`}>
                {currentJob.status.toUpperCase()}
              </span>
            </div>
            
            {currentJob.status === 'running' && (
              <div className="text-blue-600">
                Processing your images... This may take a few minutes.
              </div>
            )}

            {currentJob.status === 'succeeded' && currentJob.presentation_url && (
              <div>
                <a
                  href={currentJob.presentation_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700"
                >
                  Open Presentation
                </a>
              </div>
            )}

            {currentJob.status === 'failed' && (
              <div>
                <p className="text-red-600 mb-2">
                  {currentJob.error_message || 'Failed to generate slides'}
                </p>
                <button
                  onClick={handleRetry}
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                >
                  Retry
                </button>
              </div>
            )}

            {currentJob.events.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Steps</h3>
                <div className="space-y-2">
                  {currentJob.events.map((event) => (
                    <div key={event.id} className="text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-700">{event.step}</span>
                        <span className={`${
                          event.status === 'completed' ? 'text-green-600' :
                          event.status === 'failed' ? 'text-red-600' :
                          'text-blue-600'
                        }`}>
                          {event.status}
                        </span>
                      </div>
                      {event.duration_seconds && (
                        <div className="text-gray-500 text-xs">
                          {event.duration_seconds}s
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
