import './globals.css'
import { Providers } from './providers'

export const metadata = {
  title: 'images2slides',
  description: 'Convert infographic images into Google Slides',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="min-h-screen">{children}</div>
        </Providers>
      </body>
    </html>
  )
}
