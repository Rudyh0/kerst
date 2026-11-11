// Mijn lootje: openen, het verlanglijstje van de ander, privé afvinken en notities.
import { $, avatar, get, html, icoon, korteLink, on, post, put, toonFout, vertraag, veiligeLink, zet } from '../hulp.js'
import { spelregelsKaart, spelregelsPills } from '../onderdelen.js'
import { deeltjes, hoofdletter, opslagDeeltjes, thema } from '../themas.js'

const CONFETTI = {
  standaard: ['#3b5bdb', '#5f3dc4', '#f2bf5e', '#69db7c'],
  kerst: ['#c22d35', '#1d6a48', '#f2c14e', '#ffffff'],
  sinterklaas: ['#b0182a', '#e6be5a', '#ffffff', '#a0612b'],
  zomer: ['#0c8599', '#f59f00', '#ff8a5c', '#3bc9db'],
  halloween: ['#ff8a3d', '#7048e8', '#2b8a3e', '#1b1520'],
}

function confetti(themaId) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const kleuren = CONFETTI[themaId] || CONFETTI.standaard
  const laag = document.createElement('div')
  laag.className = 'confetti'
  laag.setAttribute('aria-hidden', 'true')
  let s = ''
  for (let i = 0; i < 90; i++) {
    const k = kleuren[i % kleuren.length]
    s += `<i style="--x:${Math.random() * 100}%;--s:${6 + Math.random() * 8}px;--k:${k};--d:${2.2 + Math.random() * 2}s;--w:${Math.random() * 0.6}s;--z:${(Math.random() - 0.5) * 240}px;--r:${(Math.random() - 0.5) * 1080}deg"></i>`
  }
  laag.innerHTML = s
  document.body.append(laag)
  setTimeout(() => laag.remove(), 5200)
}

export function toon(root, ctx) {
  const slug = ctx.params.slug
  let data = null
  let weg = false
  let vuil = false

  async function laad() {
    try {
      data = await get(`/v/${slug}/lootje`)
    } catch (f) {
      if (!weg) ctx.vieringFout(f)
      return
    }
    if (weg) return
    teken()
  }

  function teken(onthul = false) {
    const v = data.viering
    const t = thema(v.thema)
    if (data.status === 'niet_getrokken') {
      zet(root, html`<div class="pagina smal">
        <header class="kop"><div class="kop-tekst"><p class="eyebrow">${v.naam}</p><h1 class="page-title">Mijn lootje</h1></div></header>
        <div class="lootje-dicht wachten">
          ${opslagDeeltjes() ? deeltjes(v.thema, { factor: 0.7 }) : ''}
          <div class="envelop stil"></div>
          <h2>Nog even geduld…</h2>
          <p>De lootjes zijn nog niet getrokken. Je krijgt een melding zodra het zover is.</p>
          <a class="btn btn-lg" href="/${v.slug}/verlanglijst">Maak alvast je verlanglijstje</a>
        </div>
        <div style="margin-top:20px">${spelregelsKaart(v)}</div>
      </div>`)
      return
    }
    if (data.status === 'doet_niet_mee') {
      zet(root, html`<div class="pagina smal">
        <header class="kop"><div class="kop-tekst"><p class="eyebrow">${v.naam}</p><h1 class="page-title">Mijn lootje</h1></div></header>
        <div class="card leeg"><span class="icoon-rond">${icoon('info', 22)}</span>
          <p>Je doet niet mee met de lootjes van deze viering. Klopt dat niet? Vraag de organisator om opnieuw te trekken.</p></div>
      </div>`)
      return
    }
    if (!data.geopend) {
      zet(root, html`<div class="pagina smal">
        <header class="kop"><div class="kop-tekst"><p class="eyebrow">${v.naam}</p><h1 class="page-title">Mijn lootje</h1></div></header>
        <div class="lootje-dicht" data-dicht>
          ${opslagDeeltjes() ? deeltjes(v.thema) : ''}
          <div class="envelop"></div>
          <h2>Je hebt een lootje getrokken!</h2>
          <p>Wie zou het zijn? Zorg dat niemand meekijkt…</p>
          <button class="btn btn-lg" type="button" data-open>${icoon('cadeau', 20)}Open je lootje</button>
        </div>
      </div>`)
      return
    }
    const o = data.ontvanger
    const gehaald = data.wensen.filter((w) => w.afgevinkt).length
    zet(root, html`<div class="pagina">
      <header class="kop">
        <div class="kop-tekst">
          <p class="eyebrow">${v.naam} · jouw lootje</p>
          <div class="onthulling ${onthul ? 'onthul-animatie' : ''}">
            ${avatar(o, 72)}
            <div><h1 class="page-title">${o.naam}</h1>
              <p class="ondertitel">Houd het geheim! ${o.naam} weet niet dat jij dit lootje hebt.</p></div>
          </div>
          <div class="chips" style="margin-top:6px">${spelregelsPills(v)}</div>
        </div>
      </header>
      <div class="twee-kolommen aside-onder">
        <section>
          <h2 class="sectie-titel">Verlanglijstje van ${o.naam}
            ${data.wensen.length ? html`<span class="aantal">${gehaald} van ${data.wensen.length} gehaald</span>` : ''}</h2>
          ${data.wensen.length
            ? html`<p class="hint" style="margin:-4px 0 12px">Vink af wat je hebt gekocht. Alleen jij ziet dat.</p>
              <ul class="lijst wensen">${data.wensen.map((w) => {
                const link = veiligeLink(w.link)
                return html`<li class="wens ${w.afgevinkt ? 'gehaald' : ''}">
                  <label class="vink"><input type="checkbox" data-vink="${w.id}" ${w.afgevinkt ? 'checked' : ''} aria-label="${w.titel} gehaald" /><span>${icoon('check', 16, 2.4)}</span></label>
                  <div class="midden">
                    <div class="titel">${w.titel}</div>
                    ${w.toelichting ? html`<div class="toelichting">${w.toelichting}</div>` : ''}
                    ${link || w.prijs
                      ? html`<div class="extra">${w.prijs ? html`<span class="pill">${icoon('label', 14)}${w.prijs}</span>` : ''}
                        ${link ? html`<a class="link" href="${link}" target="_blank" rel="noopener noreferrer">${icoon('link', 14)}${korteLink(link)}</a>` : ''}</div>`
                      : ''}
                  </div>
                </li>`
              })}</ul>`
            : html`<div class="card leeg"><span class="icoon-rond goud">${icoon('lijst', 22)}</span>
                <p><strong>${o.naam} heeft nog niets op het lijstje gezet.</strong><br />
                Stuur een anoniem berichtje om te vragen wat ${o.naam} graag wil. Je krijgt een melding zodra het lijstje verandert.</p></div>`}
        </section>
        <aside>
          <a class="card tegel" href="/${v.slug}/berichten/lootje">
            <div class="tegel-kop"><span class="icoon-rond">${icoon('anoniem', 20)}</span><h2>Anoniem berichtje</h2>
              ${data.ongelezen ? html`<span class="badge">${data.ongelezen}</span>` : ''}<span class="pijl">${icoon('chevron-right', 18)}</span></div>
            <p class="muted">Vraag ${o.naam} iets zonder dat ${o.naam} weet wie je bent. ${hoofdletter(o.naam)} ziet alleen ‘${t.engel}’.</p>
          </a>
          <section class="card blok notities">
            <div class="kaart-kop"><h2>Mijn notities</h2>${icoon('lock', 18)}</div>
            <textarea class="input" data-notities maxlength="3000" placeholder="Ideeën, waar je wat koopt, wat het kostte… Alleen jij ziet dit.">${data.notities}</textarea>
            <span class="opgeslagen" data-opgeslagen></span>
          </section>
          ${spelregelsKaart(v)}
        </aside>
      </div>
    </div>`)
  }

  const bewaarNotities = vertraag(async (tekst) => {
    const plek = $('[data-opgeslagen]', root)
    try {
      await put(`/v/${slug}/lootje/notities`, { tekst })
      vuil = false
      if (plek) plek.textContent = 'Opgeslagen'
    } catch (f) {
      if (plek) plek.textContent = f.message
    }
  }, 700)

  on(root, 'input', '[data-notities]', (e, el) => {
    const plek = $('[data-opgeslagen]', root)
    if (plek) plek.textContent = 'Bezig met opslaan…'
    data.notities = el.value
    vuil = true
    bewaarNotities(el.value)
  })

  on(root, 'click', '[data-open]', async (e, el) => {
    el.disabled = true
    $('[data-dicht]', root)?.classList.add('open')
    try {
      await post(`/v/${slug}/lootje/open`)
    } catch (f) {
      toonFout(f)
      el.disabled = false
      return
    }
    setTimeout(() => {
      if (weg) return
      data.geopend = true
      teken(true)
      confetti(data.viering.thema)
    }, 650)
  })

  on(root, 'change', '[data-vink]', async (e, el) => {
    const id = Number(el.dataset.vink)
    const w = data.wensen.find((x) => x.id === id)
    w.afgevinkt = el.checked
    el.closest('.wens').classList.toggle('gehaald', el.checked)
    try {
      await put(`/v/${slug}/lootje/vinkje/${id}`, { afgevinkt: el.checked })
      const gehaald = data.wensen.filter((x) => x.afgevinkt).length
      const aantal = $('.sectie-titel .aantal', root)
      if (aantal) aantal.textContent = `${gehaald} van ${data.wensen.length} gehaald`
    } catch (f) {
      toonFout(f)
      el.checked = !el.checked
      w.afgevinkt = el.checked
    }
  })

  const opMelding = (e) => {
    const m = e.detail
    if ((m.soort === 'wensen' || m.soort === 'lootje') && m.link === `/${slug}/lootje`) {
      // Niet midden in het typen van notities alles opnieuw tekenen.
      if (document.activeElement?.matches('[data-notities]')) return
      laad()
    }
  }
  window.addEventListener('planr:melding', opMelding)
  laad()
  return () => {
    weg = true
    if (vuil) bewaarNotities.nu(data.notities)
    window.removeEventListener('planr:melding', opMelding)
  }
}
