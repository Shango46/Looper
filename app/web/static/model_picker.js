/* Model picker Alpine.js component — used by model selection dropdowns site-wide.
   Reads from window.LOOPER_MODELS, set per-page by the {% block scripts %} override. */

function _modelLabel(m) {
  const catLabels = { text: 'Text', vision: 'Vision', video: 'Video', image: 'Image Gen', audio: 'Audio' };
  const cat = catLabels[m.cat] || 'Text';

  let price;
  if (m.price_in === 0 && m.price_out === 0) {
    price = 'FREE';
  } else {
    const fmt = n => n === 0 ? '$0' : n < 0.1 ? '$' + n.toFixed(4) : '$' + n.toFixed(2);
    price = fmt(m.price_in) + ' / ' + fmt(m.price_out) + ' per 1M';
  }

  let ctx = '';
  if (m.ctx >= 1000000) ctx = (m.ctx / 1000000).toFixed(0) + 'M ctx';
  else if (m.ctx >= 1000) ctx = Math.round(m.ctx / 1000) + 'k ctx';
  else if (m.ctx > 0) ctx = m.ctx + ' ctx';

  const parts = [m.name, '[' + cat + ']', price];
  if (ctx) parts.push(ctx);
  if (!m.tools) parts.push('⚠ no tools');
  return parts.join('  ·  ');
}

function modelPicker(initialId) {
  return {
    search: '',
    catFilter: 'all',
    currentId: initialId || '',
    cats: [
      { id: 'all',    label: 'All' },
      { id: 'text',   label: 'Text' },
      { id: 'vision', label: 'Vision' },
      { id: 'video',  label: 'Video' },
      { id: 'image',  label: 'Image Gen' },
      { id: 'audio',  label: 'Audio' },
      { id: 'free',   label: 'Free' },
    ],
    get allModels() {
      return window.LOOPER_MODELS || [];
    },
    catCount(catId) {
      const all = this.allModels;
      if (catId === 'all')  return all.length;
      if (catId === 'free') return all.filter(m => m.price_in === 0 && m.price_out === 0).length;
      return all.filter(m => m.cat === catId).length;
    },
    get filtered() {
      const s = this.search.toLowerCase();
      const cf = this.catFilter;
      const cid = this.currentId;
      return this.allModels
        .filter(m => {
          if (m.id === cid) return true;           // always keep the currently selected model visible
          if (cf === 'free' && !(m.price_in === 0 && m.price_out === 0)) return false;
          if (cf !== 'all' && cf !== 'free' && m.cat !== cf) return false;
          if (s && !m.name.toLowerCase().includes(s) && !m.id.toLowerCase().includes(s)) return false;
          return true;
        })
        .map(m => ({ ...m, label: _modelLabel(m) }));
    },
    get filteredCount() {
      return this.filtered.filter(m => m.id !== this.currentId || !this.currentId).length;
    },
  };
}

/* Apply an Agent Shop template to the hire/edit form containing the given select element. */
function applyAgentTemplate(selectEl) {
  const templateId = parseInt(selectEl.value, 10);
  if (!templateId) return;
  const tpl = (window.LOOPER_AGENT_TEMPLATES || []).find(t => t.id === templateId);
  if (!tpl) return;

  const modal = selectEl.closest('.modal');
  if (!modal) return;

  const titleEl = modal.querySelector('[name="title"], [name="ceo_title"]');
  const personalityEl = modal.querySelector('[name="personality"], [name="ceo_personality"]');
  if (titleEl)       titleEl.value = tpl.title;
  if (personalityEl) personalityEl.value = tpl.personality;

  if (tpl.recommended_model_id) {
    const pickerEl = modal.querySelector('[x-data]');
    if (pickerEl) {
      const data = Alpine.$data(pickerEl);
      if (data && 'currentId' in data) {
        data.currentId = tpl.recommended_model_id;
        data.search = '';
        data.catFilter = 'all';
      }
    }
  }
}

/* Catalog component for the settings page — display-only, no selection. */
function modelCatalog() {
  return {
    search: '',
    catFilter: 'all',
    cats: [
      { id: 'all',    label: 'All' },
      { id: 'text',   label: 'Text' },
      { id: 'vision', label: 'Vision' },
      { id: 'video',  label: 'Video' },
      { id: 'image',  label: 'Image Gen' },
      { id: 'audio',  label: 'Audio' },
      { id: 'free',   label: 'Free' },
    ],
    get allModels() {
      return window.LOOPER_MODELS || [];
    },
    catCount(catId) {
      const all = this.allModels;
      if (catId === 'all')  return all.length;
      if (catId === 'free') return all.filter(m => m.price_in === 0 && m.price_out === 0).length;
      return all.filter(m => m.cat === catId).length;
    },
    get filtered() {
      const s = this.search.toLowerCase();
      const cf = this.catFilter;
      const results = this.allModels.filter(m => {
        if (cf === 'free' && !(m.price_in === 0 && m.price_out === 0)) return false;
        if (cf !== 'all' && cf !== 'free' && m.cat !== cf) return false;
        if (s && !m.name.toLowerCase().includes(s) && !m.id.toLowerCase().includes(s)) return false;
        return true;
      });
      return results.slice(0, 200);
    },
    get totalFiltered() {
      const s = this.search.toLowerCase();
      const cf = this.catFilter;
      return this.allModels.filter(m => {
        if (cf === 'free' && !(m.price_in === 0 && m.price_out === 0)) return false;
        if (cf !== 'all' && cf !== 'free' && m.cat !== cf) return false;
        if (s && !m.name.toLowerCase().includes(s) && !m.id.toLowerCase().includes(s)) return false;
        return true;
      }).length;
    },
    catLabel(catId) {
      return { text: 'Text', vision: 'Vision', video: 'Video', image: 'Image Gen', audio: 'Audio' }[catId] || 'Text';
    },
    priceLabel(m) {
      if (m.price_in === 0 && m.price_out === 0) return 'FREE';
      const fmt = n => n === 0 ? '$0' : n < 0.1 ? '$' + n.toFixed(4) : '$' + n.toFixed(2);
      return fmt(m.price_in) + ' / ' + fmt(m.price_out) + ' per 1M tokens';
    },
    ctxLabel(ctx) {
      if (!ctx) return '';
      if (ctx >= 1000000) return (ctx / 1000000).toFixed(0) + 'M ctx';
      if (ctx >= 1000) return Math.round(ctx / 1000) + 'k ctx';
      return ctx + ' ctx';
    },
  };
}
