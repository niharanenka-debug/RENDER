(() => {
  'use strict';

  const API = '/api';
  const navItems = [
    ['dashboard', 'Dashboard', '⌂'], ['summarizer', 'Summarizer', '▤'], ['flashcards', 'Flashcards', '▧'],
    ['chat', 'Study Chat', '◌'], ['quiz', 'Quiz', '✓'], ['mock_exam', 'Mock Exam', '◷'], ['mistakes', 'Mistake Notebook', '↺']
  ];
  const allowedCounts = [5, 10, 15, 20, 25];
  const state = {
    csrf: '', bootstrap: null, page: 'dashboard', artifacts: [], mistakes: [],
    artifactKind: '', loading: false, chatMessages: [], quiz: null, flash: { artifact: null, index: 0, flipped: false },
    examTimer: null, examSeconds: 0, noticeTimer: null
  };
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function node(tag, className, text, ...children) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    [text, ...children].forEach(child => {
      if (child === undefined || child === null) return;
      if (child instanceof Node) item.append(child);
      else item.append(document.createTextNode(String(child)));
    });
    return item;
  }
  function append(parent, ...children) {
    children.flat().forEach(child => { if (child !== null && child !== undefined) parent.append(child); });
    return parent;
  }
  function button(label, className, action, opts = {}) {
    const b = node('button', className, label);
    b.type = 'button';
    if (opts.title) b.title = opts.title;
    if (opts.disabled) b.disabled = true;
    if (opts.ariaLabel) b.setAttribute('aria-label', opts.ariaLabel);
    if (action) b.addEventListener('click', action);
    return b;
  }
  function setBusy(value) {
    state.loading = value;
    const view = $('#view');
    if (view) view.setAttribute('aria-busy', value ? 'true' : 'false');
  }
  function setNotice(message, type = 'info', persist = false) {
    const region = $('#notice-region');
    region.replaceChildren();
    if (!message) return;
    const box = node('div', `notice notice-${type}`);
    box.setAttribute('role', type === 'error' ? 'alert' : 'status');
    append(box, node('span', 'notice-symbol', type === 'error' ? '!' : type === 'success' ? '✓' : 'i'), node('span', '', message), button('×', 'notice-dismiss', () => region.replaceChildren(), { ariaLabel: 'Dismiss message' }));
    region.append(box);
    window.clearTimeout(state.noticeTimer);
    if (!persist && type !== 'error') state.noticeTimer = window.setTimeout(() => region.replaceChildren(), 6500);
  }
  function jsonText(value) {
    if (typeof value === 'string') return value;
    if (value === null || value === undefined) return '';
    try { return JSON.stringify(value, null, 2); } catch (_) { return String(value); }
  }
  function displayDate(value) {
    if (!value) return '';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }
  function extractError(data, fallback) {
    if (data && typeof data === 'object') {
      const detail = data.error || data.message || data.detail;
      if (typeof detail === 'string') return detail;
      if (detail !== undefined) return jsonText(detail);
    }
    return fallback;
  }
  async function request(path, options = {}, mutation = false) {
    const headers = new Headers(options.headers || {});
    if (mutation) {
      headers.set('X-CSRF-Token', state.csrf || '');
      if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    }
    let response;
    try { response = await fetch(`${API}${path}`, { ...options, headers }); }
    catch (error) { throw new Error(`Could not reach the study service. ${error.message || 'Check your connection and try again.'}`); }
    const raw = await response.text();
    let data = {};
    if (raw) { try { data = JSON.parse(raw); } catch (_) { data = { error: raw }; } }
    if (!response.ok) throw new Error(extractError(data, `Request failed (${response.status})`));
    return data;
  }
  async function refreshBootstrap() {
    const data = await request('/bootstrap');
    const previous = state.bootstrap && state.bootstrap.active_source;
    const next = data.active_source;
    const fingerprint = source => source ? `${source.id}|${source.kind}|${source.source_ref || ''}` : '';
    if (state.bootstrap && fingerprint(previous) !== fingerprint(next)) {
      state.chatMessages = [];
      state.quiz = null;
      state.flash = { artifact: null, index: 0, flipped: false };
      if (state.examTimer) { clearInterval(state.examTimer); state.examTimer = null; }
    }
    state.bootstrap = data;
    state.csrf = data.csrf_token || '';
    state.mistakes = Array.isArray(data.mistakes) ? data.mistakes : [];
    renderGlobalSource();
    renderAiStatus();
    return data;
  }
  async function refreshArtifacts(kind) {
    const data = await request(`/artifacts?kind=${encodeURIComponent(kind)}`);
    state.artifacts = Array.isArray(data) ? data : Array.isArray(data.artifacts) ? data.artifacts : [];
    state.artifactKind = kind;
    return state.artifacts;
  }
  async function refreshSummaries() {
    const [summaries, notes] = await Promise.all(['summary', 'notes'].map(async kind => {
      const data = await request(`/artifacts?kind=${kind}`);
      return Array.isArray(data.artifacts) ? data.artifacts : [];
    }));
    state.artifacts = [...summaries, ...notes].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    state.artifactKind = 'summary';
    return state.artifacts;
  }
  async function afterMutation({ kind } = {}) {
    await refreshBootstrap();
    if (kind) await refreshArtifacts(kind);
    renderPage();
  }
  function hasSource() { return !!(state.bootstrap && state.bootstrap.active_source); }
  function activeSource() { return state.bootstrap && state.bootstrap.active_source; }
  function renderAiStatus() {
    const chip = $('#ai-status');
    if (!state.bootstrap) return;
    const configured = !!state.bootstrap.ai_configured;
    chip.className = `status-chip ${configured ? 'status-ready' : 'status-missing'}`;
    chip.textContent = configured ? `AI ready${state.bootstrap.model ? ` · ${state.bootstrap.model}` : ''}` : 'AI key not configured';
    chip.title = configured ? 'AI generation is available.' : 'Configure an AI provider key on the backend to enable generation.';
  }
  function renderGlobalSource() {
    const data = state.bootstrap || {};
    const source = data.active_source || null;
    const top = $('#top-source-label');
    const badge = $('#active-source-badge');
    const details = $('#active-source-content');
    const list = $('#source-history-list');
    const sources = Array.isArray(data.sources) ? data.sources : [];
    top.textContent = source ? `Using: ${source.title || 'Untitled source'}` : 'No active source';
    badge.replaceChildren();
    const dot = node('span', 'badge-dot');
    append(badge, dot, node('span', '', source ? `Active · ${source.title || 'Untitled source'}` : 'No source selected'));
    badge.classList.toggle('is-live', !!source);
    details.replaceChildren();
    if (source) {
      const meta = node('div', 'active-source-meta');
      append(meta, node('span', 'kind-tag', source.kind || 'source'), node('span', 'meta-separator', '•'), node('span', '', `Added ${displayDate(source.created_at) || 'recently'}`));
      const ref = source.source_ref ? node('div', 'source-reference', source.source_ref) : null;
      const content = node('div', 'source-preview', source.content || 'This source is active and ready to use.');
      content.setAttribute('tabindex', '0');
      append(details, node('div', 'active-source-title', source.title || 'Untitled source'), meta, ref, content);
    } else {
      append(details, node('div', 'empty-compact', node('span', 'empty-icon', '◌'), node('p', '', 'No source yet'), node('span', '', 'Add text, a file, or a web link to get started.')));
    }
    $('#source-count').textContent = String(sources.length);
    list.replaceChildren();
    if (!sources.length) {
      list.append(node('p', 'subtle-empty', 'Your sources will appear here.'));
      return;
    }
    sources.forEach(item => {
      const row = node('div', `history-row${source && String(item.id) === String(source.id) ? ' history-row-active' : ''}`);
      const info = node('div', 'history-info');
      append(info, node('div', 'history-title', item.title || 'Untitled source'), node('div', 'history-meta', `${item.kind || 'source'}${item.created_at ? ` · ${displayDate(item.created_at)}` : ''}`));
      const controls = node('div', 'history-actions');
      if (!source || String(item.id) !== String(source.id)) controls.append(button('Activate', 'button button-small button-secondary', () => activateSource(item.id)));
      else controls.append(node('span', 'current-label', 'In use'));
      controls.append(button('Delete', 'text-button danger-text', () => deleteSource(item.id, item.title), { ariaLabel: `Delete ${item.title || 'source'}` }));
      append(row, info, controls);
      list.append(row);
    });
  }
  function setSourceKind(kind) {
    $('#source-kind').value = kind;
    $$('.source-kind-tab').forEach(tab => {
      const selected = tab.dataset.sourceKind === kind;
      tab.classList.toggle('is-active', selected);
      tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      tab.tabIndex = selected ? 0 : -1;
    });
    $$('[data-kind-panel]').forEach(panel => panel.classList.toggle('hidden', panel.dataset.kindPanel !== kind));
    $('#source-form-error').classList.add('hidden');
    $('#file-error').classList.add('hidden');
  }
  async function submitSource(event) {
    event.preventDefault();
    const formError = $('#source-form-error');
    formError.classList.add('hidden');
    const kind = $('#source-kind').value;
    const title = $('#source-title').value.trim();
    const submit = $('#source-submit');
    submit.disabled = true;
    submit.textContent = 'Adding source…';
    try {
      let data;
      if (kind === 'text') {
        const text = $('#source-text').value.trim();
        if (!text) throw new Error('Paste some study material before adding this source.');
        data = await request('/sources', { method: 'POST', body: JSON.stringify({ kind: 'text', title, text }) }, true);
      } else if (kind === 'url') {
        const url = $('#source-url').value.trim();
        if (!url) throw new Error('Enter a public web link to continue.');
        let parsed;
        try { parsed = new URL(url); } catch (_) { throw new Error('Enter a valid URL beginning with http:// or https://.'); }
        if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('Only HTTP and HTTPS links are supported.');
        data = await request('/sources', { method: 'POST', body: JSON.stringify({ kind: 'url', url, ...(title ? { title } : {}) }) }, true);
      } else {
        const file = $('#source-file').files[0];
        if (!file) throw new Error('Choose a file before adding this source.');
        if (file.size > 20 * 1024 * 1024) throw new Error('This file is larger than 20 MB. Choose a smaller file.');
        const payload = new FormData();
        payload.append('kind', 'file');
        payload.append('file', file);
        if (title) payload.append('title', title);
        data = await request('/sources', { method: 'POST', body: payload }, true);
      }
      await refreshBootstrap();
      $('#source-form').reset();
      $('#text-count').textContent = '0 characters';
      $('#file-label').textContent = 'Drop a file here or browse';
      setSourceKind('text');
      setNotice(data.source ? `${data.source.title || 'Source'} is active across all tools.` : 'Source added and activated across all tools.', 'success');
      await ensurePageData();
      renderPage();
    } catch (error) {
      formError.textContent = error.message;
      formError.classList.remove('hidden');
    } finally {
      submit.disabled = false;
      submit.replaceChildren(node('span', 'button-icon', '＋'), document.createTextNode(' Add & activate source'));
    }
  }
  async function activateSource(id) {
    try { await request(`/sources/${encodeURIComponent(id)}/activate`, { method: 'POST', body: '{}' }, true); await afterMutation(); setNotice('Source activated. Every study tool now uses it.', 'success'); }
    catch (error) { setNotice(error.message, 'error', true); }
  }
  async function deleteSource(id, title) {
    if (!window.confirm(`Delete “${title || 'this source'}”? This cannot be undone.`)) return;
    try { await request(`/sources/${encodeURIComponent(id)}`, { method: 'DELETE' }, true); await afterMutation(); setNotice('Source deleted.', 'success'); }
    catch (error) { setNotice(error.message, 'error', true); }
  }
  function switchPage(page) {
    state.page = page;
    $$('#main-nav [data-page]').forEach(link => {
      const active = link.dataset.page === page;
      link.classList.toggle('nav-active', active);
      if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    $('#main-nav').classList.remove('nav-open');
    $('#mobile-nav-toggle').setAttribute('aria-expanded', 'false');
    ensurePageData().then(renderPage).catch(error => { setNotice(error.message, 'error', true); renderPage(); });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function initializeNavigation() {
    const nav = $('#main-nav');
    navItems.forEach(([id, label, glyph]) => {
      const link = button('', 'nav-link', () => switchPage(id));
      link.dataset.page = id;
      append(link, node('span', 'nav-icon', glyph), node('span', 'nav-text', label));
      nav.append(link);
    });
    const toggle = $('#mobile-nav-toggle');
    toggle.addEventListener('click', () => {
      const open = !$('#main-nav').classList.contains('nav-open');
      $('#main-nav').classList.toggle('nav-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
  async function ensurePageData() {
    if (state.page === 'mistakes') {
      await refreshBootstrap();
      state.mistakes = Array.isArray(state.bootstrap.mistakes) ? state.bootstrap.mistakes : [];
    } else if (['summarizer', 'flashcards', 'quiz', 'mock_exam'].includes(state.page)) {
      if (state.page === 'summarizer') await refreshSummaries();
      else {
        const kind = state.page === 'mock_exam' ? 'mock_exam' : state.page === 'flashcards' ? 'flashcards' : 'quiz';
        await refreshArtifacts(kind);
      }
    }
  }
  function pageTitle(kicker, title, description) {
    const header = node('header', 'module-heading');
    append(header, node('div', 'eyebrow', kicker), node('h1', '', title), node('p', 'module-description', description));
    return header;
  }
  function moduleCard(title, detail, icon) {
    const card = node('div', 'module-card');
    append(card, node('span', 'module-card-icon', icon || '✦'), node('div', 'module-card-title', title), node('p', 'module-card-detail', detail));
    return card;
  }
  function actionButton(label, handler, disabled = false, primary = true) {
    return button(label, `button ${primary ? 'button-primary' : 'button-secondary'}`, handler, { disabled });
  }
  function noSourceMessage() {
    const card = node('div', 'inline-callout callout-warn');
    append(card, node('span', 'callout-icon', '↥'), node('div', '', node('strong', '', 'Add a source to begin'), node('p', '', 'Use the source panel above. The selected source is shared by every study tool.')));
    return card;
  }
  function renderDashboard(view) {
    const source = activeSource();
    const artifacts = Array.isArray(state.bootstrap?.artifacts) ? state.bootstrap.artifacts : [];
    const mistakes = Array.isArray(state.bootstrap?.mistakes) ? state.bootstrap.mistakes : [];
    append(view, pageTitle('YOUR STUDY SPACE', 'Make your next session count.', 'Everything you need to understand, remember, and prepare—grounded in your own material.'));
    const hero = node('section', 'dashboard-hero');
    append(hero, node('div', 'hero-orb', ''), node('div', 'hero-kicker', source ? 'READY WHEN YOU ARE' : 'START WITH YOUR MATERIAL'), node('h2', '', source ? `Pick up where you left off.` : 'Bring your material. Build your momentum.'), node('p', '', source ? `“${source.title || 'Untitled source'}” is the active source for every tool.` : 'Add a source above, then turn it into clear notes, confident recall, and exam-ready practice.'), button(source ? 'Open summarizer' : 'Add a source above', 'button button-primary', () => source ? switchPage('summarizer') : $('#source-text').focus(), { ariaLabel: source ? 'Open summarizer' : 'Focus the source input' }));
    view.append(hero);
    const stats = node('div', 'stats-grid');
    const activeMistakes = mistakes.filter(item => (item.status || 'open') !== 'resolved').length;
    [[source ? '1' : '0', 'Active source', source ? source.kind || 'source selected' : 'Ready for your first source'], [String(artifacts.length), 'Study artifacts', 'Saved summaries, decks & practice'], [String(activeMistakes), 'To review', 'Open items in your notebook']].forEach(([value, label, caption]) => {
      const box = node('div', 'stat-card');
      append(box, node('div', 'stat-value', value), node('div', 'stat-label', label), node('div', 'stat-caption', caption)); stats.append(box);
    });
    view.append(stats);
    append(view, sectionHeading('Your toolkit', 'Choose a way to study'), quickActions());
    if (artifacts.length) {
      append(view, sectionHeading('Recently saved', 'Keep your progress going'));
      const recent = node('div', 'recent-artifacts');
      artifacts.slice(0, 4).forEach(item => {
        const row = button('', 'recent-artifact', () => switchPage(item.kind === 'flashcards' ? 'flashcards' : item.kind === 'quiz' ? 'quiz' : 'summarizer'));
        append(row, node('span', 'artifact-icon', artifactIcon(item.kind)), node('span', 'recent-artifact-copy', node('strong', '', item.title || 'Untitled artifact'), node('small', '', `${item.kind || 'study item'}${item.created_at ? ` · ${displayDate(item.created_at)}` : ''}`)), node('span', 'row-arrow', '↗'));
        recent.append(row);
      }); view.append(recent);
    }
    if (!state.bootstrap?.ai_configured) view.append(aiMissingCallout());
  }
  function sectionHeading(kicker, title) {
    const h = node('div', 'section-heading'); append(h, node('div', 'eyebrow', kicker), node('h2', '', title)); return h;
  }
  function quickActions() {
    const grid = node('div', 'quick-grid');
    const actions = [
      ['summarizer', 'Summarize & make notes', 'Turn dense material into a clear, useful study guide.', '▤'],
      ['flashcards', 'Build flashcards', 'Practice active recall, one card at a time.', '▧'],
      ['chat', 'Ask study chat', 'Get an explanation grounded in your selected source.', '◌'],
      ['quiz', 'Take a quiz', 'Test what you know and learn from every answer.', '✓'],
      ['mock_exam', 'Run a mock exam', 'Practice under a timer with focused questions.', '◷'],
      ['mistakes', 'Review mistakes', 'Turn missed questions into your next breakthrough.', '↺']
    ];
    actions.forEach(([page, title, detail, icon]) => {
      const card = button('', 'quick-card', () => switchPage(page));
      append(card, node('span', 'quick-icon', icon), node('strong', '', title), node('span', '', detail), node('span', 'quick-arrow', '↗'));
      grid.append(card);
    });
    return grid;
  }
  function aiMissingCallout() {
    const box = node('div', 'inline-callout callout-info');
    append(box, node('span', 'callout-icon', '✦'), node('div', '', node('strong', '', 'AI key not configured'), node('p', '', 'Study generation and chat will work when an AI key is configured on the backend. No sample output is shown in its place.')));
    return box;
  }
 
