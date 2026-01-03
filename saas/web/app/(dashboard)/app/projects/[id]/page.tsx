'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  getProject,
  updateProject,
  uploadImage,
  reorderImages,
  deleteImage,
  generateJob,
  getJob,
  Project,
  ProjectImage,
  Job,
  PageSize,
} from '@/lib/api'

function SortableImage({
  image,
  onDelete,
}: {
  image: ProjectImage
  onDelete: (id: number) => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: image.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-4 p-4 bg-white dark:bg-gray-800 rounded-lg shadow"
    >
      <div
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
      >
        <svg className="w-5 h-5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
          <path d="M7 2a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 2zm0 6a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 8zm0 6a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 14zm6-8a2 2 0 1 0-.001-4.001A2 2 0 0 0 13 6zm0 2a2 2 0 1 0 .001 4.001A2 2 0 0 0 13 8zm0 6a2 2 0 1 0 .001 4.001A2 2 0 0 0 13 14z" />
        </svg>
      </div>

      <div className="flex-1">
        <p className="font-medium truncate">{image.original_filename}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {image.width_px && image.height_px
            ? `${image.width_px} × ${image.height_px}`
            : 'Processing...'}
          {' • '}
          {(image.byte_size / 1024).toFixed(1)} KB
        </p>
      </div>

      <button
        onClick={() => onDelete(image.id)}
        className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
    </div>
  )
}

function JobStatusPanel({ job, onRefresh }: { job: Job; onRefresh: () => void }) {
  const statusColors: Record<string, string> = {
    queued: 'bg-yellow-100 text-yellow-800',
    running: 'bg-blue-100 text-blue-800',
    succeeded: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    canceled: 'bg-gray-100 text-gray-800',
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold">Job Status</h3>
        <span className={`px-2 py-1 text-xs rounded ${statusColors[job.status]}`}>
          {job.status}
        </span>
      </div>

      <div className="space-y-2 text-sm">
        <p>
          <span className="text-gray-500">Step:</span> {job.step}
        </p>
        <p>
          <span className="text-gray-500">Attempt:</span> {job.attempt}
        </p>
        {job.started_at && (
          <p>
            <span className="text-gray-500">Started:</span>{' '}
            {new Date(job.started_at).toLocaleTimeString()}
          </p>
        )}
        {job.finished_at && (
          <p>
            <span className="text-gray-500">Finished:</span>{' '}
            {new Date(job.finished_at).toLocaleTimeString()}
          </p>
        )}
      </div>

      {job.error_message && (
        <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded text-sm">
          {job.error_message}
        </div>
      )}

      {job.presentation_url && (
        <div className="mt-4">
          <a
            href={job.presentation_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
              <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
            </svg>
            Open Presentation
          </a>
        </div>
      )}

      {(job.status === 'queued' || job.status === 'running') && (
        <div className="mt-4">
          <button
            onClick={onRefresh}
            className="text-sm text-blue-600 hover:underline"
          >
            Refresh status
          </button>
        </div>
      )}

      {job.events.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium mb-2">Recent Events</h4>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {job.events.slice(-5).reverse().map((event) => (
              <div
                key={event.id}
                className={`text-xs p-2 rounded ${
                  event.level === 'error'
                    ? 'bg-red-50 dark:bg-red-900/20'
                    : 'bg-gray-50 dark:bg-gray-700'
                }`}
              >
                <span className="text-gray-500">
                  {new Date(event.ts).toLocaleTimeString()}
                </span>{' '}
                {event.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ProjectPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = parseInt(params.id as string)

  const [project, setProject] = useState<Project | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const loadProject = useCallback(async () => {
    try {
      const data = await getProject(projectId)
      setProject(data)

      // Load latest job if exists
      if (data.latest_job_id) {
        const jobData = await getJob(data.latest_job_id)
        setJob(jobData)
      }
    } catch (err) {
      setError('Failed to load project')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    loadProject()
  }, [loadProject])

  // Poll job status while running
  useEffect(() => {
    if (!job || (job.status !== 'queued' && job.status !== 'running')) return

    const interval = setInterval(async () => {
      try {
        const jobData = await getJob(job.id)
        setJob(jobData)
        if (jobData.status !== 'queued' && jobData.status !== 'running') {
          // Refresh project to update status
          const projectData = await getProject(projectId)
          setProject(projectData)
        }
      } catch (err) {
        console.error('Failed to poll job status:', err)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [job?.id, job?.status, projectId])

  async function handleFileDrop(e: React.DragEvent) {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files).filter((f) =>
      ['image/png', 'image/jpeg', 'image/webp'].includes(f.type)
    )
    if (files.length === 0) return
    await uploadFiles(files)
  }

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files) return
    await uploadFiles(Array.from(files))
  }

  async function uploadFiles(files: File[]) {
    if (!project) return

    setUploading(true)
    setError(null)

    try {
      for (const file of files) {
        const newImage = await uploadImage(project.id, file)
        setProject((prev) =>
          prev
            ? { ...prev, images: [...prev.images, newImage] }
            : prev
        )
      }
    } catch (err) {
      setError('Failed to upload image(s)')
      console.error(err)
    } finally {
      setUploading(false)
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || !project || active.id === over.id) return

    const oldIndex = project.images.findIndex((img) => img.id === active.id)
    const newIndex = project.images.findIndex((img) => img.id === over.id)

    const newImages = arrayMove(project.images, oldIndex, newIndex)
    setProject({ ...project, images: newImages })

    try {
      await reorderImages(project.id, newImages.map((img) => img.id))
    } catch (err) {
      console.error('Failed to save order:', err)
      // Reload to get correct order
      loadProject()
    }
  }

  async function handleDeleteImage(imageId: number) {
    if (!project) return
    if (!confirm('Delete this image?')) return

    try {
      await deleteImage(project.id, imageId)
      setProject({
        ...project,
        images: project.images.filter((img) => img.id !== imageId),
      })
    } catch (err) {
      console.error('Failed to delete image:', err)
    }
  }

  async function handleGenerate() {
    if (!project || project.images.length === 0) return

    setGenerating(true)
    setError(null)

    try {
      const { job_id } = await generateJob(project.id)
      const jobData = await getJob(job_id)
      setJob(jobData)
      setProject({ ...project, latest_job_id: job_id })
    } catch (err) {
      setError('Failed to start generation')
      console.error(err)
    } finally {
      setGenerating(false)
    }
  }

  async function handleTitleChange(newTitle: string) {
    if (!project || newTitle === project.title) return

    try {
      await updateProject(project.id, { title: newTitle })
      setProject({ ...project, title: newTitle })
    } catch (err) {
      console.error('Failed to update title:', err)
    }
  }

  async function handlePageSizeChange(newPageSize: PageSize) {
    if (!project || newPageSize === project.page_size) return

    try {
      await updateProject(project.id, { page_size: newPageSize })
      setProject({ ...project, page_size: newPageSize })
    } catch (err) {
      console.error('Failed to update page size:', err)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-white"></div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 mb-4">Project not found</p>
        <button
          onClick={() => router.push('/app')}
          className="text-blue-600 hover:underline"
        >
          Back to projects
        </button>
      </div>
    )
  }

  const canGenerate = project.images.length > 0 && !generating && job?.status !== 'running' && job?.status !== 'queued'

  return (
    <div>
      <div className="flex items-center gap-4 mb-8">
        <button
          onClick={() => router.push('/app')}
          className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <input
          type="text"
          value={project.title}
          onChange={(e) => handleTitleChange(e.target.value)}
          className="text-2xl font-bold bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 -mx-2"
        />
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-100 text-red-700 rounded-lg">{error}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Images */}
        <div className="lg:col-span-2 space-y-6">
          {/* Upload zone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleFileDrop}
            className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center hover:border-blue-500 transition-colors"
          >
            <input
              type="file"
              id="file-upload"
              multiple
              accept="image/png,image/jpeg,image/webp"
              onChange={handleFileSelect}
              className="hidden"
            />
            <label
              htmlFor="file-upload"
              className="cursor-pointer"
            >
              {uploading ? (
                <div className="flex items-center justify-center gap-2">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                  <span>Uploading...</span>
                </div>
              ) : (
                <>
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 48 48">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" />
                  </svg>
                  <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                    Drag and drop images here, or click to browse
                  </p>
                  <p className="mt-1 text-xs text-gray-500">
                    PNG, JPEG, or WebP up to 20MB
                  </p>
                </>
              )}
            </label>
          </div>

          {/* Image list */}
          {project.images.length > 0 && (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={project.images.map((img) => img.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-2">
                  {project.images.map((image) => (
                    <SortableImage
                      key={image.id}
                      image={image}
                      onDelete={handleDeleteImage}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}
        </div>

        {/* Right: Settings and Job */}
        <div className="space-y-6">
          {/* Settings */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 className="font-semibold mb-4">Settings</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Slide Size
                </label>
                <select
                  value={project.page_size}
                  onChange={(e) => handlePageSizeChange(e.target.value as PageSize)}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                >
                  <option value="16:9">Widescreen 16:9</option>
                  <option value="16:10">Widescreen 16:10</option>
                  <option value="4:3">Standard 4:3</option>
                </select>
              </div>

              <button
                onClick={handleGenerate}
                disabled={!canGenerate}
                className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {generating ? 'Starting...' : 'Generate Slides'}
              </button>

              {project.images.length === 0 && (
                <p className="text-sm text-gray-500 text-center">
                  Upload at least one image to generate slides
                </p>
              )}
            </div>
          </div>

          {/* Job Status */}
          {job && <JobStatusPanel job={job} onRefresh={loadProject} />}
        </div>
      </div>
    </div>
  )
}