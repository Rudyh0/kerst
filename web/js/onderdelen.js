// Onderdelen die op meerdere pagina's terugkomen: de countdown, spelregels en 'wanneer & waar'.
import { evenementWanneer, html, icoon } from './hulp.js'
import { deeltjes, logoVast, opslagDeeltjes, thema } from './themas.js'

/** Het moment van de viering als Date (zonder tijd: begin van de dag), of null. */
export function moment(v) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v?.datum || '')) return null
  const [j, m, d] = v.datum.split('-').map(Number)
  const [u, min] = /^\d{2}:\d{2}$/.test(v.tijd || '') ? v.tijd.split(':').map(Number) : [0, 0]
  return new Date(j, m - 1, d, u, min)
}

function stand(v) {
  const doel = moment(v)
  if (!doel) return { soort: 'geen' }
  const nu = new Date()
  const ms = doel - nu
  const zelfdeDag = doel.toDateString() === nu.toDateString()
  if (ms <= 0) {
    if (zelfdeDag || nu - doel < 12 * 3600 * 1000) return { soort: 'nu' }
    return { soort: 'geweest' }
  }
  const s = Math.floor(ms / 1000)
  return { soort: 'telt', dagen: Math.floor(s / 86400), uren: Math.floor((s % 86400) / 3600), minuten: Math.floor((s % 3600) / 60), seconden: s % 60 }
}

const twee = (n) => String(n).padStart(2, '0')

function aftelInhoud(v) {
  const st = stand(v)
  if (st.soort === 'geen') return html`<p class="aftel-tekst">De datum volgt nog.</p>`
  if (st.soort === 'nu') return html`<p class="aftel-tekst groot">Het is zover! ${thema(v.thema).emoji}</p>`
  if (st.soort === 'geweest') return html`<p class="aftel-tekst">Dit feest is geweest. Het was gezellig!</p>`
  const blok = (getal, enkel, meer, cls = '') => html`<div class="tel ${cls}"><b>${getal}</b><span>${getal === 1 || getal === '01' ? enkel : meer}</span></div>`
  return html`<div class="tellers" role="timer" aria-label="Nog ${st.dagen} dagen, ${st.uren} uur en ${st.minuten} minuten">
    ${blok(st.dagen, 'dag', 'dagen')}
    ${blok(twee(st.uren), 'uur', 'uur')}
    ${blok(twee(st.minuten), 'minuut', 'minuten')}
    ${blok(twee(st.seconden), 'seconde', 'seconden', 'sec')}
  </div>`
}

/** De grote kop van het dashboard met countdown. */
export function aftelHeld(v, { groet = '' } = {}) {
  const wanneer = evenementWanneer(v)
  return html`<section class="held" aria-label="${v.naam}">
    ${opslagDeeltjes() ? deeltjes(v.thema) : ''}
    <div class="held-binnen">
      <div class="held-kop">
        <span class="held-logo">${logoVast(v.thema, 40, true)}</span>
        <div class="held-titels">
          ${groet ? html`<p class="held-groet">${groet}</p>` : ''}
          <h1>${v.naam}</h1>
          ${wanneer || v.locatie ? html`<p class="held-sub">${[wanneer, v.locatie].filter(Boolean).join(' · ')}</p>` : ''}
        </div>
      </div>
      <div class="aftel" data-aftel>${aftelInhoud(v)}</div>
    </div>
  </section>`
}

/** Laat de countdown tikken. Geeft een functie terug om te stoppen. */
export function startAftellen(root, v) {
  const plek = root.querySelector('[data-aftel]')
  if (!plek || !moment(v)) return () => {}
  const tik = () => {
    const st = stand(v)
    if (st.soort !== 'telt') {
      plek.innerHTML = aftelInhoud(v).toString()
      return
    }
    const getallen = plek.querySelectorAll('.tel b')
    if (getallen.length !== 4) {
      plek.innerHTML = aftelInhoud(v).toString()
      return
    }
    const waarden = [st.dagen, twee(st.uren), twee(st.minuten), twee(st.seconden)]
    getallen.forEach((b, i) => {
      if (b.textContent !== String(waarden[i])) b.textContent = waarden[i]
    })
  }
  const t = setInterval(tik, 1000)
  return () => clearInterval(t)
}

/** Korte tekst voor in lijsten: 'nog 12 dagen', 'vandaag!', 'geweest'. */
export function aftelKort(v) {
  const st = stand(v)
  if (st.soort === 'geen') return 'datum volgt'
  if (st.soort === 'nu') return 'vandaag!'
  if (st.soort === 'geweest') return 'geweest'
  if (st.dagen === 0) return st.uren ? `nog ${st.uren} uur` : 'bijna!'
  return st.dagen === 1 ? 'morgen!' : `nog ${st.dagen} dagen`
}

const KEUZE = {
  gedicht: { wel: 'Met een gedicht', geen: 'Geen gedicht', mag: 'Gedicht mag, hoeft niet' },
  surprise: { wel: 'Met een surprise', geen: 'Geen surprise', mag: 'Surprise mag, hoeft niet' },
}

/** De spelregels van een viering als lijstje [{icoon, tekst, nadruk}]. */
export function regels(v) {
  const uit = []
  if (v.budget) uit.push({ icoon: 'label', tekst: `Maximaal ${v.budget}`, nadruk: true })
  if (v.gedicht && KEUZE.gedicht[v.gedicht]) uit.push({ icoon: 'pencil', tekst: KEUZE.gedicht[v.gedicht], nadruk: v.gedicht === 'wel' })
  if (v.surprise && KEUZE.surprise[v.surprise]) uit.push({ icoon: 'cadeau', tekst: KEUZE.surprise[v.surprise], nadruk: v.surprise === 'wel' })
  for (const r of v.regels || []) uit.push({ icoon: 'check', tekst: r })
  return uit
}

export function spelregelsKaart(v, { titel = 'Spelregels' } = {}) {
  const lijst = regels(v)
  if (!lijst.length) return ''
  return html`<section class="card blok spelregels">
    <div class="tegel-kop"><span class="icoon-rond goud">${icoon('ster', 20)}</span><h2>${titel}</h2></div>
    <ul class="regels">${lijst.map((r) => html`<li class="${r.nadruk ? 'nadruk' : ''}">${icoon(r.icoon, 18)}<span>${r.tekst}</span></li>`)}</ul>
  </section>`
}

export function spelregelsPills(v) {
  const lijst = regels(v).filter((r) => r.icoon !== 'check')
  return lijst.map((r) => html`<span class="pill ${r.nadruk ? 'pill-goud' : ''}">${icoon(r.icoon, 14)}${r.tekst}</span>`)
}

export function routeLink(locatie) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(locatie)}`
}

export function wanneerWaarKaart(v) {
  const wanneer = evenementWanneer(v)
  return html`<section class="card blok">
    <div class="tegel-kop"><span class="icoon-rond">${icoon('kalender', 20)}</span><h2>Wanneer en waar</h2></div>
    <div class="feiten">
      <div class="feit">${icoon('kalender', 18)}<span><strong>${wanneer || 'Datum volgt nog'}</strong></span></div>
      ${v.locatie
        ? html`<div class="feit">${icoon('pin', 18)}<span><strong>${v.locatie}</strong>
            <a class="link klein" href="${routeLink(v.locatie)}" target="_blank" rel="noopener noreferrer">Route plannen</a></span></div>`
        : ''}
    </div>
    ${v.welkomst ? html`<p class="welkomst">${v.welkomst}</p>` : ''}
  </section>`
}
