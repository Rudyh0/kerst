// Meldingen in de app (bel, paneel, toasts) en pushmeldingen op dit apparaat.
import { get, html, icoon, post, tijdGeleden, toast, zet } from './hulp.js'
import { thema } from './themas.js'

const ICOON = { lootje: 'cadeau', berichten: 'berichten', wensen: 'lijst', menu: 'bestek', algemeen: 'kalender', deelnemers: 'users' }
const INTERVAL = 15000

let app = null
let laatste = 0
let ongelezen = 0
let lijst = []
let timer = null
let bezig = false
let paneel = null

function zichtbaarLuisteraar() {
  if (!document.hidden) haalNu()
}

export function start(a) {
  app = a
  laatste = 0
  lijst = []
  stop()
  haal()
  timer = setInterval(() => {
    if (!document.hidden) haal()
  }, INTERVAL)
  document.addEventListener('visibilitychange', zichtbaarLuisteraar)
  window.addEventListener('focus', zichtbaarLuisteraar)
  herstelPush()
}

export function stop() {
  clearInterval(timer)
  timer = null
  document.removeEventListener('visibilitychange', zichtbaarLuisteraar)
  window.removeEventListener('focus', zichtbaarLuisteraar)
  sluitPaneel()
}

export function haalNu() {
  if (app) haal()
}

async function haal() {
  if (bezig) return
  bezig = true
  try {
    const eerste = laatste === 0
    const r = await get(eerste ? '/meldingen' : `/meldingen?na=${laatste}`)
    ongelezen = r.ongelezen
    if (eerste) {
      lijst = r.meldingen
    } else if (r.meldingen.length) {
      const nieuw = r.meldingen
      const ids = new Set(nieuw.map((m) => m.id))
      lijst = [...nieuw.slice().reverse(), ...lijst.filter((m) => !ids.has(m.id))].slice(0, 80)
      let moetSessie = false
      for (const m of nieuw) {
        window.dispatchEvent(new CustomEvent('planr:melding', { detail: m }))
        if (['berichten', 'lootje', 'deelnemers', 'algemeen'].includes(m.soort)) moetSessie = true
        if (m.link && location.pathname === m.link) continue
        toast({ titel: m.titel, tekst: m.tekst.split('\n').pop(), icoon: ICOON[m.soort] || 'bel', link: m.link || null })
      }
      if (moetSessie) app.vernieuwSessie()
    }
    laatste = Math.max(laatste, r.laatste)
    toonBadge()
    if (paneel) tekenPaneel()
  } catch {
    /* volgende keer opnieuw */
  } finally {
    bezig = false
  }
}

export function toonBadge() {
  for (const b of document.querySelectorAll('[data-badge="meldingen"]')) {
    b.hidden = !ongelezen
    b.textContent = ongelezen > 99 ? '99+' : String(ongelezen)
  }
  if ('setAppBadge' in navigator) {
    ;(ongelezen ? navigator.setAppBadge(ongelezen) : navigator.clearAppBadge()).catch(() => {})
  }
  const titel = document.title.replace(/^\(\d+\+?\) /, '')
  document.title = ongelezen ? `(${ongelezen}) ${titel}` : titel
}

/** Een pagina is geopend: meldingen die daarnaar wijzen zijn dan gelezen. */
export function paginaGeopend(pad) {
  if (!lijst.some((m) => !m.gelezen && m.link === pad)) return
  for (const m of lijst) if (m.link === pad) m.gelezen = true
  post('/meldingen/gelezen', { link: pad })
    .then((r) => {
      ongelezen = r.ongelezen
      toonBadge()
    })
    .catch(() => {})
}

// ------------------------------------------------------------------ paneel

export function openPaneel() {
  if (paneel) return sluitPaneel()
  paneel = document.createElement('div')
  document.body.append(paneel)
  tekenPaneel()
  get('/meldingen')
    .then((r) => {
      lijst = r.meldingen
      ongelezen = r.ongelezen
      laatste = Math.max(laatste, r.laatste)
      toonBadge()
      if (paneel) tekenPaneel()
    })
    .catch(() => {})
  paneel.querySelector('.meldingen-paneel')?.focus()
}

export function sluitPaneel() {
  if (paneel) {
    paneel.remove()
    paneel = null
  }
}

function tekenPaneel() {
  zet(paneel, html`<button class="scrim" type="button" aria-label="Sluiten" data-sluit></button>
    <section class="meldingen-paneel" role="dialog" aria-label="Meldingen" tabindex="-1">
      <header class="paneel-kop">
        <h2>Meldingen</h2>
        ${ongelezen ? html`<button class="btn btn-sm" type="button" data-alles>Alles gelezen</button>` : ''}
        <button class="icon-btn" type="button" data-sluit aria-label="Sluiten">${icoon('close', 20)}</button>
      </header>
      <div class="paneel-lijst">
        ${lijst.length
          ? lijst.map(
              (m) => html`<a class="melding ${m.gelezen ? '' : 'ongelezen'}" href="${m.link || '/'}" data-id="${m.id}">
                <span class="icoon-rond">${icoon(ICOON[m.soort] || 'bel', 18)}</span>
                <span class="midden">
                  <span class="titel">${m.titel}</span>
                  ${m.tekst ? html`<span class="tekst">${m.tekst}</span>` : ''}
                  <time datetime="${m.gemaakt}">${m.viering ? `${thema(m.viering.thema).emoji} ${m.viering.naam} · ` : ''}${tijdGeleden(m.gemaakt)}</time>
                </span>
              </a>`,
            )
          : html`<div class="leeg"><span class="icoon-rond">${icoon('bel', 22)}</span><p>Nog geen meldingen. Zodra er iets gebeurt, zie je het hier.</p></div>`}
      </div>
    </section>`)
  paneel.querySelectorAll('[data-sluit]').forEach((b) => b.addEventListener('click', sluitPaneel))
  paneel.querySelector('[data-alles]')?.addEventListener('click', async () => {
    const r = await post('/meldingen/gelezen', { alles: true })
    ongelezen = r.ongelezen
    lijst.forEach((m) => (m.gelezen = true))
    toonBadge()
    tekenPaneel()
  })
  paneel.querySelectorAll('.melding').forEach((a) =>
    a.addEventListener('click', () => {
      const id = Number(a.dataset.id)
      const m = lijst.find((x) => x.id === id)
      if (m && !m.gelezen) {
        m.gelezen = true
        ongelezen = Math.max(0, ongelezen - 1)
        toonBadge()
        post('/meldingen/gelezen', { ids: [id] }).catch(() => {})
      }
      sluitPaneel()
    }),
  )
}

// ------------------------------------------------------------------ push

export const pushOndersteund = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

export const isIOS = () => /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
export const isApp = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true

function sleutelNaarBytes(b64) {
  const opvul = '='.repeat((4 - (b64.length % 4)) % 4)
  const ruw = atob((b64 + opvul).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from([...ruw].map((c) => c.charCodeAt(0)))
}

function apparaatNaam() {
  const ua = navigator.userAgent
  const os = /iPhone/.test(ua) ? 'iPhone' : /iPad/.test(ua) ? 'iPad' : /Android/.test(ua) ? 'Android' : /Mac/.test(ua) ? 'Mac' : /Windows/.test(ua) ? 'Windows' : /Linux/.test(ua) ? 'Linux' : 'Apparaat'
  const browser = /Edg\//.test(ua) ? 'Edge' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'browser'
  return `${browser} op ${os}`
}

export async function pushStatus() {
  if (!pushOndersteund()) return 'niet'
  if (!app?.staat.sessie?.push) return 'server'
  if (Notification.permission === 'denied') return 'geblokkeerd'
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  return sub && Notification.permission === 'granted' ? 'aan' : 'uit'
}

export async function pushAan() {
  const toestemming = await Notification.requestPermission()
  if (toestemming !== 'granted') throw new Error('Je browser staat meldingen voor deze site niet toe. Zet het aan in de instellingen van je browser.')
  const reg = await navigator.serviceWorker.ready
  const sleutel = sleutelNaarBytes(app.staat.sessie.vapid)
  let sub = await reg.pushManager.getSubscription()
  if (sub && sub.options?.applicationServerKey) {
    const oud = new Uint8Array(sub.options.applicationServerKey)
    if (oud.length !== sleutel.length || oud.some((b, i) => b !== sleutel[i])) {
      await sub.unsubscribe()
      sub = null
    }
  }
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: sleutel })
  await post('/push', { ...sub.toJSON(), apparaat: apparaatNaam() })
}

export async function pushUit() {
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  if (sub) {
    await post('/push/weg', { endpoint: sub.endpoint }).catch(() => {})
    await sub.unsubscribe()
  }
}

export const pushTest = () => post('/push/test')

/** Na inloggen: een bestaand abonnement op dit apparaat (opnieuw) aan dit account koppelen. */
async function herstelPush() {
  try {
    if (!pushOndersteund() || Notification.permission !== 'granted' || !app.staat.sessie?.push) return
    const reg = await navigator.serviceWorker.ready
    const sub = await reg.pushManager.getSubscription()
    if (sub) await post('/push', { ...sub.toJSON(), apparaat: apparaatNaam() })
  } catch {
    /* niet erg */
  }
}
