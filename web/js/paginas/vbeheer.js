// Beheer van één viering: deelnemers, lootjes en instellingen.
import { $, ApiFout, api, avatar, bevestig, del, get, html, icoon, metKnop, on, post, put, tijdGeleden, toast, toonFout, wisFout, zet } from '../hulp.js'
import { thema, zetThema } from '../themas.js'
import { vieringFormulier } from '../vieringformulier.js'

export function toon(root, ctx) {
  const slug = ctx.params.slug
  const tab = ctx.params.tab
  let data = null
  let weg = false

  async function laad() {
    try {
      data = await get(`/beheer/v/${slug}`)
    } catch (f) {
      if (weg) return
      if (f instanceof ApiFout && f.data.code === 'geen_beheerder') {
        zet(root, html`<div class="pagina smal"><div class="card leeg"><span class="icoon-rond">${icoon('lock', 22)}</span>
          <p>Dit is alleen voor de organisator.</p><a class="btn" href="/${slug}">Terug</a></div></div>`)
        return
      }
      ctx.vieringFout(f)
      return
    }
    if (weg) return
    zetThema(data.viering.thema, slug)
    teken()
  }

  function teken() {
    const v = data.viering
    const tabs = [['deelnemers', 'Deelnemers', 'users']]
    if (v.lootjes) tabs.push(['lootjes', 'Lootjes', 'cadeau'])
    tabs.push(['instellingen', 'Instellingen', 'instellingen'])
    zet(root, html`<div class="pagina">
      <header class="kop">
        <div class="kop-tekst"><p class="eyebrow">Beheer · ${thema(v.thema).emoji} ${thema(v.thema).naam}</p><h1 class="page-title">${v.naam}</h1>
          <p class="ondertitel"><a class="link" href="/${v.slug}">${location.host}/${v.slug}</a></p></div>
        <div class="knoppen">
          <button class="btn" type="button" data-kopieer>${icoon('link', 18)}Link kopiëren</button>
          ${data.ik_doe_mee ? html`<a class="btn" href="/${v.slug}">Naar de viering</a>` : ''}
        </div>
      </header>
      <nav class="segmented tab-balk" aria-label="Onderdelen">
        ${tabs.map(([id, t, i]) => html`<a href="/${v.slug}/beheer/${id}" ${id === tab ? html`aria-current="page"` : ''}>${icoon(i, 18)}${t}</a>`)}
      </nav>
      <div data-tab></div>
    </div>`)
    const plek = $('[data-tab]', root)
    if (tab === 'lootjes' && v.lootjes) lootjes(plek)
    else if (tab === 'instellingen') instellingen(plek)
    else deelnemers(plek)
  }

  // ---------------------------------------------------------------- deelnemers

  function deelnemers(plek) {
    const v = data.viering
    const ds = data.deelnemers
    const actief = ds.filter((d) => d.status === 'actief').length
    zet(plek, html`<div class="twee-kolommen aside-onder">
      <section>
        <h2 class="sectie-titel">Deelnemers <span class="aantal">${actief} van ${ds.length} doen mee</span></h2>
        ${ds.length
          ? html`<ul class="lijst deelnemers">${ds.map(
              (d) => html`<li>
                ${avatar(d, 40)}
                <div class="midden">
                  <div class="titel">${d.naam}${d.ik ? ' (jij)' : ''}
                    ${d.status === 'actief' ? html`<span class="pill pill-groen">Doet mee</span>` : html`<span class="pill">Uitgenodigd</span>`}
                    ${d.beheerder ? html`<span class="pill">Beheerder</span>` : ''}</div>
                  <div class="sub">${d.email}${d.status === 'actief'
                    ? d.laatst_gezien ? ` · ${tijdGeleden(d.laatst_gezien)} gezien` : ''
                    : d.uitgenodigd_op ? ` · uitgenodigd ${tijdGeleden(d.uitgenodigd_op)}` : ''}</div>
                </div>
                ${v.lootjes
                  ? html`<label class="lootjes-schakel" title="Doet mee met lootjes trekken">
                      <span>Lootjes</span><span class="schakelaar"><input type="checkbox" data-mee="${d.id}" ${d.doet_mee ? 'checked' : ''} /><span></span></span></label>`
                  : ''}
                <details class="menu">
                  <summary class="icon-btn klein" aria-label="Meer">${icoon('more', 18)}</summary>
                  <div class="menu-lijst">
                    ${d.status !== 'actief' ? html`<button type="button" data-opnieuw="${d.id}">${icoon('mail', 18)}Uitnodiging opnieuw sturen</button>` : ''}
                    ${d.ik ? '' : html`<button type="button" class="gevaar" data-verwijder="${d.id}">${icoon('trash', 18)}Uit deze viering halen</button>`}
                    ${d.ik && d.status === 'actief' ? html`<span class="muted klein" style="padding:8px 10px">Dit ben jij</span>` : ''}
                  </div>
                </details>
              </li>`,
            )}</ul>`
          : html`<div class="card leeg"><span class="icoon-rond">${icoon('users', 22)}</span><p>Nog niemand uitgenodigd.</p></div>`}
        ${data.ik_doe_mee ? '' : html`<div class="banner" style="margin-top:16px"><span class="icoon-rond">${icoon('info', 20)}</span>
          <div class="tekst"><strong>Je doet zelf niet mee</strong><p>Wil je ook een lootje en een verlanglijstje? Doe dan zelf mee.</p></div>
          <button class="btn btn-primary btn-sm" type="button" data-zelf>Zelf meedoen</button></div>`}
      </section>
      <aside>
        <section class="card blok">
          <h2>Mensen uitnodigen</h2>
          <form class="stapel" data-uitnodigen novalidate>
            <div class="field"><label for="adressen">E-mailadressen</label>
              <textarea class="input" id="adressen" name="tekst" rows="6" placeholder="anna@voorbeeld.nl&#10;Bert <bert@voorbeeld.nl>&#10;Cees, cees@voorbeeld.nl"></textarea>
              <span class="hint">Eén per regel. Een naam erbij mag. Wie al een account heeft, doet met één klik mee.</span></div>
            <p class="error-text" data-fout hidden></p>
            <p class="goed-text" data-goed hidden></p>
            <button class="btn btn-primary btn-lg" type="submit">${icoon('mail', 18)}Uitnodigingen versturen</button>
          </form>
        </section>
      </aside>
    </div>`)
  }

  // ---------------------------------------------------------------- lootjes

  function lootjes(plek) {
    const l = data.lootjes
    const v = data.viering
    const procent = l.mee ? Math.round((l.mee_actief / l.mee) * 100) : 0
    let inhoud
    if (!l.actief) {
      const iedereen = l.mee > 0 && l.mee === l.mee_actief
      const genoeg = l.mee_actief >= l.minimum
      inhoud = html`<section class="card blok">
        <div class="tegel-kop"><span class="icoon-rond">${icoon('cadeau', 20)}</span><h2>Nog niet getrokken</h2></div>
        <div class="stand"><div class="balk"><span style="width:${procent}%"></span></div><strong class="tabular">${l.mee_actief} / ${l.mee}</strong></div>
        <p class="muted">${l.mee_actief} van de ${l.mee} deelnemers aan de lootjes hebben zich aangemeld.</p>
        ${l.wachten_op.length ? html`<p class="klein">Nog niet aangemeld: <strong>${l.wachten_op.join(', ')}</strong></p>` : ''}
        ${!genoeg ? html`<p class="hint">Er zijn minstens ${l.minimum} aangemelde deelnemers nodig.</p>` : ''}
        <div class="knoppen">
          <button class="btn btn-feest btn-lg" type="button" data-trek ${iedereen && genoeg ? '' : 'disabled'}>${icoon('cadeau', 20)}Lootjes trekken</button>
          ${!iedereen && genoeg ? html`<button class="btn btn-lg" type="button" data-trek-actief>Trek met wie er al is (${l.mee_actief})</button>` : ''}
        </div>
        <p class="hint">Iedereen krijgt een mail en een melding. Niemand trekt zichzelf. Ook jij als beheerder ziet niet wie wie heeft.</p>
      </section>`
    } else {
      inhoud = html`<section class="card blok">
        <div class="tegel-kop"><span class="icoon-rond groen">${icoon('check', 20)}</span><h2>De lootjes zijn getrokken</h2></div>
        <p class="muted">Getrokken ${tijdGeleden(l.getrokken_op)} met ${l.in_trekking} deelnemers.</p>
        <div class="stand"><div class="balk"><span style="width:${l.in_trekking ? Math.round((l.geopend / l.in_trekking) * 100) : 0}%"></span></div>
          <strong class="tabular">${l.geopend} / ${l.in_trekking}</strong></div>
        <p class="muted">${l.geopend} van de ${l.in_trekking} hebben hun lootje al bekeken.</p>
        <div class="knoppen">
          <button class="btn" type="button" data-opnieuw-trekken>${icoon('refresh', 18)}Opnieuw trekken</button>
          <button class="btn btn-danger" type="button" data-ongedaan>Trekking ongedaan maken</button>
        </div>
        <p class="hint">Opnieuw trekken geeft iedereen (misschien) een ander lootje. Berichtjes en afgevinkte cadeaus van de vorige trekking zijn dan niet meer te zien.</p>
      </section>`
    }
    zet(plek, html`<div class="pagina smal" style="margin:0">${inhoud}
      ${v.budget || v.regels.length || v.gedicht || v.surprise ? '' : html`<p class="hint" style="margin-top:12px">Tip: zet een maximale prijs en spelregels bij <a class="link" href="/${v.slug}/beheer/instellingen">Instellingen</a>.</p>`}
    </div>`)
  }

  async function trek(opties, knop) {
    await metKnop(knop, async () => {
      try {
        const r = await post(`/beheer/v/${slug}/lootjes`, { actie: 'trekken', ...opties })
        toast({ titel: 'De lootjes zijn getrokken!', tekst: `${r.deelnemers} deelnemers krijgen nu een melding.`, soort: 'goed' })
        await ctx.vernieuwSessie()
        laad()
      } catch (f) {
        toonFout(f)
      }
    })
  }

  // ---------------------------------------------------------------- instellingen

  function instellingen(plek) {
    const v = data.viering
    zet(plek, html`<div data-formulier></div>
      <section class="card blok gevaar-zone">
        <h2>Viering verwijderen</h2>
        <p class="muted">Alles van deze viering verdwijnt: het menu, de verlanglijstjes, de lootjes en de berichten. Dit kun je niet terugdraaien.</p>
        <form class="knoppen" data-verwijder-viering novalidate>
          <input class="input" name="bevestig" placeholder="Typ ${v.slug} ter bevestiging" autocomplete="off" style="max-width:280px" />
          <button class="btn btn-danger" type="submit">${icoon('trash', 18)}Verwijderen</button>
        </form>
      </section>`)
    vieringFormulier($('[data-formulier]', plek), v, {
      knopTekst: 'Opslaan',
      onOpslaan: (velden, knop, fout) =>
        metKnop(knop, async () => {
          wisFout(fout)
          try {
            const r = await put(`/beheer/v/${slug}`, velden)
            toast({ titel: 'Opgeslagen', tekst: r.gewijzigd && velden.melden ? 'Iedereen krijgt een melding van de wijzigingen.' : '', soort: 'goed', duur: 3000 })
            await ctx.vernieuwSessie()
            if (r.slug !== slug) ctx.ga(`/${r.slug}/beheer/instellingen`, { vervang: true })
            else laad()
          } catch (f) {
            toonFout(f, fout)
          }
        }),
    })
  }

  // ---------------------------------------------------------------- acties

  on(root, 'click', '[data-kopieer]', async () => {
    const url = `${location.origin}/${slug}`
    try {
      await navigator.clipboard.writeText(url)
      toast({ titel: 'Link gekopieerd', tekst: url, soort: 'goed', duur: 3000 })
    } catch {
      toast({ titel: 'De link', tekst: url })
    }
  })
  on(root, 'submit', '[data-uitnodigen]', (e) => {
    e.preventDefault()
    const form = e.target
    const fout = $('[data-fout]', form)
    const goed = $('[data-goed]', form)
    wisFout(fout)
    goed.hidden = true
    metKnop($('button[type=submit]', form), async () => {
      try {
        const r = await post(`/beheer/v/${slug}/uitnodigen`, { tekst: form.tekst.value })
        const delen = []
        if (r.toegevoegd.length) delen.push(`${r.toegevoegd.length} uitgenodigd`)
        if (r.bestond.length) delen.push(`${r.bestond.length} deed al mee`)
        if (r.ongeldig.length) delen.push(`niet herkend: ${r.ongeldig.join(', ')}`)
        form.tekst.value = r.ongeldig.join('\n')
        await laad()
        toast({ titel: r.toegevoegd.length ? 'Uitnodigingen verstuurd' : 'Niemand nieuw uitgenodigd', tekst: delen.join(' · '), soort: r.toegevoegd.length ? 'goed' : 'info' })
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
  on(root, 'change', '[data-mee]', async (e, el) => {
    try {
      await put(`/beheer/v/${slug}/deelnemers/${el.dataset.mee}`, { doet_mee: el.checked })
      const d = data.deelnemers.find((x) => x.id === Number(el.dataset.mee))
      if (d) d.doet_mee = el.checked
      if (data.lootjes.actief) toast({ titel: 'Aangepast', tekst: 'Dit geldt pas bij de volgende trekking.', duur: 4000 })
    } catch (f) {
      el.checked = !el.checked
      toonFout(f)
    }
  })
  on(root, 'click', '[data-opnieuw]', async (e, el) => {
    el.closest('details')?.removeAttribute('open')
    try {
      await post(`/beheer/v/${slug}/deelnemers/${el.dataset.opnieuw}/uitnodigen`)
      toast({ titel: 'Uitnodiging opnieuw verstuurd', soort: 'goed', duur: 3000 })
      laad()
    } catch (f) {
      toonFout(f)
    }
  })
  on(root, 'click', '[data-verwijder]', async (e, el) => {
    el.closest('details')?.removeAttribute('open')
    const d = data.deelnemers.find((x) => x.id === Number(el.dataset.verwijder))
    if (!d || !(await bevestig({ titel: `${d.naam} uit ${data.viering.naam} halen?`, tekst: 'Het account blijft bestaan voor andere vieringen.', ja: 'Weghalen', gevaar: true }))) return
    try {
      await del(`/beheer/v/${slug}/deelnemers/${d.id}`)
      laad()
    } catch (f) {
      toonFout(f)
    }
  })
  on(root, 'click', '[data-zelf]', async (e, el) => {
    await metKnop(el, async () => {
      try {
        await post(`/beheer/v/${slug}/ikdoemee`)
        await ctx.vernieuwSessie()
        laad()
      } catch (f) {
        toonFout(f)
      }
    })
  })
  on(root, 'click', '[data-trek]', (e, el) => trek({}, el))
  on(root, 'click', '[data-trek-actief]', async (e, el) => {
    const l = data.lootjes
    if (!(await bevestig({ titel: 'Trekken zonder iedereen?', tekst: `${l.wachten_op.join(', ')} ${l.wachten_op.length === 1 ? 'doet' : 'doen'} dan niet mee met de lootjes.`, ja: 'Toch trekken' }))) return
    trek({ alleen_actief: true }, el)
  })
  on(root, 'click', '[data-opnieuw-trekken]', async (e, el) => {
    if (!(await bevestig({ titel: 'Opnieuw trekken?', tekst: 'Iedereen krijgt (misschien) een ander lootje en een nieuwe melding. Berichtjes en afgevinkte cadeaus van deze trekking zijn daarna niet meer te zien.', ja: 'Opnieuw trekken', gevaar: true }))) return
    trek({ opnieuw: true, alleen_actief: true }, el)
  })
  on(root, 'click', '[data-ongedaan]', async (e, el) => {
    if (!(await bevestig({ titel: 'Trekking ongedaan maken?', tekst: 'Niemand heeft dan nog een lootje. Iedereen krijgt hier een melding van.', ja: 'Ongedaan maken', gevaar: true }))) return
    await metKnop(el, async () => {
      try {
        await post(`/beheer/v/${slug}/lootjes`, { actie: 'ongedaan' })
        await ctx.vernieuwSessie()
        laad()
      } catch (f) {
        toonFout(f)
      }
    })
  })
  on(root, 'submit', '[data-verwijder-viering]', async (e) => {
    e.preventDefault()
    const form = e.target
    if (form.bevestig.value.trim() !== slug) {
      toast({ titel: 'Typ de link ter bevestiging', tekst: slug, soort: 'fout' })
      return
    }
    if (!(await bevestig({ titel: `${data.viering.naam} verwijderen?`, tekst: 'Dit kun je niet terugdraaien.', ja: 'Definitief verwijderen', gevaar: true }))) return
    try {
      await api('DELETE', `/beheer/v/${slug}`, { bevestig: slug })
      await ctx.vernieuwSessie()
      toast({ titel: 'Viering verwijderd', soort: 'goed' })
      ctx.ga('/beheer', { vervang: true })
    } catch (f) {
      toonFout(f)
    }
  })

  laad()
  return () => {
    weg = true
  }
}
