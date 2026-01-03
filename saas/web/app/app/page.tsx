import { getServerSession } from 'next-auth'
import { authOptions } from '@/app/api/auth/[...nextauth]/route'
import Link from 'next/link'
import { redirect } from 'next/navigation'
import { API_URL, Project } from '@/lib/api'

async function getProjects(accessToken: string): Promise<Project[]> {
  const res = await fetch(`${API_URL}/api/v1/projects`, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
    },
    cache: 'no-store',
  })
  
  if (!res.ok) {
    return []
  }
  
  return res.json()
}

export default async function Dashboard() {
  const session = await getServerSession(authOptions)
  
  if (!session?.accessToken) {
    redirect('/api/auth/signin')
  }
  
  const projects = await getProjects(session.accessToken)
  
  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">images2slides</h1>
          <div className="flex items-center gap-4">
            {session.user?.image && (
              <img 
                src={session.user.image} 
                alt={session.user.name || 'User'}
                className="w-8 h-8 rounded-full"
              />
            )}
            <span className="text-gray-700">{session.user?.name}</span>
            <Link 
              href="/api/auth/signout"
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Sign out
            </Link>
          </div>
        </div>
      </header>
      
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold text-gray-900">Your Projects</h2>
          <Link
            href="/app/projects/new"
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            New Project
          </Link>
        </div>
        
        {projects.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
            <p className="text-gray-500 mb-4">No projects yet</p>
            <Link
              href="/app/projects/new"
              className="text-primary-600 hover:text-primary-700"
            >
              Create your first project
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => (
              <Link
                key={project.id}
                href={`/app/projects/${project.id}`}
                className="block bg-white p-6 rounded-lg border border-gray-200 hover:border-primary-300 hover:shadow-md transition-all"
              >
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {project.title}
                </h3>
                <p className="text-sm text-gray-500">
                  {project.image_count} image{project.image_count !== 1 ? 's' : ''}
                </p>
                <p className="text-xs text-gray-400 mt-2">
                  Created: {new Date(project.created_at).toLocaleDateString()}
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
