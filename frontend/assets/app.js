/* تربچه — chat + map shopping assistant (no build step, vanilla JS). */
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const fa = n => Number(n).toLocaleString('fa-IR');
const faDigits = s => String(s ?? '').replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
const store = {get(k) {try {return localStorage.getItem(k)} catch {return null}}, set(k, v) {try {localStorage.setItem(k, v)} catch {}}, del(k) {try {localStorage.removeItem(k)} catch {}}};

function money(n, {short = true} = {}) {
  if (n == null || !n) return 'نامشخص';
  if (!short) return fa(n) + ' تومان';
  if (n >= 1e9) return fa(+(n / 1e9).toFixed(2)) + ' میلیارد';
  if (n >= 1e6) return fa(+(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)) + ' میلیون';
  if (n >= 1e3) return fa(Math.round(n / 1e3)) + ' هزار';
  return fa(n);
}
const pinPrice = n => !n ? '؟' : n >= 1e9 ? faDigits((n / 1e9).toFixed(1)) + 'B' : n >= 1e6 ? faDigits(+(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)) + 'م' : faDigits(Math.round(n / 1e3)) + 'ه';
const km = d => d == null ? null : d < 1 ? fa(Math.round(d * 1000)) + ' متر' : fa(+d.toFixed(1)) + ' کیلومتر';

/* ------------------------------------------------------------------ mascot */
const MASCOT = `<svg viewBox="0 0 120 140" aria-hidden="true"><defs><linearGradient id="rbG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F2477C"/><stop offset=".62" stop-color="#E8336B"/><stop offset="1" stop-color="#FFD3E0"/></linearGradient><linearGradient id="lfG" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#1C9A5B"/><stop offset="1" stop-color="#3CCB82"/></linearGradient></defs>
<g class="m-leaves"><path d="M58 37C44 30 34 16 40 6c10 4 18 16 18 31Z" fill="url(#lfG)"/><path d="M62 37c14-7 26-19 20-29-12 4-20 16-20 29Z" fill="url(#lfG)"/><path d="M60 38c-8-14-6-30 1-36 7 7 8 22-1 36Z" fill="#2BB673"/></g>
<g stroke="#2A1F2D" stroke-width="3.2" stroke-linecap="round" fill="none"><path d="M50 104q-3 12-5 22"/><path d="M70 104q3 12 5 22"/><path d="M95 80q9 6 12 16"/></g>
<ellipse cx="42" cy="128" rx="7" ry="3.6" fill="#B81F50"/><ellipse cx="78" cy="128" rx="7" ry="3.6" fill="#B81F50"/>
<circle cx="107.5" cy="97.5" r="4" fill="#F2477C" stroke="#2A1F2D" stroke-width="2"/>
<g class="m-wave"><path d="M25 78q-10-6-13-18" stroke="#2A1F2D" stroke-width="3.2" stroke-linecap="round" fill="none"/><circle cx="11.5" cy="57.5" r="4.4" fill="#F2477C" stroke="#2A1F2D" stroke-width="2"/></g>
<path d="M60 34c32 0 44 26 36 48-6 16-22 24-32 40q-4 8-8 0C46 106 30 98 24 82 16 60 28 34 60 34Z" fill="url(#rbG)"/>
<ellipse cx="42" cy="50" rx="9" ry="5" fill="#fff" opacity=".35" transform="rotate(-28 42 50)"/>
<g class="m-eyes"><ellipse cx="48" cy="68" rx="4.6" ry="6.2" fill="#2A1F2D"/><ellipse cx="72" cy="68" rx="4.6" ry="6.2" fill="#2A1F2D"/><circle cx="49.6" cy="65.6" r="1.7" fill="#fff"/><circle cx="73.6" cy="65.6" r="1.7" fill="#fff"/></g>
<ellipse cx="39" cy="79" rx="5.5" ry="3.4" fill="#FF9DBB" opacity=".8"/><ellipse cx="81" cy="79" rx="5.5" ry="3.4" fill="#FF9DBB" opacity=".8"/>
<path d="M51 79q9 12 18 0-9 4-18 0Z" fill="#2A1F2D"/><path d="M55.5 84.5q4.5 4 9 0-4.5-1.5-9 0Z" fill="#FF7A9C"/></svg>`;
const mascot = (cls = '') => `<span class="mascot ${cls}">${MASCOT}</span>`;
(() => {const st = document.createElement('style'); st.textContent = `.m-wave{transform-origin:25px 78px;animation:wave 2.4s ease-in-out infinite}.m-leaves{transform-origin:60px 38px;animation:sway 3s ease-in-out infinite}.m-eyes{transform-origin:60px 68px;animation:blink 4s infinite}@keyframes wave{0%,60%,100%{transform:rotate(0)}70%{transform:rotate(-18deg)}80%{transform:rotate(10deg)}90%{transform:rotate(-12deg)}}@keyframes sway{0%,100%{transform:rotate(-3deg)}50%{transform:rotate(3deg)}}@keyframes blink{0%,46%,50%,100%{transform:scaleY(1)}48%{transform:scaleY(.1)}}`; document.head.append(st)})();

const ICON = {
  pin: '<svg viewBox="0 0 24 24"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.5"/></svg>',
  money: '<svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="12" rx="3"/><circle cx="12" cy="12" r="2.5"/></svg>',
  radius: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/></svg>',
  card: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 10h18M7 15h4"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/></svg>',
  store: '<svg viewBox="0 0 24 24"><path d="M4 10v9h16v-9M3 6l2-3h14l2 3v2a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0V6Z"/></svg>',
  phone: '<svg viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/></svg>',
  map: '<svg viewBox="0 0 24 24"><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Zm0 0v14m6-12v14"/></svg>',
  route: '<svg viewBox="0 0 24 24"><circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h7a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h7"/></svg>',
  building: '<svg viewBox="0 0 24 24"><path d="M4 21V5l8-2v18M12 7l8 2v12M8 8v.01M8 12v.01M8 16v.01M16 12v.01M16 16v.01"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>',
};
const REASON = {best_choice: ['بهترین انتخاب', 'p'], cheapest: ['ارزان‌ترین', 'g'], nearest: ['نزدیک‌ترین', 'g'], open_now: ['الان باز است', 'g'], installment: ['خرید قسطی', 'p'], fresh_price: ['قیمت به‌روز', '']};

/* ------------------------------------------------------------------ state */
const S = {sid: null, prefs: {}, blocks: {}, compare: new Map(), busy: false, step: 0, health: null, areas: [], stores: null, pick: false};
let blockSeq = 0;
const api = async (path, opts = {}) => {
  const r = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined});
  if (!r.ok) throw Object.assign(new Error('HTTP ' + r.status), {status: r.status});
  return r.json();
};
const qs = o => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== '' && v !== false)).toString();
function prefParams(extra = {}) {
  const p = S.prefs;
  return {budget: p.budget, lat: p.lat, lon: p.lon, radius: p.lat != null ? p.radius : null, installment: p.installment || null, open_now: p.open_now || null, ...extra};
}

/* ------------------------------------------------------------------ thread helpers */
const thread = $('#thread');
function scrollEnd() {requestAnimationFrame(() => thread.scrollTop = thread.scrollHeight)}
function richText(t) {
  return esc(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/^\s*[-•]\s+/gm, '• ');
}
function addUser(text) {
  $('.welcome')?.remove();
  thread.insertAdjacentHTML('beforeend', `<div class="msg user"><div class="bubble">${esc(text)}</div></div>`);
  scrollEnd();
}
function addBot(text) {
  $('.welcome')?.remove();
  thread.insertAdjacentHTML('beforeend', `<div class="msg bot"><span class="avatar">${MASCOT}</span><div class="bubble">${richText(text)}</div></div>`);
  scrollEnd();
}
function addBlock(html, id) {
  $('.welcome')?.remove();
  const el = document.createElement('div');
  el.className = 'block'; if (id) el.id = id;
  el.innerHTML = html; thread.append(el); scrollEnd();
  return el;
}
function thinking() {
  const el = document.createElement('div');
  el.className = 'thinking';
  el.innerHTML = `<span class="avatar">${MASCOT}</span><div class="think-card"><ol></ol></div>`;
  thread.append(el); scrollEnd();
  return {
    step(text) {$$('li.now', el).forEach(li => li.classList.remove('now')); el.querySelector('ol').insertAdjacentHTML('beforeend', `<li class="now">${esc(text)}</li>`); scrollEnd()},
    done() {el.remove()},
  };
}
function toast(text, ms = 2600) {
  const t = $('#toast'); t.textContent = text; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => t.hidden = true, ms);
}
function setSuggestions(list) {
  $('#suggest').innerHTML = (list || []).map(s => `<button type="button" data-act="prompt" data-text="${esc(s)}">${esc(s)}</button>`).join('');
}
function setStep(n) {
  S.step = Math.max(S.step, n);
  $$('#steps li').forEach(li => {
    const k = +li.dataset.step;
    li.classList.toggle('active', k === n);
    li.classList.toggle('done', k < n || (k <= S.step && k !== n));
  });
}

/* ------------------------------------------------------------------ preference chips */
function renderPrefs() {
  const p = S.prefs;
  const loc = p.lat != null ? (p.area ? p.area : 'موقعیت من') : 'موقعیت؟';
  $('#prefbar').innerHTML = `
    <button class="pchip ${p.lat != null ? 'on' : ''}" data-act="pop-location">${ICON.pin}${esc(loc)}</button>
    <button class="pchip ${p.budget ? 'on' : ''}" data-act="pop-budget">${ICON.money}${p.budget ? 'تا ' + money(p.budget) : 'بودجه'}</button>
    ${p.lat != null ? `<button class="pchip on" data-act="pop-radius">${ICON.radius}${fa(p.radius || 5)} کیلومتر</button>` : ''}
    <button class="pchip ${p.installment ? 'on' : ''}" data-act="toggle" data-key="installment">${ICON.card}قسطی</button>
    <button class="pchip ${p.open_now ? 'on' : ''}" data-act="toggle" data-key="open_now">${ICON.clock}الان باز</button>`;
  Map_.setUser(p);
}
async function patchPrefs(patch, {rerun = true} = {}) {
  S.prefs = await api(`/api/sessions/${S.sid}/preferences`, {method: 'PATCH', body: patch});
  renderPrefs();
  if (rerun) rerunLast();
}
function rerunLast() {
  const last = [...$$('.block[data-kind]')].pop();
  if (!last) return;
  if (last.dataset.kind === 'stores') showStores(last.dataset.pid, {silent: true, replace: last});
  else if (last.dataset.kind === 'products') runSearch(last.dataset.q, {silent: true, replace: last});
}

/* popovers */
function openPopover(anchor, html, onMount) {
  const pop = $('#popover'); pop.innerHTML = html; pop.hidden = false;
  const r = anchor.getBoundingClientRect();
  const w = Math.min(340, innerWidth * .92);
  pop.style.top = Math.min(r.bottom + 8, innerHeight - pop.offsetHeight - 10) + 'px';
  pop.style.left = Math.max(8, Math.min(r.right - w, innerWidth - w - 8)) + 'px';
  onMount?.(pop);
}
const closePopover = () => $('#popover').hidden = true;
function popBudget(anchor) {
  const presets = [2e6, 5e6, 10e6, 20e6, 30e6, 50e6, 100e6];
  openPopover(anchor, `<h4>سقف بودجه</h4>
    <input type="text" inputmode="numeric" id="budgetIn" placeholder="مثلاً ۲۵ میلیون یا 25000000" value="${S.prefs.budget ? fa(S.prefs.budget) : ''}">
    <div class="opts">${presets.map(v => `<button type="button" data-budget="${v}" class="${S.prefs.budget === v ? 'on' : ''}">${money(v)}</button>`).join('')}</div>
    <div class="row"><button class="btn primary" type="button" id="budgetOk">اعمال</button><button class="btn ghost" type="button" id="budgetClear">بدون سقف</button></div>`, pop => {
    const apply = v => {closePopover(); v ? patchPrefs({budget: v}) : patchPrefs({clear_budget: true})};
    $$('[data-budget]', pop).forEach(b => b.onclick = () => apply(+b.dataset.budget));
    $('#budgetOk', pop).onclick = () => apply(parseBudget($('#budgetIn', pop).value));
    $('#budgetClear', pop).onclick = () => apply(null);
    $('#budgetIn', pop).focus();
  });
}
function parseBudget(t) {
  t = String(t).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٬,\s]/g, '');
  const n = parseFloat(t); if (!n) return null;
  if (/میلیارد/.test(t)) return Math.round(n * 1e9);
  if (/میلیون|م$/.test(t) || n < 1000) return Math.round(n * 1e6);
  if (/هزار/.test(t)) return Math.round(n * 1e3);
  return Math.round(n);
}
function popRadius(anchor) {
  openPopover(anchor, `<h4>شعاع جستجو از موقعیت شما</h4><div class="opts">${[1, 2, 3, 5, 10, 20].map(v => `<button type="button" data-r="${v}" class="${+S.prefs.radius === v ? 'on' : ''}">${fa(v)} کیلومتر</button>`).join('')}</div>`, pop => {
    $$('[data-r]', pop).forEach(b => b.onclick = () => {closePopover(); patchPrefs({radius: +b.dataset.r})});
  });
}
async function popLocation(anchor) {
  if (!S.areas.length) S.areas = await api('/api/areas').catch(() => []);
  const list = q => S.areas.filter(a => !q || a.name.includes(q)).slice(0, 30).map(a => `<button type="button" data-area="${esc(a.name)}"><span>${esc(a.name)}</span><small>${fa(a.shops)} فروشگاه</small></button>`).join('');
  openPopover(anchor, `<h4>کجا هستی؟</h4>
    <div class="row" style="margin:0 0 8px"><button class="btn primary sm" type="button" id="gps">${ICON.pin} موقعیت فعلی من</button><button class="btn soft sm" type="button" id="pickMap">${ICON.map} انتخاب روی نقشه</button></div>
    <input type="text" id="areaIn" placeholder="جستجوی محله… (فردوسی، جمهوری، تجریش…)">
    <div class="arealist" id="areaList">${list('')}</div>
    ${S.prefs.lat != null ? '<div class="row"><button class="btn ghost sm" type="button" id="clearLoc">حذف موقعیت</button></div>' : ''}`, pop => {
    $('#areaIn', pop).oninput = e => $('#areaList', pop).innerHTML = list(e.target.value.trim());
    pop.onclick = e => {
      const b = e.target.closest('[data-area]'); if (!b) return;
      const a = S.areas.find(x => x.name === b.dataset.area);
      closePopover(); patchPrefs({lat: a.lat, lon: a.lon, area: a.name, radius: S.prefs.lat == null ? 3 : S.prefs.radius});
      Map_.fly(a.lat, a.lon, 14);
    };
    $('#gps', pop).onclick = () => {closePopover(); locateMe()};
    $('#pickMap', pop).onclick = () => {closePopover(); startPick()};
    $('#clearLoc', pop) && ($('#clearLoc', pop).onclick = () => {closePopover(); patchPrefs({clear_location: true})});
  });
}
function locateMe() {
  if (!navigator.geolocation) return toast('مرورگر موقعیت‌یابی را پشتیبانی نمی‌کند');
  toast('در حال گرفتن موقعیت…');
  navigator.geolocation.getCurrentPosition(pos => {
    const {latitude: lat, longitude: lon} = pos.coords;
    patchPrefs({lat, lon, area: null, radius: S.prefs.lat == null ? 3 : S.prefs.radius}); Map_.fly(lat, lon, 14); toast('موقعیتت ثبت شد');
  }, () => {toast('اجازه موقعیت داده نشد؛ روی نقشه انتخاب کن'); startPick()}, {enableHighAccuracy: true, timeout: 8000});
}
function startPick() {S.pick = true; setView('map'); $('.map-pane').classList.add('picking'); $('#pickHint').hidden = false}
function stopPick() {S.pick = false; $('.map-pane').classList.remove('picking'); $('#pickHint').hidden = true}

/* ------------------------------------------------------------------ renderers */
function imgTag(url, cls = '') {
  return url ? `<img class="${cls}" src="${esc(url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'ph',innerHTML:MASCOT}))">` : `<span class="ph">${MASCOT}</span>`;
}
function productCard(p) {
  const sel = S.compare.has(p.product_id);
  const price = p.recorded_min_price ? (p.recorded_max_price && p.recorded_max_price !== p.recorded_min_price ? `از ${money(p.recorded_min_price)}` : money(p.recorded_min_price)) : 'قیمت ثبت نشده';
  const minis = [
    p.shop_count ? `<span class="mini">${ICON.store.replace('<svg', '<svg width="12" height="12"')}${fa(p.shop_count)} فروشگاه حضوری</span>` : '<span class="mini a">فروشنده‌ای با این شرایط نیست</span>',
    p.nearest_km != null ? `<span class="mini g">نزدیک‌ترین ${km(p.nearest_km)}</span>` : '',
    p.installment_shops ? `<span class="mini p">قسطی</span>` : '',
    p.open_shops ? `<span class="mini g">${fa(p.open_shops)} باز</span>` : '',
  ].join('');
  return `<article class="pcard ${sel ? 'sel' : ''}" data-pid="${esc(p.product_id)}">
    <div class="pimg" data-act="detail" data-pid="${esc(p.product_id)}">${imgTag(p.image_url)}
      <label class="cmp-toggle" onclick="event.stopPropagation()"><input type="checkbox" data-act="cmp" data-pid="${esc(p.product_id)}" ${sel ? 'checked' : ''}>مقایسه</label></div>
    <div class="pbody">
      <h4 class="ptitle" title="${esc(p.persian_title)}">${esc(p.persian_title)}</h4>
      <div class="pcat">${esc(p.category_name || '')}${p.brand_name ? ' · ' + esc(p.brand_name) : ''}</div>
      <div class="price">${price} ${p.recorded_min_price ? '<small>تومان · ثبت‌شده</small>' : ''}</div>
      <div class="minis">${minis}</div>
      <button class="btn primary sm wide" type="button" data-act="stores" data-pid="${esc(p.product_id)}" ${p.shop_count ? '' : 'disabled'}>${ICON.store} فروشگاه‌ها و قیمت‌ها</button>
    </div></article>`;
}
function constraintText(c) {
  const parts = [];
  if (c?.budget) parts.push('تا ' + money(c.budget));
  if (c?.lat != null && c?.radius) parts.push(fa(c.radius) + ' کیلومتری ' + (S.prefs.area || 'شما'));
  if (c?.installment) parts.push('قسطی');
  if (c?.open_now) parts.push('الان باز');
  return parts.length ? 'با شرط: ' + parts.join('، ') : '';
}
function renderProducts(data, {q} = {}) {
  const id = 'b' + (++blockSeq);
  S.blocks[id] = {kind: 'products', data, q: q ?? data.query, page: 0};
  for (const p of data.results) S.compare.has(p.product_id) && S.compare.set(p.product_id, p);
  const more = data.total > (data.page + 1) * data.limit ? `<button class="more" type="button" data-act="more" data-block="${id}">نتایج بیشتر</button>` : '';
  const empty = !data.results.length ? `<div class="note warn">نتیجه‌ای با این شرایط پیدا نشد. بودجه، محدوده یا فیلتر قسطی/الان‌باز را تغییر بده.</div>` : '';
  const sem = data.retrieval?.vector_index ? ' · جستجوی ترکیبی' : '';
  return {id, html: `<div class="block-head"><strong>${fa(data.total)} کالا برای «${esc(q ?? data.query ?? '')}»</strong><span>${constraintText(data.constraints)}${sem}</span></div>${empty}<div class="carousel" id="${id}-c">${data.results.map(productCard).join('')}${more}</div>`};
}
function storeRow(r, i) {
  const s = r.shop, open = s.open || {};
  const fresh = r.freshness || {};
  return `<li class="srow" data-offer="${esc(r.offer_id)}" data-shop="${esc(s.shop_id)}">
    <span class="rank">${fa(i + 1)}</span>
    <div><div class="sname" data-act="shop" data-shop="${esc(s.shop_id)}">${esc(s.name || 'فروشگاه')}</div></div>
    <div class="sprice">${r.price_toman ? money(r.price_toman) : 'بدون قیمت'}<small class="${fresh.status === 'stale' ? 'stale' : ''}">${esc(fresh.label || '')}</small></div>
    <div class="sline">
      ${s.distance_km != null ? `<span>${ICON.pin}${km(s.distance_km)}</span>` : ''}
      <span class="${open.status}">${ICON.clock}${esc(open.label || 'نامشخص')}</span>
      ${s.mall?.summary ? `<span>${ICON.building}${esc(s.mall.summary)}</span>` : `<span>${ICON.building}${esc(s.area || '')}</span>`}
      ${s.installment?.length ? `<span>${ICON.card}${s.installment.map(x => esc(x.provider)).join('، ')}</span>` : ''}
    </div>
    <div class="reasons">${(r.reasons || []).map(k => REASON[k] ? `<span class="mini ${REASON[k][1]}">${REASON[k][0]}</span>` : '').join('')}</div>
    <div class="sactions">
      <button class="btn soft sm" type="button" data-act="inquire" data-offer="${esc(r.offer_id)}">${ICON.phone} استعلام موجودی و قیمت</button>
      <button class="btn ghost sm" type="button" data-act="focus" data-shop="${esc(s.shop_id)}">${ICON.map} نقشه</button>
      ${s.lat != null ? `<a class="btn ghost sm" target="_blank" rel="noopener" href="https://balad.ir/location?latitude=${s.lat}&longitude=${s.lon}&zoom=17">${ICON.route} مسیر</a>` : ''}
    </div></li>`;
}
const SORTS = {best: ['پیشنهادی', (a, b) => b.score - a.score], cheapest: ['ارزان‌ترین', (a, b) => (a.price_toman || 9e18) - (b.price_toman || 9e18)], nearest: ['نزدیک‌ترین', (a, b) => (a.shop.distance_km ?? 9e9) - (b.shop.distance_km ?? 9e9)], open: ['الان باز', (a, b) => (a.shop.open.status !== 'open') - (b.shop.open.status !== 'open') || b.score - a.score]};
function renderStores(data, id) {
  id = id || 'b' + (++blockSeq);
  const blk = S.blocks[id] = S.blocks[id] || {kind: 'stores', data, sort: 'best'};
  blk.data = data;
  const rows = [...data.results].sort(SORTS[blk.sort][1]);
  const sm = data.summary || {};
  const ex = data.excluded || {}, exParts = [];
  if (ex.budget) exParts.push(`${fa(ex.budget)} به‌خاطر بودجه`); if (ex.radius) exParts.push(`${fa(ex.radius)} به‌خاطر فاصله`);
  if (ex.installment) exParts.push(`${fa(ex.installment)} بدون قسطی`); if (ex.closed) exParts.push(`${fa(ex.closed)} بسته`);
  const p = data.product || {};
  const html = `<div class="sblock">
    <div class="shead">${imgTag(p.image_url)}<div><h3>${esc(p.persian_title || '')}</h3>
      <div class="ssum">${sm.shops ? `<span class="mini">${fa(sm.shops)} فروشگاه</span><span class="mini">${money(sm.min_price)}${sm.max_price && sm.max_price !== sm.min_price ? ' تا ' + money(sm.max_price) : ''}</span>${sm.open_now ? `<span class="mini g">${fa(sm.open_now)} باز</span>` : ''}${sm.installment ? `<span class="mini p">${fa(sm.installment)} قسطی</span>` : ''}${sm.nearest_km != null ? `<span class="mini g">نزدیک‌ترین ${km(sm.nearest_km)}</span>` : ''}` : '<span class="mini a">فروشگاهی با این شرایط پیدا نشد</span>'}</div></div></div>
    ${rows.length > 1 ? `<div class="seg">${Object.entries(SORTS).map(([k, [label]]) => `<button type="button" data-act="sort" data-block="${id}" data-sort="${k}" class="${blk.sort === k ? 'on' : ''}">${label}</button>`).join('')}</div>` : ''}
    <ol class="slist">${rows.slice(0, blk.all ? 40 : 6).map(storeRow).join('')}</ol>
    ${rows.length > 6 && !blk.all ? `<div style="padding:0 12px 12px"><button class="btn ghost sm wide" type="button" data-act="all-stores" data-block="${id}">نمایش همه ${fa(rows.length)} فروشگاه</button></div>` : ''}
    <div class="sfoot"><span title="معیار رتبه‌بندی">چرا این ترتیب؟ ${esc(data.ranking || '')}</span>${exParts.length ? `<span>حذف‌شده: ${exParts.join('، ')}</span>` : ''}</div>
  </div>`;
  return {id, html, rows};
}
function renderCompare(data) {
  const prods = data.products, market = data.market || [];
  const minPrice = Math.min(...market.map(m => m.min_price || Infinity));
  const head = `<tr><th></th>${prods.map(p => `<th>${imgTag(p.image_url)}${esc(p.persian_title)}</th>`).join('')}</tr>`;
  const mrow = (label, f, best) => `<tr><th>${label}</th>${market.map((m, i) => `<td class="${best && best(m) ? 'best' : ''}">${f(m, i)}</td>`).join('')}</tr>`;
  const body = [
    mrow('کمترین قیمت ثبت‌شده', m => m.min_price ? money(m.min_price) : 'نامشخص', m => m.min_price && m.min_price === minPrice),
    mrow('فروشگاه حضوری', m => fa(m.shops || 0)),
    mrow('الان باز', m => m.shops ? fa(m.open_now || 0) : '—'),
    mrow('قسطی', m => m.shops ? fa(m.installment || 0) : '—'),
    ...data.rows.map(r => `<tr class="${r.differs ? 'diff' : ''}"><th>${esc(r.key)}</th>${r.values.map(v => `<td>${v == null ? '<span class="unknown">ثبت نشده</span>' : esc(v)}</td>`).join('')}</tr>`),
    `<tr><th></th>${prods.map(p => `<td><button class="btn primary sm" type="button" data-act="stores" data-pid="${esc(p.product_id)}">فروشگاه‌ها</button></td>`).join('')}</tr>`,
  ].join('');
  return `<div class="block-head"><strong>مقایسه ${fa(prods.length)} کالا</strong><span>ردیف‌های زرد = تفاوت</span></div><div class="ctable-wrap"><table class="ctable"><thead>${head}</thead><tbody>${body}</tbody></table></div><div class="note">${esc(data.note || '')}</div>`;
}
function renderInquiry(d) {
  const r = d.response, s = d.shop;
  const cls = d.status === 'calling' ? 'calling' : d.status === 'confirmed' ? 'ok' : 'bad';
  const title = {calling: `در حال تماس با «${esc(s.name)}»…`, confirmed: `«${esc(s.name)}» تأیید کرد ✅`, unavailable: `«${esc(s.name)}»: موجود نیست`, no_answer: `«${esc(s.name)}» پاسخ نداد`, issue: `«${esc(s.name)}»: مشکل در مراجعه`}[d.status];
  let body = '';
  if (d.status === 'calling') {
    const pct = Math.min(96, (d.elapsed_s / d.expected_s) * 100);
    body = `<p>سؤال‌ها: موجودی، قیمت امروز، ساعت مراجعه</p><div class="bar"><i style="width:${pct}%"></i></div>`;
  } else if (r) {
    const inv = r.answered === false ? '<b class="na">بی‌پاسخ</b>' : r.inventory === 'available' ? '<b class="ok">موجود است</b>' : r.inventory === 'unavailable' ? '<b class="no">ناموجود</b>' : '<b class="na">نامشخص</b>';
    const price = r.price ? `<b class="${r.over_budget ? 'no' : 'ok'}">${money(r.price, {short: false})}</b>` : '<b class="na">اعلام نشد</b>';
    const diff = r.price && d.recorded_price_toman && r.price !== d.recorded_price_toman ? ` <small>(ثبت‌شده: ${money(d.recorded_price_toman)})</small>` : '';
    body = `<div class="qa"><div><span>موجودی</span>${inv}</div><div><span>قیمت امروز</span><span>${price}${diff}</span></div><div><span>مراجعه</span>${r.visit === 'possible' ? '<b class="ok">امکان‌پذیر</b>' : r.visit === 'not_possible' ? '<b class="no">امکان‌پذیر نیست</b>' : '<b class="na">نامشخص</b>'}</div>${r.notes ? `<div><span>یادداشت</span><span>${esc(r.notes)}</span></div>` : ''}</div>`;
    if (d.status === 'confirmed') body += `<div class="row" style="margin-top:10px"><a class="btn primary sm" target="_blank" rel="noopener" href="https://balad.ir/location?latitude=${s.lat}&longitude=${s.lon}&zoom=17">${ICON.route} مسیر با بلد</a><a class="btn ghost sm" target="_blank" rel="noopener" href="https://neshan.org/maps/@${s.lat},${s.lon},17z">نشان</a>${s.mall?.summary ? `<span class="mini g" style="height:30px">${esc(s.mall.summary)}</span>` : ''}</div>`;
  }
  const alts = d.alternatives?.length ? `<div class="alts"><h5>🔁 جایگزین‌های پیشنهادی (همین کالا)</h5>${d.alternatives.map(a => `<div class="alt"><div><b>${esc(a.shop.name)}</b><br><span class="${a.shop.open.status}">${esc(a.shop.open.label)}</span>${a.shop.distance_km != null ? ' · ' + km(a.shop.distance_km) : ''}</div><div style="text-align:end"><b>${money(a.price_toman)}</b><br><button class="btn soft sm" type="button" data-act="inquire" data-offer="${esc(a.offer_id)}">استعلام از این</button></div></div>`).join('')}</div>` : (d.status !== 'calling' && d.status !== 'confirmed' ? '<div class="note warn">فروشگاه جایگزینی با شرایط فعلی پیدا نشد.</div>' : '');
  return `<div class="iq ${cls}"><div class="iq-top"><span class="phone">${ICON.phone}</span><div><h4>${title}</h4><p>${esc(s.mall?.summary || s.address || '')}</p></div></div>${body}${alts}<span class="sim">ⓘ ${esc(d.disclaimer)}</span></div>`;
}
function renderProductSheet(p) {
  const specs = (p.specs || []).map(s => `<tr><td>${esc(s.key)}</td><td>${esc(s.value)}</td></tr>`).join('');
  return `<h2>${esc(p.persian_title)}</h2><div class="pcat">${esc(p.category_name || '')}${p.brand_name ? ' · ' + esc(p.brand_name) : ''}</div>
    <div class="gallery">${(p.image_urls || []).map(u => `<img src="${esc(u)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`).join('') || `<span class="ph" style="width:80px">${MASCOT}</span>`}</div>
    <div class="row"><button class="btn primary" type="button" data-act="stores" data-pid="${esc(p.product_id)}">${ICON.store} فروشگاه‌های حضوری</button><button class="btn soft" type="button" data-act="cmp-add" data-pid="${esc(p.product_id)}">افزودن به مقایسه</button></div>
    <h3>مشخصات ثبت‌شده</h3>${specs ? `<table class="kv">${specs}</table>` : '<div class="note">مشخصاتی برای این کالا ثبت نشده.</div>'}`;
}
function renderShopSheet(s) {
  const inst = s.installment?.length ? s.installment.map(x => `<span class="mini p">${esc(x.provider)}${x.in_person_confirmed ? ' · حضوری' : ''}</span>`).join(' ') : '<span class="unknown">ثبت نشده (نامشخص)</span>';
  return `<h2>${esc(s.name)}</h2><div class="${s.open.status}">${esc(s.open.label)}</div>
    ${s.mall?.summary ? `<div class="mallbox">${ICON.building}<div>داخل ${esc(s.mall.summary)}${s.mall.plate ? ' · پلاک ' + faDigits(s.mall.plate) : ''}</div></div>` : ''}
    <p style="margin:6px 0;color:var(--ink-2)">${esc(s.address || '')}${s.area ? ' · محله ' + esc(s.area) : ''}${s.distance_km != null ? ' · ' + km(s.distance_km) + ' از شما' : ''}</p>
    <div class="routes">${s.lat != null ? `<a class="btn primary sm" target="_blank" rel="noopener" href="https://balad.ir/location?latitude=${s.lat}&longitude=${s.lon}&zoom=17">${ICON.route} مسیر با بلد</a><a class="btn ghost sm" target="_blank" rel="noopener" href="https://neshan.org/maps/@${s.lat},${s.lon},17z">نشان</a><a class="btn ghost sm" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=${s.lat},${s.lon}">گوگل‌مپ</a>` : ''}</div>
    <h3>ساعت کاری ثبت‌شده</h3><table class="kv">${s.hours.map(h => `<tr><td>${h.day}</td><td>${esc(h.hours)}</td></tr>`).join('')}</table>
    <h3>خرید قسطی / اعتباری</h3><div>${inst}</div>
    <h3>ارتباط</h3><div>${s.contacts.map(c => `<span class="mini">${esc(c.channel)} · ${esc(c.number)}</span>`).join(' ') || '<span class="unknown">ثبت نشده</span>'}${s.instagram ? ` <a href="https://instagram.com/${esc(s.instagram)}" target="_blank" rel="noopener">اینستاگرام</a>` : ''}${s.website ? ` <a href="${esc(s.website)}" target="_blank" rel="noopener">وب‌سایت</a>` : ''}</div>
    <div class="note">شماره‌های تماس دیتاست ساختگی است؛ برای استعلام از دکمه «استعلام» در فهرست فروشگاه‌ها استفاده کن (شبیه‌سازی‌شده).</div>`;
}
function openSheet(html) {$('#sheetBody').innerHTML = html; $('#sheet').hidden = false; $('#sheetBody').parentElement.scrollTop = 0}
const closeSheet = () => $('#sheet').hidden = true;

/* ------------------------------------------------------------------ component dispatcher (agent + direct) */
function showComponent(c) {
  const d = c.data;
  if (c.ui === 'products') {
    const {id, html} = renderProducts(d, {q: d.query});
    const el = addBlock(html, id); el.dataset.kind = 'products'; el.dataset.q = d.query || '';
    setStep(1);
  } else if (c.ui === 'stores') {
    const {id, html, rows} = renderStores(d);
    const el = addBlock(html, id); el.dataset.kind = 'stores'; el.dataset.pid = d.product_id;
    S.stores = {product: d.product, rows}; Map_.showStores(d.product, rows); setStep(3);
  } else if (c.ui === 'compare') {
    addBlock(renderCompare(d)); setStep(1);
  } else if (c.ui === 'inquiry') {
    mountInquiry(d); setStep(4);
  } else if (c.ui === 'product') {
    addBlock(`<div class="carousel">${productCard({...d, recorded_min_price: null, shop_count: 1})}</div>`);
  } else if (c.ui === 'shop') {
    addBlock(`<div class="sblock" style="padding:14px">${renderShopSheet(d)}</div>`);
  } else if (c.ui === 'location') {
    if (d.found) {addBlock(`<div class="note">📍 موقعیت روی «${esc(d.name)}» تنظیم شد · شعاع ${fa(d.radius)} کیلومتر${d.approximate ? ' (تقریبی)' : ''}</div>`); Map_.fly(d.lat, d.lon, 14); setStep(2)}
  } else if (c.ui === 'preferences') {
    S.prefs = d; renderPrefs();
    const t = constraintText({...d, radius: d.lat != null ? d.radius : null});
    t && addBlock(`<div class="note">✓ شرایط ثبت شد — ${esc(t.replace('با شرط: ', ''))}</div>`);
  }
}
function mountInquiry(d) {
  const el = addBlock(renderInquiry(d));
  el.dataset.kind = 'inquiry';
  const poll = async () => {
    if (d.status !== 'calling') return;
    await new Promise(r => setTimeout(r, 1200));
    try {d = await api(`/api/sessions/${S.sid}/inquiries/${d.id}`)} catch {return}
    el.innerHTML = renderInquiry(d);
    if (d.status !== 'calling') {
      setSuggestions(d.status === 'confirmed' ? ['مسیر رفتن رو نشون بده', 'یه فروشگاه دیگه هم بپرس'] : ['جایگزین اول رو استعلام کن', 'فروشگاه‌های الان‌باز رو نشون بده']);
      if (d.alternatives?.length) Map_.showStores(S.stores?.product, d.alternatives, {keep: true});
      scrollEnd(); return;
    }
    poll();
  };
  poll();
}

/* ------------------------------------------------------------------ direct actions (no LLM round-trip) */
async function runSearch(q, {silent = false, replace = null, note = ''} = {}) {
  if (!silent) addUser(q);
  const data = await api('/api/search?' + qs({q, ...prefParams(), limit: 12}));
  data.query = q;
  const {id, html} = renderProducts(data, {q});
  if (replace) {replace.innerHTML = html; replace.id = id}
  else {const el = addBlock((note ? `<div class="note warn">${esc(note)}</div>` : '') + html, id); el.dataset.kind = 'products'; el.dataset.q = q}
  setStep(1); setSuggestions(['دوتای اول رو مقایسه کن', 'فقط فروشگاه‌های قسطی', 'من نزدیک میدان فردوسی هستم']);
}
async function showStores(pid, {silent = false, replace = null} = {}) {
  const title = $(`.pcard[data-pid="${CSS.escape(pid)}"] .ptitle`)?.textContent || 'این کالا';
  if (!silent) addUser(`فروشگاه‌های حضوری «${title}» رو نشون بده`);
  closeSheet();
  const data = await api(`/api/products/${encodeURIComponent(pid)}/stores?` + qs({...prefParams(), limit: 40}));
  const {id, html, rows} = renderStores(data, replace?.id);
  if (replace) replace.innerHTML = html;
  else {const el = addBlock(html, id); el.dataset.kind = 'stores'; el.dataset.pid = pid}
  S.stores = {product: data.product, rows}; Map_.showStores(data.product, rows); setStep(3);
  const sug = ['از بهترین فروشگاه موجودی رو بپرس'];
  if (S.prefs.lat == null) sug.push('من نزدیک میدان فردوسی هستم');
  if (!S.prefs.open_now) sug.push('فقط اونایی که الان بازن');
  setSuggestions(sug);
  if (!silent && S.prefs.lat == null) addBot('برای اینکه نزدیک‌ترین‌ها رو هم حساب کنم، از دکمه **📍 موقعیت؟** بالای گفتگو محله‌ات رو انتخاب کن.');
}
async function doCompare(ids) {
  addUser('این‌ها رو با هم مقایسه کن');
  const data = await api('/api/compare/table', {method: 'POST', body: {ids, session_id: S.sid}});
  addBlock(renderCompare(data)); setStep(1);
  setSuggestions(['کدوم بیشتر می‌ارزه؟', 'فروشگاه‌های ارزون‌ترینش']);
}
async function inquire(offerId) {
  const name = $(`.srow[data-offer="${CSS.escape(offerId)}"] .sname`)?.textContent;
  addUser(name ? `از «${name}» موجودی و قیمت امروز رو بپرس` : 'از این فروشگاه استعلام بگیر');
  const d = await api(`/api/sessions/${S.sid}/inquiries`, {method: 'POST', body: {offer_id: offerId}});
  mountInquiry(d); setStep(4);
}

/* ------------------------------------------------------------------ agent (SSE) */
async function ask(text) {
  if (S.busy || !text.trim()) return;
  S.busy = true; $('#send').disabled = true; setSuggestions([]);
  addUser(text);
  const th = thinking();
  let gotComponent = false, failed = false;
  try {
    const r = await fetch(`/api/sessions/${S.sid}/agent`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message: text})});
    if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const {value, done} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const line = buf.slice(0, i).trim(); buf = buf.slice(i + 2);
        if (!line.startsWith('data:')) continue;
        const ev = JSON.parse(line.slice(5));
        if (ev.type === 'status') th.step(ev.text);
        else if (ev.type === 'component') {th.done(); showComponent(ev); gotComponent = true}
        else if (ev.type === 'error') failed = true;
        else if (ev.type === 'message') {
          th.done();
          if (failed && !gotComponent) {addBot(ev.text); await runSearch(text, {silent: true, note: 'نتایج جستجوی مستقیم (بدون هوش مصنوعی):'}).catch(() => {})}
          else addBot(ev.text);
        } else if (ev.type === 'done') {S.prefs = ev.preferences || S.prefs; renderPrefs(); setSuggestions(ev.suggestions)}
      }
    }
  } catch (e) {
    th.done();
    addBot('ارتباط با دستیار برقرار نشد؛ نتایج جستجوی مستقیم رو نشونت می‌دم.');
    await runSearch(text, {silent: true}).catch(() => addBot('جستجو هم انجام نشد؛ اتصال سرور را بررسی کن.'));
  } finally {
    th.done(); S.busy = false; $('#send').disabled = false; $('#input').focus();
  }
}

/* ------------------------------------------------------------------ compare tray */
function renderTray() {
  const tray = $('#compareTray'), items = [...S.compare.values()];
  tray.hidden = items.length < 1;
  tray.innerHTML = `<div class="thumbs">${items.map(p => p.image_url ? `<img src="${esc(p.image_url)}" alt="" referrerpolicy="no-referrer">` : '').join('')}</div>
    <span>${fa(items.length)} کالا برای مقایسه</span>
    <button class="btn primary sm" type="button" data-act="do-compare" ${items.length < 2 ? 'disabled' : ''}>مقایسه کن</button>
    <button class="icon-btn" type="button" data-act="clear-cmp" aria-label="پاک کردن" style="color:inherit">${ICON.x}</button>`;
}
function findProduct(pid) {
  for (const b of Object.values(S.blocks)) if (b.kind === 'products') {const p = b.data.results.find(x => x.product_id === pid); if (p) return p}
  return {product_id: pid};
}

/* ------------------------------------------------------------------ map */
const Map_ = (() => {
  let map, userLayer, storeLayer, densityLayer, markers = new Map();
  function init(cfg) {
    map = L.map('map', {zoomControl: false, attributionControl: true}).setView([35.700, 51.405], 12);
    L.control.zoom({position: 'topright'}).addTo(map);
    L.tileLayer(cfg.tile_url, {maxZoom: 19, attribution: cfg.attribution}).addTo(map);
    userLayer = L.layerGroup().addTo(map); storeLayer = L.layerGroup().addTo(map); densityLayer = L.layerGroup().addTo(map);
    map.on('click', e => {if (S.pick) {stopPick(); patchPrefs({lat: e.latlng.lat, lon: e.latlng.lng, area: null, radius: S.prefs.lat == null ? 3 : S.prefs.radius}); toast('موقعیتت روی نقشه ثبت شد')}});
    loadDensity(); head();
  }
  async function loadDensity() {
    try {
      const d = await api('/api/map/clusters?' + qs({west: 51.1, east: 51.7, south: 35.55, north: 35.85, zoom: 12}));
      for (const c of d.cells) {
        if (c.shops < 2) continue;
        const size = Math.min(64, 18 + Math.sqrt(c.shops) * 4);
        L.marker([c.lat, c.lon], {interactive: false, icon: L.divIcon({className: '', html: `<div class="density" style="width:${size}px;height:${size}px;margin:-${size / 2}px 0 0 -${size / 2}px">${fa(c.shops)}</div>`})}).addTo(densityLayer);
      }
    } catch {}
  }
  function head(product, count) {
    $('#mapHead').innerHTML = product ? `<div class="card">${imgTag(product.image_url)}<div><b style="display:block;max-width:360px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(product.persian_title)}</b><span style="color:var(--ink-3)">${fa(count)} فروشگاه روی نقشه</span></div><button class="icon-btn" type="button" data-act="clear-map" aria-label="پاک کردن نقشه">${ICON.x}</button></div>`
      : `<div class="card">${mascot()}<div><b>۶٬۴۷۶ فروشگاه حضوری تهران</b><br><span style="color:var(--ink-3)">کالا که انتخاب کنی، فروشگاه‌هاش اینجا میان</span></div></div>`;
    const b = $('#mapBadge'); b.hidden = !count; b.textContent = count ? fa(count) : '';
  }
  function setUser(p) {
    if (!map) return;
    userLayer.clearLayers();
    if (p.lat == null) return;
    L.marker([p.lat, p.lon], {icon: L.divIcon({className: '', html: '<div class="me" style="margin:-9px 0 0 -9px"></div>'}), zIndexOffset: 1000}).addTo(userLayer).bindTooltip(p.area || 'موقعیت شما', {direction: 'top'});
    L.circle([p.lat, p.lon], {radius: (p.radius || 3) * 1000, color: '#2F7BF6', weight: 1.5, fillOpacity: .05, dashArray: '6 6'}).addTo(userLayer);
  }
  function showStores(product, rows, {keep = false} = {}) {
    if (!map) return;
    if (!keep) {storeLayer.clearLayers(); markers.clear()}
    map.removeLayer(densityLayer);
    const pts = [];
    rows.forEach((r, i) => {
      const s = r.shop; if (s.lat == null || markers.has(s.shop_id)) return;
      const cls = `pin ${s.open.status} ${i === 0 && !keep ? 'top' : ''}`;
      const m = L.marker([s.lat, s.lon], {icon: L.divIcon({className: '', html: `<div class="${cls}"><div class="tag"><b>${keep ? '↻' : fa(i + 1)}</b>${pinPrice(r.price_toman)}</div><div class="stem"></div></div>`, iconSize: [0, 0]}), zIndexOffset: 500 - i}).addTo(storeLayer);
      m.bindPopup(`<b style="font-size:14px">${esc(s.name)}</b><div>${money(r.price_toman)} تومان · <span class="${s.open.status}">${esc(s.open.label)}</span></div>${s.mall?.summary ? `<div>🏬 ${esc(s.mall.summary)}</div>` : ''}${s.distance_km != null ? `<div>📍 ${km(s.distance_km)}</div>` : ''}<div style="display:flex;gap:6px;margin-top:8px"><button class="btn soft sm" data-act="inquire" data-offer="${esc(r.offer_id)}">استعلام</button><button class="btn ghost sm" data-act="shop" data-shop="${esc(s.shop_id)}">جزئیات</button></div>`);
      m.on('click', () => highlight(s.shop_id));
      markers.set(s.shop_id, m); pts.push([s.lat, s.lon]);
    });
    if (S.prefs.lat != null && !keep) pts.push([S.prefs.lat, S.prefs.lon]);
    if (pts.length) map.fitBounds(pts, {padding: [70, 70], maxZoom: 15});
    head(product, markers.size);
  }
  function highlight(shopId) {
    $$('.srow.hl').forEach(x => x.classList.remove('hl'));
    const row = [...$$(`.srow[data-shop="${CSS.escape(shopId)}"]`)].pop();
    if (row) {row.classList.add('hl'); if (innerWidth > 860) row.scrollIntoView({block: 'center', behavior: 'smooth'})}
  }
  function focus(shopId) {
    const m = markers.get(shopId); if (!m) return;
    setView('map'); map.flyTo(m.getLatLng(), 16, {duration: .6}); setTimeout(() => m.openPopup(), 650);
  }
  function clear() {storeLayer.clearLayers(); markers.clear(); densityLayer.addTo(map); head()}
  const fly = (lat, lon, z = 14) => map?.flyTo([lat, lon], z, {duration: .7});
  const invalidate = () => map && setTimeout(() => map.invalidateSize(), 60);
  return {init, setUser, showStores, focus, fly, clear, invalidate, highlight};
})();

function setView(v) {$('#app').dataset.view = v; if (v === 'map') Map_.invalidate()}

/* ------------------------------------------------------------------ events */
document.addEventListener('click', async e => {
  const t = e.target.closest('[data-act]');
  if (!$('#popover').hidden && !e.target.closest('#popover') && !e.target.closest('[data-act^="pop-"]')) closePopover();
  if (!t) return;
  const a = t.dataset.act;
  try {
    if (a === 'prompt') ask(t.dataset.text);
    else if (a === 'stores') {setView('chat'); await showStores(t.dataset.pid)}
    else if (a === 'detail') openSheet(renderProductSheet(await api(`/api/products/${encodeURIComponent(t.dataset.pid)}/full`)));
    else if (a === 'shop') openSheet(renderShopSheet(await api(`/api/shops/${encodeURIComponent(t.dataset.shop)}/card?` + qs({lat: S.prefs.lat, lon: S.prefs.lon}))));
    else if (a === 'inquire') {closeSheet(); if (innerWidth <= 860) setView('chat'); await inquire(t.dataset.offer)}
    else if (a === 'focus') Map_.focus(t.dataset.shop);
    else if (a === 'close-sheet') closeSheet();
    else if (a === 'sort' || a === 'all-stores') {
      const blk = S.blocks[t.dataset.block]; if (a === 'sort') blk.sort = t.dataset.sort; else blk.all = true;
      const {html, rows} = renderStores(blk.data, t.dataset.block); $('#' + t.dataset.block).innerHTML = html;
      S.stores = {product: blk.data.product, rows}; Map_.showStores(blk.data.product, rows);
    } else if (a === 'more') {
      const blk = S.blocks[t.dataset.block]; blk.page++; t.textContent = '…';
      const data = await api('/api/search?' + qs({q: blk.q, ...prefParams(), page: blk.page, limit: 12}));
      blk.data.results.push(...data.results);
      t.insertAdjacentHTML('beforebegin', data.results.map(productCard).join(''));
      if (data.total > (data.page + 1) * data.limit) t.textContent = 'نتایج بیشتر'; else t.remove();
    } else if (a === 'cmp-add') {const p = findProduct(t.dataset.pid); S.compare.set(p.product_id, p); renderTray(); toast('به مقایسه اضافه شد')}
    else if (a === 'do-compare') {const ids = [...S.compare.keys()].slice(0, 4); S.compare.clear(); renderTray(); $$('.pcard.sel').forEach(x => {x.classList.remove('sel'); const c = $('input', x); if (c) c.checked = false}); await doCompare(ids)}
    else if (a === 'clear-cmp') {S.compare.clear(); renderTray(); $$('.pcard.sel').forEach(x => {x.classList.remove('sel'); const c = $('input', x); if (c) c.checked = false})}
    else if (a === 'pop-budget') popBudget(t);
    else if (a === 'pop-radius') popRadius(t);
    else if (a === 'pop-location') popLocation(t);
    else if (a === 'toggle') patchPrefs({[t.dataset.key]: !S.prefs[t.dataset.key]});
    else if (a === 'clear-map') Map_.clear();
    else if (a === 'cancel-pick') stopPick();
  } catch (err) {console.error(err); toast('خطا در دریافت اطلاعات؛ دوباره امتحان کن')}
});
document.addEventListener('change', e => {
  const t = e.target.closest('[data-act="cmp"]'); if (!t) return;
  const pid = t.dataset.pid;
  if (t.checked) {if (S.compare.size >= 4) {t.checked = false; return toast('حداکثر ۴ کالا')} S.compare.set(pid, findProduct(pid))} else S.compare.delete(pid);
  t.closest('.pcard')?.classList.toggle('sel', t.checked); renderTray();
});
document.addEventListener('keydown', e => {if (e.key === 'Escape') {closeSheet(); closePopover(); stopPick()}});
$('#composer').addEventListener('submit', e => {e.preventDefault(); const v = $('#input').value.trim(); if (!v) return; $('#input').value = ''; autosize(); ask(v)});
const autosize = () => {const i = $('#input'); i.style.height = 'auto'; i.style.height = Math.min(140, i.scrollHeight) + 'px'};
$('#input').addEventListener('input', autosize);
$('#input').addEventListener('keydown', e => {if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {e.preventDefault(); $('#composer').requestSubmit()}});
$('#toMap').onclick = () => setView('map');
$('#toChat').onclick = () => setView('chat');
$('#locateBtn').onclick = locateMe;
$('#newChat').onclick = async () => {store.del('torob.sid'); S.blocks = {}; S.step = 0; S.compare.clear(); renderTray(); Map_.clear(); await newSession(); welcome()};
$('#themeBtn').onclick = () => {
  const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = dark ? 'light' : 'dark'; store.set('torob.theme', document.documentElement.dataset.theme);
};

/* ------------------------------------------------------------------ boot */
const statsHtml = h => h ? `<div class="stats"><span><b>${fa(h.products)}</b> کالا</span><span><b>${fa(h.shops)}</b> فروشگاه حضوری</span><span><b>${fa(h.offers)}</b> قیمت ثبت‌شده</span></div>` : '<div class="stats"></div>';
function welcome() {
  const h = S.health;
  thread.innerHTML = `<div class="welcome">${mascot()}
    <h2>سلام! من تربچه‌ام 👋</h2>
    <p>بگو دنبال چی هستی. کمکت می‌کنم مدل مناسب رو انتخاب کنی، فروشگاه‌های حضوری نزدیکت رو پیدا و مقایسه کنم و قبل از رفتن از فروشنده موجودی و قیمت روز رو بپرسم.</p>
    ${statsHtml(h)}
    <div class="starters">
      <button class="starter" type="button" data-act="prompt" data-text="یه گوشی سامسونگ تا ۳۰ میلیون می‌خوام که بشه قسطی خرید"><span class="em">📱</span>یه گوشی سامسونگ تا ۳۰ میلیون، قسطی</button>
      <button class="starter" type="button" data-act="prompt" data-text="هدفون بی‌سیم خوب برای ورزش، نمی‌دونم کدوم مدل بهتره"><span class="em">🎧</span>هدفون بی‌سیم برای ورزش؛ کدوم مدل؟</button>
      <button class="starter" type="button" data-act="prompt" data-text="دوربین مداربسته وای‌فای نزدیک جمهوری که الان باز باشه"><span class="em">📷</span>دوربین مداربسته نزدیک جمهوری، الان باز</button>
      <button class="starter" type="button" data-act="prompt" data-text="ساعت هوشمند زیر ۵ میلیون، دو تا مدل خوب رو مقایسه کن"><span class="em">⌚</span>ساعت هوشمند زیر ۵ میلیون + مقایسه</button>
    </div></div>`;
  setSuggestions([]); setStep(0); $$('#steps li').forEach(li => li.className = '');
}
async function newSession() {
  const s = await api('/api/sessions', {method: 'POST', body: {}});
  S.sid = s.id; S.prefs = s.preferences; store.set('torob.sid', S.sid); renderPrefs();
}
(async function boot() {
  const theme = store.get('torob.theme'); if (theme) document.documentElement.dataset.theme = theme;
  $('#logo').innerHTML = MASCOT;
  const cfg = await api('/api/map-config').catch(() => ({tile_url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '© OpenStreetMap'}));
  Map_.init(cfg);
  api('/api/health').then(h => {S.health = h; const st = $('.welcome .stats'); if (st) st.outerHTML = statsHtml(h)}).catch(() => {});
  const saved = store.get('torob.sid');
  let restored = false;
  if (saved) {
    try {
      const sum = await api(`/api/sessions/${saved}/summary`);
      S.sid = saved; S.prefs = sum.preferences; renderPrefs();
      if (sum.chat_history?.length) {
        thread.innerHTML = '';
        for (const m of sum.chat_history) m.role === 'user' ? addUser(m.content) : addBot(m.content);
        addBlock('<div class="note">— ادامه گفتگوی قبلی · برای شروع تازه دکمه + را بزن —</div>');
        restored = true;
      }
    } catch {store.del('torob.sid')}
  }
  if (!S.sid) await newSession();
  if (!restored) welcome();
  if (S.prefs.lat != null) Map_.fly(S.prefs.lat, S.prefs.lon, 13);
  window.addEventListener('resize', Map_.invalidate);
})();
