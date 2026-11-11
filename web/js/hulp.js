// Kleine hulpjes die overal gebruikt worden: veilige HTML, de API, datums, toasts en dialogen.
import { svg } from './iconen.js'

// ------------------------------------------------------------------ veilige HTML

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c])

class Veilig {
  constructor(h) {
    this.h = h
  }
  toString() {
    return this.h
  }
}

/** Markeert tekst als veilige HTML (alleen voor eigen opmaak, nooit voor invoer van gebruikers). */
export const raw = (h) => new Veilig(h)

function deel(v) {
  if (v == null || v === false || v === true) return ''
  if (v instanceof Veilig) return v.h
  if (Array.isArray(v)) return v.map(deel).join('')
  return esc(v)
}

/** Tagged template: alles wat je invult wordt ge-escaped, behalve andere html``-stukken. */
export function html(strings, ...waarden) {
  let uit = strings[0]
  for (let i = 0; i < waarden.length; i++) uit += deel(waarden[i]) + strings[i + 1]
  return new Veilig(uit)
}

export const icoon = (naam, maat = 20, lijn = 1.75) => raw(svg(naam, maat, lijn))

export function zet(el, inhoud) {
  el.innerHTML = deel(inhoud)
}

export const $ = (sel, root = document) => root.querySelector(sel)
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)]

/** Eventdelegatie: on(root, 'click', '[data-x]', (e, el) => ...) */
export function on(root, type, selector, fn) {
  const handler = (e) => {
    const el = e.target.closest(selector)
    if (el && root.contains(el)) fn(e, el)
  }
  root.addEventListener(type, handler)
  return () => root.removeEventListener(type, handler)
}

// ------------------------------------------------------------------ API

export class ApiFout extends Error {
  constructor(status, data) {
    super((data && data.fout) || 'Er ging iets mis.')
    this.status = status
    this.data = data || {}
  }
}

export async function api(methode, pad, data) {
  const opties = { method: methode, headers: { 'X-Planr': '1' }, credentials: 'same-origin' }
  if (data !== undefined) {
    opties.headers['Content-Type'] = 'application/json'
    opties.body = JSON.stringify(data)
  }
  let r
  try {
    r = await fetch('/api' + pad, opties)
  } catch {
    throw new ApiFout(0, { fout: 'Geen verbinding. Controleer je internet en probeer het opnieuw.' })
  }
  let body = {}
  try {
    body = await r.json()
  } catch {
    body = {}
  }
  if (!r.ok) {
    if (r.status === 401 && body.code === 'niet_ingelogd') window.dispatchEvent(new CustomEvent('planr:uitgelogd'))
    if (r.status >= 500 && !body.fout) body.fout = 'De server is even niet bereikbaar. Probeer het zo nog eens.'
    throw new ApiFout(r.status, body)
  }
  return body
}

export const get = (p) => api('GET', p)
export const post = (p, d = {}) => api('POST', p, d)
export const put = (p, d = {}) => api('PUT', p, d)
export const del = (p) => api('DELETE', p)

/** Zet een knop op 'bezig' tijdens een actie. */
export async function metKnop(knop, fn) {
  if (knop) {
    knop.disabled = true
    knop.classList.add('bezig')
  }
  try {
    return await fn()
  } finally {
    if (knop) {
      knop.disabled = false
      knop.classList.remove('bezig')
    }
  }
}

/** Toont een foutmelding in een formulier (element met [data-fout]) of als toast. */
export function toonFout(fout, plek) {
  const tekst = fout instanceof Error ? fout.message : String(fout)
  if (plek) {
    plek.textContent = tekst
    plek.hidden = false
    const veld = fout?.data?.veld && plek.closest('form')?.querySelector(`[name="${fout.data.veld}"]`)
    if (veld) {
      veld.classList.add('fout')
      veld.focus()
      veld.addEventListener('input', () => veld.classList.remove('fout'), { once: true })
    }
  } else {
    toast({ titel: 'Dat lukte niet', tekst, soort: 'fout' })
  }
}

export function wisFout(plek) {
  if (plek) {
    plek.textContent = ''
    plek.hidden = true
  }
}

export function formulier(form) {
  const uit = {}
  for (const [k, v] of new FormData(form)) uit[k] = typeof v === 'string' ? v.trim() : v
  return uit
}

// ------------------------------------------------------------------ datums

const dagFmt = new Intl.DateTimeFormat('nl-NL', { day: 'numeric', month: 'long' })
const dagJaarFmt = new Intl.DateTimeFormat('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
const weekdagFmt = new Intl.DateTimeFormat('nl-NL', { weekday: 'long', day: 'numeric', month: 'long' })
const tijdFmt = new Intl.DateTimeFormat('nl-NL', { hour: '2-digit', minute: '2-digit' })
const kortFmt = new Intl.DateTimeFormat('nl-NL', { day: 'numeric', month: 'short' })

export function tijdGeleden(iso) {
  const d = new Date(iso)
  if (isNaN(d)) return ''
  const s = (Date.now() - d.getTime()) / 1000
  if (s < 60) return 'zojuist'
  if (s < 3600) return `${Math.floor(s / 60)} min geleden`
  if (s < 86400 && d.getDate() === new Date().getDate()) return `vandaag om ${tijdFmt.format(d)}`
  const gisteren = new Date()
  gisteren.setDate(gisteren.getDate() - 1)
  if (d.toDateString() === gisteren.toDateString()) return `gisteren om ${tijdFmt.format(d)}`
  if (s < 7 * 86400) return `${Math.max(2, Math.round(s / 86400))} dagen geleden`
  return d.getFullYear() === new Date().getFullYear() ? dagFmt.format(d) : dagJaarFmt.format(d)
}

export const tijd = (iso) => tijdFmt.format(new Date(iso))

export function dagLabel(iso) {
  const d = new Date(iso)
  const vandaag = new Date()
  if (d.toDateString() === vandaag.toDateString()) return 'Vandaag'
  const gisteren = new Date()
  gisteren.setDate(vandaag.getDate() - 1)
  if (d.toDateString() === gisteren.toDateString()) return 'Gisteren'
  return d.getFullYear() === vandaag.getFullYear() ? weekdagFmt.format(d) : dagJaarFmt.format(d)
}

export const kortDatum = (iso) => kortFmt.format(new Date(iso))

/** Datum van het evenement ('2026-12-25') als Date, of null als het geen datum is. */
export function evenementDatum(ev) {
  if (!ev || !/^\d{4}-\d{2}-\d{2}$/.test(ev.datum || '')) return null
  const [j, m, d] = ev.datum.split('-').map(Number)
  return new Date(j, m - 1, d)
}

export function evenementWanneer(ev) {
  const d = evenementDatum(ev)
  const datum = d ? weekdagFmt.format(d) : ev?.datum || ''
  return [datum, ev?.tijd ? `om ${ev.tijd}` : ''].filter(Boolean).join(' ')
}

export function nachtjes(ev) {
  const d = evenementDatum(ev)
  if (!d) return null
  const vandaag = new Date()
  vandaag.setHours(0, 0, 0, 0)
  return Math.round((d - vandaag) / 86400000)
}

// ------------------------------------------------------------------ namen en avatars

export function initialen(naam) {
  const delen = String(naam || '?').trim().split(/\s+/).filter(Boolean)
  if (delen.length === 0) return '?'
  if (delen.length === 1) return delen[0].slice(0, 2).toUpperCase()
  return (delen[0][0] + delen[delen.length - 1][0]).toUpperCase()
}

export function avatar(persoon, maat = 36) {
  const toon = Math.abs(Number(persoon?.toon) || 0) % 6
  return html`<span class="avatar t${toon}" style="--size:${maat}px" aria-hidden="true">${initialen(persoon?.naam)}</span>`
}

export function engelAvatar(maat = 36) {
  return html`<span class="avatar engel" style="--size:${maat}px" aria-hidden="true">?</span>`
}

export function namenLijst(namen, max = 3) {
  if (!namen.length) return ''
  if (namen.length === 1) return namen[0]
  if (namen.length <= max) return namen.slice(0, -1).join(', ') + ' en ' + namen[namen.length - 1]
  const rest = namen.length - max + 1
  return namen.slice(0, max - 1).join(', ') + ` en ${rest} anderen`
}

// ------------------------------------------------------------------ toasts

let toastPlek
export function toast({ titel, tekst = '', soort = 'info', icoon: icoonNaam, link, duur = 6000 }) {
  if (!toastPlek) {
    toastPlek = document.createElement('div')
    toastPlek.className = 'toasts'
    toastPlek.setAttribute('role', 'status')
    toastPlek.setAttribute('aria-live', 'polite')
    document.body.append(toastPlek)
  }
  const el = document.createElement(link ? 'button' : 'div')
  el.className = `toast ${soort}`
  if (link) el.type = 'button'
  const naam = icoonNaam || (soort === 'fout' ? 'info' : soort === 'goed' ? 'check' : 'bel')
  zet(el, html`<span class="icoon-rond ${soort === 'goed' ? 'groen' : ''}">${icoon(naam, 18)}</span>
    <span><span class="titel">${titel}</span>${tekst ? html`<span class="tekst">${tekst}</span>` : ''}</span>`)
  const weg = () => {
    el.classList.add('weg')
    setTimeout(() => el.remove(), 200)
  }
  if (link) {
    el.addEventListener('click', () => {
      weg()
      window.dispatchEvent(new CustomEvent('planr:ga', { detail: link }))
    })
  }
  toastPlek.append(el)
  while (toastPlek.children.length > 3) toastPlek.firstElementChild.remove()
  setTimeout(weg, duur)
}

// ------------------------------------------------------------------ dialoog

export function bevestig({ titel, tekst = '', ja = 'Ja', nee = 'Annuleren', gevaar = false }) {
  return new Promise((klaar) => {
    const d = document.createElement('dialog')
    d.className = 'dialoog'
    zet(d, html`<form method="dialog" class="dialoog-binnen">
      <h2>${titel}</h2>
      ${tekst ? html`<p>${tekst}</p>` : ''}
      <div class="knoppen">
        <button class="btn" value="nee" type="submit">${nee}</button>
        <button class="btn ${gevaar ? 'btn-feest' : 'btn-primary'}" value="ja" type="submit">${ja}</button>
      </div>
    </form>`)
    document.body.append(d)
    d.addEventListener('close', () => {
      klaar(d.returnValue === 'ja')
      d.remove()
    })
    d.addEventListener('click', (e) => {
      if (e.target === d) d.close('nee')
    })
    d.showModal()
    d.querySelector('[value="ja"]').focus()
  })
}

// ------------------------------------------------------------------ overig

export function autoHoogte(textarea, max = 160) {
  const pas = () => {
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(max, textarea.scrollHeight + 2) + 'px'
  }
  textarea.addEventListener('input', pas)
  pas()
  return pas
}

export function vertraag(fn, ms) {
  let t
  const v = (...args) => {
    clearTimeout(t)
    t = setTimeout(() => fn(...args), ms)
  }
  v.nu = (...args) => {
    clearTimeout(t)
    fn(...args)
  }
  return v
}

export function veiligeLink(url) {
  return /^https?:\/\//i.test(url || '') ? url : ''
}

export function korteLink(url) {
  try {
    const u = new URL(url)
    return u.hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export const opslag = {
  lees(k, standaard = null) {
    try {
      const v = localStorage.getItem('planr.' + k)
      return v === null ? standaard : JSON.parse(v)
    } catch {
      return standaard
    }
  },
  zet(k, v) {
    try {
      localStorage.setItem('planr.' + k, JSON.stringify(v))
    } catch {
      /* privémodus: niet erg */
    }
  },
}
