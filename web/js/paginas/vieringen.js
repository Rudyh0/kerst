// Mijn vieringen: het begin na het inloggen.
import { html, icoon, on, post, toast, toonFout, evenementWanneer, zet } from '../hulp.js'
import { aftelKort } from '../onderdelen.js'
import { deeltjes, logoVast, opslagDeeltjes, thema } from '../themas.js'

export function toon(root, ctx) {
  function teken() {
    const s = ctx.staat.sessie
    const g = s.gebruiker
    const lijst = s.vieringen
    const nieuw = lijst.filter((v) => v.status !== 'actief')
    const actief = lijst.filter((v) => v.status === 'actief')
    const kaart = (v) => {
      const t = thema(v.thema)
      const open = v.status !== 'actief'
      return html`<article class="viering-kaart card">
        <a class="viering-held" href="/${v.slug}" style="background:${t.held}" tabindex="-1" aria-hidden="true">
          ${opslagDeeltjes() ? deeltjes(v.thema, { factor: 0.45 }) : ''}
          ${logoVast(v.thema, 44, true)}
          <span class="viering-aftel">${aftelKort(v)}</span>
        </a>
        <div class="blok">
          <div>
            <h2><a class="kaart-link" href="/${v.slug}">${v.naam}</a></h2>
            <p class="muted klein">${evenementWanneer(v) || 'Datum volgt nog'}${v.locatie ? ` · ${v.locatie}` : ''}</p>
          </div>
          <div class="chips">
            ${v.menu ? html`<span class="pill">${icoon('bestek', 14)}Menu</span>` : ''}
            ${v.lootjes ? html`<span class="pill ${v.lootjes_getrokken ? 'pill-groen' : ''}">${icoon('cadeau', 14)}${v.lootjes_getrokken ? 'Lootjes getrokken' : 'Lootjes'}</span>` : ''}
            ${v.berichten_ongelezen ? html`<span class="pill pill-accent">${icoon('berichten', 14)}${v.berichten_ongelezen} nieuw</span>` : ''}
          </div>
          ${open
            ? html`<div class="knoppen"><button class="btn btn-feest" type="button" data-aannemen="${v.slug}">Doe mee</button>
                <span class="muted klein">Je bent uitgenodigd</span></div>`
            : ''}
        </div>
      </article>`
    }
    zet(root, html`<div class="pagina">
      <header class="kop">
        <div class="kop-tekst"><p class="eyebrow">${s.app_naam}</p><h1 class="page-title">Hoi ${g.naam}!</h1>
          <p class="ondertitel">${lijst.length ? 'Dit zijn de feesten waar je bij hoort.' : 'Je doet nog nergens aan mee.'}</p></div>
        ${g.beheerder ? html`<a class="btn btn-primary" href="/beheer/nieuw">${icoon('plus', 18)}Nieuwe viering</a>` : ''}
      </header>
      ${nieuw.length ? html`<h2 class="sectie-titel">Uitnodigingen <span class="aantal">${nieuw.length}</span></h2>
        <div class="vieringen-raster" style="margin-bottom:32px">${nieuw.map(kaart)}</div>` : ''}
      ${actief.length ? html`${nieuw.length ? html`<h2 class="sectie-titel">Mijn vieringen</h2>` : ''}
        <div class="vieringen-raster">${actief.map(kaart)}</div>` : ''}
      ${!lijst.length
        ? html`<div class="card leeg"><span class="icoon-rond">${icoon('kalender', 22)}</span>
            <p>Zodra iemand je uitnodigt, zie je de viering hier.</p>
            ${g.beheerder ? html`<a class="btn btn-primary" href="/beheer/nieuw">Maak je eerste viering</a>` : ''}</div>`
        : ''}
    </div>`)
  }

  on(root, 'click', '[data-aannemen]', async (e, el) => {
    el.disabled = true
    try {
      await post(`/v/${el.dataset.aannemen}/aannemen`)
      await ctx.vernieuwSessie()
      toast({ titel: 'Leuk dat je meedoet!', soort: 'goed' })
      ctx.ga(`/${el.dataset.aannemen}`)
    } catch (f) {
      toonFout(f)
      el.disabled = false
    }
  })

  teken()
  ctx.vernieuwSessie().then(() => {
    if (root.isConnected) teken()
  })
}
