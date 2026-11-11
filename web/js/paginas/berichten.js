// Anonieme berichten: met je lootje (jij bent anoniem) en met je geheime gever (die is anoniem).
import { $, autoHoogte, avatar, dagLabel, engelAvatar, get, html, icoon, on, post, tijd, toonFout, zet } from '../hulp.js'
import { hoofdletter } from '../themas.js'

export function toon(root, ctx) {
  const slug = ctx.params.slug
  const gekozen = ctx.params.gesprek
  let data = null
  let weg = false
  let teller = null

  async function laad() {
    try {
      data = await get(`/v/${slug}/berichten`)
    } catch (f) {
      if (!weg) ctx.vieringFout(f)
      return
    }
    if (weg) return
    teken()
  }

  function info(soort) {
    const g = data.gesprekken[soort]
    const v = data.viering
    if (soort === 'lootje') {
      const bekend = g && g.geopend
      return {
        titel: bekend ? `Aan ${g.naam}` : 'Aan je lootje',
        sub: bekend ? 'Jij bent anoniem' : 'Open eerst je lootje',
        avatar: bekend ? avatar({ naam: g.naam, toon: g.toon }, 44) : html`<span class="avatar" style="--size:44px">${icoon('cadeau', 20)}</span>`,
        uitleg: bekend ? `${g.naam} ziet niet wie je bent, alleen ‘${v.engel}’. Vraag gerust wat ${g.naam} graag wil hebben.` : '',
      }
    }
    return {
      titel: `Van ${v.engel}`,
      sub: 'Wie zou het zijn?',
      avatar: engelAvatar(44),
      uitleg: `${hoofdletter(v.engel)} heeft jouw lootje. Jij weet niet wie het is, en dat blijft lekker zo tot het feest.`,
    }
  }

  function voorbeeld(g) {
    if (!g || !g.berichten.length) return 'Nog geen berichten'
    const laatste = g.berichten[g.berichten.length - 1]
    return (laatste.mij ? 'Jij: ' : '') + laatste.tekst.split('\n')[0]
  }

  function bubbels(g) {
    let dag = ''
    const uit = []
    for (const b of g.berichten) {
      const d = dagLabel(b.gemaakt)
      if (d !== dag) {
        dag = d
        uit.push(html`<div class="dag">${d}</div>`)
      }
      uit.push(html`<div class="bubbel ${b.mij ? 'mij' : ''}" data-id="${b.id}">${b.tekst}<time datetime="${b.gemaakt}">${tijd(b.gemaakt)}</time></div>`)
    }
    return uit
  }

  function teken() {
    const v = data.viering
    if (data.status !== 'getrokken') {
      root.classList.remove('vol')
      zet(root, html`<div class="pagina smal">
        <header class="kop"><div class="kop-tekst"><p class="eyebrow">${v.naam}</p><h1 class="page-title">Berichten</h1></div></header>
        <div class="card leeg"><span class="icoon-rond">${icoon('anoniem', 22)}</span>
          <p><strong>Nog geen berichten.</strong><br />Na de lootjestrekking kun je hier anoniem berichtjes sturen naar je lootje, en krijg je berichtjes van ${v.engel}.</p></div>
      </div>`)
      return
    }
    const soorten = ['lootje', 'engel'].filter((s) => data.gesprekken[s])
    const actief = gekozen && data.gesprekken[gekozen] ? gekozen : null
    const breed = window.matchMedia('(min-width: 901px)').matches
    const toonDraad = actief || (breed ? soorten[0] : null)
    const g = toonDraad ? data.gesprekken[toonDraad] : null
    const i = toonDraad ? info(toonDraad) : null
    zet(root, html`<div class="chat ${actief ? 'met-draad' : ''}">
      <div class="gesprekken">
        <div class="gesprekken-kop"><h1>Berichten</h1></div>
        ${soorten.length
          ? soorten.map((s) => {
              const x = info(s)
              const gs = data.gesprekken[s]
              return html`<a class="gesprek-link ${s === toonDraad ? 'actief' : ''}" href="/${slug}/berichten/${s}">
                ${x.avatar}
                <span class="midden"><span class="titel">${x.titel}</span><span class="voorbeeld">${voorbeeld(gs)}</span></span>
                ${gs.ongelezen ? html`<span class="badge">${gs.ongelezen}</span>` : ''}
              </a>`
            })
          : html`<p class="muted" style="padding:16px 20px">Je doet niet mee met de lootjes van deze viering.</p>`}
      </div>
      <section class="draad">
        ${g
          ? html`<header class="draad-kop">
              <a class="icon-btn terug" href="/${slug}/berichten" aria-label="Terug">${icoon('chevron-left', 22)}</a>
              ${i.avatar}
              <div class="wie"><h2>${i.titel}</h2><p>${i.sub}</p></div>
            </header>
            <div class="draad-scroll" data-scroll>
              ${i.uitleg ? html`<div class="uitleg-anoniem">${icoon('anoniem', 18)}<span>${i.uitleg}</span></div>` : ''}
              <div class="bubbels" data-bubbels>${bubbels(g)}</div>
            </div>
            ${toonDraad === 'lootje' && !g.geopend
              ? html`<div class="schrijf"><p class="muted" style="flex:1">Open eerst je lootje, dan weet je aan wie je schrijft.</p>
                  <a class="btn btn-feest" href="/${slug}/lootje">${icoon('cadeau', 18)}Open je lootje</a></div>`
              : html`<form class="schrijf" data-schrijf novalidate>
                  <textarea class="input" name="tekst" rows="1" maxlength="2000" placeholder="Schrijf een berichtje…" aria-label="Bericht"></textarea>
                  <button class="btn btn-feest verstuur" type="submit" aria-label="Versturen">${icoon('verstuur', 20)}</button>
                </form>`}`
          : html`<div class="leeg" style="margin:auto"><span class="icoon-rond">${icoon('berichten', 22)}</span><p>Kies een gesprek.</p></div>`}
      </section>
    </div>`)
    if (g) {
      const scroll = $('[data-scroll]', root)
      scroll.scrollTop = scroll.scrollHeight
      const ta = $('textarea', root)
      if (ta) {
        autoHoogte(ta)
        if (breed || actief) ta.focus({ preventScroll: true })
      }
      if (g.ongelezen) {
        post(`/v/${slug}/berichten/gelezen`, { gesprek: toonDraad })
          .then(() => ctx.vernieuwSessie())
          .catch(() => {})
        g.ongelezen = 0
      }
    }
    root.dataset.gesprek = toonDraad || ''
  }

  async function verstuur(form) {
    const ta = form.tekst
    const tekst = ta.value.trim()
    if (!tekst) return
    const gesprek = root.dataset.gesprek
    const knop = $('button[type=submit]', form)
    knop.disabled = true
    try {
      const b = await post(`/v/${slug}/berichten`, { gesprek, tekst })
      data.gesprekken[gesprek].berichten.push(b)
      ta.value = ''
      ta.dispatchEvent(new Event('input'))
      const lijst = $('[data-bubbels]', root)
      zet(lijst, bubbels(data.gesprekken[gesprek]))
      lijst.lastElementChild?.classList.add('nieuw')
      const scroll = $('[data-scroll]', root)
      scroll.scrollTop = scroll.scrollHeight
    } catch (f) {
      toonFout(f)
    } finally {
      knop.disabled = false
      ta.focus()
    }
  }

  on(root, 'submit', '[data-schrijf]', (e) => {
    e.preventDefault()
    verstuur(e.target)
  })
  on(root, 'keydown', '[data-schrijf] textarea', (e, el) => {
    // Enter verstuurt (op een computer), Shift+Enter is een nieuwe regel.
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && window.matchMedia('(pointer: fine)').matches) {
      e.preventDefault()
      verstuur(el.form)
    }
  })

  const vingerafdruk = (d) =>
    d.status + JSON.stringify(['lootje', 'engel'].map((s) => d.gesprekken?.[s]?.berichten.length ?? -1))

  async function ververs() {
    if (!data || data.status !== 'getrokken') return laad()
    let nieuw
    try {
      nieuw = await get(`/v/${slug}/berichten`)
    } catch {
      return
    }
    if (weg || vingerafdruk(nieuw) === vingerafdruk(data)) return
    const ta = $('textarea', root)
    const concept = ta?.value || ''
    const focus = document.activeElement === ta
    data = nieuw
    teken()
    const nieuweTa = $('textarea', root)
    if (nieuweTa && concept) {
      nieuweTa.value = concept
      nieuweTa.dispatchEvent(new Event('input'))
    }
    if (nieuweTa && focus) nieuweTa.focus({ preventScroll: true })
  }

  const opMelding = (e) => {
    if ((e.detail.soort === 'berichten' || e.detail.soort === 'lootje') && e.detail.link?.startsWith(`/${slug}/`)) ververs()
  }
  window.addEventListener('planr:melding', opMelding)
  // Als je in een gesprek zit, iets vaker kijken of er iets nieuws is.
  teller = setInterval(() => {
    if (!document.hidden && root.dataset.gesprek) ververs()
  }, 8000)
  laad()
  return () => {
    weg = true
    clearInterval(teller)
    window.removeEventListener('planr:melding', opMelding)
  }
}
