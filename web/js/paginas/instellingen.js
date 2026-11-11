// Mijn instellingen: naam, meldingen, weergave en wachtwoord.
import { $, ApiFout, formulier, html, icoon, metKnop, on, opslag, post, put, toast, toonFout, wisFout, zet } from '../hulp.js'
import { isApp, isIOS, pushAan, pushStatus, pushTest, pushUit } from '../meldingen.js'
import { uitloggen } from '../app.js'
import { zetModus } from '../themas.js'

const SOORTEN = [
  ['lootje', 'Lootjes', 'Als de lootjes getrokken zijn'],
  ['berichten', 'Anonieme berichten', 'Van je lootje of je geheime gever'],
  ['wensen', 'Verlanglijstje van je lootje', 'Als je lootje iets toevoegt of aanpast'],
  ['menu', 'Menu en drankjes', 'Als iemand iets meeneemt of aanpast'],
  ['algemeen', 'Nieuws over een viering', 'Datum, plaats of spelregels veranderd'],
  ['deelnemers', 'Nieuwe deelnemers', 'Als iemand een uitnodiging aanneemt'],
]

export function toon(root, ctx) {
  async function pushBlok() {
    const st = await pushStatus().catch(() => 'niet')
    let tekst
    let knoppen = ''
    if (st === 'aan') {
      tekst = 'Staan aan op dit apparaat.'
      knoppen = html`<button class="btn btn-sm" type="button" data-push-test>Test</button><button class="btn btn-sm" type="button" data-push-uit>Uitzetten</button>`
    } else if (st === 'uit') {
      tekst = 'Krijg een melding op dit apparaat, ook als de app dicht is.'
      knoppen = html`<button class="btn btn-primary btn-sm" type="button" data-push-aan>Aanzetten</button>`
    } else if (st === 'geblokkeerd') {
      tekst = 'Je browser blokkeert meldingen voor deze site. Zet ze aan via het slotje naast het adres.'
    } else if (st === 'server') {
      tekst = 'Pushmeldingen staan uit op de server.'
    } else if (isIOS() && !isApp()) {
      tekst = "Op een iPhone of iPad: tik op Deel en kies 'Zet op beginscherm'. Open de app daarna vanaf je beginscherm en zet hier meldingen aan."
    } else {
      tekst = 'Deze browser ondersteunt geen pushmeldingen. Je krijgt wel mails en meldingen in de app.'
    }
    return html`<div class="instelling"><div class="tekst"><strong>Pushmeldingen op dit apparaat</strong><span class="muted klein">${tekst}</span></div>
      <div class="knoppen" style="flex-wrap:nowrap">${knoppen}</div></div>`
  }

  async function teken() {
    const g = ctx.staat.sessie.gebruiker
    const v = g.voorkeuren
    const modus = opslag.lees('modus', 'systeem')
    const push = await pushBlok()
    const soorten = SOORTEN.filter(([id]) => id !== 'deelnemers' || g.beheerder)
    zet(root, html`<div class="pagina smal">
      <header class="kop"><div class="kop-tekst"><p class="eyebrow">Jouw account</p><h1 class="page-title">Instellingen</h1></div></header>
      <div class="secties">
        <section class="card blok">
          <h2>Profiel</h2>
          <form class="stapel" data-profiel novalidate>
            <div class="raster-velden">
              <div class="field"><label for="naam">Naam</label><input class="input" id="naam" name="naam" value="${g.voornaam || g.naam}" maxlength="40" /></div>
              <div class="field"><label for="email">E-mailadres</label><input class="input" id="email" value="${g.email}" disabled /></div>
            </div>
            <p class="error-text" data-fout hidden></p>
            <div class="knoppen"><button class="btn btn-primary" type="submit">Opslaan</button></div>
          </form>
        </section>

        <section class="card blok">
          <h2>Meldingen</h2>
          <div data-push>${push}</div>
          <table class="voorkeuren">
            <thead><tr><th>Waarover</th><th>E-mail</th><th>Push</th></tr></thead>
            <tbody>${soorten.map(
              ([id, titel, uitleg]) => html`<tr>
                <td><strong>${titel}</strong><span class="muted klein">${uitleg}</span></td>
                <td><span class="schakelaar"><input type="checkbox" data-voorkeur="mail.${id}" ${v.mail[id] ? 'checked' : ''} aria-label="E-mail: ${titel}" /><span></span></span></td>
                <td><span class="schakelaar"><input type="checkbox" data-voorkeur="push.${id}" ${v.push[id] ? 'checked' : ''} aria-label="Push: ${titel}" /><span></span></span></td>
              </tr>`,
            )}</tbody>
          </table>
          <p class="hint">In de app zie je altijd alle meldingen bij het belletje. Uitnodigingen en wachtwoordmails krijg je altijd.</p>
        </section>

        <section class="card blok">
          <h2>Weergave</h2>
          <div class="instelling"><div class="tekst"><strong>Licht of donker</strong></div>
            <div class="segmented" role="radiogroup" aria-label="Licht of donker">
              ${[['systeem', 'Systeem'], ['licht', 'Licht'], ['donker', 'Donker']].map(
                ([w, t]) => html`<button type="button" data-modus="${w}" aria-pressed="${modus === w ? 'true' : 'false'}">${t}</button>`,
              )}
            </div></div>
          <div class="instelling"><div class="tekst"><strong>Animaties</strong><span class="muted klein">Sneeuw, pepernoten, bubbels en vonken bij de thema's.</span></div>
            <span class="schakelaar"><input type="checkbox" data-deeltjes ${opslag.lees('deeltjes', true) ? 'checked' : ''} aria-label="Animaties" /><span></span></span></div>
        </section>

        <section class="card blok">
          <h2>Wachtwoord wijzigen</h2>
          <form class="stapel" data-wachtwoord novalidate>
            <input type="email" value="${g.email}" autocomplete="username" hidden />
            <div class="raster-velden">
              <div class="field"><label for="huidig">Huidig wachtwoord</label><input class="input" id="huidig" name="huidig" type="password" autocomplete="current-password" /></div>
              <div class="field"><label for="nieuw">Nieuw wachtwoord</label><input class="input" id="nieuw" name="nieuw" type="password" autocomplete="new-password" />
                <span class="hint">Minstens 8 tekens. Andere apparaten worden uitgelogd.</span></div>
            </div>
            <p class="error-text" data-fout hidden></p>
            <div class="knoppen"><button class="btn" type="submit">Wachtwoord wijzigen</button></div>
          </form>
        </section>

        <button class="btn btn-lg btn-danger" type="button" data-uit>${icoon('logout', 18)}Uitloggen</button>
      </div>
    </div>`)
  }

  async function herteken() {
    const plek = $('[data-push]', root)
    if (plek) zet(plek, await pushBlok())
  }

  on(root, 'submit', '[data-profiel]', (e) => {
    e.preventDefault()
    const fout = $('[data-fout]', e.target)
    wisFout(fout)
    metKnop($('button', e.target), async () => {
      try {
        await put('/ik', formulier(e.target))
        await ctx.vernieuwSessie()
        toast({ titel: 'Opgeslagen', soort: 'goed', duur: 2500 })
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
  on(root, 'change', '[data-voorkeur]', async (e, el) => {
    const [kanaal, soort] = el.dataset.voorkeur.split('.')
    try {
      await put('/ik', { voorkeuren: { [kanaal]: { [soort]: el.checked } } })
      ctx.staat.sessie.gebruiker.voorkeuren[kanaal][soort] = el.checked
    } catch (f) {
      el.checked = !el.checked
      toonFout(f)
    }
  })
  on(root, 'click', '[data-modus]', (e, el) => {
    zetModus(el.dataset.modus)
    root.querySelectorAll('[data-modus]').forEach((b) => b.setAttribute('aria-pressed', b === el ? 'true' : 'false'))
  })
  on(root, 'change', '[data-deeltjes]', (e, el) => {
    opslag.zet('deeltjes', el.checked)
    toast({ titel: el.checked ? 'Animaties staan aan' : 'Animaties staan uit', duur: 2500 })
  })
  on(root, 'submit', '[data-wachtwoord]', (e) => {
    e.preventDefault()
    const fout = $('[data-fout]', e.target)
    wisFout(fout)
    metKnop($('button', e.target), async () => {
      try {
        await post('/ik/wachtwoord', formulier(e.target))
        e.target.reset()
        toast({ titel: 'Wachtwoord gewijzigd', soort: 'goed' })
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
  on(root, 'click', '[data-push-aan]', async (e, el) => {
    await metKnop(el, async () => {
      try {
        await pushAan()
        toast({ titel: 'Pushmeldingen staan aan', soort: 'goed' })
      } catch (f) {
        toonFout(f instanceof ApiFout ? f : new Error(f.message || 'Aanzetten lukte niet.'))
      }
    })
    herteken()
  })
  on(root, 'click', '[data-push-uit]', async (e, el) => {
    await metKnop(el, async () => {
      try {
        await pushUit()
      } catch (f) {
        toonFout(f)
      }
    })
    herteken()
  })
  on(root, 'click', '[data-push-test]', async (e, el) => {
    await metKnop(el, async () => {
      try {
        const r = await pushTest()
        toast({ titel: 'Testmelding verstuurd', tekst: `Naar ${r.apparaten} ${r.apparaten === 1 ? 'apparaat' : 'apparaten'}.`, soort: 'goed' })
      } catch (f) {
        toonFout(f)
      }
    })
  })
  on(root, 'click', '[data-uit]', () => uitloggen())

  teken()
}
