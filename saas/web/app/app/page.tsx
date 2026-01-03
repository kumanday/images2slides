import Link from "next/link"

export default function DashboardPage() {
  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">My Projects</h1>
        <Link
          href="/app/projects/new"
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          New Project
        </Link>
      </div>

      <div className="bg-white rounded-lg shadow p-8 text-center">
        <p className="text-gray-600 mb-4">No projects yet</p>
        <Link
          href="/app/projects/new"
          className="text-blue-600 hover:text-blue-700"
        >
          Create your first project
        </Link>
      </div>
    </div>
  )
}
