// Service worker van plan-r: alleen voor pushmeldingen (geen offline-cache, zodat updates meteen werken).
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()))

const isSafari = /Safari\//.test(navigator.userAgent) && !/Chrom(e|ium)\//.test(navigator.userAgent)

self.addEventListener('push', (e) => {
  let d = {}
  try {
    d = e.data ? e.data.json() : {}
  } catch {
    d = { titel: 'plan-r', tekst: e.data ? e.data.text() : '' }
  }
  e.waitUntil(
    (async () => {
      const vensters = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const open = vensters.find((c) => c.visibilityState === 'visible' && c.focused)
      for (const c of vensters) c.postMessage({ soort: 'push', data: d })
      // Heb je de app open en in beeld? Dan toont de app zelf een melding. Safari wil altijd een melding zien.
      if (open && !isSafari) return
      await self.registration.showNotification(d.titel || 'plan-r', {
        body: d.tekst || '',
        icon: '/icons/icon-192.png',
        badge: '/icons/badge-96.png',
        tag: d.tag || undefined,
        renotify: Boolean(d.tag),
        data: { link: d.link || '/' },
      })
    })(),
  )
})

self.addEventListener('notificationclick', (e) => {
  e.notification.close()
  const link = (e.notification.data && e.notification.data.link) || '/'
  const url = new URL(link, self.location.origin).href
  e.waitUntil(
    (async () => {
      const vensters = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const c of vensters) {
        if (new URL(c.url).origin === self.location.origin) {
          await c.focus()
          c.postMessage({ soort: 'ga', link })
          return
        }
      }
      await self.clients.openWindow(url)
    })(),
  )
})
