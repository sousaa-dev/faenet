// ═══════════════════════════════════════════════════════════════════
//  FaeNet app.js — Feed, Stories, Profile, DM, Hub, Explore, Notifs
// ═══════════════════════════════════════════════════════════════════
const ME = __USER__.username;
const MY_CURSO = __USER__.curso || 'Informática';

// ── Router ────────────────────────────────────────────────────────
window.addEventListener('popstate', routeFromURL);

function navigate(page, push = true) {
  const url = ['feed','explore','notifications'].includes(page) ? '/feed' : `/${page}`;
  if (push) history.pushState({ page }, '', url);
  renderPage(page);
  updateNav(page);
}

function routeFromURL() {
  const p = location.pathname;
  if (p.startsWith('/profile/')) { const u = p.replace('/profile/', ''); renderProfile(u); updateNav('profile'); }
  else if (p.startsWith('/messages/')) { const u = p.replace('/messages/', ''); renderMessages(u); updateNav('messages'); }
  else if (p === '/messages')  { renderMessages(); updateNav('messages'); }
  else if (p === '/hub')       { renderHub();      updateNav('hub'); }
  else if (p === '/profile')   { renderProfile(ME); updateNav('profile'); }
  else                         { renderFeed();     updateNav('feed'); }
}

function renderPage(page) {
  const map = { feed: renderFeed, explore: renderExplore, notifications: renderNotifications, messages: renderMessages, hub: renderHub };
  if (map[page]) map[page]();
  else if (page === 'profile') { history.pushState({}, '', '/profile'); renderProfile(ME); }
}

function updateNav(page) {
  document.querySelectorAll('.nav-link,.mn').forEach(el => el.classList.toggle('active', el.dataset.page === page));
}

// ── Init ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setSidebarAvatar(__USER__);
  updateComposeAvatar(__USER__);
  routeFromURL();
  loadBadges();
  loadSuggestions();
  document.querySelectorAll('.modal-overlay').forEach(el => el.addEventListener('click', e => { if (e.target === el) closeModal(el.id); }));
  // ping online every 30s
  setInterval(() => fetch('/api/me/online', { method: 'POST' }).catch(() => {}), 30000);
});

function setSidebarAvatar(u) {
  const el = document.getElementById('sidebar-avatar');
  if (!el) return;
  el.innerHTML = u.avatar_img ? `<img src="${u.avatar_img}" alt=""/>` : (u.avatar_text || '?');
}
function updateComposeAvatar(u) {
  const el = document.getElementById('compose-avatar');
  if (!el) return;
  el.innerHTML = u.avatar_img ? `<img src="${u.avatar_img}" alt=""/>` : (u.avatar_text || '?');
}

async function loadBadges() {
  try {
    const [nr, mr] = await Promise.all([fetch('/api/notifications'), fetch('/api/conversations')]);
    const notifs = await nr.json(); const convos = await mr.json();
    const un = Array.isArray(notifs) ? notifs.filter(n => !n.read).length : 0;
    const um = Array.isArray(convos) ? convos.reduce((s, c) => s + (c.unread || 0), 0) : 0;
    setBadge('notif-badge', un); setBadge('mob-notif-badge', un); setBadge('msg-badge', um);
  } catch (e) {}
}

function setBadge(id, n) {
  const el = document.getElementById(id);
  if (!el) return;
  if (n > 0) { el.textContent = n; el.classList.remove('hidden'); }
  else el.classList.add('hidden');
}

// ── Modals ────────────────────────────────────────────────────────
function openModal(id) { document.getElementById(id)?.classList.remove('hidden'); }
function closeModal(id) {
  document.getElementById(id)?.classList.add('hidden');
  if (id === 'story-modal') resetStoryModal();
  if (id === 'story-viewer') clearTimeout(storyAutoTimer);
}

// ── Helpers ───────────────────────────────────────────────────────
function esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>'); }
function setMain(html) { document.getElementById('main-content').innerHTML = html; }
function avHTML(u, cls) {
  return u && u.avatar_img
    ? `<div class="${cls}"><img src="${u.avatar_img}" alt=""/></div>`
    : `<div class="${cls}">${(u && u.avatar_text) || '?'}</div>`;
}
function updateCounter(tid, cid, max) {
  const el = document.getElementById(cid);
  if (el) el.textContent = max - (document.getElementById(tid)?.value.length || 0);
}
let rpSearchTimer;
function rpSearch(q) { clearTimeout(rpSearchTimer); rpSearchTimer = setTimeout(() => _rpSearch(q), 300); }

// ═══════════════════════════════════════════════════════════════════
//  FEED
// ═══════════════════════════════════════════════════════════════════
async function renderFeed() {
  setMain(`<div class="spinner-wrap"><div class="spinner"></div></div>`);
  const [sd, pd] = await Promise.all([fetch('/api/stories').then(r => r.json()), fetch('/api/posts').then(r => r.json())]);
  const postsHTML = Array.isArray(pd) && pd.length ? pd.map(renderPostCard).join('') :
    `<div class="empty-state"><div class="ei">📭</div><p>Nenhuma publicação.<br/>Siga pessoas para ver o feed!</p></div>`;
  setMain(`
    <div class="feed-title">Início</div>
    ${renderStoriesBar(sd)}
    <div class="quick-compose" onclick="openModal('post-modal')">
      ${avHTML(__USER__, 'post-av')}
      <div class="qc-placeholder">O que está acontecendo na FAETEC?</div>
    </div>
    <div id="posts-list">${postsHTML}</div>`);
}

// ── Stories Bar ───────────────────────────────────────────────────
function renderStoriesBar(data) {
  if (!Array.isArray(data)) data = [];
  const add = `<div class="story-bubble add-story" onclick="openModal('story-modal')">
    <div class="story-ring seen"><div class="story-av" style="font-size:24px;color:var(--brand)">+</div></div>
    <span class="story-username">Seu story</span></div>`;
  const items = data.map((u, i) => `
    <div class="story-bubble" onclick="openStoryViewer(${i},currentStoriesData)">
      <div class="story-ring ${u.has_unseen ? '' : 'seen'}">
        <div class="story-av">${u.avatar_img ? `<img src="${u.avatar_img}" alt=""/>` : u.avatar_text}</div>
      </div>
      <span class="story-username">${esc(u.username === ME ? 'Você' : u.name.split(' ')[0])}</span>
    </div>`).join('');
  // store for viewer
  window.currentStoriesData = data;
  return `<div class="stories-bar">${add}${items}</div>`;
}

// ── Story Viewer ──────────────────────────────────────────────────
let storyViewerData = [], storyViewerIdx = { user: 0, story: 0 }, storyAutoTimer = null;

async function openStoryViewer(userIdx, data) {
  if (data) storyViewerData = data;
  else { const r = await fetch('/api/stories'); storyViewerData = await r.json(); }
  if (!storyViewerData.length) return;
  storyViewerIdx = { user: userIdx || 0, story: 0 };
  showCurrentStory();
  openModal('story-viewer');
}

function showCurrentStory() {
  clearTimeout(storyAutoTimer);
  const { user, story } = storyViewerIdx;
  const ud = storyViewerData[user]; if (!ud) return closeModal('story-viewer');
  const s = ud.stories[story]; if (!s) return closeModal('story-viewer');
  document.getElementById('sv-image').src = s.image;
  document.getElementById('sv-name').textContent = ud.name;
  document.getElementById('sv-time').textContent = s.time || 'recentemente';
  document.getElementById('sv-caption').textContent = s.caption || '';
  const av = document.getElementById('sv-avatar');
  av.innerHTML = ud.avatar_img ? `<img src="${ud.avatar_img}" alt=""/>` : ud.avatar_text;
  // delete button — only my stories
  const actEl = document.getElementById('sv-actions');
  actEl.innerHTML = s.username === ME
    ? `<button class="sv-delete-btn" onclick="deleteStory('${s.id}')">🗑 Apagar</button>` : '';
  // progress bar reset
  const pb = document.getElementById('sv-progress');
  pb.style.animation = 'none'; pb.offsetHeight; pb.style.animation = '';
  fetch(`/api/stories/${s.id}/view`, { method: 'POST' }).catch(() => {});
  storyAutoTimer = setTimeout(() => storyNav(1), 5200);
}

function storyNav(dir) {
  clearTimeout(storyAutoTimer);
  const { user, story } = storyViewerIdx;
  const ud = storyViewerData[user]; if (!ud) return;
  const ns = story + dir;
  if (ns >= 0 && ns < ud.stories.length) storyViewerIdx.story = ns;
  else {
    const nu = user + dir;
    if (nu >= 0 && nu < storyViewerData.length) storyViewerIdx = { user: nu, story: 0 };
    else return closeModal('story-viewer');
  }
  showCurrentStory();
}

async function deleteStory(sid) {
  if (!confirm('Apagar este story?')) return;
  await fetch(`/api/stories/${sid}/delete`, { method: 'POST' });
  closeModal('story-viewer');
  renderFeed();
}

let storyImageB64 = null;
function handleStoryImage(e) {
  const file = e.target.files[0]; if (!file) return;
  const r = new FileReader();
  r.onload = ev => {
    storyImageB64 = ev.target.result;
    document.getElementById('story-preview-img').src = storyImageB64;
    document.getElementById('story-preview-img').classList.remove('hidden');
    document.getElementById('story-upload-area').classList.add('hidden');
    document.getElementById('story-caption').classList.remove('hidden');
    document.getElementById('story-submit-btn').disabled = false;
  };
  r.readAsDataURL(file);
}

async function submitStory() {
  if (!storyImageB64) return;
  const btn = document.getElementById('story-submit-btn');
  btn.disabled = true; btn.textContent = 'Publicando...';
  await fetch('/api/stories', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: storyImageB64, caption: document.getElementById('story-caption').value }) });
  closeModal('story-modal'); renderFeed();
}

function resetStoryModal() {
  storyImageB64 = null;
  document.getElementById('story-preview-img').src = '';
  document.getElementById('story-preview-img').classList.add('hidden');
  document.getElementById('story-upload-area').classList.remove('hidden');
  document.getElementById('story-caption').classList.add('hidden');
  document.getElementById('story-caption').value = '';
  const btn = document.getElementById('story-submit-btn');
  btn.disabled = true; btn.textContent = 'Publicar story';
  document.getElementById('story-img-input').value = '';
}

// ── Post cards ────────────────────────────────────────────────────
function renderPostCard(p) {
  const mine = p.username === ME;
  const likeIcon = p.liked
    ? `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`
    : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`;

  const saveIcon = `<svg viewBox="0 0 24 24" fill="${p.saved?'currentColor':'none'}" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>`;
  const repostIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17,1 21,5 17,9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7,23 3,19 7,15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>`;

  // Repost quote
  let repostHTML = '';
  if (p.repost_of) {
    repostHTML = `<div class="repost-label">↩ Repostou</div>
      <div class="repost-quote" onclick="goProfile('${esc(p.repost_of.username)}')">
        <div class="rq-name">${esc(p.repost_of.name)}</div>
        <div class="rq-content">${esc(p.repost_of.content || '')}</div>
        ${renderGallery(p.repost_of.images || [])}
      </div>`;
  }

  // Gallery
  const galleryHTML = renderGallery(p.images || []);

  // Poll
  const pollHTML = p.poll ? renderPoll(p.poll, p.id) : '';

  // Comments
  const cmtsHTML = (p.comments || []).map(c => renderCommentItem(c, p.id)).join('');

  return `<div class="post-card" id="pc-${p.id}">
    <div class="post-hd">
      ${avHTML(p, 'post-av')} 
      <div class="post-meta" onclick="goProfile('${p.username}')" style="cursor:pointer">
        <div class="post-name">${esc(p.name)}</div>
        <div class="post-turma">${esc(p.turma || '')}</div>
        <div class="post-time">${p.time || ''}</div>
      </div>
      <button class="post-menu-btn" onclick="togglePostMenu('${p.id}')">⋯</button>
    </div>
    ${repostHTML}
    ${p.content ? `<div class="post-body">${esc(p.content)}</div>` : ''}
    ${galleryHTML}
    ${pollHTML}
    <div class="post-actions">
      <button class="act-btn ${p.liked ? 'liked' : ''}" id="like-btn-${p.id}" onclick="toggleLike('${p.id}')">
        ${likeIcon}<span id="like-count-${p.id}">${p.like_count || 0}</span>
      </button>
      <button class="act-btn" onclick="toggleComments('${p.id}')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span id="cmt-count-${p.id}">${(p.comments || []).length}</span>
      </button>
      <button class="act-btn ${p.reposted ? 'reposted' : ''}" id="repost-btn-${p.id}" onclick="toggleRepost('${p.id}')" title="Repostar">
        ${repostIcon}<span id="repost-count-${p.id}">${p.repost_count || 0}</span>
      </button>
      <button class="act-btn ${p.saved ? 'saved' : ''}" id="save-btn-${p.id}" onclick="toggleSave('${p.id}')" title="Salvar">
        ${saveIcon}
      </button>
    </div>
    <div class="comments-area hidden" id="cmt-area-${p.id}">
      <div id="cmt-list-${p.id}">${cmtsHTML}</div>
      <div id="reply-indicator-${p.id}"></div>
      <div class="cmt-input-row">
        <input class="cmt-input" id="cmt-inp-${p.id}" placeholder="Comentar..." onkeydown="if(event.key==='Enter')sendComment('${p.id}')"/>
        <button class="cmt-send" onclick="sendComment('${p.id}')">→</button>
      </div>
    </div>
  </div>`;
}

function renderGallery(images) {
  if (!images || !images.length) return '';
  const n = images.length;
  const cls = n === 1 ? 'g1' : n === 2 ? 'g2' : n === 3 ? 'g3' : n === 4 ? 'g4' : 'gm';
  if (n === 1) return `<div class="post-gallery g1" onclick="openImageFull('${images[0]}')"><img src="${images[0]}" alt=""/></div>`;
  if (n === 2) return `<div class="post-gallery g2">${images.map(src => `<img src="${src}" onclick="openImageFull('${src}')" alt=""/>`).join('')}</div>`;
  if (n === 3) return `<div class="post-gallery g3"><div class="gi0"><img src="${images[0]}" onclick="openImageFull('${images[0]}')" alt=""/></div><div class="gi1"><img src="${images[1]}" onclick="openImageFull('${images[1]}')" alt=""/></div><div class="gi2"><img src="${images[2]}" onclick="openImageFull('${images[2]}')" alt=""/></div></div>`;
  if (n === 4) return `<div class="post-gallery g4">${images.map(src => `<img src="${src}" onclick="openImageFull('${src}')" alt=""/>`).join('')}</div>`;
  // 5+
  const shown = images.slice(0, 4);
  const more = n - 4;
  return `<div class="post-gallery gm">${shown.map((src, i) => i < 3
    ? `<img src="${src}" onclick="openImageFull('${src}')" alt=""/>`
    : `<div class="gm-more" onclick="openImageFull('${src}')"><img src="${src}" alt=""/><div class="gm-more-lbl">+${more}</div></div>`).join('')}</div>`;
}

function renderPoll(poll, pid) {
  const total = poll.total || 0;
  const voted = poll.voted;
  const opts = (poll.options || []).map(opt => {
    const count = (poll.votes?.[opt] || []).length;
    const pct = total > 0 ? Math.round(count / total * 100) : 0;
    return `<div class="poll-option ${voted === opt ? 'voted' : ''} ${voted ? 'no-vote' : ''}" onclick="${voted ? '' : `votePoll('${pid}','${opt.replace(/'/g,"\\'")}');return false`}">
      <div class="poll-bar" style="width:${pct}%"></div>
      <div class="poll-opt-label">${esc(opt)}${voted === opt ? ' ✓' : ''}</div>
      ${voted ? `<div class="poll-opt-pct">${pct}%</div>` : ''}
    </div>`;
  }).join('');
  return `<div class="post-poll"><div class="poll-question">📊 ${esc(poll.question)}</div>${opts}<div class="poll-meta">${total} voto${total !== 1 ? 's' : ''}</div></div>`;
}

function renderCommentItem(c, pid) {
  return `<div class="comment-item" id="c-${c.id}">
    ${avHTML(c, 'cmt-av')}
    <div class="cmt-body">
      ${c.reply_to ? `<div class="cmt-reply-to">↩ respondendo a um comentário</div>` : ''}
      <div class="cmt-name">${esc(c.user)}</div>
      <div class="cmt-text">${esc(c.text)}</div>
      <div class="cmt-footer">
        <span class="cmt-time">${c.time || ''}</span>
        <button class="cmt-reply-btn" onclick="setReply('${pid}','${c.id}','${esc(c.user)}')">Responder</button>
      </div>
    </div>
  </div>`;
}

// Context menu
let openCtxMenu = null;
function togglePostMenu(pid) {
  // close others
  document.querySelectorAll('.post-ctx-menu').forEach(el => el.remove());
  if (openCtxMenu === pid) { openCtxMenu = null; return; }
  openCtxMenu = pid;
  const card = document.getElementById(`pc-${pid}`);
  if (!card) return;
  const isOwner = card.querySelector('.post-name')?.textContent === __USER__.name || true; // check via data
  const menu = document.createElement('div');
  menu.className = 'post-ctx-menu';
  menu.id = `ctx-${pid}`;
  // We'll check ownership server-side on delete
  menu.innerHTML = `
    <div class="ctx-item" onclick="toggleSave('${pid}');closeCtx()">🔖 Salvar publicação</div>
    <div class="ctx-item" onclick="toggleRepost('${pid}');closeCtx()">↩ Repostar</div>
    <div class="ctx-item danger" onclick="deletePost('${pid}')">🗑 Apagar publicação</div>`;
  card.style.position = 'relative';
  card.appendChild(menu);
  // close on outside click
  setTimeout(() => document.addEventListener('click', closeCtxOnce, { once: true }), 0);
}

function closeCtxOnce() { document.querySelectorAll('.post-ctx-menu').forEach(el => el.remove()); openCtxMenu = null; }
function closeCtx() { closeCtxOnce(); }

// Post actions
async function toggleLike(pid) {
  const r = await fetch(`/api/posts/${pid}/like`, { method: 'POST' }); const d = await r.json();
  const btn = document.getElementById(`like-btn-${pid}`); if (!btn) return;
  btn.classList.toggle('liked', d.liked);
  btn.querySelector('svg').setAttribute('fill', d.liked ? 'currentColor' : 'none');
  document.getElementById(`like-count-${pid}`).textContent = d.count;
}

async function toggleSave(pid) {
  const r = await fetch(`/api/posts/${pid}/save`, { method: 'POST' }); const d = await r.json();
  const btn = document.getElementById(`save-btn-${pid}`); if (!btn) return;
  btn.classList.toggle('saved', d.saved);
  btn.querySelector('svg').setAttribute('fill', d.saved ? 'currentColor' : 'none');
  showToast(d.saved ? '🔖 Publicação salva!' : 'Publicação removida dos salvos');
}

async function toggleRepost(pid) {
  const r = await fetch(`/api/posts/${pid}/repost`, { method: 'POST' }); const d = await r.json();
  const btn = document.getElementById(`repost-btn-${pid}`); if (btn) btn.classList.toggle('reposted', d.reposted);
  document.getElementById(`repost-count-${pid}`)?.textContent !== undefined && (document.getElementById(`repost-count-${pid}`).textContent = d.count);
  if (d.reposted) { showToast('↩ Repostado no seu perfil!'); setTimeout(renderFeed, 500); }
}

async function votePoll(pid, option) {
  const r = await fetch(`/api/posts/${pid}/poll/vote`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ option }) });
  const d = await r.json();
  const card = document.getElementById(`pc-${pid}`); if (!card) return;
  const pollEl = card.querySelector('.post-poll'); if (!pollEl) return;
  const total = d.total;
  card.querySelectorAll('.poll-option').forEach((el, i) => {
    const opt = card.querySelectorAll('.poll-opt-label')[i]?.textContent.replace(' ✓', '');
    const count = (d.votes[opt] || []).length;
    const pct = total > 0 ? Math.round(count / total * 100) : 0;
    el.querySelector('.poll-bar').style.width = pct + '%';
    el.classList.add('no-vote');
    el.removeAttribute('onclick');
    if (!el.querySelector('.poll-opt-pct')) { const s = document.createElement('div'); s.className = 'poll-opt-pct'; el.appendChild(s); }
    el.querySelector('.poll-opt-pct').textContent = pct + '%';
    if (opt === d.voted) { el.classList.add('voted'); el.querySelector('.poll-opt-label').textContent = opt + ' ✓'; }
  });
  card.querySelector('.poll-meta').textContent = `${total} voto${total !== 1 ? 's' : ''}`;
}

async function deletePost(pid) {
  if (!confirm('Apagar esta publicação?')) return;
  closeCtx();
  const r = await fetch(`/api/posts/${pid}/delete`, { method: 'POST' });
  if (r.ok) { document.getElementById(`pc-${pid}`)?.remove(); showToast('Publicação apagada'); }
  else showToast('Você só pode apagar suas próprias publicações');
}

function toggleComments(pid) {
  const a = document.getElementById(`cmt-area-${pid}`);
  if (a) { a.classList.toggle('hidden'); document.getElementById(`cmt-inp-${pid}`)?.focus(); }
}

let replyingTo = {}; // pid -> {id, name}
function setReply(pid, cid, name) {
  replyingTo[pid] = { id: cid, name };
  const ri = document.getElementById(`reply-indicator-${pid}`);
  if (ri) ri.innerHTML = `<div class="reply-indicator"><span>↩ Respondendo a <strong>${esc(name)}</strong></span><button onclick="clearReply('${pid}')">✕</button></div>`;
  document.getElementById(`cmt-inp-${pid}`)?.focus();
}
function clearReply(pid) {
  delete replyingTo[pid];
  const ri = document.getElementById(`reply-indicator-${pid}`);
  if (ri) ri.innerHTML = '';
}

async function sendComment(pid) {
  const inp = document.getElementById(`cmt-inp-${pid}`);
  const text = inp.value.trim(); if (!text) return;
  const reply_to = replyingTo[pid]?.id || null;
  const r = await fetch(`/api/posts/${pid}/comment`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, reply_to }) });
  const c = await r.json();
  const list = document.getElementById(`cmt-list-${pid}`);
  list.insertAdjacentHTML('beforeend', renderCommentItem(c, pid));
  inp.value = ''; clearReply(pid);
  const cc = document.getElementById(`cmt-count-${pid}`);
  if (cc) cc.textContent = parseInt(cc.textContent || 0) + 1;
}

// ── Post Modal ────────────────────────────────────────────────────
let postImagesB64 = [];
let pollBuilderOpen = false;

function handlePostImages(e) {
  const files = Array.from(e.target.files); if (!files.length) return;
  files.forEach(file => {
    const r = new FileReader();
    r.onload = ev => {
      postImagesB64.push(ev.target.result);
      renderImageStrip();
    };
    r.readAsDataURL(file);
  });
  e.target.value = '';
}

function renderImageStrip() {
  const strip = document.getElementById('img-preview-strip');
  strip.innerHTML = postImagesB64.map((b64, i) => `
    <div class="img-thumb">
      <img src="${b64}" alt=""/>
      <button class="img-thumb-rm" onclick="removePostImage(${i})">✕</button>
    </div>`).join('') +
    (postImagesB64.length < 6 ? `<div class="img-add-more" onclick="document.getElementById('post-img-input').click()">+</div>` : '');
}

function removePostImage(i) {
  postImagesB64.splice(i, 1);
  renderImageStrip();
}

let pollOptions = ['', ''];
function togglePollBuilder() {
  pollBuilderOpen = !pollBuilderOpen;
  const wrap = document.getElementById('poll-builder-wrap');
  if (!pollBuilderOpen) { wrap.innerHTML = ''; pollOptions = ['', '']; return; }
  renderPollBuilder();
}

function renderPollBuilder() {
  const wrap = document.getElementById('poll-builder-wrap');
  wrap.innerHTML = `<div class="poll-builder">
    <input id="poll-question" placeholder="Pergunta da enquete..." value="${esc(pollOptions._q || '')}"/>
    ${pollOptions.map((o, i) => `<div class="poll-opt-row">
      <input placeholder="Opção ${i + 1}" value="${esc(o)}" oninput="pollOptions[${i}]=this.value"/>
      ${i >= 2 ? `<button class="rm-poll-opt" onclick="removePollOpt(${i})">✕</button>` : ''}
    </div>`).join('')}
    ${pollOptions.length < 4 ? `<button class="add-poll-opt" onclick="addPollOpt()">+ Adicionar opção</button>` : ''}
    <button class="rm-poll-btn" onclick="togglePollBuilder()">Remover enquete</button>
  </div>`;
}

function addPollOpt() { pollOptions.push(''); renderPollBuilder(); }
function removePollOpt(i) { pollOptions.splice(i, 1); renderPollBuilder(); }

async function submitPost() {
  const content = document.getElementById('post-text').value.trim();
  let poll = null;
  if (pollBuilderOpen) {
    const q = document.getElementById('poll-question')?.value.trim();
    const opts = pollOptions.filter(o => o.trim());
    if (q && opts.length >= 2) poll = { question: q, options: opts };
  }
  if (!content && !postImagesB64.length && !poll) return;
  const btn = document.querySelector('#post-modal .btn-brand.sm');
  btn.disabled = true; btn.textContent = 'Publicando...';
  const r = await fetch('/api/posts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content, images: postImagesB64, poll }) });
  const post = await r.json();
  closeModal('post-modal');
  document.getElementById('post-text').value = '';
  postImagesB64 = []; pollBuilderOpen = false; pollOptions = ['', ''];
  document.getElementById('img-preview-strip').innerHTML = '';
  document.getElementById('poll-builder-wrap').innerHTML = '';
  updateCounter('post-text', 'post-counter', 500);
  btn.disabled = false; btn.textContent = 'Publicar';
  const list = document.getElementById('posts-list');
  if (list) { list.querySelector('.empty-state')?.remove(); list.insertAdjacentHTML('afterbegin', renderPostCard(post)); }
}

// ═══════════════════════════════════════════════════════════════════
//  PROFILE
// ═══════════════════════════════════════════════════════════════════
let profileActiveTab = 'posts';

async function renderProfile(username) {
  setMain(`<div class="spinner-wrap"><div class="spinner"></div></div>`);
  const [ur, pr, mr] = await Promise.all([fetch(`/api/users/${username}`), fetch(`/api/posts/user/${username}`), fetch('/api/me')]);
  const user = await ur.json(); const posts = await pr.json(); const me = await mr.json();
  if (user.error) { setMain(`<div class="empty-state"><div class="ei">😕</div><p>Usuário não encontrado.</p></div>`); return; }
  const isMe = username === ME;
  const isFollowing = (me.following || []).includes(username);

  // Banner
  const bannerHTML = user.banner_img
    ? `<div class="profile-banner"${isMe ? ' onclick="document.getElementById(\'ep-banner-input\').click()"' : ''}>
        <img src="${user.banner_img}" alt="banner"/>
        ${isMe ? `<div class="banner-edit-hint"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21,15 16,10 5,21"/></svg> Trocar banner</div>` : ''}
      </div>`
    : `<div class="profile-banner"${isMe ? ' onclick="document.getElementById(\'ep-banner-input\').click()"' : ''}>
        <div class="profile-banner-bg"></div>
        ${isMe ? `<div class="banner-edit-hint"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21,15 16,10 5,21"/></svg> Adicionar banner</div>` : ''}
      </div>`;

  const bigAv = user.avatar_img
    ? `<div class="profile-big-av"><img src="${user.avatar_img}" alt=""/></div>`
    : `<div class="profile-big-av">${user.avatar_text || '?'}</div>`;

  const actions = isMe
    ? `<div class="profile-actions">
        <button class="btn-outline" onclick="openEditProfile()">Editar perfil</button>
        <button class="btn-outline" onclick="navigate('messages')">Mensagens</button>
       </div>`
    : `<div class="profile-actions">
        <button class="btn-brand-outline ${isFollowing ? 'on' : ''}" id="follow-btn" onclick="toggleFollow('${username}')">${isFollowing ? 'Seguindo' : 'Seguir'}</button>
        <button class="btn-msg" onclick="goMessages('${username}')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>Mensagem
        </button>
       </div>`;

  const postsHTML = Array.isArray(posts) && posts.length ? posts.map(renderPostCard).join('') :
    `<div class="empty-state"><div class="ei">📝</div><p>Nenhuma publicação ainda.</p></div>`;

  setMain(`
    <div class="profile-box">
      ${bannerHTML}
      <div class="profile-body">
        ${bigAv}
        <div class="profile-name-row">
          <div>
            <div class="profile-name">${esc(user.name)}</div>
            <div class="profile-uname">@${user.username} ${user.online ? '<span class="online-dot-sm"></span>' : ''}</div>
            <div class="profile-turma">${esc(user.turma || user.curso || '')}</div>
          </div>
          ${actions}
        </div>
        ${user.bio ? `<div class="profile-bio">${esc(user.bio)}</div>` : ''}
        <div class="profile-stats">
          <div class="stat"><div class="stat-n">${(posts || []).length}</div><div class="stat-l">Posts</div></div>
          <div class="stat"><div class="stat-n" id="followers-n">${(user.followers || []).length}</div><div class="stat-l">Seguidores</div></div>
          <div class="stat"><div class="stat-n">${(user.following || []).length}</div><div class="stat-l">Seguindo</div></div>
        </div>
      </div>
    </div>
    <div class="profile-nav-tabs">
      <button class="profile-tab active" data-tab="posts" onclick="switchProfileTab('${username}','posts',this)">Publicações</button>
      ${isMe ? `<button class="profile-tab" data-tab="saved" onclick="switchProfileTab('${username}','saved',this)">Salvos</button>` : ''}
    </div>
    <div id="profile-posts">${postsHTML}</div>`);

  if (isMe) {
    // Prefill edit modal
    document.getElementById('ep-name').value = user.name;
    document.getElementById('ep-bio').value = user.bio || '';
    document.getElementById('ep-turma').value = user.turma || '';
    updateCounter('ep-bio', 'ep-bio-counter', 200);
    const epAv = document.getElementById('ep-avatar-preview');
    epAv.innerHTML = user.avatar_img ? `<img src="${user.avatar_img}" alt=""/>` : user.avatar_text;
    // Banner preview in modal
    const bp = document.getElementById('ep-banner-preview');
    if (bp && user.banner_img) bp.style.backgroundImage = `url(${user.banner_img})`;
    // Wire up inline banner click
    const bannerEl = document.querySelector('.profile-banner');
    if (bannerEl) bannerEl.addEventListener('click', () => document.getElementById('ep-banner-input')?.click());
  }
}

async function switchProfileTab(username, tab, btn) {
  document.querySelectorAll('.profile-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const el = document.getElementById('profile-posts');
  el.innerHTML = `<div class="spinner-wrap"><div class="spinner"></div></div>`;
  if (tab === 'saved') {
    const r = await fetch('/api/posts/saved'); const posts = await r.json();
    el.innerHTML = posts.length ? posts.map(renderPostCard).join('') :
      `<div class="empty-state"><div class="ei">🔖</div><p>Nenhuma publicação salva.</p></div>`;
  } else {
    const r = await fetch(`/api/posts/user/${username}`); const posts = await r.json();
    el.innerHTML = posts.length ? posts.map(renderPostCard).join('') :
      `<div class="empty-state"><div class="ei">📝</div><p>Nenhuma publicação ainda.</p></div>`;
  }
}

function openEditProfile() { openModal('edit-profile-modal'); }

let newAvatarB64 = null, newBannerB64 = null;
function handleProfileImage(e) {
  const f = e.target.files[0]; if (!f) return;
  const r = new FileReader(); r.onload = ev => {
    newAvatarB64 = ev.target.result;
    document.getElementById('ep-avatar-preview').innerHTML = `<img src="${newAvatarB64}" alt=""/>`;
  }; r.readAsDataURL(f);
}
function handleBannerImage(e) {
  const f = e.target.files[0]; if (!f) return;
  const r = new FileReader(); r.onload = ev => {
    newBannerB64 = ev.target.result;
    const bp = document.getElementById('ep-banner-preview');
    bp.style.backgroundImage = `url(${newBannerB64})`;
    bp.style.backgroundSize = 'cover';
    bp.style.backgroundPosition = 'center';
    bp.querySelector('div')?.style && (bp.querySelector('div').style.display = 'none');
  }; r.readAsDataURL(f);
}

async function saveProfile() {
  const payload = { name: document.getElementById('ep-name').value.trim(), bio: document.getElementById('ep-bio').value, turma: document.getElementById('ep-turma').value.trim() };
  if (newAvatarB64) payload.avatar_img = newAvatarB64;
  if (newBannerB64) payload.banner_img = newBannerB64;
  const r = await fetch('/api/me/edit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const updated = await r.json();
  Object.assign(__USER__, updated);
  newAvatarB64 = null; newBannerB64 = null;
  setSidebarAvatar(updated); updateComposeAvatar(updated);
  closeModal('edit-profile-modal');
  renderProfile(ME);
  showToast('✅ Perfil atualizado!');
}

async function toggleFollow(username) {
  const r = await fetch(`/api/users/${username}/follow`, { method: 'POST' }); const d = await r.json();
  const btn = document.getElementById('follow-btn');
  if (btn) { btn.textContent = d.following ? 'Seguindo' : 'Seguir'; btn.classList.toggle('on', d.following); }
  const fn = document.getElementById('followers-n'); if (fn) fn.textContent = d.followers_count;
}

function goProfile(username) { history.pushState({}, '', `/profile/${username}`); renderProfile(username); updateNav('profile'); }
function goMessages(username) { history.pushState({}, '', `/messages/${username}`); renderMessages(username); updateNav('messages'); }

// ═══════════════════════════════════════════════════════════════════
//  MESSAGES
// ═══════════════════════════════════════════════════════════════════
let activeChatUser = null, replyMsg = null;

async function renderMessages(withUser = null) {
  setMain(`<div class="spinner-wrap"><div class="spinner"></div></div>`);
  const r = await fetch('/api/conversations'); const convos = await r.json();
  const list = Array.isArray(convos) ? convos : [];

  const convosHTML = list.length ? list.map(c => `
    <div class="convo-item ${withUser === c.with ? 'active' : ''}" id="ci-${c.with}" onclick="openChat('${c.with}')">
      <div class="convo-av-wrap">
        ${c.avatar_img ? `<div class="convo-av"><img src="${c.avatar_img}" alt=""/></div>` : `<div class="convo-av">${c.avatar_text}</div>`}
        ${c.online ? `<div class="online-dot"></div>` : ''}
      </div>
      <div class="convo-info">
        <div class="convo-name">${esc(c.name)}</div>
        <div class="convo-last">${esc(c.last_message || '')}</div>
      </div>
      <div class="convo-meta">
        <div class="convo-time">${c.last_time || ''}</div>
        ${c.unread ? `<div class="convo-unread">${c.unread}</div>` : ''}
      </div>
    </div>`).join('')
    : `<div class="empty-state" style="padding:30px 16px"><div class="ei">💬</div><p style="font-size:13px">Nenhuma conversa ainda</p></div>`;

  setMain(`<div class="messages-layout">
    <div class="convos-list">
      <div class="convos-hd">Mensagens</div>
      <div class="convo-search"><input placeholder="Buscar conversa..." oninput="filterConvos(this.value)"/></div>
      <div id="convos-body">${convosHTML}</div>
    </div>
    <div class="chat-area" id="chat-panel">
      <div class="chat-empty"><div class="ei">💬</div><p>Selecione uma conversa</p></div>
    </div>
  </div>`);

  if (withUser) openChat(withUser);
}

function filterConvos(q) {
  document.querySelectorAll('.convo-item').forEach(el => {
    const name = el.querySelector('.convo-name')?.textContent.toLowerCase() || '';
    el.style.display = name.includes(q.toLowerCase()) ? '' : 'none';
  });
}

async function openChat(username) {
  activeChatUser = username;
  const ur = await fetch(`/api/users/${username}`); const u = await ur.json();
  const panel = document.getElementById('chat-panel'); if (!panel) return;

  const statusHTML = u.online
    ? `<span class="chat-hd-status status-online">● online</span>`
    : `<span class="chat-hd-status status-offline">● offline</span>`;

  panel.innerHTML = `
    <div class="chat-hd">
      <div class="chat-hd-av" style="position:relative">
        ${u.avatar_img ? `<img src="${u.avatar_img}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%"/>` : u.avatar_text}
        ${u.online ? `<div class="online-dot"></div>` : ''}
      </div>
      <div class="chat-hd-info">
        <div class="chat-hd-name" onclick="goProfile('${username}')">${esc(u.name)}</div>
        ${statusHTML}
      </div>
    </div>
    <div class="chat-messages" id="chat-msgs"></div>
    <div class="chat-input-area">
      <div class="chat-reply-bar hidden" id="chat-reply-bar">
        <div class="rb-text" id="rb-text"></div>
        <button class="rb-cancel" onclick="cancelReply()">✕</button>
      </div>
      <div class="chat-input-row">
        <button class="chat-attach-btn" onclick="document.getElementById('chat-file-input').click()" title="Enviar arquivo">📎</button>
        <button class="chat-attach-btn" onclick="document.getElementById('chat-img-input').click()" title="Enviar imagem">🖼</button>
        <button class="emoji-picker-btn" onclick="toggleEmojiPanel()">😊</button>
        <input type="file" id="chat-file-input" class="hidden" onchange="sendFileMsg(event,'file')"/>
        <input type="file" id="chat-img-input" accept="image/*" class="hidden" onchange="sendFileMsg(event,'image')"/>
        <input class="chat-input" id="chat-input" placeholder="Mensagem..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChatMsg()}"/>
        <button class="btn-brand sm" onclick="sendChatMsg()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/></svg>
        </button>
      </div>
    </div>`;

  // Highlight convo
  document.querySelectorAll('.convo-item').forEach(el => el.classList.remove('active'));
  document.getElementById(`ci-${username}`)?.classList.add('active');

  await loadChatMessages(username);
}

async function loadChatMessages(username) {
  const r = await fetch(`/api/messages/${username}`); const msgs = await r.json();
  const el = document.getElementById('chat-msgs'); if (!el) return;
  el.innerHTML = (Array.isArray(msgs) && msgs.length) ? msgs.map(renderMsg).join('') :
    `<div class="chat-empty"><div class="ei">👋</div><p style="font-size:13px">Diga olá!</p></div>`;
  el.scrollTop = el.scrollHeight;
}

function renderMsg(m) {
  const mine = m.from === ME;
  let innerHTML = '';
  if (m.reply_to) innerHTML += `<div class="msg-reply-preview">↩ ${esc(m.reply_to.text || 'mensagem')}</div>`;
  if (m.file_url && m.file_type === 'image')
    innerHTML += `<img class="msg-img-attach" src="${m.file_url}" alt="" onclick="openImageFull('${m.file_url}')"/>`;
  else if (m.file_url)
    innerHTML += `<a class="msg-file" href="${m.file_url}" target="_blank" download="${m.file_name}">
      <div class="msg-file-icon">📄</div>
      <div class="msg-file-info"><div class="msg-file-name">${esc(m.file_name || 'arquivo')}</div><div class="msg-file-lbl">Clique para abrir</div></div></a>`;
  if (m.text) innerHTML += `<div class="msg-text">${esc(m.text)}</div>`;

  return `<div class="msg-row ${mine ? 'mine' : 'theirs'}">
    <div class="msg-bubble ${mine ? 'mine' : 'theirs'}">
      ${innerHTML}
      <div class="msg-footer">
        ${mine ? '' : ''}<span class="msg-time">${m.time || ''}</span>
        <button class="msg-reply-btn" onclick="startReply('${esc(m.text||'')}')">↩</button>
      </div>
    </div>
  </div>`;
}

function startReply(text) {
  replyMsg = { text };
  const bar = document.getElementById('chat-reply-bar');
  const rb = document.getElementById('rb-text');
  if (bar && rb) { rb.innerHTML = `Respondendo: <strong>${esc(text.substring(0, 60))}${text.length > 60 ? '...' : ''}</strong>`; bar.classList.remove('hidden'); }
  document.getElementById('chat-input')?.focus();
}

function cancelReply() {
  replyMsg = null;
  document.getElementById('chat-reply-bar')?.classList.add('hidden');
}

async function sendChatMsg() {
  const inp = document.getElementById('chat-input');
  const text = inp.value.trim(); if (!text && !replyMsg) return;
  inp.value = '';
  const body = { text };
  if (replyMsg) { body.reply_to = replyMsg; cancelReply(); }
  const r = await fetch(`/api/messages/${activeChatUser}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const msg = await r.json();
  appendMsg(msg);
}

async function sendFileMsg(e, type) {
  const file = e.target.files[0]; if (!file) return;
  e.target.value = '';
  const reader = new FileReader();
  reader.onload = async ev => {
    const body = type === 'image'
      ? { image_b64: ev.target.result, text: '' }
      : { file_b64: ev.target.result, file_name: file.name, file_type: 'file', text: '' };
    const r = await fetch(`/api/messages/${activeChatUser}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const msg = await r.json();
    appendMsg(msg);
  };
  reader.readAsDataURL(file);
}

function appendMsg(msg) {
  const el = document.getElementById('chat-msgs'); if (!el) return;
  el.querySelector('.chat-empty')?.remove();
  el.insertAdjacentHTML('beforeend', renderMsg(msg));
  el.scrollTop = el.scrollHeight;
}

// Emoji
const EMOJIS = ['😀','😂','😍','🥰','😎','🤔','😢','😡','👍','👎','❤️','🔥','🎉','💯','🙏','👏','😭','🤣','😊','😇','🥳','🤩','😴','🤦','🤷','💪','🫡','👀','✨','🎓','📚','💻','⚡','🚀','🌟'];
let emojiOpen = false;
function toggleEmojiPanel() {
  emojiOpen = !emojiOpen;
  const existing = document.getElementById('emoji-panel');
  if (existing) { existing.remove(); emojiOpen = false; return; }
  const panel = document.createElement('div');
  panel.id = 'emoji-panel'; panel.className = 'emoji-panel';
  panel.innerHTML = `<div class="emoji-grid">${EMOJIS.map(e => `<button class="emoji-btn" onclick="insertEmoji('${e}')">${e}</button>`).join('')}</div>`;
  document.querySelector('.chat-area')?.appendChild(panel);
  setTimeout(() => document.addEventListener('click', closeEmojiOnce, { once: true }), 0);
}
function closeEmojiOnce(e) { if (!e.target.closest('#emoji-panel') && !e.target.closest('.emoji-picker-btn')) { document.getElementById('emoji-panel')?.remove(); emojiOpen = false; } }
function insertEmoji(e) {
  const inp = document.getElementById('chat-input'); if (!inp) return;
  inp.value += e; inp.focus();
  document.getElementById('emoji-panel')?.remove(); emojiOpen = false;
}

// ═══════════════════════════════════════════════════════════════════
//  HUB
// ═══════════════════════════════════════════════════════════════════
let hubTab = 'estagios';

async function renderHub() {
  setMain(`<div class="spinner-wrap"><div class="spinner"></div></div>`);
  const r = await fetch(`/api/hub/${encodeURIComponent(MY_CURSO)}`); const data = await r.json();
  renderHubContent(data);
}

function renderHubContent(data, tab = hubTab) {
  hubTab = tab;
  const tabs = [['estagios','🎯 Estágios'],['provas','📋 Provas'],['forum','💬 Fórum']];
  const tabsHTML = tabs.map(([t, l]) => `<button class="hub-tab ${tab === t ? 'active' : ''}" onclick="switchHubTab('${t}')">${l}</button>`).join('');
  const content = tab === 'estagios' ? renderEstagios(data.estagios || []) : tab === 'provas' ? renderProvas(data.provas || []) : renderForum(data.forum || []);
  setMain(`<div class="hub-header"><div class="hub-title">Hub do Curso</div><div class="hub-curso">📚 ${MY_CURSO}</div></div>
    <div class="hub-tabs">${tabsHTML}</div><div id="hub-section">${content}</div>`);
}

async function switchHubTab(tab) {
  hubTab = tab;
  document.querySelectorAll('.hub-tab').forEach(b => b.classList.toggle('active', b.textContent.includes(tab === 'estagios' ? 'Estágio' : tab === 'provas' ? 'Prova' : 'Fórum')));
  const r = await fetch(`/api/hub/${encodeURIComponent(MY_CURSO)}`); const data = await r.json();
  document.getElementById('hub-section').innerHTML = tab === 'estagios' ? renderEstagios(data.estagios || []) : tab === 'provas' ? renderProvas(data.provas || []) : renderForum(data.forum || []);
}

function renderEstagios(items) {
  const list = items.length ? items.map(e => `<div class="hub-card"><div class="hub-card-title">${esc(e.title)}</div><div class="hub-card-company">🏢 ${esc(e.company)}</div><div class="hub-card-desc">${esc(e.description)}</div><div class="hub-card-footer"><span class="hub-chip chip-deadline">⏰ ${e.deadline || 'N/A'}</span>${e.link && e.link !== '#' ? `<a class="hub-link" href="${e.link}" target="_blank">Ver vaga →</a>` : ''}</div></div>`).join('')
    : `<div class="empty-state"><div class="ei">🎯</div><p>Nenhuma vaga ainda.</p></div>`;
  return `<div class="hub-section"><div class="hub-action-row"><button class="btn-brand sm" onclick="openModal('hub-estagio-modal')">+ Nova vaga</button></div>${list}</div>`;
}

function renderProvas(items) {
  const list = items.length ? items.map(p => `<div class="hub-card"><div class="hub-card-title">${esc(p.title)}</div><span class="hub-chip chip-subject">📖 ${esc(p.subject)}</span><div class="hub-card-desc" style="margin-top:8px">${esc(p.description)}</div><div class="hub-card-footer" style="margin-top:8px"><span class="hub-chip chip-date">📅 ${p.date || 'N/A'}</span></div></div>`).join('')
    : `<div class="empty-state"><div class="ei">📋</div><p>Nenhum aviso ainda.</p></div>`;
  return `<div class="hub-section"><div class="hub-action-row"><button class="btn-brand sm" onclick="openModal('hub-prova-modal')">+ Novo aviso</button></div>${list}</div>`;
}

function renderForum(topics) {
  const list = topics.length ? topics.map(t => `<div class="forum-topic" onclick="openForumTopic('${t.id}')"><div class="ft-header">${avHTML(t, 'ft-av')}<div class="ft-meta"><div class="ft-title">${esc(t.title)}</div><div class="ft-name">${esc(t.name)}</div></div></div><div class="ft-content">${esc(t.content.substring(0, 140))}${t.content.length > 140 ? '...' : ''}</div><div class="ft-footer">${(t.tags || []).map(g => `<span class="ft-tag">${esc(g)}</span>`).join('')}${t.solved ? '<span class="ft-solved">✓ Resolvido</span>' : ''}<span class="ft-answers">${(t.answers || []).length} respostas</span></div></div>`).join('')
    : `<div class="empty-state"><div class="ei">💬</div><p>Nenhuma dúvida ainda.</p></div>`;
  return `<div class="hub-section"><div class="hub-action-row"><button class="btn-brand sm" onclick="openModal('hub-forum-modal')">+ Fazer pergunta</button></div>${list}</div>`;
}

async function openForumTopic(tid) {
  const r = await fetch(`/api/hub/${encodeURIComponent(MY_CURSO)}`); const data = await r.json();
  const t = data.forum.find(x => x.id === tid); if (!t) return;
  const answersHTML = (t.answers || []).map(a => `<div class="answer-card"><div class="answer-header">${avHTML(a, 'ans-av')}<div><div class="ans-name">${esc(a.name)}</div><div class="ans-time">${a.time || 'recentemente'}</div></div></div><div class="ans-content">${esc(a.content)}</div></div>`).join('');
  document.getElementById('hub-section').innerHTML = `
    <div class="topic-back" onclick="switchHubTab('forum')">← Voltar ao fórum</div>
    <div class="hub-card">
      <div class="ft-header">${avHTML(t, 'ft-av')}<div class="ft-meta"><div class="ft-title" style="font-size:16px">${esc(t.title)}</div><div class="ft-name">${esc(t.name)}</div></div>
      ${t.username === ME ? `<button class="btn-outline" style="font-size:11px;padding:4px 10px" onclick="toggleSolved('${tid}')">${t.solved ? 'Reabrir' : 'Marcar resolvido'}</button>` : ''}
      </div>
      <div class="ans-content" style="margin-top:8px">${esc(t.content)}</div>
      <div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">${(t.tags || []).map(g => `<span class="ft-tag">${esc(g)}</span>`).join('')}${t.solved ? '<span class="ft-solved">✓ Resolvido</span>' : ''}</div>
    </div>
    <div style="font-family:'Syne',sans-serif;font-size:13px;font-weight:700;color:var(--muted);margin:16px 0 10px">${(t.answers || []).length} RESPOSTAS</div>
    <div class="answers-list" id="answers-list">${answersHTML || `<div class="empty-state"><div class="ei">🤔</div><p>Seja o primeiro a responder!</p></div>`}</div>
    <div class="answer-input-area">
      <div style="font-size:13px;font-weight:600;margin-bottom:10px">Sua resposta</div>
      <textarea class="ans-textarea" id="answer-input" placeholder="Escreva sua resposta..." rows="4"></textarea>
      <button class="btn-brand w100" onclick="submitAnswer('${tid}')">Enviar resposta</button>
    </div>`;
}

async function submitAnswer(tid) {
  const content = document.getElementById('answer-input')?.value.trim(); if (!content) return;
  const r = await fetch(`/api/hub/${encodeURIComponent(MY_CURSO)}/forum/${tid}/answer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) });
  const a = await r.json();
  document.getElementById('answer-input').value = '';
  const list = document.getElementById('answers-list'); list.querySelector('.empty-state')?.remove();
  list.insertAdjacentHTML('beforeend', `<div class="answer-card"><div class="answer-header">${avHTML(a, 'ans-av')}<div><div class="ans-name">${esc(a.name)}</div><div class="ans-time">agora mesmo</div></div></div><div class="ans-content">${esc(a.content)}</div></div>`);
}

async function toggleSolved(tid) {
  await fetch(`/api/hub/${encodeURIComponent(MY_CURSO)}/forum/${tid}/solve`, { method: 'POST' });
  openForumTopic(tid);
}

async function submitEstagio() {
  const p = { title: document.getElementById('hb-est-title').value.trim(), company: document.getElementById('hb-est-company').value.trim(), description: document.getElementById('hb-est-desc').value.trim(), deadline: document.getElementById('hb-est-deadline').value, link: document.getElementById('hb-est-link').value.trim() || '#' };
  if (!p.title || !p.company) return;
  await fetch(`/api/hub/${encodeURIComponent(MY_CURSO)}/estagios`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) });
  closeModal('hub-estagio-modal'); switchHubTab('estagios');
}

async function submitProva() {
  const p = { title: document.getElementById('hb-pv-title').value.trim(), subject: document.getElementById('hb-pv-subject').value.trim(), date: document.getElementById('hb-pv-date').value, description: document.getElementById('hb-pv-desc').value.trim() };
  if (!p.title || !p.subject) return;
  await fetch(`/api/hub/${encodeURIComponent(MY_CURSO)}/provas`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) });
  closeModal('hub-prova-modal'); switchHubTab('provas');
}

async function submitForumTopic() {
  const tags = document.getElementById('hb-fo-tags').value.split(',').map(t => t.trim()).filter(Boolean);
  const p = { title: document.getElementById('hb-fo-title').value.trim(), content: document.getElementById('hb-fo-content').value.trim(), tags };
  if (!p.title || !p.content) return;
  await fetch(`/api/hub/${encodeURIComponent(MY_CURSO)}/forum`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) });
  closeModal('hub-forum-modal'); switchHubTab('forum');
}

// ═══════════════════════════════════════════════════════════════════
//  EXPLORE
// ═══════════════════════════════════════════════════════════════════
async function renderExplore() {
  setMain(`<div class="spinner-wrap"><div class="spinner"></div></div>`);
  const [ur, pr] = await Promise.all([fetch('/api/users/search?q='), fetch('/api/posts/all')]);
  const users = await ur.json(); const posts = await pr.json();
  const usersHTML = users.filter(u => u.username !== ME).map(u => `
    <div class="person-card" onclick="goProfile('${u.username}')">
      ${u.avatar_img ? `<div class="pc-av"><img src="${u.avatar_img}" alt=""/></div>` : `<div class="pc-av">${u.avatar_text}</div>`}
      ${u.online ? `<div style="font-size:9px;color:var(--success)">● online</div>` : ''}
      <div class="pc-name">${esc(u.name)}</div>
      <div class="pc-turma">${esc(u.turma || '')}</div>
    </div>`).join('');
  const postsHTML = Array.isArray(posts) && posts.length ? posts.map(renderPostCard).join('') :
    `<div class="empty-state"><div class="ei">📭</div><p>Nenhuma publicação.</p></div>`;
  setMain(`
    <div class="explore-title">Explorar</div>
    <div class="explore-search-bar">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input type="text" id="explore-search" placeholder="Buscar pessoas pelo nome ou usuário..." oninput="exploreSearch(this.value)" autocomplete="off"/>
    </div>
    <div id="explore-search-results" class="hidden" style="margin-bottom:20px"></div>
    <div id="explore-people-section">
      <div class="rp-title" style="margin-bottom:12px">Pessoas</div>
      <div class="people-grid" id="people-grid">${usersHTML || '<p style="color:var(--muted);font-size:13px">Nenhum usuário.</p>'}</div>
    </div>
    <div class="rp-title" style="margin-bottom:14px">Todas as publicações</div>
    <div id="explore-posts">${postsHTML}</div>`);
}

let exploreSearchTimer;
function exploreSearch(q) {
  clearTimeout(exploreSearchTimer);
  exploreSearchTimer = setTimeout(async () => {
    const resultsEl = document.getElementById('explore-search-results');
    const peopleSection = document.getElementById('explore-people-section');
    if (!q.trim()) { resultsEl.classList.add('hidden'); peopleSection.style.display = ''; return; }
    const r = await fetch(`/api/users/search?q=${encodeURIComponent(q)}`); const users = await r.json();
    peopleSection.style.display = 'none';
    resultsEl.classList.remove('hidden');
    resultsEl.innerHTML = `<div class="rp-title" style="margin-bottom:12px">Resultados para "${esc(q)}"</div>` +
      (users.length ? `<div class="people-grid">${users.map(u => `<div class="person-card" onclick="goProfile('${u.username}')">${u.avatar_img ? `<div class="pc-av"><img src="${u.avatar_img}" alt=""/></div>` : `<div class="pc-av">${u.avatar_text}</div>`}<div class="pc-name">${esc(u.name)}</div><div class="pc-turma">${esc(u.turma || '')}</div></div>`).join('')}</div>`
        : `<div style="color:var(--muted);font-size:13px;padding:12px 0">Nenhum resultado encontrado.</div>`);
  }, 280);
}

// ═══════════════════════════════════════════════════════════════════
//  NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════════
async function renderNotifications() {
  setMain(`<div class="spinner-wrap"><div class="spinner"></div></div>`);
  const r = await fetch('/api/notifications'); const notifs = await r.json();
  await fetch('/api/notifications/read', { method: 'POST' });
  setBadge('notif-badge', 0); setBadge('mob-notif-badge', 0);
  const html = Array.isArray(notifs) && notifs.length ? notifs.map(n => `
    <div class="notif-item">
      ${n.avatar_img ? `<div class="notif-av"><img src="${n.avatar_img}" alt=""/></div>` : `<div class="notif-av">${n.avatar_text || '?'}</div>`}
      <div class="notif-text-wrap">
        <div class="notif-main"><strong>${esc(n.from)}</strong> ${esc(n.text)}</div>
        <div class="notif-time-lbl">${n.time || ''}</div>
      </div>
      ${!n.read ? '<div class="unread-dot"></div>' : ''}
    </div>`).join('')
    : `<div class="empty-state"><div class="ei">🔔</div><p>Nenhuma notificação ainda.</p></div>`;
  setMain(`<div style="font-family:'Syne',sans-serif;font-size:20px;font-weight:700;margin-bottom:20px">Notificações</div>${html}`);
}

// ═══════════════════════════════════════════════════════════════════
//  RIGHT PANEL
// ═══════════════════════════════════════════════════════════════════
async function loadSuggestions() {
  const r = await fetch('/api/users/suggestions'); const users = await r.json();
  const list = document.getElementById('rp-sugg-list'); if (!list) return;
  if (!Array.isArray(users) || !users.length) { document.getElementById('rp-suggestions').style.display = 'none'; return; }
  list.innerHTML = users.map(u => `<div class="rp-card">
    <div class="rp-av" onclick="goProfile('${u.username}')" style="position:relative">
      ${u.avatar_img ? `<img src="${u.avatar_img}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%"/>` : u.avatar_text}
    </div>
    <div class="rp-info"><div class="rp-name" onclick="goProfile('${u.username}')">${esc(u.name)}</div><div class="rp-turma">${esc(u.turma || '')}</div></div>
    <button class="btn-follow" id="sf-${u.username}" onclick="rpFollow('${u.username}')">Seguir</button>
  </div>`).join('');
}

async function rpFollow(username) {
  const r = await fetch(`/api/users/${username}/follow`, { method: 'POST' }); const d = await r.json();
  const btn = document.getElementById(`sf-${username}`);
  if (btn) { btn.textContent = d.following ? 'Seguindo' : 'Seguir'; btn.classList.toggle('on', d.following); }
}

async function _rpSearch(q) {
  const res = document.getElementById('rp-search-results'); const sugg = document.getElementById('rp-suggestions');
  if (!q.trim()) { res.classList.add('hidden'); sugg.style.display = ''; return; }
  const r = await fetch(`/api/users/search?q=${encodeURIComponent(q)}`); const users = await r.json();
  sugg.style.display = 'none'; res.classList.remove('hidden');
  res.innerHTML = `<div class="rp-title" style="margin-bottom:10px">Resultados</div>` +
    (users.map(u => `<div class="rp-card" style="cursor:pointer" onclick="goProfile('${u.username}')">
      ${u.avatar_img ? `<div class="rp-av"><img src="${u.avatar_img}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%"/></div>` : `<div class="rp-av">${u.avatar_text}</div>`}
      <div class="rp-info"><div class="rp-name">${esc(u.name)}</div><div class="rp-turma">${esc(u.turma || '')}</div></div>
    </div>`).join('') || `<div style="color:var(--muted);font-size:13px;padding:6px 0">Nenhum resultado.</div>`);
}

// ═══════════════════════════════════════════════════════════════════
//  UTILS
// ═══════════════════════════════════════════════════════════════════
function openImageFull(src) {
  const ov = document.createElement('div');
  ov.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.92);display:flex;align-items:center;justify-content:center;cursor:zoom-out;padding:20px';
  ov.innerHTML = `<img src="${src}" style="max-width:92vw;max-height:92vh;border-radius:10px;object-fit:contain"/>`;
  ov.onclick = () => ov.remove();
  document.body.appendChild(ov);
}

function showToast(msg) {
  const t = document.createElement('div');
  t.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#1e2a42;border:1px solid rgba(255,255,255,.15);color:#fff;padding:10px 20px;border-radius:99px;font-size:13px;z-index:9998;animation:fadeUp .25s ease;box-shadow:0 4px 16px rgba(0,0,0,.5)';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2500);
}
