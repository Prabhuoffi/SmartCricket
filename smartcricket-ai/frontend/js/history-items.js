(function (root) {
  function combine(analyses, sessions) {
    return [
      ...analyses.map(data => ({ kind: 'analysis', data, created_at: data.created_at })),
      ...sessions.map(data => ({ kind: 'live', data, created_at: data.created_at })),
    ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at) || b.data.id - a.data.id);
  }
  function search(items, query) {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(({ kind, data }) => (kind === 'live'
      ? `${data.title} ${data.day} live practice shot image`
      : `${data.original_name || ''} ${data.session_label || ''} ${data.shot || ''} ${data.mode || ''}`)
      .toLowerCase().includes(q));
  }
  const api = { combine, search };
  root.SCHistoryItems = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
