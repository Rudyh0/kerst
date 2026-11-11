// De app: router, schil (zijbalk, tabbalk) en sessie.
import { $, ApiFout, get, html, icoon, on, opslag, post, toast, zet } from './hulp.js'
import { deeltjes, logo, logoVast, thema, zetModus, zetThema } from './themas.js'
import * as meldingen from './meldingen.js'

const PAGINAS = {
  toegang: () => import('./paginas/toegang.js'),
  vieringen: () => import('./paginas/vieringen.js'),
  instellingen: () => import('./paginas/instellingen.js'),
  beheer: () => import('./paginas/beheer.js'),
  dashboard: () => import('./paginas/dashboard.js'),
  menu: () => import('./paginas/menu.js'),
  lootje: () => import('./paginas/lootje.js'),
  berichten: () => import('./paginas/berichten.js'),
  verlanglijst: () => import('./paginas/verlanglijst.js'),
  vbeheer: () => import('./paginas/vbeheer.js'),
}

// [patroon, pagina, params(match), opties]
const ROUTES = [
  [/^\/inloggen$/, 'toegang', () => ({ soort: 'inloggen' }), { publiek: true }],
  [/^\/wachtwoord-vergeten$/, 'toegang', () => ({ soort: 'vergeten' }), { publiek: true }],
  [/^\/uitnodiging\/([\w-]+)$/, 'toegang', (m) => ({ soort: 'uitnodiging', token: m[1] }), { publiek: true }],
  [/^\/herstel\/([\w-]+)$/, 'toegang', (m) => ({ soort: 'herstel', token: m[1] }), { publiek: true }],
  [/^\/$/, 'vieringen', () => ({})],
  [/^\/instellingen$/, 'instellingen', () => ({})],
  [/^\/beheer(?:\/(vieringen|nieuw|email|accounts))?$/, 'beheer', (m) => ({ tab: m[1] || 'vieringen' })],
  [/^\/([a-z0-9-]{3,40})$/, 'dashboard', (m) => ({ slug: m[1] })],
  [/^\/([a-z0-9-]{3,40})\/menu$/, 'menu', (m) => ({ slug: m[1] })],
  [/^\/([a-z0-9-]{3,40})\/lootje$/, 'lootje', (m) => ({ slug: m[1] })],
  [/^\/([a-z0-9-]{3,40})\/verlanglijst$/, 'verlanglijst', (m) => ({ slug: m[1] })],
  [/^\/([a-z0-9-]{3,40})\/berichten(?:\/(lootje|engel))?$/, 'berichten', (m) => ({ slug: m[1], gesprek: m[2] || null })],
  [/^\/([a-z0-9-]{3,40})\/beheer(?:\/(deelnemers|lootjes|instellingen))?$/, 'vbeheer', (m) => ({ slug: m[1], tab: m[2] || 'deelnemers' })],
]

export const staat = {
  sessie: null,
  context: null, // slug van de viering waar we in zitten, of null
}

let huidigeOpruim = null
let huidigePagina = ''
let schilSleutel = ''
let renderTeller = 0

// ------------------------------------------------------------------ navigatie

export function ga(pad, { vervang = false } = {}) {
  if (pad === location.pathname + location.search + location.hash && !vervang) return render()
  if (vervang) history.replaceState({}, '', pad)
  else history.pushState({}, '', pad)
  render()
}

window.addEventListener('popstate', () => render())
window.addEventListener('planr:ga', (e) => ga(e.detail))
window.addEventListener('planr:uitgelogd', () => {
  if (!staat.sessie?.gebruiker) return
  staat.sessie = null
  meldingen.stop()
  ga('/inloggen', { vervang: true })
})

document.addEventListener('click', (e) => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
  const a = e.target.closest('a[href]')
  if (!a || a.target || a.hasAttribute('download')) return
  const href = a.getAttribute('href')
  if (!href.startsWith('/') || href.startsWith('//') || href.startsWith('/api/')) return
  e.preventDefault()
  // Een openstaand menuutje sluiten
  a.closest('details[open]')?.removeAttribute('open')
  ga(href)
})

// Uitklapmenu's sluiten bij een klik ernaast
document.addEventListener('click', (e) => {
  for (const d of document.querySelectorAll('details.menu[open]')) {
    if (!d.contains(e.target)) d.removeAttribute('open')
  }
})

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    for (const d of document.querySelectorAll('details.menu[open]')) d.removeAttribute('open')
    sluitSheet()
  }
})

// ------------------------------------------------------------------ sessie

export async function laadSessie() {
  staat.sessie = await get('/sessie')
  return staat.sessie
}

export async function vernieuwSessie() {
  try {
    const oud = JSON.stringify(staat.sessie?.vieringen || [])
    await laadSessie()
    if (!staat.sessie.gebruiker) return
    if (JSON.stringify(staat.sessie.vieringen) !== oud) {
      schilSleutel = ''
      tekenSchil()
    }
  } catch {
    /* later opnieuw */
  }
}

export const viering = (slug = staat.context) => staat.sessie?.vieringen?.find((v) => v.slug === slug) || null

// ------------------------------------------------------------------ schil

function navItem(href, ikoon, tekst, { badge = 0, actief = false, id = '' } = {}) {
  return html`<a class="nav-item ${actief ? 'actief' : ''}" href="${href}" data-nav="${id || href}" ${actief ? html`aria-current="page"` : ''}>
    ${icoon(ikoon, 20)}<span>${tekst}</span>${badge ? html`<span class="badge">${badge}</span>` : ''}</a>`
}

function tabItem(href, ikoon, tekst, id, badge = 0) {
  return html`<a class="tab" href="${href}" data-nav="${id}">${icoon(ikoon, 22)}<span>${tekst}</span>${badge ? html`<span class="badge">${badge}</span>` : ''}</a>`
}

function navLijst() {
  const s = staat.sessie
  const g = s.gebruiker
  const v = viering()
  if (!v || v.status !== 'actief') {
    return {
      boven: [
        ['/', 'home', 'Mijn vieringen', 'vieringen'],
        ['/instellingen', 'instellingen', 'Instellingen', 'instellingen'],
      ],
      onder: g.beheerder ? [['/beheer', 'beheer', 'Beheer', 'beheer']] : [],
      tabs: [
        ['/', 'home', 'Vieringen', 'vieringen'],
        ['/instellingen', 'instellingen', 'Instellingen', 'instellingen'],
        ...(g.beheerder ? [['/beheer', 'beheer', 'Beheer', 'beheer']] : []),
      ],
      meer: [],
    }
  }
  const b = `/${v.slug}`
  const boven = [[b, 'home', 'Overzicht', 'dashboard']]
  if (v.menu) boven.push([`${b}/menu`, 'bestek', thema(v.thema).menu, 'menu'])
  if (v.lootjes) {
    boven.push([`${b}/lootje`, 'cadeau', 'Mijn lootje', 'lootje'])
    boven.push([`${b}/berichten`, 'berichten', 'Berichten', 'berichten', v.berichten_ongelezen])
    boven.push([`${b}/verlanglijst`, 'lijst', 'Mijn verlanglijst', 'verlanglijst'])
  }
  const onder = []
  if (g.beheerder) onder.push([`${b}/beheer`, 'beheer', 'Beheer viering', 'vbeheer'])
  onder.push(['/instellingen', 'instellingen', 'Instellingen', 'instellingen'])
  const tabs = [[b, 'home', 'Overzicht', 'dashboard']]
  if (v.menu) tabs.push([`${b}/menu`, 'bestek', 'Menu', 'menu'])
  if (v.lootjes) {
    tabs.push([`${b}/lootje`, 'cadeau', 'Lootje', 'lootje'])
    tabs.push([`${b}/berichten`, 'berichten', 'Berichten', 'berichten', v.berichten_ongelezen])
    if (!v.menu) tabs.push([`${b}/verlanglijst`, 'lijst', 'Wensen', 'verlanglijst'])
  }
  const meer = []
  if (v.lootjes && v.menu) meer.push([`${b}/verlanglijst`, 'lijst', 'Mijn verlanglijst'])
  meer.push(['/', 'home', 'Alle vieringen'])
  meer.push(['/instellingen', 'instellingen', 'Instellingen'])
  if (g.beheerder) {
    meer.push([`${b}/beheer`, 'beheer', 'Beheer viering'])
    meer.push(['/beheer', 'beheer', 'Beheer (alles)'])
  }
  return { boven, onder, tabs, meer }
}

function merk() {
  const s = staat.sessie
  const v = viering()
  const andere = s.vieringen.filter((x) => x.slug !== v?.slug)
  if (!v) {
    return html`<a class="merk" href="/">${logo('standaard', 30)}<span>${s.app_naam}</span></a>`
  }
  return html`<details class="menu wissel">
    <summary class="merk" aria-label="Wissel van viering">${logo(v.thema, 30)}<span>${v.naam}</span>${icoon('chevron-down', 16)}</summary>
    <div class="menu-lijst wissel-lijst">
      ${andere.map((x) => html`<a href="/${x.slug}">${logoVast(x.thema, 22)}<span>${x.naam}</span>${x.status !== 'actief' ? html`<span class="pill pill-accent">Nieuw</span>` : ''}</a>`)}
      <a href="/">${icoon('home', 18)}<span>Alle vieringen</span></a>
    </div>
  </details>`
}

function tekenSchil() {
  const app = $('#app')
  const s = staat.sessie
  const v = viering()
  const sleutel = JSON.stringify([staat.context, v, s.gebruiker.beheerder, s.app_naam])
  if (sleutel === schilSleutel && $('#inhoud')) return
  schilSleutel = sleutel
  const n = navLijst()
  const kleinMerk = v
    ? html`<a class="merk" href="/${v.slug}">${logo(v.thema, 28)}<span>${v.naam}</span></a>`
    : html`<a class="merk" href="/">${logo('standaard', 28)}<span>${s.app_naam}</span></a>`
  let knop = ''
  if (v && v.status === 'actief') {
    if (v.menu) knop = html`<a class="btn btn-primary nieuw" href="/${v.slug}/menu#toevoegen">${icoon('plus', 18)}Iets meenemen</a>`
    else if (v.lootjes) knop = html`<a class="btn btn-primary nieuw" href="/${v.slug}/verlanglijst#toevoegen">${icoon('plus', 18)}Wens toevoegen</a>`
  }
  const oudMain = $('#inhoud')
  zet(app, html`
    ${v && opslag.lees('deeltjes', true) ? deeltjes(v.thema, { achter: true }) : ''}
    <div class="shell">
      <aside class="sidebar">
        ${merk()}
        <nav class="nav-items" aria-label="Hoofdmenu">${n.boven.map(([h, i, t, id, b]) => navItem(h, i, t, { id, badge: b }))}</nav>
        ${knop}
        <div class="nav-onder">
          <button class="nav-item" type="button" data-actie="meldingen">${icoon('bel', 20)}<span>Meldingen</span><span class="badge" data-badge="meldingen" hidden></span></button>
          ${n.onder.map(([h, i, t, id]) => navItem(h, i, t, { id }))}
          ${v ? '' : html`<button class="nav-item" type="button" data-actie="uitloggen">${icoon('logout', 20)}<span>Uitloggen</span></button>`}
        </div>
      </aside>
      <header class="topbalk">
        ${kleinMerk}
        <button class="icon-btn" type="button" data-actie="meldingen" aria-label="Meldingen">${icoon('bel', 22)}<span class="badge" data-badge="meldingen" hidden></span></button>
      </header>
      <main class="inhoud" id="inhoud" tabindex="-1"></main>
      <nav class="tabs" aria-label="Menu">
        ${n.tabs.map(([h, i, t, id, b]) => tabItem(h, i, t, id, b))}
        ${n.meer.length ? html`<button class="tab" type="button" data-actie="meer">${icoon('more', 22)}<span>Meer</span></button>` : ''}
      </nav>
    </div>`)
  // De pagina zelf laten staan: alleen de navigatie eromheen is vernieuwd.
  if (oudMain) $('#inhoud').replaceWith(oudMain)
  markeerActief(huidigePagina)
  meldingen.toonBadge()
}

function markeerActief(pagina) {
  const id = pagina === 'beheer' ? 'beheer' : pagina
  for (const el of document.querySelectorAll('[data-nav]')) {
    const actief = el.dataset.nav === id
    el.classList.toggle('actief', actief)
    if (actief) el.setAttribute('aria-current', 'page')
    else el.removeAttribute('aria-current')
  }
}

let sheet = null
function sluitSheet() {
  if (sheet) {
    sheet.remove()
    sheet = null
  }
}

function openMeer() {
  sluitSheet()
  const n = navLijst()
  sheet = document.createElement('div')
  zet(sheet, html`<button class="scrim" type="button" aria-label="Sluiten" data-sluit></button>
    <div class="sheet" role="menu">
      ${n.meer.map(([h, i, t]) => html`<a class="rij" href="${h}" role="menuitem">${icoon(i, 20)}<span>${t}</span></a>`)}
      <button class="rij" type="button" data-actie="uitloggen" role="menuitem">${icoon('logout', 20)}<span>Uitloggen</span></button>
    </div>`)
  sheet.addEventListener('click', (e) => {
    if (e.target.closest('[data-sluit], a')) sluitSheet()
  })
  document.body.append(sheet)
}

export async function uitloggen() {
  try {
    await post('/uitloggen')
  } catch {
    /* toch doorgaan */
  }
  staat.sessie = null
  meldingen.stop()
  sluitSheet()
  location.href = '/inloggen'
}

on(document, 'click', '[data-actie]', (e, el) => {
  const actie = el.dataset.actie
  if (actie === 'meldingen') meldingen.openPaneel()
  else if (actie === 'meer') openMeer()
  else if (actie === 'uitloggen') uitloggen()
})

// ------------------------------------------------------------------ fouten binnen een viering

/** Toont een nette melding als een viering niet (meer) bestaat, je geen lid bent of je nog moet aannemen. */
export function vieringFout(root, fout) {
  const d = fout instanceof ApiFout ? fout.data : {}
  const code = d.code
  if (code === 'uitnodiging_open') {
    const v = d.viering
    zetThema(v.thema, v.slug)
    zet(root, html`<div class="pagina smal"><div class="card uitnodiging-kaart">
      <div class="uitnodiging-held" style="background:${thema(v.thema).held}">${deeltjes(v.thema, { factor: 0.6 })}${logoVast(v.thema, 56, true)}</div>
      <div class="blok">
        <h1 class="sectie-titel groot-titel">Je bent uitgenodigd voor ${v.naam}</h1>
        <p class="muted">Doe mee om het overzicht, het menu en de lootjes van deze viering te zien.</p>
        <div class="knoppen"><button class="btn btn-feest btn-lg" type="button" data-aannemen>Doe mee</button><a class="btn btn-lg" href="/">Later</a></div>
      </div></div></div>`)
    $('[data-aannemen]', root).addEventListener('click', async (e) => {
      e.currentTarget.disabled = true
      try {
        await post(`/v/${v.slug}/aannemen`)
        await vernieuwSessie()
        toast({ titel: 'Leuk dat je meedoet!', soort: 'goed' })
        schilSleutel = ''
        render()
      } catch (f) {
        toast({ titel: 'Dat lukte niet', tekst: f.message, soort: 'fout' })
        e.currentTarget.disabled = false
      }
    })
    return
  }
  if (code === 'geen_lid') {
    zet(root, html`<div class="pagina smal"><div class="card leeg">
      <span class="icoon-rond">${icoon('lock', 22)}</span>
      <h1 class="sectie-titel">Je doet niet mee met ${d.viering?.naam || 'deze viering'}</h1>
      <p>Vraag de organisator om een uitnodiging.</p>
      <div class="knoppen">
        ${d.beheerder ? html`<a class="btn btn-primary" href="/${d.viering.slug}/beheer">Naar het beheer</a>` : ''}
        <a class="btn" href="/">Mijn vieringen</a>
      </div></div></div>`)
    return
  }
  if (code === 'geen_viering') {
    zet(root, html`<div class="pagina smal"><div class="card leeg">
      <span class="icoon-rond">${icoon('info', 22)}</span>
      <h1 class="sectie-titel">Deze viering bestaat niet (meer)</h1>
      <p>Misschien is de link veranderd. Kijk bij je vieringen.</p>
      <a class="btn btn-primary" href="/">Mijn vieringen</a></div></div>`)
    return
  }
  if (code === 'module_uit') {
    zet(root, html`<div class="pagina smal"><div class="card leeg">
      <span class="icoon-rond">${icoon('info', 22)}</span>
      <h1 class="sectie-titel">${d.fout}</h1>
      <a class="btn btn-primary" href="/${staat.context}">Naar het overzicht</a></div></div>`)
    return
  }
  zet(root, html`<div class="pagina smal"><div class="card leeg">
    <span class="icoon-rond">${icoon('info', 22)}</span>
    <h1 class="sectie-titel">Dat lukte niet</h1><p>${fout.message}</p>
    <button class="btn" type="button" data-opnieuw>Opnieuw proberen</button></div></div>`)
  $('[data-opnieuw]', root).addEventListener('click', () => render())
}

// ------------------------------------------------------------------ render

function zoekRoute(pad) {
  for (const [patroon, pagina, params, opties = {}] of ROUTES) {
    const m = pad.match(patroon)
    if (m) return { pagina, params: params(m), opties }
  }
  return null
}

export async function render() {
  const mijnBeurt = ++renderTeller
  const pad = location.pathname.replace(/\/+$/, '') || '/'
  const route = zoekRoute(pad)
  if (huidigeOpruim) {
    try {
      huidigeOpruim()
    } catch {
      /* niets */
    }
    huidigeOpruim = null
  }
  sluitSheet()
  const app = $('#app')

  if (!route) {
    zetThema('standaard')
    staat.context = null
    if (staat.sessie?.gebruiker) tekenSchil()
    const plek = $('#inhoud') || app
    zet(plek, html`<div class="pagina smal"><div class="card leeg"><span class="icoon-rond">${icoon('info', 22)}</span>
      <h1 class="sectie-titel">Deze pagina bestaat niet</h1><a class="btn btn-primary" href="/">Naar het begin</a></div></div>`)
    return
  }

  if (route.opties.publiek) {
    staat.context = null
    schilSleutel = ''
    zetThema('standaard')
    meldingen.sluitPaneel()
    const mod = await PAGINAS[route.pagina]()
    if (mijnBeurt !== renderTeller) return
    huidigeOpruim = mod.toon(app, { params: route.params, staat, ga, laadSessie }) || null
    klaar()
    return
  }

  if (!staat.sessie?.gebruiker) {
    ga('/inloggen?terug=' + encodeURIComponent(location.pathname + location.search), { vervang: true })
    return
  }

  staat.context = route.params.slug || null
  const v = viering()
  zetThema(staat.context ? v?.thema || opslag.lees('themas', {})[staat.context] || 'standaard' : 'standaard', staat.context)
  huidigePagina = route.pagina
  tekenSchil()
  markeerActief(route.pagina)
  // Een vers element per pagina, zodat event-handlers van de vorige pagina niet blijven hangen.
  const oudMain = $('#inhoud')
  const main = oudMain.cloneNode(false)
  oudMain.replaceWith(main)
  main.classList.toggle('vol', route.pagina === 'berichten')
  zet(main, html`<div class="laden" aria-label="Laden"></div>`)
  window.scrollTo(0, 0)
  const mod = await PAGINAS[route.pagina]()
  if (mijnBeurt !== renderTeller) return
  huidigeOpruim =
    mod.toon(main, {
      params: route.params,
      staat,
      ga,
      viering: v,
      vieringFout: (fout) => vieringFout(main, fout),
      vernieuwSessie,
    }) || null
  meldingen.paginaGeopend(pad)
  klaar()
}

let splashWeg = false
function klaar() {
  if (splashWeg) return
  splashWeg = true
  const splash = $('#splash')
  if (!splash) return
  const wacht = Math.max(0, 900 - performance.now())
  setTimeout(() => {
    splash.classList.add('klaar')
    setTimeout(() => splash.remove(), 400)
  }, wacht)
}

// ------------------------------------------------------------------ start

async function start() {
  zetModus()
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
    navigator.serviceWorker.addEventListener('message', (e) => {
      if (e.data?.soort === 'push') meldingen.haalNu()
      if (e.data?.soort === 'ga' && e.data.link) ga(e.data.link)
    })
  }
  try {
    await laadSessie()
  } catch (f) {
    zet($('#app'), html`<div class="toegang"><div class="toegang-kaart"><h1>Geen verbinding</h1>
      <p class="intro">${f.message}</p><button class="btn btn-primary" type="button" id="opnieuw">Opnieuw proberen</button></div></div>`)
    $('#opnieuw').addEventListener('click', () => location.reload())
    klaar()
    return
  }
  if (staat.sessie.gebruiker) meldingen.start({ staat, ga, vernieuwSessie })
  await render()
}

/** Na inloggen: sessie laden, meldingen starten en naar de juiste plek. */
export async function naInloggen(terug) {
  await laadSessie()
  meldingen.start({ staat, ga, vernieuwSessie })
  schilSleutel = ''
  const actief = staat.sessie.vieringen.filter((v) => v.status === 'actief')
  let doel = terug && terug.startsWith('/') && !terug.startsWith('//') && !terug.startsWith('/inloggen') ? terug : null
  if (!doel) doel = actief.length === 1 && staat.sessie.vieringen.length === 1 ? `/${actief[0].slug}` : '/'
  ga(doel, { vervang: true })
}

start()
