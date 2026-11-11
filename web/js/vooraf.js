// Draait vóór de rest (zonder module), zodat licht/donker en het thema meteen goed staan.
;(function () {
  var html = document.documentElement
  var keuze = 'systeem'
  var thema = 'standaard'
  try {
    keuze = JSON.parse(localStorage.getItem('planr.modus')) || 'systeem'
    var pad = location.pathname.split('/')[1] || ''
    var themas = JSON.parse(localStorage.getItem('planr.themas')) || {}
    if (themas[pad]) thema = themas[pad]
  } catch {
    // geen opslag beschikbaar: standaardwaarden
  }
  var donker = keuze === 'donker' || (keuze === 'systeem' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches)
  html.setAttribute('data-modus', donker ? 'donker' : 'licht')
  html.setAttribute('data-thema', thema)
})()
