import { getServerSession } from "next-auth"
import { redirect } from "next/navigation"
import { authOptions } from "./api/auth/[...nextauth]/route"

export default async function Home() {
  const session = await getServerSession(authOptions)

  if (session) {
    redirect("/app")
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
      <div className="max-w-4xl mx-auto px-4 text-center">
        <h1 className="text-5xl font-bold text-gray-900 mb-6">
          Images to Slides
        </h1>
        <p className="text-xl text-gray-600 mb-8">
          Convert static infographic images into editable Google Slides presentations
        </p>
        <div className="bg-white rounded-lg shadow-xl p-8 mb-8">
          <h2 className="text-2xl font-semibold text-gray-800 mb-4">How it works</h2>
          <div className="grid md:grid-cols-3 gap-6 text-left">
            <div>
              <div className="text-3xl mb-2">📤</div>
              <h3 className="font-semibold text-gray-800 mb-2">1. Upload</h3>
              <p className="text-gray-600">Upload your infographic images</p>
            </div>
            <div>
              <div className="text-3xl mb-2">🔄</div>
              <h3 className="font-semibold text-gray-800 mb-2">2. Process</h3>
              <p className="text-gray-600">AI analyzes and extracts content</p>
            </div>
            <div>
              <div className="text-3xl mb-2">📊</div>
              <h3 className="font-semibold text-gray-800 mb-2">3. Generate</h3>
              <p className="text-gray-600">Get editable Google Slides</p>
            </div>
          </div>
        </div>
        <a
          href="/api/auth/signin"
          className="inline-block bg-blue-600 text-white px-8 py-4 rounded-lg font-semibold text-lg hover:bg-blue-700 transition-colors"
        >
          Sign in with Google
        </a>
      </div>
    </div>
  )
}
