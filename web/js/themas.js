// Thema's per viering: logo, deeltjes en een paar woorden die per feest verschillen.
import { html, raw, opslag } from './hulp.js'

export const THEMAS = {
  standaard: {
    naam: 'Standaard',
    emoji: '🎉',
    deeltjes: null,
    held: 'linear-gradient(135deg, #3b5bdb 0%, #5f3dc4 100%)',
    hoofd: '#3b5bdb',
    accent: '#f2bf5e',
    engel: 'je geheime gever',
    kleur: '#3b5bdb',
    menu: 'Menu',
    omschrijving: 'Strak en rustig, voor elk feest.',
  },
  kerst: {
    naam: 'Kerst',
    emoji: '🎄',
    deeltjes: 'sneeuw',
    held: 'linear-gradient(160deg, #c22d35 0%, #8f1b22 100%)',
    hoofd: '#1d6a48',
    accent: '#f2c14e',
    engel: 'je geheime kerstengel',
    kleur: '#b3262e',
    menu: 'Kerstmenu',
    omschrijving: 'Kerstrood, dennengroen en sneeuw.',
  },
  sinterklaas: {
    naam: 'Sinterklaas',
    emoji: '🎁',
    deeltjes: 'pepernoten',
    held: 'linear-gradient(160deg, #b51d2e 0%, #6e0f1a 100%)',
    hoofd: '#b0182a',
    accent: '#e6be5a',
    engel: 'de Sint',
    kleur: '#b0182a',
    menu: 'Menu',
    omschrijving: 'Mijterrood en goud, met pepernoten.',
  },
  zomer: {
    naam: 'Zomer',
    emoji: '☀️',
    deeltjes: 'bubbels',
    held: 'linear-gradient(175deg, #ffc15e 0%, #ff8a5c 45%, #f25f7a 70%, #0c8599 100%)',
    hoofd: '#0c8599',
    accent: '#f59f00',
    engel: 'je geheime zomergast',
    kleur: '#0c8599',
    menu: 'Menu',
    omschrijving: 'Zonsondergang aan zee.',
  },
  halloween: {
    naam: 'Halloween',
    emoji: '🎃',
    deeltjes: 'vonken',
    held: 'radial-gradient(circle at 82% 22%, #ffb35c 0 34px, rgba(255,179,92,.25) 35px 46px, transparent 47px), linear-gradient(160deg, #3a2352 0%, #140d1f 100%)',
    hoofd: '#d9480f',
    accent: '#2b8a3e',
    engel: 'je geheime geest',
    kleur: '#d9480f',
    menu: 'Menu',
    omschrijving: 'Pompoenoranje en griezelpaars.',
  },
}

export const thema = (id) => THEMAS[id] || THEMAS.standaard
export const opslagDeeltjes = () => opslag.lees('deeltjes', true)
export const hoofdletter = (t) => (t ? t[0].toUpperCase() + t.slice(1) : t)

// ------------------------------------------------------------------ logo's (zelfde stijl als Afterfeed: afgeronde balkjes)

const LOGOS = {
  standaard: `<rect class="tak" x="6" y="15" width="22" height="5" rx="2.5" style="fill:H"/>
    <rect class="tak" x="6" y="24.5" width="31" height="5" rx="2.5" style="fill:H"/>
    <rect class="tak" x="6" y="34" width="15" height="5" rx="2.5" style="fill:H"/>
    <path class="logo-accent" style="fill:A" d="M37.5 3.5l2.2 4.6 4.6 2.2-4.6 2.2-2.2 4.6-2.2-4.6-4.6-2.2 4.6-2.2z"/>`,
  kerst: `<path class="logo-accent" style="fill:A" d="M24 1.5l2.6 5.3 5.3 2.6-5.3 2.6L24 17.3l-2.6-5.3-5.3-2.6 5.3-2.6z"/>
    <rect class="tak" x="17" y="19" width="14" height="4.8" rx="2.4" style="fill:H"/>
    <rect class="tak" x="11.5" y="26.4" width="25" height="4.8" rx="2.4" style="fill:H"/>
    <rect class="tak" x="6" y="33.8" width="36" height="4.8" rx="2.4" style="fill:H"/>
    <rect class="tak" x="21.5" y="41.2" width="5" height="5.3" rx="1.7" style="fill:H"/>`,
  sinterklaas: `<path class="tak" style="fill:H" d="M12.5 43V22c0-7 4.6-13.2 11.5-18 6.9 4.8 11.5 11 11.5 18v21a1.5 1.5 0 0 1-1.5 1.5H14a1.5 1.5 0 0 1-1.5-1.5z"/>
    <rect class="logo-accent" style="fill:A" x="22.2" y="13" width="3.6" height="15.5" rx="1.3"/>
    <rect class="logo-accent" style="fill:A" x="16.8" y="18.4" width="14.4" height="3.6" rx="1.3"/>
    <rect class="logo-accent" style="fill:A" x="12.5" y="34.5" width="23" height="4.2"/>`,
  zomer: `<path class="logo-accent" style="fill:A" d="M11.5 23.5a12.5 12.5 0 0 1 25 0z"/>
    <rect class="tak" x="4.5" y="27" width="39" height="4.6" rx="2.3" style="fill:H"/>
    <rect class="tak" x="10.5" y="34.2" width="27" height="4.6" rx="2.3" style="fill:H"/>
    <rect class="tak" x="17.5" y="41.4" width="13" height="4.6" rx="2.3" style="fill:H"/>
    <rect class="logo-accent" style="fill:A" x="22.3" y="3" width="3.4" height="6" rx="1.7"/>
    <rect class="logo-accent" style="fill:A" x="22.3" y="3" width="3.4" height="6" rx="1.7" transform="rotate(-45 24 23.5)"/>
    <rect class="logo-accent" style="fill:A" x="22.3" y="3" width="3.4" height="6" rx="1.7" transform="rotate(45 24 23.5)"/>`,
  halloween: `<rect class="logo-accent" style="fill:A" x="21.8" y="5" width="4.6" height="10" rx="2" transform="rotate(14 24 10)"/>
    <ellipse class="tak" style="fill:H" cx="16.5" cy="29" rx="11" ry="13.5"/>
    <ellipse class="tak" style="fill:H" cx="31.5" cy="29" rx="11" ry="13.5"/>
    <ellipse class="tak rib" style="fill:H;stroke:G;stroke-width:1.6" cx="24" cy="29" rx="8" ry="14.5"/>
    <path style="fill:G" d="M14.5 26.5l4-5.5 4 5.5zM25.5 26.5l4-5.5 4 5.5zM15 32.5c3.5 4.5 14.5 4.5 18 0l-3 1.3-3-2-3 2-3-2-3 2z"/>`,
}

/** Logo van een thema. Zonder kleuren volgt het de variabelen van het actieve thema. */
export function logoSvg(id, maat = 32, kleuren = {}) {
  const h = kleuren.hoofd || 'var(--logo-hoofd)'
  const a = kleuren.accent || 'var(--logo-accent)'
  const g = kleuren.gat || 'var(--logo-gat)'
  const vorm = (LOGOS[id] || LOGOS.standaard).replace(/fill:H/g, `fill:${h}`).replace(/fill:A/g, `fill:${a}`).replace(/:G/g, `:${g}`)
  return `<svg class="logo" width="${maat}" height="${maat}" viewBox="0 0 48 48" aria-hidden="true" focusable="false">${vorm}</svg>`
}

export const logo = (id, maat, kleuren) => raw(logoSvg(id, maat, kleuren))

/** Logo in vaste kleuren (voor voorbeelden van een ander thema dan het actieve). */
export const logoVast = (id, maat = 32, wit = false) => {
  const t = thema(id)
  return logo(id, maat, wit ? { hoofd: '#ffffff', accent: t.accent, gat: 'rgba(0,0,0,.55)' } : { hoofd: t.hoofd, accent: t.accent, gat: '#ffffff' })
}

// ------------------------------------------------------------------ deeltjes

const DEELTJES = {
  sneeuw: { aantal: 36, maat: [2, 5], duur: [9, 18], zwaai: 26, licht: [0.35, 0.9] },
  pepernoten: { aantal: 16, maat: [6, 10], duur: [10, 18], zwaai: 18, licht: [0.5, 0.95] },
  bubbels: { aantal: 18, maat: [6, 16], duur: [12, 22], zwaai: 22, licht: [0.35, 0.8] },
  vonken: { aantal: 24, maat: [2, 4], duur: [8, 15], zwaai: 30, licht: [0.45, 1] },
}

const willekeurig = (min, max) => min + Math.random() * (max - min)

/** Deeltjes voor een thema. achter = de achtergrond van de hele pagina (rustiger). */
export function deeltjes(id, { achter = false, factor = 1 } = {}) {
  const soort = thema(id).deeltjes
  if (!soort) return ''
  const c = DEELTJES[soort]
  const aantal = Math.round(c.aantal * factor * (achter ? 0.7 : 1))
  const stukjes = []
  for (let i = 0; i < aantal; i++) {
    const s = willekeurig(...c.maat).toFixed(1)
    const d = willekeurig(...c.duur).toFixed(1)
    const o = (willekeurig(...c.licht) * (achter ? 0.6 : 1)).toFixed(2)
    stukjes.push(
      `<i style="--x:${willekeurig(0, 100).toFixed(1)}%;--s:${s}px;--d:${d}s;--w:-${willekeurig(0, d).toFixed(1)}s;--o:${o};--z:${willekeurig(-c.zwaai, c.zwaai).toFixed(0)}px"></i>`,
    )
  }
  return html`<div class="deeltjes ${soort} ${achter ? 'achter' : ''}" aria-hidden="true">${raw(stukjes.join(''))}</div>`
}

// ------------------------------------------------------------------ thema zetten

const THEMA_KLEUR = { licht: '#f4f5f7', donker: '#111214' }

export function zetThema(id, slug) {
  const t = THEMAS[id] ? id : 'standaard'
  document.documentElement.dataset.thema = t
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) {
    const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()
    meta.setAttribute('content', bg || THEMA_KLEUR[document.documentElement.dataset.modus] || '#f4f5f7')
  }
  if (slug) {
    const bekend = opslag.lees('themas', {})
    if (bekend[slug] !== t) {
      bekend[slug] = t
      opslag.zet('themas', bekend)
    }
  }
}

// ------------------------------------------------------------------ licht/donker

const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null

export function zetModus(keuze) {
  if (keuze) opslag.zet('modus', keuze)
  const k = opslag.lees('modus', 'systeem')
  const donker = k === 'donker' || (k === 'systeem' && media && media.matches)
  document.documentElement.dataset.modus = donker ? 'donker' : 'licht'
  zetThema(document.documentElement.dataset.thema)
}

if (media) {
  const luister = () => {
    if (opslag.lees('modus', 'systeem') === 'systeem') zetModus()
  }
  if (media.addEventListener) media.addEventListener('change', luister)
  else if (media.addListener) media.addListener(luister)
}
