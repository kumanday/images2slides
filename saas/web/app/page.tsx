import Link from 'next/link'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/app/api/auth/[...nextauth]/route'

export default async function Home() {
  const session = await getServerSession(authOptions)

  return (
    <main className="min-h-screen flex flex-col">
      {/* Hero Section */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-16 bg-gradient-to-b from-blue-50 to-white">
        <h1 className="text-5xl font-bold text-center text-gray-900 mb-6">
          Transform Infographics into<br />Editable Slides
        </h1>
        <p className="text-xl text-gray-600 text-center max-w-2xl mb-8">
          Upload your infographic images and let AI convert them into beautiful, 
          editable Google Slides presentations in seconds.
        </p>
        
        {session ? (
          <Link 
            href="/app"
            className="px-8 py-4 bg-primary-600 text-white text-lg font-semibold rounded-lg hover:bg-primary-700 transition-colors"
          >
            Go to Dashboard
          </Link>
        ) : (
          <Link 
            href="/api/auth/signin"
            className="px-8 py-4 bg-primary-600 text-white text-lg font-semibold rounded-lg hover:bg-primary-700 transition-colors"
          >
            Sign in with Google
          </Link>
        )}
      </div>

      {/* Features */}
      <div className="px-4 py-16 bg-white">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="p-6 rounded-lg border border-gray-200">
            <h3 className="text-xl font-semibold mb-3">🔍 Smart Text Extraction</h3>
            <p className="text-gray-600">
              Our AI Vision-Language Model accurately detects and extracts text from 
              infographic images, preserving the original layout.
            </p>
          </div>
          <div className="p-6 rounded-lg border border-gray-200">
            <h3 className="text-xl font-semibold mb-3">🎨 Layout Preservation</h3>
            <p className="text-gray-600">
              Reconstruct your infographics as native slide elements including text 
              boxes and images, maintaining visual fidelity.
            </p>
          </div>
          <div className="p-6 rounded-lg border border-gray-200">
            <h3 className="text-xl font-semibold mb-3">☁️ Direct to Drive</h3>
            <p className="text-gray-600">
              Generated presentations are created directly in your Google Drive, 
              ready for editing and sharing.
            </p>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="px-4 py-8 bg-gray-50 border-t">
        <p className="text-center text-gray-600">
          Built with Next.js, FastAPI, and Google AI
        </p>
      </footer>
    </main>
  )
}
