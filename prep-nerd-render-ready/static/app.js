(() => {
  'use strict';

  const API = '/api';
  const navItems = [
    ['dashboard', 'Dashboard', '⌂'], ['summarizer', 'Summarizer', '▤'], ['notes_generator', 'Notes Generator', '✎'],
    ['chat', 'Study Chat', '◌'], ['mock_exam', 'Mock Exam', '◷'], ['mistakes', 'Mistake Notebook', '↺']
  ];
  const allowedCounts = [5, 10, 15, 20, 25];
  const state = {
    csrf: '', bootstrap: null, page: 'dashboard', artifacts: [], mistakes: [],
    artifactKind: '', loading: false, chatMessages: [], assessment: null,
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
      state.assessment = null;
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
    } else if (['summarizer', 'notes_generator'].includes(state.page)) {
      await refreshSummaries();
    } else if (state.page === 'mock_exam') {
      await refreshArtifacts('mock_exam');
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
    const artifacts = (Array.isArray(state.bootstrap?.artifacts) ? state.bootstrap.artifacts : []).filter(item => !['quiz', 'flashcards'].includes(item.kind));
    const mistakes = Array.isArray(state.bootstrap?.mistakes) ? state.bootstrap.mistakes : [];
    append(view, pageTitle('YOUR STUDY SPACE', 'Make your next session count.', 'Everything you need to understand, remember, and prepare—grounded in your own material.'));
    const hero = node('section', 'dashboard-hero');
    append(hero, node('div', 'hero-orb', ''), node('div', 'hero-kicker', source ? 'READY WHEN YOU ARE' : 'START WITH YOUR MATERIAL'), node('h2', '', source ? `Pick up where you left off.` : 'Bring your material. Build your momentum.'), node('p', '', source ? `“${source.title || 'Untitled source'}” is the active source for every tool.` : 'Add a source above, then turn it into clear notes, confident recall, and exam-ready practice.'), button(source ? 'Open summarizer' : 'Add a source above', 'button button-primary', () => source ? switchPage('summarizer') : $('#source-text').focus(), { ariaLabel: source ? 'Open summarizer' : 'Focus the source input' }));
    view.append(hero);
    const stats = node('div', 'stats-grid');
    const activeMistakes = mistakes.filter(item => (item.status || 'open') !== 'resolved').length;
    [[source ? '1' : '0', 'Active source', source ? source.kind || 'source selected' : 'Ready for your first source'], [String(artifacts.length), 'Study artifacts', 'Saved notes, summaries & exams'], [String(activeMistakes), 'To review', 'Open items in your notebook']].forEach(([value, label, caption]) => {
      const box = node('div', 'stat-card');
      append(box, node('div', 'stat-value', value), node('div', 'stat-label', label), node('div', 'stat-caption', caption)); stats.append(box);
    });
    view.append(stats);
    append(view, sectionHeading('Your toolkit', 'Choose a way to study'), quickActions());
    if (artifacts.length) {
      append(view, sectionHeading('Recently saved', 'Keep your progress going'));
      const recent = node('div', 'recent-artifacts');
      artifacts.slice(0, 4).forEach(item => {
        const target = item.kind === 'mock_exam' ? 'mock_exam' : item.kind === 'notes' ? 'notes_generator' : 'summarizer';
        const row = button('', 'recent-artifact', () => switchPage(target));
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
      ['summarizer', 'Summarize material', 'Turn a source into a clear, useful study guide.', '▤'],
      ['notes_generator', 'Generate topic notes', 'Choose a notes style and length for any topic.', '✎'],
      ['chat', 'Ask study chat', 'Get an explanation grounded in your selected source.', '◌'],
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
  function artifactIcon(kind) { return kind === 'mock_exam' ? '✓' : kind === 'notes' ? '✎' : '▤'; }
  function field(labelText, control, hint) {
    const wrap = node('div', 'field-group');
    append(wrap, node('label', '', labelText), control);
    if (hint) wrap.append(node('p', 'field-hint', hint));
    return wrap;
  }
  function selectControl(items, value, className = 'control-select') {
    const select = node('select', className);
    items.forEach(([v, label]) => { const option = node('option', '', label); option.value = v; select.append(option); });
    select.value = value;
    return select;
  }
  function setOptions(select, values, selected) {
    values.forEach(v => { const o = node('option', '', String(v)); o.value = String(v); select.append(o); });
    select.value = String(selected);
  }
  async function generate(action, options = {}) {
    const topicOnlyNotes = action === 'notes' && typeof options.topic === 'string' && !!options.topic.trim();
    if (!hasSource() && !topicOnlyNotes) { setNotice('Add or activate a source above before generating this material.', 'error', true); return null; }
    setBusy(true);
    try {
      const payload = { action, style: options.style || 'Key Takeaways', difficulty: options.difficulty || 'Medium', count: Number(options.count || 10), depth: options.depth || 'Standard', title: options.title || '' };
      if (topicOnlyNotes) { payload.topic = options.topic.trim(); payload.size = options.size || 'Medium'; }
      const data = await request('/generate', { method: 'POST', body: JSON.stringify(payload) }, true);
      await refreshBootstrap();
      const kind = action === 'summary' || action === 'notes' ? 'summary' : 'mock_exam';
      if (kind === 'summary') await refreshSummaries(); else await refreshArtifacts(kind);
      renderPage();
      setNotice(`${data.artifact?.title || 'Study material'} is ready and saved.`, 'success');
      return data.artifact || null;
    } catch (error) { setNotice(error.message, 'error', true); return null; }
    finally { setBusy(false); }
  }
  function artifactPayload(item) { return item && item.payload !== undefined ? item.payload : ''; }
  function renderSummarizer(view) {
    append(view, pageTitle('CLEAR THE CLUTTER', 'Summarizer & notes', 'Shape your active source into a study guide that fits the way you learn.'));
    const controls = node('section', 'generator-panel panel');
    const form = node('div', 'generator-controls');
    const mode = selectControl([['summary', 'Summary'], ['notes', 'Study notes']], 'summary');
    const style = selectControl([['Executive Summary', 'Executive summary'], ['Key Takeaways', 'Key takeaways'], ['Detailed Analysis', 'Detailed analysis'], ['Short Abstract', 'Short abstract'], ['Action Items', 'Action items']], 'Key Takeaways');
    const depth = selectControl([['Automatic', 'Automatic'], ['Quick', 'Quick scan'], ['Standard', 'Standard'], ['Deep', 'Deep dive'], ['Exhaustive', 'Exhaustive']], 'Standard');
    const title = node('input', 'control-input'); title.type = 'text'; title.maxLength = 180; title.placeholder = 'Optional title';
    append(form, field('Output', mode), field('Style', style), field('Depth', depth), field('Title', title));
    const go = actionButton('Generate from active source', () => generate(mode.value, { style: style.value, depth: depth.value, title: title.value } ), !hasSource());
    append(controls, form, node('div', 'generator-action-row', go));
    view.append(controls);
    if (!hasSource()) view.append(noSourceMessage());
    const artifact = state.artifacts[0];
    if (artifact) {
      append(view, sectionHeading('SAVED OUTPUT', artifact.title || 'Your study guide'));
      view.append(editableArtifact(artifact));
    } else if (hasSource()) view.append(emptyPrompt('Your first study guide is one click away.', 'Generate a summary or study notes from the active source above.'));
  }
  function editableArtifact(item) {
    const panel = node('article', 'artifact-editor panel');
    const head = node('div', 'artifact-editor-head');
    append(head, node('span', 'artifact-type', `${artifactIcon(item.kind)} ${item.kind || 'study artifact'}`), node('span', 'artifact-date', displayDate(item.created_at)));
    const title = node('input', 'control-input artifact-title-input'); title.type = 'text'; title.maxLength = 180; title.value = item.title || '';
    title.setAttribute('aria-label', 'Artifact title');
    const body = node('textarea', 'artifact-textarea'); body.rows = 18;
    const originalPayload = artifactPayload(item);
    body.value = originalPayload && typeof originalPayload === 'object' && typeof originalPayload.text === 'string' ? originalPayload.text : jsonText(originalPayload);
    body.setAttribute('aria-label', 'Edit artifact content');
    const actions = node('div', 'artifact-actions');
    actions.append(button('Save changes', 'button button-primary', async () => {
      let payload = body.value;
      if (originalPayload && typeof originalPayload === 'object' && typeof originalPayload.text === 'string') payload = { ...originalPayload, text: body.value };
      else if (typeof item.payload !== 'string' && item.payload !== undefined) { try { payload = JSON.parse(body.value); } catch (_) { setNotice('This artifact uses structured data. Keep the content as valid JSON to save.', 'error', true); return; } }
      try { await request(`/artifacts/${encodeURIComponent(item.id)}`, { method: 'PATCH', body: JSON.stringify({ title: title.value.trim() || item.title || '', payload }) }, true); await refreshBootstrap(); await refreshSummaries(); renderPage(); setNotice('Changes saved.', 'success'); }
      catch (error) { setNotice(error.message, 'error', true); }
    }));
    actions.append(button('Download .txt', 'button button-secondary', () => downloadText(`${title.value || item.title || 'study-notes'}.txt`, body.value)));
    append(panel, head, title, body, actions);
    return panel;
  }
  function downloadText(filename, text) {
    const safeName = filename.replace(/[\\/:*?"<>|]+/g, '-');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = safeName;
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(link.href);
  }
  function emptyPrompt(title, detail) { const box = node('div', 'empty-state'); append(box, node('span', 'empty-illustration', '✦'), node('strong', '', title), node('p', '', detail)); return box; }
  function renderNotesGenerator(view) {
    append(view, pageTitle('NOTES GENERATOR', 'Notes from any topic', 'Type a topic, choose the style and length, and generate notes without adding a source.'));
    const panel = node('section', 'generator-panel panel');
    const form = node('div', 'generator-controls');
    const topic = node('input', 'control-input');
    topic.type = 'text';
    topic.maxLength = 300;
    topic.placeholder = 'e.g. Photosynthesis, SQL joins, or World War I';
    topic.setAttribute('aria-label', 'Topic name');

    const style = selectControl([
      ['Structured study notes', 'Structured study notes'],
      ['Concise revision notes', 'Concise revision notes'],
      ['Detailed lecture notes', 'Detailed lecture notes'],
      ['Exam-focused notes', 'Exam-focused notes'],
      ['Beginner-friendly notes', 'Beginner-friendly notes'],
      ['Cornell notes', 'Cornell notes'],
      ['Mind-map-style outline', 'Mind-map-style outline'],
      ['Custom instructions', 'Custom instructions']
    ], 'Structured study notes');
    const size = selectControl([
      ['Brief', 'Brief (~300 words)'],
      ['Short', 'Short (~600 words)'],
      ['Medium', 'Medium (~1,000 words)'],
      ['Detailed', 'Detailed (~1,800 words)'],
      ['Comprehensive', 'Comprehensive (~3,000 words)']
    ], 'Medium');
    const custom = node('input', 'control-input');
    custom.type = 'text';
    custom.maxLength = 500;
    custom.placeholder = 'e.g. Use question-and-answer format with examples';
    custom.setAttribute('aria-label', 'Custom notes style instructions');
    const customField = field('Custom style instructions', custom);
    customField.hidden = true;
    style.addEventListener('change', () => { customField.hidden = style.value !== 'Custom instructions'; });

    append(form, field('Topic name', topic), field('Preferred notes style', style), field('Notes length', size), customField);
    const generateButton = actionButton('Generate notes', async () => {
      const preferredStyle = style.value === 'Custom instructions' ? custom.value.trim() : style.value;
      await generate('notes', { topic: topic.value.trim(), style: preferredStyle, size: size.value, title: topic.value.trim() });
    }, true);
    const updateDisabled = () => {
      generateButton.disabled = !topic.value.trim() || (style.value === 'Custom instructions' && !custom.value.trim());
    };
    topic.addEventListener('input', updateDisabled);
    custom.addEventListener('input', updateDisabled);
    style.addEventListener('change', updateDisabled);
    append(panel, form, node('div', 'generator-action-row', generateButton));
    view.append(panel);

    const savedNotes = state.artifacts.find(item => item.kind === 'notes');
    if (savedNotes) {
      append(view, sectionHeading('SAVED NOTES', savedNotes.title || 'Your notes'));
      view.append(editableArtifact(savedNotes));
    } else {
      view.append(emptyPrompt('Your notes will appear here', 'Enter a topic and generate your first set of notes.'));
    }
    if (!state.bootstrap?.ai_configured) view.append(aiMissingCallout());
  }
  function renderChat(view) {
    append(view, pageTitle('GROUNDED STUDY CHAT', 'Ask your source', 'Explore tricky ideas and get answers grounded in the material you selected.'));
    const panel = node('section', 'chat-panel panel');
    const messages = node('div', 'chat-messages');
    if (!state.chatMessages.length) append(messages, node('div', 'chat-empty', node('span', 'chat-orbit', '◌'), node('strong', '', 'What would you like to understand?'), node('p', '', hasSource() ? 'Ask a question about the active source. Answers are returned with any citation text the service provides.' : 'Add a source above to ground your conversation.')));
    state.chatMessages.forEach(message => {
      const bubble = node('article', `chat-message ${message.role === 'user' ? 'chat-user' : 'chat-assistant'}`);
      append(bubble, node('div', 'chat-role', message.role === 'user' ? 'YOU' : 'STUDY GUIDE'), node('div', 'chat-text', message.text));
      messages.append(bubble);
    });
    const form = node('form', 'chat-form');
    const input = node('textarea', 'chat-input'); input.rows = 2; input.placeholder = 'Ask a question about your source…'; input.setAttribute('aria-label', 'Your study question'); input.disabled = !hasSource();
    const send = button('Send ↗', 'button button-primary chat-send', null, { disabled: !hasSource() }); send.type = 'submit';
    append(form, input, send);
    form.addEventListener('submit', async e => {
      e.preventDefault(); const question = input.value.trim(); if (!question) return;
      state.chatMessages.push({ role: 'user', text: question }); state.chatMessages.push({ role: 'assistant', text: 'Thinking through your source…', pending: true }); renderPage();
      try {
        const data = await request('/chat', { method: 'POST', body: JSON.stringify({ question }) }, true);
        const pending = state.chatMessages.findLastIndex ? state.chatMessages.findLastIndex(m => m.pending) : state.chatMessages.length - 1;
        if (pending >= 0) state.chatMessages[pending] = { role: 'assistant', text: data.answer || 'No answer was returned.' };
      } catch (error) {
        const pending = state.chatMessages.findLastIndex ? state.chatMessages.findLastIndex(m => m.pending) : state.chatMessages.length - 1;
        if (pending >= 0) state.chatMessages[pending] = { role: 'assistant', text: `Could not answer: ${error.message}` };
      }
      renderPage(); $('#view').scrollIntoView({ block: 'end', behavior: 'smooth' });
    });
    append(panel, messages, form, node('p', 'chat-footnote', 'Answers use the active source. Verify important details against your original material.'));
    view.append(panel);
    if (!hasSource()) view.append(noSourceMessage());
  }
  function questionsFrom(payload) {
    if (Array.isArray(payload)) return payload;
    if (payload && typeof payload === 'object') return payload.questions || payload.items || payload.problems || [];
    return [];
  }
  function renderMockExam(view) {
    append(view, pageTitle('MOCK EXAM', 'Mock exam', 'A focused timed practice run, built from your active source.'));
    const panel = node('section', 'generator-panel panel');
    const controls = node('div', 'generator-controls compact-controls');
    const count = selectControl(allowedCounts.map(n => [String(n), `${n} questions`]), '10');
    const difficulty = selectControl([['Easy', 'Easy'], ['Medium', 'Medium'], ['Hard', 'Hard']], 'Medium');
    const duration = selectControl([[10, '10 minutes'], [20, '20 minutes'], [30, '30 minutes'], [45, '45 minutes'], [60, '60 minutes']], '30');
    append(controls, field('Question count', count), field('Difficulty', difficulty), field('Time limit', duration));
    const title = node('input', 'control-input'); title.type = 'text'; title.placeholder = 'Optional exam title'; title.maxLength = 180;
    append(controls, field('Title', title));
    append(panel, controls, node('div', 'generator-action-row', actionButton('Create mock exam', async () => {
      const artifact = await generate('mock_exam', { count: count.value, difficulty: difficulty.value, title: title.value });
      if (artifact) { state.assessment = { artifact, answers: {}, submitted: false, result: null, duration: Number(duration.value) * 60 }; renderPage(); }
    }, !hasSource())));
    view.append(panel);
    if (!hasSource()) view.append(noSourceMessage());
    const current = state.assessment?.artifact?.kind === 'mock_exam' ? state.assessment : null;
    const artifact = current?.artifact || state.artifacts[0];
    if (!artifact) { if (hasSource()) view.append(emptyPrompt('Ready when you are', 'Choose a question count and time limit to get started.')); return; }
    if (!state.assessment || state.assessment.artifact.id !== artifact.id) state.assessment = { artifact, answers: {}, submitted: false, result: null, duration: 0 };
    renderQuestionSet(view, state.assessment);
  }
  function renderQuestionSet(view, session) {
    const questions = questionsFrom(artifactPayload(session.artifact));
    const wrap = node('section', 'question-set');
    const head = node('div', 'question-set-head');
    append(head, node('h2', '', session.artifact.title || 'Mock exam'));
    if (session.duration && !session.submitted) {
      const timer = node('div', 'exam-timer', formatTime(state.examSeconds || session.duration)); timer.setAttribute('aria-live', 'polite'); head.append(timer);
      if (!state.examTimer) startExamTimer(timer, session);
    }
    append(wrap, head, node('p', 'question-instructions', session.submitted ? 'Review each question and its explanation below.' : `Select one answer for each of ${questions.length} questions.`));
    if (!questions.length) { wrap.append(emptyPrompt('No questions found in this exam.', 'Generate another mock exam from your active source.')); view.append(wrap); return; }
    questions.forEach((question, index) => {
      const card = node('fieldset', `question-card${session.submitted ? ' question-reviewed' : ''}`);
      const legend = node('legend', 'question-legend', `${index + 1}. ${questionText(question)}`);
      card.append(legend);
      const rawOptions = question.options || question.choices || [];
      const options = Array.isArray(rawOptions) ? rawOptions : Object.entries(rawOptions).map(([key, text]) => ({ key, text }));
      options.forEach((option, choiceIndex) => {
        const val = optionValue(option, choiceIndex);
        const optionText = optionLabel(option);
        const label = node('label', 'answer-option');
        const input = document.createElement('input'); input.type = 'radio'; input.name = `question-${index}`; input.value = val; input.checked = session.answers[index] === val; input.disabled = session.submitted;
        input.addEventListener('change', () => { session.answers[index] = val; });
        append(label, input, node('span', '', optionText));
        if (session.submitted) {
          if (isCorrectChoice(question, option, val)) label.classList.add('answer-correct');
          else if (session.answers[index] === val) label.classList.add('answer-wrong');
        }
        card.append(label);
      });
      if (session.submitted) {
        const answerText = correctAnswerText(question);
        const feedback = node('div', `answer-feedback ${isQuestionCorrect(question, session.answers[index]) ? 'feedback-right' : 'feedback-wrong'}`);
        append(feedback, node('strong', '', isQuestionCorrect(question, session.answers[index]) ? 'Correct' : 'Review this one'), answerText ? node('p', '', `Answer: ${answerText}`) : null, question.explanation ? node('p', 'answer-explanation', question.explanation) : null);
        card.append(feedback);
      }
      wrap.append(card);
    });
    if (!session.submitted) {
      const submit = actionButton('Submit exam', () => gradeAssessment(session), false);
      const unanswered = questions.length - Object.keys(session.answers).length;
      const footer = node('div', 'assessment-footer');
      append(footer, node('span', 'subtle-text', `${unanswered} unanswered`), submit);
      wrap.append(footer);
    } else if (session.result) {
      const score = session.result.score || {};
      const result = node('div', 'score-banner');
      append(result, node('span', 'score-percent', `${score.percentage ?? 0}%`), node('div', '', node('strong', '', `${score.correct ?? 0} of ${score.total ?? questions.length} correct`), node('p', '', `${score.unanswered ?? 0} unanswered · Missed questions have been added to your Mistake Notebook.`)));
      wrap.append(result);
    }
    view.append(wrap);
  }
  function questionText(q) { return typeof q === 'string' ? q : q.question || q.prompt || q.text || 'Question'; }
  function optionValue(option, i) { if (option && typeof option === 'object') return String(option.id ?? option.key ?? option.label ?? option.text ?? i); return String(option); }
  function optionLabel(option) { if (option && typeof option === 'object') return String(option.text ?? option.label ?? option.value ?? jsonText(option)); return String(option); }
  function correctAnswerValue(question) {
    const a = question.correct_answer ?? question.answer ?? question.correct ?? question.answer_index;
    if (a === undefined || a === null) return '';
    if (typeof a === 'number') return String(a);
    if (typeof a === 'object') return String(a.id ?? a.key ?? a.label ?? a.text ?? '');
    return String(a);
  }
  function correctAnswerText(question) {
    const raw = question.correct_answer ?? question.answer ?? question.correct;
    if (raw && typeof raw === 'object') return optionLabel(raw);
    if (typeof raw === 'number' && Array.isArray(question.options || question.choices)) return optionLabel((question.options || question.choices)[raw]);
    if (typeof raw === 'string' && /^[A-D]$/.test(raw) && question.options && !Array.isArray(question.options)) return `${raw} — ${question.options[raw] || ''}`;
    return raw === undefined || raw === null ? '' : String(raw);
  }
  function isCorrectChoice(question, option, value) {
    const raw = correctAnswerValue(question);
    if (raw === value || raw === optionLabel(option)) return true;
    const sourceOptions = question.options || question.choices || [];
    if (!Array.isArray(sourceOptions)) return false;
    const idx = sourceOptions.indexOf(option);
    return String(idx) === raw;
  }
  function isQuestionCorrect(question, answer) { return answer !== undefined && (correctAnswerValue(question) === String(answer) || correctAnswerText(question) === String(answer)); }
  function formatTime(seconds) { const s = Math.max(0, Number(seconds)); return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; }
  function startExamTimer(element, session) {
    state.examSeconds = session.duration;
    state.examTimer = window.setInterval(() => {
      if (state.assessment !== session || session.submitted) { clearInterval(state.examTimer); state.examTimer = null; return; }
      state.examSeconds -= 1;
      const timer = $('.exam-timer'); if (timer) timer.textContent = formatTime(state.examSeconds);
      if (state.examSeconds <= 0) { clearInterval(state.examTimer); state.examTimer = null; gradeAssessment(session); }
    }, 1000);
  }
  async function gradeAssessment(session) {
    if (session.submitted) return;
    const questions = questionsFrom(artifactPayload(session.artifact));
    const answers = questions.map((_, i) => session.answers[i] ?? null);
    try {
      const data = await request('/grade', { method: 'POST', body: JSON.stringify({ kind: session.artifact.kind, title: session.artifact.title || '', questions, answers }) }, true);
      session.result = data; session.submitted = true;
      if (state.examTimer) { clearInterval(state.examTimer); state.examTimer = null; }
      await refreshBootstrap();
      renderPage();
    } catch (error) { setNotice(error.message, 'error', true); }
  }
  function renderMistakes(view) {
    append(view, pageTitle('LEARN FROM EVERY MISS', 'Mistake notebook', 'A low-pressure place to revisit questions and make the learning stick.'));
    const mistakes = state.mistakes || [];
    if (!mistakes.length) { view.append(emptyPrompt('No mistakes to review yet', 'After you submit a mock exam, missed questions appear here.')); return; }
    const filters = node('div', 'mistake-summary');
    const open = mistakes.filter(m => (m.status || m.payload?.status || 'Needs More Practice') === 'Needs More Practice').length;
    append(filters, node('span', '', `${mistakes.length} saved`), node('span', '', `${open} open`)); view.append(filters);
    const list = node('div', 'mistake-list');
    mistakes.forEach((item, index) => {
      const card = node('article', 'mistake-card');
      const head = node('div', 'mistake-card-head');
      const status = item.status || item.payload?.status || 'Needs More Practice';
      const statusClass = status === 'Reviewed' ? 'status-reviewed' : 'status-needs';
      append(head, node('span', 'mistake-index', `REVIEW ${String(index + 1).padStart(2, '0')}`), node('span', `status-pill ${statusClass}`, status));
      const q = mistakeQuestion(item);
      const payload = item.payload && typeof item.payload === 'object' ? item.payload : {};
      append(card, head, node('h3', '', q || 'Missed question'), (item.explanation || payload.explanation) ? node('p', 'mistake-explanation', item.explanation || payload.explanation) : null);
      const detail = item.answer || item.correct_answer || item.expected_answer || payload.correct_answer;
      if (detail) card.append(node('p', 'mistake-answer', `Answer to remember: ${typeof detail === 'object' ? jsonText(detail) : detail}`));
      const select = selectControl([['Needs More Practice', 'Needs more practice'], ['Reviewed', 'Reviewed']], status, 'status-select');
      select.setAttribute('aria-label', `Update status for ${q || 'mistake'}`);
      select.addEventListener('change', async () => {
        try { await request(`/mistakes/${encodeURIComponent(item.id)}`, { method: 'PATCH', body: JSON.stringify({ status: select.value }) }, true); await refreshBootstrap(); state.mistakes = state.bootstrap.mistakes || []; renderPage(); setNotice('Mistake status updated.', 'success'); }
        catch (error) { setNotice(error.message, 'error', true); }
      });
      const actions = node('div', 'mistake-actions'); append(actions, select); card.append(actions); list.append(card);
    });
    view.append(list);
  }
  function mistakeQuestion(item) {
    if (item.question) return String(item.question);
    if (item.prompt) return String(item.prompt);
    if (item.payload) return typeof item.payload === 'string' ? item.payload : item.payload.question || jsonText(item.payload);
    return '';
  }
  function renderPage() {
    const view = $('#view');
    view.replaceChildren();
    $$('#main-nav [data-page]').forEach(link => { const active = link.dataset.page === state.page; link.classList.toggle('nav-active', active); if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current'); });
    switch (state.page) {
      case 'summarizer': renderSummarizer(view); break;
      case 'notes_generator': renderNotesGenerator(view); break;
      case 'chat': renderChat(view); break;
      case 'mock_exam': renderMockExam(view); break;
      case 'mistakes': renderMistakes(view); break;
      default: renderDashboard(view);
    }
  }
  function initializeSourceComposer() {
    $$('.source-kind-tab').forEach(tab => tab.addEventListener('click', () => setSourceKind(tab.dataset.sourceKind)));
    $('#source-form').addEventListener('submit', submitSource);
    $('#source-text').addEventListener('input', () => { $('#text-count').textContent = `${$('#source-text').value.length.toLocaleString()} characters`; });
    $('#source-file').addEventListener('change', () => {
      const file = $('#source-file').files[0];
      $('#file-label').textContent = file ? file.name : 'Drop a file here or browse';
      const error = $('#file-error');
      if (file && file.size > 20 * 1024 * 1024) { error.textContent = 'This file is larger than 20 MB. Choose a smaller file.'; error.classList.remove('hidden'); }
      else error.classList.add('hidden');
    });
    const drop = $('.file-drop');
    drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('is-dragging'); });
    drop.addEventListener('dragleave', () => drop.classList.remove('is-dragging'));
    drop.addEventListener('drop', e => {
      e.preventDefault(); drop.classList.remove('is-dragging'); const files = e.dataTransfer.files;
      if (files.length) { const dt = new DataTransfer(); dt.items.add(files[0]); $('#source-file').files = dt.files; $('#source-file').dispatchEvent(new Event('change')); setSourceKind('file'); }
    });
  }
  async function start() {
    initializeNavigation(); initializeSourceComposer();
    setBusy(true);
    try { await refreshBootstrap(); renderPage(); await ensurePageData(); renderPage(); }
    catch (error) { renderPage(); setNotice(error.message, 'error', true); }
    finally { setBusy(false); }
  }
  document.addEventListener('DOMContentLoaded', start);
})();
