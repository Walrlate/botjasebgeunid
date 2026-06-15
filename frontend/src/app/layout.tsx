import type { Metadata, Viewport } from 'next'
import '../styles/globals.css'
import Script from 'next/script'

export const metadata: Metadata = {
  title: 'GEUNID-JASEB Premium Ecosystem',
  description: 'Premium Telegram Jaseb Bot Web Client',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
}


export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="id">
      <head>
        <Script 
          src="https://telegram.org/js/telegram-web-app.js" 
          strategy="beforeInteractive"
        />
      </head>
      <body>
        {children}
      </body>
    </html>
  )
}
