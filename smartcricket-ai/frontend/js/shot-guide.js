(function (root) {
  function match(text, guides) {
    const said = String(text || '').toLowerCase();
    const aliases = guides.flatMap(guide => guide.aliases.map(alias => ({ alias: alias.toLowerCase(), guide })));
    aliases.sort((a, b) => b.alias.length - a.alias.length);
    return aliases.find(({ alias }) => new RegExp(`(^|[^a-z])${alias.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=$|[^a-z])`).test(said))?.guide || null;
  }

  function frame(family, phase) {
    const back = family === 'cross' || family === 'high';
    const front = phase === 0 ? 90 : back ? 103 : family === 'low' ? 70 : 67;
    const headY = family === 'low' && phase > 0 ? 50 : 38;
    const hipY = family === 'low' && phase > 0 ? 104 : 93;
    const hands = phase === 0 ? [82, 45]
      : phase === 1 ? family === 'cross' ? [150, 78] : family === 'high' ? [155, 49] : family === 'low' ? [79, 112] : [93, 98]
      : family === 'cross' ? [178, 62] : family === 'high' ? [178, 27] : family === 'low' ? [168, 98] : [156, 40];
    const tip = phase === 0 ? [67, 12]
      : phase === 1 ? family === 'cross' ? [186, 75] : family === 'high' ? [190, 27] : family === 'low' ? [48, 116] : [81, 132]
      : family === 'low' ? [204, 81] : [190, 12];
    return `<svg viewBox="0 0 240 160" role="img" aria-label="Illustrated batting position">
      <path d="M25 141 H216" stroke="#486e5b" stroke-width="2"/>
      <circle cx="113" cy="${headY}" r="12" fill="#f3e9d2"/>
      <path d="M113 ${headY + 13} L116 ${hipY} M116 ${hipY} L${front} 140 M116 ${hipY} L139 140" stroke="#f3e9d2" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      <path d="M112 ${headY + 25} L${hands[0]} ${hands[1]} M123 ${headY + 29} L${hands[0] + 3} ${hands[1] + 3}" stroke="#8ce6b1" stroke-width="7" stroke-linecap="round" fill="none"/>
      <path d="M${hands[0]} ${hands[1]} L${tip[0]} ${tip[1]}" stroke="#f5c542" stroke-width="9" stroke-linecap="round"/>
      <circle cx="${hands[0]}" cy="${hands[1]}" r="5" fill="#fff"/>
    </svg>`;
  }

  const api = { match, frame };
  root.SCShotGuide = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
