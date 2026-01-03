'use client'

import { DndContext, PointerSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core'
import { arrayMove, SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import {
  deleteImage,
  generateJob,
  getJob,
  getJobArtifacts,
  getProject,
  Job,
  JobArtifact,
  PageSize,
  Project,
  ProjectImage,
  reorderImages,
  retryJob,
  updateProject,
  uploadImage,
} from '@/lib/api'

function SortableRow({ image, thumbUrl, onDelete }: { image: ProjectImage; thumbUrl?: string; onDelete: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: image.id })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div ref={setNodeRef} style={style} className="flex items-center justify-between gap-3 rounded border p-3">
      <div className="flex items-center gap-3">
        <div {...attributes} {...listeners} className="cursor-grab select-none text-gray-500">⋮⋮</div>
        <div className="h-12 w-12 overflow-hidden rounded bg-gray-100">
          {thumbUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={thumbUrl} alt={image.original_filename} className="h-full w-full object-cover" />
          ) : null}
        </div>
        <div>
          <div className="font-medium">{image.original_filename}</div>
          <div className="text-xs text-gray-600">sha {image.sha256.slice(0, 10)}…</div>
        </div>
      </div>
      <button className="rounded border px-3 py-1 text-sm" onClick={onDelete}>Delete</button>
    </div>
  )
}

export default function ProjectEditorPage() {
  const params = useParams()
  const projectId = Number(params.id)

  const [project, setProject] = useState<Project | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [artifacts, setArtifacts] = useState<JobArtifact[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  const [thumbs, setThumbs] = useState<Record<number, string>>({})

  async function refresh() {
    const p = await getProject(projectId)
    setProject(p)

    if (p.latest_job_id) {
      const j = await getJob(p.latest_job_id)
      setJob(j)
      if (j.status === 'succeeded') {
        const arts = await getJobArtifacts(j.id)
        setArtifacts(arts)
      }
    }
  }

  useEffect(() => {
    setError(null)
    refresh().catch(e => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  // Poll job while running.
  useEffect(() => {
    if (!job) return
    if (job.status !== 'queued' && job.status !== 'running') return

    const t = setInterval(async () => {
      try {
        const j = await getJob(job.id)
        setJob(j)
        if (j.status === 'succeeded') {
          const arts = await getJobArtifacts(j.id)
          setArtifacts(arts)
        }
      } catch {
        // ignore polling errors
      }
    }, 2000)

    return () => clearInterval(t)
  }, [job])

  // Best-effort thumbnail fetch (requires auth headers, so use fetch+blob)
  useEffect(() => {
    let cancelled = false
    async function loadThumbs(images: ProjectImage[]) {
      const session = await fetch('/api/auth/session').then(r => r.json())
      const idToken = session?.idToken
      if (!idToken) return

      const newThumbs: Record<number, string> = {}
      for (const img of images) {
        if (thumbs[img.id]) continue
        try {
          const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/projects/${projectId}/images/${img.id}/file`, {
            headers: { Authorization: `Bearer ${idToken}` },
          })
          if (!res.ok) continue
          const blob = await res.blob()
          const url = URL.createObjectURL(blob)
          newThumbs[img.id] = url
        } catch {
          // ignore
        }
      }
      if (!cancelled && Object.keys(newThumbs).length) {
        setThumbs(prev => ({ ...prev, ...newThumbs }))
      }
    }

    if (project?.images?.length) loadThumbs(project.images)

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.images?.map(i => i.id).join(',')])

  const imageIds = useMemo(() => project?.images?.map(i => i.id) || [], [project])

  async function onUpload(files: FileList | null) {
    if (!files || !files.length) return
    setBusy(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        await uploadImage(projectId, file)
      }
      await refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function onGenerate() {
    if (!project) return
    setBusy(true)
    setError(null)
    try {
      const res = await generateJob(projectId)
      const j = await getJob(res.job_id)
      setJob(j)
      setArtifacts([])
      await refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function onRetry() {
    if (!job) return
    setBusy(true)
    setError(null)
    try {
      const res = await retryJob(job.id)
      const j = await getJob(res.job_id)
      setJob(j)
      setArtifacts([])
      await refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function onSaveSettings(title: string, pageSize: PageSize) {
    setBusy(true)
    setError(null)
    try {
      await updateProject(projectId, { title, page_size: pageSize })
      await refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function onDeleteImage(imageId: number) {
    setBusy(true)
    setError(null)
    try {
      await deleteImage(projectId, imageId)
      await refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function onDragEnd(event: any) {
    if (!project) return
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = project.images.findIndex(i => i.id === active.id)
    const newIndex = project.images.findIndex(i => i.id === over.id)

    const newOrder = arrayMove(project.images, oldIndex, newIndex)
    setProject({ ...project, images: newOrder })

    try {
      await reorderImages(projectId, newOrder.map(i => i.id))
      await refresh()
    } catch (e: any) {
      setError(e.message)
    }
  }

  if (!project) return <div className="p-8">Loading…</div>

  return (
    <main className="mx-auto max-w-4xl p-8">
      <div className="flex items-center justify-between">
        <div>
          <Link className="text-sm text-gray-600 underline" href="/app">← Back</Link>
          <h1 className="mt-2 text-2xl font-semibold">{project.title}</h1>
        </div>
      </div>

      {error && <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>}

      <section className="mt-6 grid gap-4 rounded border p-4">
        <div className="font-medium">Settings</div>
        <div className="grid gap-3 md:grid-cols-3">
          <input
            className="rounded border px-3 py-2 md:col-span-2"
            defaultValue={project.title}
            onBlur={e => onSaveSettings(e.target.value, project.page_size)}
          />
          <select
            className="rounded border px-3 py-2"
            value={project.page_size}
            onChange={e => onSaveSettings(project.title, e.target.value as PageSize)}
          >
            <option value="16:9">16:9</option>
            <option value="16:10">16:10</option>
            <option value="4:3">4:3</option>
          </select>
        </div>
      </section>

      <section className="mt-6 grid gap-4 rounded border p-4">
        <div className="flex items-center justify-between">
          <div className="font-medium">Images</div>
          <label className="rounded bg-black px-4 py-2 text-white disabled:opacity-50">
            <input disabled={busy} type="file" accept="image/*" multiple className="hidden" onChange={e => onUpload(e.target.files)} />
            Upload
          </label>
        </div>

        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={imageIds} strategy={verticalListSortingStrategy}>
            <div className="grid gap-2">
              {project.images.map(img => (
                <SortableRow
                  key={img.id}
                  image={img}
                  thumbUrl={thumbs[img.id]}
                  onDelete={() => onDeleteImage(img.id)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>

        {project.images.length === 0 && <div className="text-gray-600">Upload at least one image.</div>}
      </section>

      <section className="mt-6 grid gap-4 rounded border p-4">
        <div className="flex items-center justify-between">
          <div className="font-medium">Generation</div>
          <div className="flex gap-2">
            <button
              disabled={busy || project.images.length === 0}
              className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
              onClick={onGenerate}
            >
              Generate Slides
            </button>
            {job && job.status === 'failed' && (
              <button disabled={busy} className="rounded border px-4 py-2" onClick={onRetry}>Retry</button>
            )}
          </div>
        </div>

        {job ? (
          <div className="grid gap-2 text-sm">
            <div>
              <span className="text-gray-600">Status:</span> {job.status} ({job.step})
            </div>
            {job.error_message ? <div className="text-red-700">{job.error_message}</div> : null}
            {job.presentation_url ? (
              <a className="underline" href={job.presentation_url} target="_blank" rel="noreferrer">Open Google Slides</a>
            ) : null}

            {job.events?.length ? (
              <div className="mt-2 rounded bg-gray-50 p-3">
                <div className="font-medium">Events</div>
                <ul className="mt-1 list-disc pl-5">
                  {job.events.slice(-10).map(ev => (
                    <li key={ev.id}>{ev.level}: {ev.event_type} — {ev.message}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {artifacts.length ? (
              <div className="mt-2 rounded bg-gray-50 p-3">
                <div className="font-medium">Artifacts</div>
                <ul className="mt-1 list-disc pl-5">
                  {artifacts.map(a => (
                    <li key={a.id}>
                      <a className="underline" href={a.download_url} target="_blank" rel="noreferrer">{a.kind}</a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="text-sm text-gray-600">No job yet.</div>
        )}
      </section>
    </main>
  )
}
