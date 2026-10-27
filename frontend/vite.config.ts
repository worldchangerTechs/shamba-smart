import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['pwa-icon.svg'],
      manifest: {
        name: 'SHAMBA SMART 360',
        short_name: 'Shamba Smart',
        description: 'Practical farm advice for every season, in the farmer’s language.',
        theme_color: '#F6F3EA',
        background_color: '#F6F3EA',
        display: 'standalone',
        scope: '/',
        start_url: '/',
        icons: [
          { src: '/pwa-icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{html,css,svg,png,woff2}'],
        navigateFallback: '/index.html',
        runtimeCaching: [
          {
            urlPattern: /\/assets\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'shamba-app-assets',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 * 180 },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const moduleId = id.replace(/\\/g, '/')
          if (!moduleId.includes('/node_modules/')) return
          if (/\/(react|react-dom|react-router|react-router-dom)\//.test(moduleId)) return 'react-vendor'
          if (moduleId.includes('/framer-motion/')) return 'motion-vendor'
          if (/\/(recharts|d3-[^/]+|victory-vendor)\//.test(moduleId)) return 'charts-vendor'
          if (moduleId.includes('/lucide-react/')) return 'icons-vendor'
          if (/\/(axios|@tanstack\/react-query)\//.test(moduleId)) return 'data-vendor'
          if (/\/(leaflet|react-leaflet)\//.test(moduleId)) return 'map-vendor'
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      ignored: ['**/images/**'],
    },
  },
})
