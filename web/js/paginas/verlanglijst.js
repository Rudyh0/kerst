// Mijn eigen verlanglijstje binnen een viering.
import { $, bevestig, del, formulier, get, html, icoon, korteLink, metKnop, on, post, put, toast, toonFout, veiligeLink, wisFout, zet } from '../hulp.js'
import { spelregelsKaart } from '../onderdelen.js'

export function toon(root, ctx) {
  const slug = ctx.params.slug
  let data = null
  let bewerk = null
  let weg = false

  async function laad() {
    try {
      data = await get(`/v/${slug}/verlanglijst`)
    } catch (f) {
      if (!weg) ctx.vieringFout(f)
      return
    }
    if (weg) return
    if (!$('.wens-pagina', root)) tekenAlles()
    else tekenLijst()
  }

  function tekenAlles() {
    const v = data.viering
    zet(root, html`<div class="pagina wens-pagina">
      <header class="kop"><div class="kop-tekst">
        <p class="eyebrow">Voor ${v.engel}</p>
        <h1 class="page-title">Mijn verlanglijstje</h1>
        <p class="ondertitel">Wie jouw lootje trekt, ziet dit lijstje en krijgt een melding als je iets verandert. Verder ziet niemand het.</p>
      </div></header>
      <div class="twee-kolommen">
        <section>
          <h2 class="sectie-titel">Mijn wensen <span class="aantal" data-aantal></span></h2>
          <ul class="lijst wensen" data-lijst></ul>
        </section>
        <aside>
          <section class="card blok" id="toevoegen">
            <h2 data-form-titel>Wens toevoegen</h2>
            <form class="stapel" novalidate>
              <div class="field"><label for="w-titel">Wat wil je graag?</label>
                <input class="input" id="w-titel" name="titel" maxlength="100" placeholder="Bijvoorbeeld: een goed boek" required /></div>
              <div class="field"><label for="w-toel">Toelichting <span class="optioneel">(mag leeg)</span></label>
                <textarea class="input" id="w-toel" name="toelichting" maxlength="500" rows="3" placeholder="Maat, kleur, welke winkel..."></textarea></div>
              <div class="field"><label for="w-link">Link <span class="optioneel">(mag leeg)</span></label>
                <input class="input" id="w-link" name="link" inputmode="url" maxlength="600" placeholder="https://..." /></div>
              <div class="field"><label for="w-prijs">Prijs ongeveer <span class="optioneel">(mag leeg)</span></label>
                <input class="input" id="w-prijs" name="prijs" maxlength="30" placeholder="${v.budget ? `Maximaal ${v.budget}` : 'Bijvoorbeeld: € 20'}" /></div>
              <p class="error-text" data-fout hidden></p>
              <div class="knoppen">
                <button class="btn btn-primary btn-lg" type="submit" style="flex:1">Toevoegen</button>
                <button class="btn btn-lg" type="button" data-annuleer hidden>Annuleren</button>
              </div>
            </form>
          </section>
          ${spelregelsKaart(v, { titel: 'Spelregels voor de cadeaus' })}
        </aside>
      </div>
    </div>`)
    tekenLijst()
    if (location.hash === '#toevoegen') setTimeout(() => $('#w-titel', root)?.focus(), 50)
  }

  function tekenLijst() {
    $('[data-aantal]', root).textContent = data.wensen.length || ''
    zet($('[data-lijst]', root), data.wensen.length
      ? data.wensen.map((w, i) => {
          const link = veiligeLink(w.link)
          return html`<li class="wens">
            <span class="nummer">${i + 1}</span>
            <div class="midden">
              <div class="titel">${w.titel}</div>
              ${w.toelichting ? html`<div class="toelichting">${w.toelichting}</div>` : ''}
              ${link || w.prijs
                ? html`<div class="extra">
                    ${w.prijs ? html`<span class="pill">${icoon('label', 14)}${w.prijs}</span>` : ''}
                    ${link ? html`<a class="link" href="${link}" target="_blank" rel="noopener noreferrer">${icoon('link', 14)}${korteLink(link)}</a>` : ''}
                  </div>`
                : ''}
            </div>
            <div class="acties">
              <button class="icon-btn klein" type="button" data-omhoog="${w.id}" aria-label="Hoger" ${i === 0 ? 'disabled' : ''}>${icoon('chevron-up', 18)}</button>
              <button class="icon-btn klein" type="button" data-omlaag="${w.id}" aria-label="Lager" ${i === data.wensen.length - 1 ? 'disabled' : ''}>${icoon('chevron-down', 18)}</button>
              <details class="menu">
                <summary class="icon-btn klein" aria-label="Meer">${icoon('more', 18)}</summary>
                <div class="menu-lijst">
                  <button type="button" data-bewerk="${w.id}">${icoon('pencil', 18)}Aanpassen</button>
                  <button type="button" class="gevaar" data-weg="${w.id}">${icoon('trash', 18)}Weghalen</button>
                </div>
              </details>
            </div>
          </li>`
        })
      : html`<li class="leeg-rij"><div class="leeg"><span class="icoon-rond goud">${icoon('ster', 22)}</span>
          <p><strong>Je lijstje is nog leeg.</strong><br />Zet erop wat je graag wilt hebben. Een link erbij helpt ${data.viering.engel} enorm.</p></div></li>`)
  }

  function zetBewerken(id) {
    const w = data.wensen.find((x) => x.id === id)
    const form = $('form', root)
    bewerk = w ? id : null
    form.titel.value = w ? w.titel : ''
    form.toelichting.value = w ? w.toelichting : ''
    form.link.value = w ? w.link : ''
    form.prijs.value = w ? w.prijs : ''
    $('[data-form-titel]', root).textContent = w ? 'Wens aanpassen' : 'Wens toevoegen'
    $('button[type=submit]', form).textContent = w ? 'Opslaan' : 'Toevoegen'
    $('[data-annuleer]', form).hidden = !w
    wisFout($('[data-fout]', root))
    if (w) {
      $('#toevoegen', root).scrollIntoView({ behavior: 'smooth', block: 'center' })
      form.titel.focus()
    }
  }

  async function verplaats(id, richting) {
    const ids = data.wensen.map((w) => w.id)
    const i = ids.indexOf(id)
    const j = i + richting
    if (j < 0 || j >= ids.length) return
    ;[ids[i], ids[j]] = [ids[j], ids[i]]
    data.wensen = ids.map((x) => data.wensen.find((w) => w.id === x))
    tekenLijst()
    try {
      await post(`/v/${slug}/verlanglijst/volgorde`, { ids })
    } catch (f) {
      toonFout(f)
      laad()
    }
  }

  on(root, 'submit', 'form', (e) => {
    e.preventDefault()
    const form = e.target
    const fout = $('[data-fout]', root)
    wisFout(fout)
    const velden = formulier(form)
    metKnop($('button[type=submit]', form), async () => {
      try {
        if (bewerk) await put(`/v/${slug}/verlanglijst/${bewerk}`, velden)
        else await post(`/v/${slug}/verlanglijst`, velden)
        if (!bewerk) toast({ titel: 'Op je lijstje gezet', tekst: velden.titel, soort: 'goed', duur: 3000 })
        zetBewerken(null)
        await laad()
        $('#w-titel', root)?.focus()
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
  on(root, 'click', '[data-annuleer]', () => zetBewerken(null))
  on(root, 'click', '[data-bewerk]', (e, el) => {
    el.closest('details')?.removeAttribute('open')
    zetBewerken(Number(el.dataset.bewerk))
  })
  on(root, 'click', '[data-omhoog]', (e, el) => verplaats(Number(el.dataset.omhoog), -1))
  on(root, 'click', '[data-omlaag]', (e, el) => verplaats(Number(el.dataset.omlaag), 1))
  on(root, 'click', '[data-weg]', async (e, el) => {
    el.closest('details')?.removeAttribute('open')
    const w = data.wensen.find((x) => x.id === Number(el.dataset.weg))
    if (!w || !(await bevestig({ titel: `${w.titel} weghalen?`, ja: 'Weghalen', gevaar: true }))) return
    try {
      await del(`/v/${slug}/verlanglijst/${w.id}`)
      if (bewerk === w.id) zetBewerken(null)
      laad()
    } catch (f) {
      toonFout(f)
    }
  })

  laad()
  return () => {
    weg = true
  }
}
