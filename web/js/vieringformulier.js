// Formulier voor een viering: gebruikt bij 'Nieuwe viering' en bij de instellingen van een viering.
import { $, $$, get, html, icoon, on, vertraag, zet } from './hulp.js'
import { THEMAS, logoVast, zetThema } from './themas.js'

const KEUZES = [
  ['', 'Niet noemen'],
  ['wel', 'Wel'],
  ['geen', 'Geen'],
  ['mag', 'Mag'],
]

function schakelKaart(naam, titel, uitleg, ikoon, aan) {
  return html`<label class="module-kaart">
    <span class="icoon-rond">${icoon(ikoon, 20)}</span>
    <span class="tekst"><strong>${titel}</strong><span class="muted klein">${uitleg}</span></span>
    <span class="schakelaar"><input type="checkbox" name="${naam}" ${aan ? 'checked' : ''} /><span></span></span>
  </label>`
}

function keuzeRij(naam, label, waarde) {
  return html`<div class="field"><span class="field-label">${label}</span>
    <div class="segmented" role="radiogroup" aria-label="${label}">
      ${KEUZES.map(([w, t]) => html`<button type="button" role="radio" data-keuze="${naam}" data-waarde="${w}" aria-pressed="${w === (waarde || '') ? 'true' : 'false'}">${t}</button>`)}
    </div></div>`
}

/**
 * Tekent het formulier in `plek`.
 * v: bestaande viering (of null voor een nieuwe). opties: { nieuw, onOpslaan(data, knop, fout) , knopTekst }
 */
export function vieringFormulier(plek, v, { nieuw = false, knopTekst = 'Opslaan', onOpslaan }) {
  const w = v || { naam: '', slug: '', thema: 'kerst', datum: '', tijd: '', locatie: '', welkomst: '', budget: '', gedicht: '', surprise: '', regels_tekst: '', menu: true, lootjes: true }
  const keuzes = { gedicht: w.gedicht || '', surprise: w.surprise || '' }
  let slugAangeraakt = !nieuw
  const host = location.host

  zet(plek, html`<form class="viering-form stapel" novalidate>
    <section class="card blok">
      <h2>Over de viering</h2>
      <div class="raster-velden">
        <div class="field breed"><label for="vf-naam">Naam</label>
          <input class="input" id="vf-naam" name="naam" value="${w.naam}" maxlength="60" placeholder="Bijvoorbeeld: Kerst met de familie" required /></div>
        <div class="field breed"><label for="vf-slug">Eigen link</label>
          <div class="link-veld"><span class="voorvoegsel">${host}/</span>
            <input class="input" id="vf-slug" name="slug" value="${w.slug}" maxlength="40" autocapitalize="off" autocomplete="off" spellcheck="false" placeholder="familie" required /></div>
          <span class="hint" data-slug-status>Kleine letters, cijfers en streepjes. Deze link deel je met de deelnemers.</span></div>
        <div class="field"><label for="vf-datum">Datum</label><input class="input" id="vf-datum" name="datum" type="date" value="${w.datum}" /></div>
        <div class="field"><label for="vf-tijd">Tijd <span class="optioneel">(mag leeg)</span></label><input class="input" id="vf-tijd" name="tijd" type="time" value="${w.tijd}" /></div>
        <div class="field breed"><label for="vf-locatie">Locatie</label>
          <input class="input" id="vf-locatie" name="locatie" value="${w.locatie}" maxlength="200" placeholder="Adres of plek, bijvoorbeeld: Dorpsstraat 1, Utrecht" /></div>
        <div class="field breed"><label for="vf-welkomst">Welkomstbericht <span class="optioneel">(mag leeg)</span></label>
          <textarea class="input" id="vf-welkomst" name="welkomst" maxlength="800" rows="3" placeholder="Bijvoorbeeld: Neem je beste kersttrui mee!">${w.welkomst}</textarea></div>
      </div>
    </section>

    <section class="card blok">
      <h2>Thema</h2>
      <p class="muted klein">Het thema bepaalt de kleuren, het logo en de animaties voor iedereen in deze viering.</p>
      <div class="themas" role="radiogroup" aria-label="Thema">
        ${Object.entries(THEMAS).map(
          ([id, t]) => html`<button type="button" class="thema-keuze" role="radio" data-thema="${id}" aria-pressed="${id === w.thema ? 'true' : 'false'}">
            <span class="thema-voorbeeld" style="background:${t.held}">${logoVast(id, 34, true)}</span>
            <span class="thema-naam">${t.emoji} ${t.naam}</span>
            <span class="muted klein">${t.omschrijving}</span>
          </button>`,
        )}
      </div>
    </section>

    <section class="card blok">
      <h2>Onderdelen</h2>
      <p class="muted klein">Kies wat er in deze viering zit. Je kunt dit later nog aanpassen.</p>
      <div class="modules">
        ${schakelKaart('menu', 'Menu', 'Iedereen geeft op wat hij of zij meeneemt, en wat ze graag drinken.', 'bestek', w.menu)}
        ${schakelKaart('lootjes', 'Lootjes en verlanglijstjes', 'Lootjes trekken, verlanglijstjes maken en anoniem berichtjes sturen.', 'cadeau', w.lootjes)}
      </div>
    </section>

    <section class="card blok" data-regels ${w.lootjes ? '' : 'hidden'}>
      <h2>Spelregels voor de cadeaus</h2>
      <p class="muted klein">Iedereen ziet deze regels bij het lootje en het verlanglijstje.</p>
      <div class="raster-velden">
        <div class="field"><label for="vf-budget">Maximale prijs</label>
          <input class="input" id="vf-budget" name="budget" value="${w.budget}" maxlength="40" placeholder="Bijvoorbeeld: 25" /></div>
        <div></div>
        ${keuzeRij('gedicht', 'Gedicht', keuzes.gedicht)}
        ${keuzeRij('surprise', 'Surprise', keuzes.surprise)}
        <div class="field breed"><label for="vf-regels">Eigen regels <span class="optioneel">(één per regel)</span></label>
          <textarea class="input" id="vf-regels" name="regels" maxlength="2000" rows="4" placeholder="Bijvoorbeeld:&#10;Inpakken in kerstpapier&#10;Geen cadeaubonnen">${w.regels_tekst || ''}</textarea></div>
      </div>
    </section>

    <div class="opslaan-balk">
      ${nieuw
        ? html`<label class="vinkregel"><input type="checkbox" name="ik_doe_mee" checked />Ik doe zelf ook mee</label>`
        : html`<label class="vinkregel"><input type="checkbox" name="melden" />Stuur iedereen een melding van de wijzigingen</label>`}
      <p class="error-text" data-fout hidden></p>
      <button class="btn btn-primary btn-lg" type="submit">${knopTekst}</button>
    </div>
  </form>`)

  const form = $('form', plek)
  const slugVeld = form.slug
  const status = $('[data-slug-status]', plek)
  let gekozenThema = w.thema

  const controleer = vertraag(async () => {
    const slug = slugVeld.value.trim().toLowerCase()
    if (!slug) {
      status.className = 'hint'
      status.textContent = 'Kleine letters, cijfers en streepjes. Deze link deel je met de deelnemers.'
      return
    }
    try {
      const r = await get(`/beheer/link?slug=${encodeURIComponent(slug)}${v ? `&behalve=${v.id}` : ''}`)
      if (slugVeld.value.trim().toLowerCase() !== slug) return
      status.className = r.vrij ? 'goed-text' : 'error-text'
      status.textContent = r.vrij ? `${host}/${slug} is vrij` : r.probleem
    } catch {
      /* stil */
    }
  }, 350)

  function maakSlug(tekst) {
    return tekst
      .normalize('NFKD')
      .replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40)
      .replace(/-+$/, '')
  }

  form.naam.addEventListener('input', () => {
    if (slugAangeraakt) return
    slugVeld.value = maakSlug(form.naam.value)
    controleer()
  })
  slugVeld.addEventListener('input', () => {
    slugAangeraakt = true
    const schoon = slugVeld.value.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-{2,}/g, '-')
    if (schoon !== slugVeld.value) slugVeld.value = schoon
    controleer()
  })
  if (v) controleer()

  on(plek, 'click', '[data-thema]', (e, el) => {
    gekozenThema = el.dataset.thema
    $$('[data-thema]', plek).forEach((b) => b.setAttribute('aria-pressed', b === el ? 'true' : 'false'))
    zetThema(gekozenThema) // meteen zien hoe het eruitziet
  })
  on(plek, 'click', '[data-keuze]', (e, el) => {
    keuzes[el.dataset.keuze] = el.dataset.waarde
    $$(`[data-keuze="${el.dataset.keuze}"]`, plek).forEach((b) => b.setAttribute('aria-pressed', b === el ? 'true' : 'false'))
  })
  form.lootjes.addEventListener('change', () => {
    $('[data-regels]', plek).hidden = !form.lootjes.checked
  })
  form.addEventListener('submit', (e) => {
    e.preventDefault()
    const data = {
      naam: form.naam.value.trim(),
      slug: slugVeld.value.trim().toLowerCase(),
      thema: gekozenThema,
      datum: form.datum.value,
      tijd: form.tijd.value,
      locatie: form.locatie.value.trim(),
      welkomst: form.welkomst.value.trim(),
      menu: form.menu.checked,
      lootjes: form.lootjes.checked,
      budget: form.budget.value.trim(),
      gedicht: keuzes.gedicht,
      surprise: keuzes.surprise,
      regels: form.regels.value,
    }
    if (nieuw) data.ik_doe_mee = form.ik_doe_mee.checked
    else data.melden = form.melden.checked
    onOpslaan(data, $('button[type=submit]', form), $('[data-fout]', form))
  })
}
