// Algemeen beheer: vieringen, een nieuwe viering, e-mail en accounts.
import { $, ApiFout, avatar, bevestig, del, evenementWanneer, formulier, get, html, icoon, metKnop, on, post, put, tijdGeleden, toast, toonFout, wisFout, zet } from '../hulp.js'
import { aftelKort } from '../onderdelen.js'
import { logoVast, thema } from '../themas.js'
import { vieringFormulier } from '../vieringformulier.js'

const TABS = [
  ['vieringen', 'Vieringen', 'kalender'],
  ['email', 'E-mail', 'mail'],
  ['accounts', 'Accounts', 'users'],
]

const STATUS = { wacht: 'Wacht', bezig: 'Bezig', verstuurd: 'Verstuurd', mislukt: 'Mislukt' }

export function toon(root, ctx) {
  const tab = ctx.params.tab
  let data = null
  let weg = false

  async function laad() {
    try {
      data = await get('/beheer')
    } catch (f) {
      if (weg) return
      zet(root, html`<div class="pagina smal"><div class="card leeg"><span class="icoon-rond">${icoon('lock', 22)}</span>
        <p>${f instanceof ApiFout && f.status === 403 ? 'Dit is alleen voor de organisator.' : f.message}</p></div></div>`)
      return
    }
    if (weg) return
    teken()
  }

  function teken() {
    zet(root, html`<div class="pagina">
      <header class="kop">
        <div class="kop-tekst"><p class="eyebrow">Beheer</p><h1 class="page-title">${tab === 'nieuw' ? 'Nieuwe viering' : 'Organiseren'}</h1></div>
        ${tab !== 'nieuw' ? html`<a class="btn btn-primary" href="/beheer/nieuw">${icoon('plus', 18)}Nieuwe viering</a>` : ''}
      </header>
      ${tab === 'nieuw'
        ? html`<a class="link" href="/beheer" style="margin:-24px 0 16px">${icoon('chevron-left', 16)}Terug naar het beheer</a>`
        : html`<nav class="segmented tab-balk" aria-label="Onderdelen">
            ${TABS.map(([id, t, i]) => html`<a href="/beheer/${id}" ${id === tab ? html`aria-current="page"` : ''}>${icoon(i, 18)}${t}</a>`)}
          </nav>`}
      <div data-tab></div>
    </div>`)
    const plek = $('[data-tab]', root)
    if (tab === 'nieuw') nieuw(plek)
    else if (tab === 'email') email(plek)
    else if (tab === 'accounts') accounts(plek)
    else vieringen(plek)
  }

  // ---------------------------------------------------------------- vieringen

  function vieringen(plek) {
    zet(plek, data.vieringen.length
      ? html`<ul class="lijst viering-lijst">${data.vieringen.map(
          (v) => html`<li>
            <span class="mini-held" style="background:${thema(v.thema).held}">${logoVast(v.thema, 26, true)}</span>
            <div class="midden">
              <div class="titel">${v.naam}</div>
              <div class="sub">/${v.slug} · ${evenementWanneer(v) || 'geen datum'} · ${aftelKort(v)}</div>
              <div class="chips" style="margin-top:6px">
                <span class="pill">${icoon('users', 14)}${v.actief} van ${v.deelnemers}</span>
                ${v.menu ? html`<span class="pill">${icoon('bestek', 14)}Menu</span>` : ''}
                ${v.lootjes ? html`<span class="pill ${v.lootjes_getrokken ? 'pill-groen' : ''}">${icoon('cadeau', 14)}${v.lootjes_getrokken ? 'Getrokken' : 'Lootjes'}</span>` : ''}
              </div>
            </div>
            <div class="acties">
              <a class="btn btn-sm" href="/${v.slug}/beheer">Beheren</a>
            </div>
          </li>`,
        )}</ul>`
      : html`<div class="card leeg"><span class="icoon-rond">${icoon('kalender', 22)}</span>
          <p><strong>Nog geen vieringen.</strong><br />Maak je eerste viering: kies een naam, een eigen link en een thema.</p>
          <a class="btn btn-primary" href="/beheer/nieuw">${icoon('plus', 18)}Nieuwe viering</a></div>`)
  }

  function nieuw(plek) {
    vieringFormulier(plek, null, {
      nieuw: true,
      knopTekst: 'Viering aanmaken',
      onOpslaan: (velden, knop, fout) =>
        metKnop(knop, async () => {
          wisFout(fout)
          try {
            const r = await post('/beheer/vieringen', velden)
            await ctx.vernieuwSessie()
            toast({ titel: 'Viering aangemaakt!', tekst: 'Nodig nu de deelnemers uit.', soort: 'goed' })
            ctx.ga(`/${r.slug}/beheer/deelnemers`)
          } catch (f) {
            toonFout(f, fout)
          }
        }),
    })
  }

  // ---------------------------------------------------------------- e-mail

  function email(plek) {
    const s = data.smtp
    const m = data.mail
    zet(plek, html`<div class="secties">
      <section class="card blok">
        <h2>Algemeen</h2>
        <form class="knoppen" data-app novalidate>
          <div class="field" style="flex:1;min-width:220px"><label for="app_naam">Naam van de app</label>
            <input class="input" id="app_naam" name="app_naam" value="${data.app_naam}" maxlength="40" /></div>
          <button class="btn" type="submit" style="align-self:flex-end">Opslaan</button>
        </form>
      </section>
      <section class="card blok">
        <h2>Mailserver</h2>
        <p class="muted klein">Hiermee verstuurt de app uitnodigingen en meldingen. Het wachtwoord wordt alleen op de server bewaard.</p>
        <form class="stapel" data-smtp novalidate>
          <div class="raster-velden">
            <div class="field"><label for="afzender_naam">Afzendernaam</label>
              <input class="input" id="afzender_naam" name="afzender_naam" value="${s.afzender_naam}" maxlength="80" placeholder="plan-r" /></div>
            <div class="field"><label for="afzender_adres">Afzenderadres</label>
              <input class="input" id="afzender_adres" name="afzender_adres" type="email" value="${s.afzender_adres}" placeholder="kerst@voorbeeld.nl" /></div>
            <div class="field"><label for="host">SMTP-server</label>
              <input class="input" id="host" name="host" value="${s.host}" placeholder="mail.voorbeeld.nl" autocapitalize="off" spellcheck="false" /></div>
            <div class="field"><label for="poort">Poort</label>
              <input class="input" id="poort" name="poort" inputmode="numeric" value="${s.poort}" placeholder="587" /></div>
            <div class="field"><label for="beveiliging">Beveiliging</label>
              <select class="input" id="beveiliging" name="beveiliging">
                ${[['starttls', 'STARTTLS (meestal poort 587)'], ['ssl', 'SSL/TLS (meestal poort 465)'], ['geen', 'Geen (niet aanbevolen)']].map(
                  ([w, t]) => html`<option value="${w}" ${s.beveiliging === w ? 'selected' : ''}>${t}</option>`,
                )}
              </select></div>
            <div class="field"><label for="gebruiker">Gebruikersnaam</label>
              <input class="input" id="gebruiker" name="gebruiker" value="${s.gebruiker}" autocomplete="off" autocapitalize="off" spellcheck="false" /></div>
            <div class="field breed"><label for="wachtwoord">Wachtwoord</label>
              <input class="input" id="wachtwoord" name="wachtwoord" type="password" autocomplete="new-password"
                placeholder="${s.wachtwoord_gezet ? '•••••••• (ingesteld, leeg laten om te houden)' : 'Nog niet ingesteld'}" /></div>
            <label class="vinkregel breed"><input type="checkbox" name="controleer" ${s.controleer ? 'checked' : ''} />Certificaat van de mailserver controleren (aanbevolen)</label>
          </div>
          <p class="error-text" data-fout hidden></p>
          <div class="knoppen"><button class="btn btn-primary btn-lg" type="submit">Opslaan</button></div>
        </form>
      </section>
      <section class="card blok">
        <h2>Testmail</h2>
        <form class="knoppen" data-test novalidate>
          <input class="input" name="aan" type="email" value="${ctx.staat.sessie.gebruiker.email}" style="flex:1;min-width:220px" aria-label="Testmail naar" />
          <button class="btn" type="submit">${icoon('mail', 18)}Stuur testmail</button>
        </form>
        <p class="error-text" data-test-fout hidden></p>
      </section>
      <section class="card blok">
        <div class="kaart-kop"><h2>Verstuurde mails</h2>
          ${m.mislukt || m.wacht ? html`<button class="btn btn-sm" type="button" data-opnieuw>${icoon('refresh', 16)}Nu opnieuw proberen</button>` : ''}</div>
        <p class="muted klein">${m.wacht} in de wachtrij · ${m.mislukt} mislukt. Snelle wijzigingen achter elkaar worden in één mail gebundeld.</p>
        ${m.log.length
          ? html`<div class="tabel-scroll"><table class="maillog"><tbody>${m.log.map(
              (r) => html`<tr>
                <td><strong>${r.onderwerp}</strong><br /><span class="muted">${r.aan}</span>
                  ${r.fout ? html`<br /><span class="fout-regel">${r.fout}</span>` : ''}</td>
                <td><span class="pill ${r.status === 'verstuurd' ? 'pill-groen' : r.status === 'mislukt' ? 'pill-accent' : ''}">${STATUS[r.status] || r.status}</span><br />
                  <span class="muted">${tijdGeleden(r.verstuurd || r.gemaakt)}</span></td>
              </tr>`,
            )}</tbody></table></div>`
          : html`<p class="muted">Nog geen mails verstuurd.</p>`}
      </section>
      <section class="card blok">
        <h2>Pushmeldingen</h2>
        <p class="muted">${data.push.actief ? `Staan aan op de server. ${data.push.apparaten} ${data.push.apparaten === 1 ? 'apparaat ontvangt' : 'apparaten ontvangen'} meldingen.` : 'Staan uit: het pakket python3-cryptography ontbreekt op de server.'}</p>
      </section>
    </div>`)
  }

  // ---------------------------------------------------------------- accounts

  function accounts(plek) {
    zet(plek, html`<ul class="lijst deelnemers">${data.accounts.map(
      (a) => html`<li>
        ${avatar(a, 40)}
        <div class="midden">
          <div class="titel">${a.naam}${a.ik ? ' (jij)' : ''}
            ${a.status === 'actief' ? '' : html`<span class="pill">Nog geen wachtwoord</span>`}
            ${a.beheerder ? html`<span class="pill pill-accent">Beheerder</span>` : ''}</div>
          <div class="sub">${a.email}${a.laatst_gezien ? ` · ${tijdGeleden(a.laatst_gezien)} gezien` : ''}</div>
          ${a.vieringen.length ? html`<div class="sub">${a.vieringen.join(', ')}</div>` : ''}
        </div>
        <details class="menu">
          <summary class="icon-btn klein" aria-label="Meer">${icoon('more', 18)}</summary>
          <div class="menu-lijst">
            ${a.ik
              ? html`<span class="muted klein" style="padding:8px 10px">Dit ben jij</span>`
              : html`<button type="button" data-beheerder="${a.id}" data-aan="${a.beheerder ? '0' : '1'}">${icoon('beheer', 18)}${a.beheerder ? 'Geen beheerder meer' : 'Beheerder maken'}</button>
                <button type="button" class="gevaar" data-account-weg="${a.id}">${icoon('trash', 18)}Account verwijderen</button>`}
          </div>
        </details>
      </li>`,
    )}</ul>`)
  }

  // ---------------------------------------------------------------- acties

  on(root, 'submit', '[data-app]', (e) => {
    e.preventDefault()
    metKnop($('button', e.target), async () => {
      try {
        await put('/beheer/app', formulier(e.target))
        await ctx.vernieuwSessie()
        toast({ titel: 'Opgeslagen', soort: 'goed', duur: 2500 })
      } catch (f) {
        toonFout(f)
      }
    })
  })
  on(root, 'submit', '[data-smtp]', (e) => {
    e.preventDefault()
    const form = e.target
    const fout = $('[data-fout]', form)
    wisFout(fout)
    const velden = formulier(form)
    velden.controleer = form.controleer.checked
    metKnop($('button[type=submit]', form), async () => {
      try {
        await put('/beheer/smtp', velden)
        toast({ titel: 'Mailinstellingen opgeslagen', tekst: 'Stuur een testmail om te kijken of het werkt.', soort: 'goed' })
        laad()
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
  on(root, 'submit', '[data-test]', (e) => {
    e.preventDefault()
    const fout = $('[data-test-fout]', root)
    wisFout(fout)
    metKnop($('button', e.target), async () => {
      try {
        const r = await post('/beheer/smtp/test', formulier(e.target))
        toast({ titel: 'Testmail verstuurd', tekst: `Kijk in de inbox van ${r.aan}.`, soort: 'goed' })
        laad()
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
  on(root, 'click', '[data-opnieuw]', async (e, el) => {
    await metKnop(el, async () => {
      try {
        await post('/beheer/mail/opnieuw')
        setTimeout(laad, 1500)
      } catch (f) {
        toonFout(f)
      }
    })
  })
  on(root, 'click', '[data-beheerder]', async (e, el) => {
    el.closest('details')?.removeAttribute('open')
    try {
      await put(`/beheer/accounts/${el.dataset.beheerder}`, { beheerder: el.dataset.aan === '1' })
      laad()
    } catch (f) {
      toonFout(f)
    }
  })
  on(root, 'click', '[data-account-weg]', async (e, el) => {
    el.closest('details')?.removeAttribute('open')
    const a = data.accounts.find((x) => x.id === Number(el.dataset.accountWeg))
    if (!a || !(await bevestig({ titel: `Account van ${a.naam} verwijderen?`, tekst: 'Alles van deze persoon verdwijnt uit alle vieringen: gerechten, wensen en berichten.', ja: 'Verwijderen', gevaar: true }))) return
    try {
      await del(`/beheer/accounts/${a.id}`)
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
