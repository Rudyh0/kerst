// Het dashboard van een viering: countdown, wanneer en waar, spelregels, lootje, menu en wie er meedoen.
import { $, avatar, get, html, icoon, opslag, zet } from '../hulp.js'
import { aftelHeld, spelregelsKaart, startAftellen, wanneerWaarKaart } from '../onderdelen.js'
import { thema } from '../themas.js'
import { isApp, isIOS, pushAan, pushOndersteund, pushStatus } from '../meldingen.js'

export function toon(root, ctx) {
  const slug = ctx.params.slug
  let stopAftellen = () => {}
  let weg = false

  async function laad() {
    let d
    try {
      d = await get(`/v/${slug}`)
    } catch (f) {
      if (!weg) ctx.vieringFout(f)
      return
    }
    if (weg) return
    teken(d)
  }

  function lootjeTegel(d) {
    const l = d.lootje
    const v = d.viering
    let inhoud
    if (l.status === 'getrokken' && l.geopend) {
      inhoud = html`<div class="tegel-rij">${avatar({ naam: l.naam, toon: l.toon }, 44)}<div><p class="groot">${l.naam}</p>
        <p class="muted">Bekijk het verlanglijstje en stuur een anoniem berichtje.</p></div></div>`
    } else if (l.status === 'getrokken') {
      inhoud = html`<p class="groot">Je lootje ligt klaar!</p><p class="muted">Open het en ontdek wie je hebt getrokken.</p>
        <span class="btn btn-feest btn-sm" style="align-self:flex-start">Open je lootje</span>`
    } else if (l.status === 'doet_niet_mee') {
      inhoud = html`<p class="muted">Je doet niet mee met de lootjes van deze viering.</p>`
    } else {
      inhoud = html`<p class="groot">Nog niet getrokken</p><p class="muted">Je krijgt een melding zodra de lootjes getrokken zijn.</p>`
    }
    return html`<a class="card tegel" href="/${v.slug}/lootje">
      <div class="tegel-kop"><span class="icoon-rond">${icoon('cadeau', 20)}</span><h2>Jouw lootje</h2>
        ${d.berichten_ongelezen ? html`<span class="badge" title="Ongelezen berichten">${d.berichten_ongelezen}</span>` : ''}
        <span class="pijl">${icoon('chevron-right', 18)}</span></div>
      ${inhoud}
    </a>`
  }

  function verlanglijstTegel(d) {
    const v = d.viering
    return html`<a class="card tegel" href="/${v.slug}/verlanglijst">
      <div class="tegel-kop"><span class="icoon-rond goud">${icoon('lijst', 20)}</span><h2>Mijn verlanglijstje</h2><span class="pijl">${icoon('chevron-right', 18)}</span></div>
      ${d.wensen
        ? html`<p class="groot">${d.wensen} ${d.wensen === 1 ? 'wens' : 'wensen'}</p><p class="muted">Alleen wie jouw lootje trekt, ziet dit lijstje.</p>`
        : html`<p class="groot">Nog leeg</p><p class="muted">Zet erop wat je graag wilt hebben. Dat maakt het makkelijk voor ${v.engel}.</p>`}
    </a>`
  }

  function menuTegel(d) {
    const v = d.viering
    const m = d.menu
    return html`<a class="card tegel" href="/${v.slug}/menu">
      <div class="tegel-kop"><span class="icoon-rond groen">${icoon('bestek', 20)}</span><h2>${thema(v.thema).menu}</h2><span class="pijl">${icoon('chevron-right', 18)}</span></div>
      ${m.mijn_gerechten.length
        ? html`<p class="muted">Jij neemt mee:</p><p class="groot klein-groot">${m.mijn_gerechten.map((g) => g.naam).join(', ')}</p>`
        : html`<p class="groot">Wat neem jij mee?</p><p class="muted">Geef op wat je maakt, dan voorkomen we dubbele toetjes.</p>`}
      <p class="muted klein">${m.gerechten} ${m.gerechten === 1 ? 'gerecht' : 'gerechten'} en ${m.drankjes} ${m.drankjes === 1 ? 'drankje' : 'drankjes'} op het menu</p>
    </a>`
  }

  async function pushBanner() {
    if (opslag.lees('pushbanner-weg', false)) return ''
    if (!pushOndersteund()) {
      if (isIOS() && !isApp()) {
        return html`<div class="banner" data-banner>
          <span class="icoon-rond">${icoon('telefoon', 20)}</span>
          <div class="tekst"><strong>Meldingen op je iPhone?</strong>
            <p>Tik op Deel en kies 'Zet op beginscherm'. Open plan-r daarna vanaf je beginscherm en zet meldingen aan.</p></div>
          <button class="icon-btn" type="button" data-banner-weg aria-label="Sluiten">${icoon('close', 18)}</button>
        </div>`
      }
      return ''
    }
    const st = await pushStatus().catch(() => 'niet')
    if (st !== 'uit') return ''
    return html`<div class="banner" data-banner>
      <span class="icoon-rond">${icoon('bel', 20)}</span>
      <div class="tekst"><strong>Mis niets</strong><p>Krijg een melding op je telefoon of computer zodra er iets nieuws is, ook als de app dicht is.</p></div>
      <div class="knoppen"><button class="btn btn-primary btn-sm" type="button" data-push-aan>Meldingen aanzetten</button>
      <button class="icon-btn" type="button" data-banner-weg aria-label="Sluiten">${icoon('close', 18)}</button></div>
    </div>`
  }

  async function teken(d) {
    const v = d.viering
    const ik = ctx.staat.sessie.gebruiker
    const banner = await pushBanner()
    if (weg) return
    const tegels = []
    if (v.lootjes) tegels.push(lootjeTegel(d), verlanglijstTegel(d))
    if (v.menu) tegels.push(menuTegel(d))
    const actief = d.deelnemers.filter((p) => p.status === 'actief')
    const wachtend = d.deelnemers.filter((p) => p.status !== 'actief')
    zet(root, html`<div class="pagina">
      ${aftelHeld(v, { groet: `Hoi ${ik.naam}!` })}
      ${banner}
      <div class="raster">
        ${wanneerWaarKaart(v)}
        ${v.lootjes ? spelregelsKaart(v) : ''}
        ${tegels}
        <section class="card blok breed">
          <div class="tegel-kop"><span class="icoon-rond">${icoon('users', 20)}</span><h2>Wie doen er mee</h2>
            <span class="pill">${actief.length}${wachtend.length ? ` van ${d.deelnemers.length}` : ''}</span></div>
          <div class="mensen-raster">
            ${d.deelnemers.map(
              (p) => html`<div class="mens">${avatar(p, 36)}<span class="wie">${p.naam}${p.ik ? ' (jij)' : ''}</span>
                ${p.status !== 'actief' ? html`<span class="pill">Uitgenodigd</span>` : ''}</div>`,
            )}
          </div>
        </section>
      </div>
    </div>`)
    stopAftellen()
    stopAftellen = startAftellen(root, v)
    $('[data-banner-weg]', root)?.addEventListener('click', () => {
      opslag.zet('pushbanner-weg', true)
      $('[data-banner]', root)?.remove()
    })
    $('[data-push-aan]', root)?.addEventListener('click', async (e) => {
      e.currentTarget.disabled = true
      try {
        await pushAan()
        $('[data-banner]', root)?.remove()
      } catch (f) {
        const { toast } = await import('../hulp.js')
        toast({ titel: 'Meldingen staan nog uit', tekst: f.message, soort: 'fout' })
        e.currentTarget.disabled = false
      }
    })
  }

  const opMelding = (e) => {
    const m = e.detail
    if (['lootje', 'algemeen', 'deelnemers', 'berichten'].includes(m.soort) && m.link?.startsWith(`/${slug}`)) laad()
  }
  window.addEventListener('planr:melding', opMelding)
  laad()
  return () => {
    weg = true
    stopAftellen()
    window.removeEventListener('planr:melding', opMelding)
  }
}
