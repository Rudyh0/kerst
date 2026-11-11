// Het gezamenlijke menu: wie neemt wat mee, en wat drinkt iedereen graag.
import { $, $$, avatar, bevestig, del, formulier, get, html, icoon, metKnop, namenLijst, on, post, put, toast, toonFout, wisFout, zet } from '../hulp.js'
import { thema } from '../themas.js'

export function toon(root, ctx) {
  const slug = ctx.params.slug
  const v = ctx.viering
  let data = null
  let bewerk = null // id van het gerecht dat we aanpassen
  let gang = 'hoofdgerecht'
  let weg = false

  async function laad() {
    try {
      data = await get(`/v/${slug}/menu`)
    } catch (f) {
      if (!weg) ctx.vieringFout(f)
      return
    }
    if (weg) return
    if (!$('.menu-pagina', root)) tekenAlles()
    else tekenLijsten()
  }

  function gangChips() {
    return data.gangen.map(
      (g) => html`<button class="chip" type="button" role="radio" aria-checked="${g.id === gang ? 'true' : 'false'}" data-gang="${g.id}">${g.naam}</button>`,
    )
  }

  function tekenAlles() {
    const t = thema(v?.thema)
    zet(root, html`<div class="pagina menu-pagina">
      <header class="kop"><div class="kop-tekst">
        <p class="eyebrow">${v?.naam || ''}</p>
        <h1 class="page-title">${t.menu}</h1>
        <p class="ondertitel">Wat neemt iedereen mee? Zo voorkomen we vier keer hetzelfde toetje.</p>
      </div></header>
      <div class="twee-kolommen">
        <div class="stapel" style="gap:28px">
          <div class="gangen" data-gangen></div>
          <section class="card blok drank">
            <div class="kaart-kop"><h2>Wat drink je graag?</h2>${icoon('glas', 20)}</div>
            <form class="drank-form" data-drank novalidate>
              <input class="input" name="tekst" placeholder="Bijvoorbeeld: alcoholvrije bubbels" maxlength="60" aria-label="Wat drink je graag?" />
              <button class="btn btn-primary" type="submit">Toevoegen</button>
            </form>
            <p class="error-text" data-drank-fout hidden></p>
            <ul class="drankjes" data-drankjes></ul>
          </section>
        </div>
        <aside>
          <section class="card blok" id="toevoegen">
            <h2 data-form-titel>Wat neem jij mee?</h2>
            <form class="stapel" data-gerecht novalidate>
              <div class="field"><label for="g-naam">Gerecht</label>
                <input class="input" id="g-naam" name="naam" maxlength="80" placeholder="Bijvoorbeeld: zelfgemaakte tiramisu" required /></div>
              <div class="field"><span class="field-label" id="gang-label">Gang</span>
                <div class="chips" role="radiogroup" aria-labelledby="gang-label" data-chips>${gangChips()}</div></div>
              <div class="field"><label for="g-toel">Toelichting <span class="optioneel">(mag leeg)</span></label>
                <input class="input" id="g-toel" name="toelichting" maxlength="200" placeholder="Bijvoorbeeld: vegetarisch, voor 8 personen" /></div>
              <p class="error-text" data-fout hidden></p>
              <div class="knoppen">
                <button class="btn btn-primary btn-lg" type="submit" style="flex:1">Toevoegen</button>
                <button class="btn btn-lg" type="button" data-annuleer hidden>Annuleren</button>
              </div>
            </form>
            <p class="grap">Anders bepaal jij dat eem.</p>
          </section>
        </aside>
      </div>
    </div>`)
    tekenLijsten()
    if (location.hash === '#toevoegen') setTimeout(() => $('#g-naam', root)?.focus(), 50)
  }

  function tekenLijsten() {
    const per = {}
    for (const g of data.gerechten) (per[g.gang] = per[g.gang] || []).push(g)
    const gangen = data.gangen.filter((g) => per[g.id])
    zet($('[data-gangen]', root), gangen.length
      ? gangen.map(
          (g) => html`<section>
            <h2 class="sectie-titel">${g.naam} <span class="aantal">${per[g.id].length}</span></h2>
            <ul class="lijst">${per[g.id].map(
              (r) => html`<li class="gerecht">
                ${avatar(r.van, 36)}
                <div class="midden"><div class="titel">${r.naam}</div>
                  <div class="sub">${r.mijn ? 'Jij neemt dit mee' : `${r.van.naam} neemt dit mee`}${r.toelichting ? ` · ${r.toelichting}` : ''}</div></div>
                ${r.mag
                  ? html`<div class="acties">
                      <button class="icon-btn klein" type="button" data-bewerk="${r.id}" aria-label="${r.naam} aanpassen">${icoon('pencil', 18)}</button>
                      <button class="icon-btn klein" type="button" data-weg="${r.id}" aria-label="${r.naam} weghalen">${icoon('trash', 18)}</button>
                    </div>`
                  : ''}
              </li>`,
            )}</ul></section>`,
        )
      : html`<div class="card leeg"><span class="icoon-rond groen">${icoon('bestek', 22)}</span>
          <p><strong>Nog niets op het menu.</strong><br />Wees de eerste en geef op wat je meeneemt!</p></div>`)
    zet($('[data-drankjes]', root), data.drankjes.length
      ? data.drankjes.map(
          (d) => html`<li>
            <div class="midden"><div class="titel">${d.tekst}</div><div class="sub">${namenLijst(d.wie)}</div></div>
            <button class="ikook" type="button" aria-pressed="${d.ikook ? 'true' : 'false'}" data-ikook="${d.id}">
              ${d.ikook ? icoon('check', 14, 2.2) : icoon('plus', 14, 2.2)}Ik ook${d.stemmen > 1 ? ` · ${d.stemmen}` : ''}</button>
            ${d.mag ? html`<button class="icon-btn klein" type="button" data-drank-weg="${d.id}" aria-label="${d.tekst} weghalen">${icoon('trash', 18)}</button>` : ''}
          </li>`,
        )
      : html`<li class="muted">Nog geen drankjes. Wat drink jij graag?</li>`)
  }

  function zetBewerken(id) {
    const g = data.gerechten.find((x) => x.id === id)
    const form = $('[data-gerecht]', root)
    bewerk = g ? id : null
    gang = g ? g.gang : 'hoofdgerecht'
    form.naam.value = g ? g.naam : ''
    form.toelichting.value = g ? g.toelichting : ''
    zet($('[data-chips]', root), gangChips())
    $('[data-form-titel]', root).textContent = g ? `${g.naam} aanpassen` : 'Wat neem jij mee?'
    $('button[type=submit]', form).textContent = g ? 'Opslaan' : 'Toevoegen'
    $('[data-annuleer]', form).hidden = !g
    wisFout($('[data-fout]', root))
    if (g) {
      $('#toevoegen', root).scrollIntoView({ behavior: 'smooth', block: 'center' })
      form.naam.focus()
    }
  }

  on(root, 'click', '[data-gang]', (e, el) => {
    gang = el.dataset.gang
    $$('[data-gang]', root).forEach((c) => c.setAttribute('aria-checked', c === el ? 'true' : 'false'))
  })
  on(root, 'click', '[data-bewerk]', (e, el) => zetBewerken(Number(el.dataset.bewerk)))
  on(root, 'click', '[data-annuleer]', () => zetBewerken(null))
  on(root, 'click', '[data-weg]', async (e, el) => {
    const g = data.gerechten.find((x) => x.id === Number(el.dataset.weg))
    if (!g || !(await bevestig({ titel: `${g.naam} weghalen?`, tekst: 'De anderen krijgen hier een melding van.', ja: 'Weghalen', gevaar: true }))) return
    try {
      await del(`/v/${slug}/menu/gerechten/${g.id}`)
      if (bewerk === g.id) zetBewerken(null)
      laad()
    } catch (f) {
      toonFout(f)
    }
  })
  on(root, 'submit', '[data-gerecht]', (e) => {
    e.preventDefault()
    const form = e.target
    const fout = $('[data-fout]', root)
    wisFout(fout)
    const velden = { ...formulier(form), gang }
    metKnop($('button[type=submit]', form), async () => {
      try {
        if (bewerk) await put(`/v/${slug}/menu/gerechten/${bewerk}`, velden)
        else await post(`/v/${slug}/menu/gerechten`, velden)
        toast({ titel: bewerk ? 'Aangepast' : 'Op het menu gezet!', tekst: velden.naam, soort: 'goed', duur: 3000 })
        zetBewerken(null)
        await laad()
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
  on(root, 'submit', '[data-drank]', (e) => {
    e.preventDefault()
    const form = e.target
    const fout = $('[data-drank-fout]', root)
    wisFout(fout)
    metKnop($('button[type=submit]', form), async () => {
      try {
        await post(`/v/${slug}/menu/drankjes`, formulier(form))
        form.reset()
        await laad()
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
  on(root, 'click', '[data-ikook]', async (e, el) => {
    el.disabled = true
    try {
      await post(`/v/${slug}/menu/drankjes/${el.dataset.ikook}/ikook`)
      await laad()
    } catch (f) {
      toonFout(f)
      el.disabled = false
    }
  })
  on(root, 'click', '[data-drank-weg]', async (e, el) => {
    try {
      await del(`/v/${slug}/menu/drankjes/${el.dataset.drankWeg}`)
      laad()
    } catch (f) {
      toonFout(f)
    }
  })

  const opMelding = (e) => {
    if (e.detail.soort === 'menu' && e.detail.link === `/${slug}/menu`) laad()
  }
  window.addEventListener('planr:melding', opMelding)
  laad()
  return () => {
    weg = true
    window.removeEventListener('planr:melding', opMelding)
  }
}
