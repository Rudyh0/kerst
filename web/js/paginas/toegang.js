// Inloggen, uitnodiging aannemen, wachtwoord vergeten en herstellen.
import { $, ApiFout, evenementWanneer, formulier, get, html, icoon, metKnop, post, toonFout, wisFout, zet } from '../hulp.js'
import { naInloggen } from '../app.js'
import { deeltjes, logo, logoVast, thema, zetThema } from '../themas.js'

function kaart(inhoud, { themaId = 'standaard' } = {}) {
  return html`<div class="toegang"><div class="toegang-kaart">
    <div class="logo">${logo(themaId, 48)}</div>
    ${inhoud}
  </div></div>`
}

const wwVeld = (naam, label, autocomplete, hint = '') => html`<div class="field">
  <label for="${naam}">${label}</label>
  <input class="input" id="${naam}" name="${naam}" type="password" autocomplete="${autocomplete}" required minlength="${autocomplete === 'new-password' ? 8 : 1}" />
  ${hint ? html`<span class="hint">${hint}</span>` : ''}
</div>`

export function toon(root, { params }) {
  const soort = params.soort
  if (soort === 'inloggen') return inloggen(root)
  if (soort === 'vergeten') return vergeten(root)
  if (soort === 'uitnodiging') return uitnodiging(root, params.token)
  if (soort === 'herstel') return herstel(root, params.token)
}

function inloggen(root) {
  const terug = new URLSearchParams(location.search).get('terug') || ''
  zet(root, kaart(html`
    <h1>Inloggen</h1>
    <p class="intro">Welkom terug! Log in om je vieringen te zien.</p>
    <form class="stapel" novalidate>
      <div class="field"><label for="email">E-mailadres</label>
        <input class="input" id="email" name="email" type="email" autocomplete="email" inputmode="email" required autofocus /></div>
      ${wwVeld('wachtwoord', 'Wachtwoord', 'current-password')}
      <p class="error-text" data-fout hidden></p>
      <button class="btn btn-primary btn-lg btn-block" type="submit">Inloggen</button>
    </form>
    <div class="onder"><a class="link" href="/wachtwoord-vergeten">Wachtwoord vergeten?</a></div>`))
  const form = $('form', root)
  form.addEventListener('submit', (e) => {
    e.preventDefault()
    const fout = $('[data-fout]', root)
    wisFout(fout)
    metKnop($('button[type=submit]', form), async () => {
      try {
        await post('/inloggen', formulier(form))
        await naInloggen(terug)
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
}

function vergeten(root) {
  zet(root, kaart(html`
    <h1>Wachtwoord vergeten</h1>
    <p class="intro">Vul je e-mailadres in. Je krijgt een mail met een link om een nieuw wachtwoord te kiezen.</p>
    <form class="stapel" novalidate>
      <div class="field"><label for="email">E-mailadres</label>
        <input class="input" id="email" name="email" type="email" autocomplete="email" inputmode="email" required autofocus /></div>
      <p class="error-text" data-fout hidden></p>
      <button class="btn btn-primary btn-lg btn-block" type="submit">Stuur de link</button>
    </form>
    <div class="onder"><a class="link" href="/inloggen">${icoon('chevron-left', 16)}Terug naar inloggen</a></div>`))
  const form = $('form', root)
  form.addEventListener('submit', (e) => {
    e.preventDefault()
    const fout = $('[data-fout]', root)
    wisFout(fout)
    metKnop($('button[type=submit]', form), async () => {
      try {
        const data = formulier(form)
        await post('/wachtwoord-vergeten', data)
        zet(root, kaart(html`
          <span class="icoon-rond groen" style="align-self:center">${icoon('mail', 22)}</span>
          <h1>Check je mail</h1>
          <p class="intro">Als ${data.email} bij ons bekend is, staat er zo een mail in je inbox. Kijk ook even in je spam.</p>
          <div class="onder"><a class="link" href="/inloggen">Terug naar inloggen</a></div>`))
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
}

function verlopen(root, f) {
  zet(root, kaart(html`
    <h1>Link verlopen</h1>
    <p class="intro">${f instanceof ApiFout ? f.message : 'Deze link werkt niet meer.'}</p>
    <a class="btn btn-primary btn-lg btn-block" href="/inloggen">Naar inloggen</a>
    <div class="onder"><a class="link" href="/wachtwoord-vergeten">Nieuwe link aanvragen</a></div>`))
}

async function uitnodiging(root, token) {
  zet(root, html`<div class="laden"></div>`)
  let info
  try {
    info = await get(`/uitnodiging/${token}`)
  } catch (f) {
    return verlopen(root, f)
  }
  const v = info.viering
  const t = v ? v.thema : 'standaard'
  zetThema(t)
  const kop = v
    ? html`<div class="uitnodiging-held" style="background:${thema(t).held}">${deeltjes(t, { factor: 0.6 })}${logoVast(t, 56, true)}</div>
        <div class="uitnodiging-info"><span>Je bent uitgenodigd voor</span><strong>${v.naam}</strong>
        ${v.datum ? html`<span>${evenementWanneer(v)}${v.locatie ? ` · ${v.locatie}` : ''}</span>` : ''}</div>`
    : html`<h1>Welkom bij plan-r</h1><p class="intro">Kies je naam en een wachtwoord om je account te maken.</p>`

  let velden
  if (info.heeft_account && info.ingelogd) {
    velden = html`<p class="intro">Je bent ingelogd als ${info.email}.</p>`
  } else if (info.heeft_account) {
    velden = html`<p class="intro">Je hebt al een account (${info.email}). Vul je wachtwoord in om mee te doen.</p>
      <input type="email" name="email" value="${info.email}" autocomplete="username" hidden />
      ${wwVeld('wachtwoord', 'Wachtwoord', 'current-password')}`
  } else {
    velden = html`<div class="field"><label for="naam">Je naam</label>
        <input class="input" id="naam" name="naam" value="${info.naam}" autocomplete="given-name" maxlength="40" required autofocus />
        <span class="hint">Zo zien de anderen je.</span></div>
      <input type="email" name="email" value="${info.email}" autocomplete="username" hidden />
      ${wwVeld('wachtwoord', 'Kies een wachtwoord', 'new-password', 'Minstens 8 tekens.')}
      ${wwVeld('herhaal', 'Nog een keer', 'new-password')}`
  }
  zet(root, html`<div class="toegang"><div class="toegang-kaart uitnodiging">
    ${v ? '' : html`<div class="logo">${logo('standaard', 48)}</div>`}
    ${kop}
    <form class="stapel" novalidate>
      ${velden}
      <p class="error-text" data-fout hidden></p>
      <button class="btn ${v ? 'btn-feest' : 'btn-primary'} btn-lg btn-block" type="submit">${v ? 'Doe mee' : 'Account maken'}</button>
    </form>
    ${info.heeft_account && !info.ingelogd ? html`<div class="onder"><a class="link" href="/wachtwoord-vergeten">Wachtwoord vergeten?</a></div>` : ''}
  </div></div>`)
  const form = $('form', root)
  form.addEventListener('submit', (e) => {
    e.preventDefault()
    const fout = $('[data-fout]', root)
    wisFout(fout)
    const data = formulier(form)
    if (!info.heeft_account && data.wachtwoord !== data.herhaal) {
      toonFout(new ApiFout(400, { fout: 'De twee wachtwoorden zijn niet hetzelfde.', veld: 'herhaal' }), fout)
      return
    }
    metKnop($('button[type=submit]', form), async () => {
      try {
        const r = await post(`/uitnodiging/${token}`, data)
        await naInloggen(r.slug ? `/${r.slug}` : '/')
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
}

async function herstel(root, token) {
  zet(root, html`<div class="laden"></div>`)
  let info
  try {
    info = await get(`/herstel/${token}`)
  } catch (f) {
    return verlopen(root, f)
  }
  zet(root, kaart(html`
    <h1>Nieuw wachtwoord</h1>
    <p class="intro">Kies een nieuw wachtwoord voor ${info.email}.</p>
    <form class="stapel" novalidate>
      <input type="email" name="email" value="${info.email}" autocomplete="username" hidden />
      ${wwVeld('wachtwoord', 'Nieuw wachtwoord', 'new-password', 'Minstens 8 tekens.')}
      ${wwVeld('herhaal', 'Nog een keer', 'new-password')}
      <p class="error-text" data-fout hidden></p>
      <button class="btn btn-primary btn-lg btn-block" type="submit">Opslaan en inloggen</button>
    </form>`))
  const form = $('form', root)
  form.addEventListener('submit', (e) => {
    e.preventDefault()
    const fout = $('[data-fout]', root)
    wisFout(fout)
    const data = formulier(form)
    if (data.wachtwoord !== data.herhaal) {
      toonFout(new ApiFout(400, { fout: 'De twee wachtwoorden zijn niet hetzelfde.', veld: 'herhaal' }), fout)
      return
    }
    metKnop($('button[type=submit]', form), async () => {
      try {
        await post(`/herstel/${token}`, { wachtwoord: data.wachtwoord })
        await naInloggen('/')
      } catch (f) {
        toonFout(f, fout)
      }
    })
  })
}
