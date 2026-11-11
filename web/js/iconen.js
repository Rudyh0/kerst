// Lijn-iconen op een raster van 24 px, in de stijl van Afterfeed.
// Gevulde iconen beginnen met "fill:".
const ICONEN = {
  home: '<path d="M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5H15V15h-6v5.5H5.5A1.5 1.5 0 0 1 4 19z"/>',
  bestek: '<path d="M7 3.5v6a2 2 0 0 0 4 0v-6M9 3.5v17"/><path d="M17 20.5v-17c-2 1-3.5 3.5-3.5 7v3H17"/>',
  cadeau: '<rect x="3.5" y="8" width="17" height="4.5" rx="1.5"/><path d="M5 12.5V19a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 19v-6.5M12 8v12.5"/><path d="M12 8C10.5 4.5 6.5 3.5 6 6s3 2 6 2zM12 8c1.5-3.5 5.5-4.5 6-2s-3 2-6 2z"/>',
  berichten: '<path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-4.2A8 8 0 1 1 20 12z"/>',
  lijst: '<path d="M9.5 6.5h10M9.5 12h10M9.5 17.5h10"/><path d="m4 6.5 1 1 2-2M4 12l1 1 2-2M4 17.5l1 1 2-2"/>',
  bel: '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  instellingen: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  beheer: '<path d="M12 3.5 5 6v5.5c0 4.3 3 7.5 7 9 4-1.5 7-4.7 7-9V6z"/><path d="m9 12 2 2 4-4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  trash: '<path d="M4.5 7h15M9.5 7V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v2M6.5 7l.8 11.5a2 2 0 0 0 2 1.5h5.4a2 2 0 0 0 2-1.5L17.5 7"/>',
  pencil: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  logout: '<path d="M14 4.5h3.5A2.5 2.5 0 0 1 20 7v10a2.5 2.5 0 0 1-2.5 2.5H14"/><path d="M10 8l-4 4 4 4M6 12h9"/>',
  glas: '<path d="M7.5 3.5h9l-.6 5.2a3.9 3.9 0 0 1-7.8 0z"/><path d="M12 12.5v8M8.5 20.5h7"/>',
  'chevron-left': '<path d="m14.5 6-6 6 6 6"/>',
  'chevron-right': '<path d="m9.5 6 6 6-6 6"/>',
  'chevron-down': '<path d="m6 9.5 6 6 6-6"/>',
  'chevron-up': '<path d="m6 14.5 6-6 6 6"/>',
  close: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  more: 'fill:<circle cx="5.5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18.5" cy="12" r="1.6"/>',
  verstuur: '<path d="M20.5 3.5 10 14"/><path d="M20.5 3.5 14 20.5l-4-6.5-6.5-4z"/>',
  ster: '<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.8l-5.2 2.8 1-5.8-4.3-4.1 5.9-.9z"/>',
  sneeuw: '<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/><path d="m9.5 4.5 2.5 2 2.5-2M9.5 19.5l2.5-2 2.5 2"/>',
  mail: '<rect x="3.5" y="5.5" width="17" height="13" rx="2.5"/><path d="m4 7 8 6 8-6"/>',
  users: '<path d="M15.5 19v-1.5a3.5 3.5 0 0 0-3.5-3.5H7a3.5 3.5 0 0 0-3.5 3.5V19"/><circle cx="9.5" cy="8" r="3.5"/><path d="M20.5 19v-1.5a3.5 3.5 0 0 0-2.5-3.35M15.5 4.6a3.5 3.5 0 0 1 0 6.8"/>',
  kalender: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  klok: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  pin: '<path d="M12 21s-6.5-5.8-6.5-11a6.5 6.5 0 0 1 13 0c0 5.2-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
  label: '<path d="M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7l8.3 8.3-8.7 8.7z"/><circle cx="8.2" cy="8.2" r="1.4"/>',
  lock: '<rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8v.01"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.3-4.9L3.5 8.5"/><path d="M3.5 3.5v5h5"/><path d="M4 13a8 8 0 0 0 14.3 4.9l2.2-2.4"/><path d="M20.5 20.5v-5h-5"/>',
  zon: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/>',
  maan: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  telefoon: '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>',
  anoniem: '<path d="M4 11.5h16M6.5 11.5l1.4-5.6A1.5 1.5 0 0 1 9.4 4.8h5.2a1.5 1.5 0 0 1 1.5 1.1l1.4 5.6"/><circle cx="8" cy="16.5" r="2.7"/><circle cx="16" cy="16.5" r="2.7"/><path d="M10.7 16.3a2.4 2.4 0 0 1 2.6 0"/>',
  boom: '<path d="M12 3 7 9.5h2.5L6 14.5h3L5 19.5h14l-4-5h3l-3.5-5H17z"/><path d="M12 19.5V22"/>',
  sleep: '<path d="M9 5.5v.01M9 12v.01M9 18.5v.01M15 5.5v.01M15 12v.01M15 18.5v.01"/>',
}

export function svg(naam, maat = 20, lijn = 1.75) {
  const ruw = ICONEN[naam] || ''
  const gevuld = ruw.startsWith('fill:')
  const lichaam = gevuld ? ruw.slice(5) : ruw
  return `<svg width="${maat}" height="${maat}" viewBox="0 0 24 24" fill="${gevuld ? 'currentColor' : 'none'}" stroke="${gevuld ? 'none' : 'currentColor'}" stroke-width="${lijn}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${lichaam}</svg>`
}
