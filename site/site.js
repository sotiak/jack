const root = document.documentElement;
const poster = new URLSearchParams(location.search).get('poster');
if (['hero', 'weights', 'design', 'features'].includes(poster)) root.dataset.poster = poster;
const systemTheme = matchMedia('(prefers-color-scheme: dark)');
const themeButton = document.querySelector('#theme');
function updateThemeLabel() {
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : systemTheme.matches;
  themeButton.textContent = dark ? 'ライトに切替' : 'ダークに切替';
}
themeButton.hidden = false;
themeButton.addEventListener('click', () => {
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : systemTheme.matches;
  const next = dark ? 'light' : 'dark';
  root.dataset.theme = next;
  try { localStorage.setItem('theme', next); } catch {}
  updateThemeLabel();
});
systemTheme.addEventListener('change', updateThemeLabel);
window.addEventListener('storage', event => {
  if (event.key !== 'theme') return;
  if (['light', 'dark'].includes(event.newValue)) root.dataset.theme = event.newValue;
  else delete root.dataset.theme;
  updateThemeLabel();
});
updateThemeLabel();
document.querySelector('aside details').open = !matchMedia('(max-width: 760px)').matches;
const sections = [...document.querySelectorAll('main section[id]')];
const observer = new IntersectionObserver(entries => {
  const visible = entries.find(entry => entry.isIntersecting);
  if (!visible) return;
  document.querySelectorAll('aside a').forEach(link => {
    if (link.hash === `#${visible.target.id}`) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
}, { rootMargin: '0px 0px -65% 0px' });
sections.forEach(section => observer.observe(section));

// Preserve the original Texture Healing controls and sweep behaviour.
const demo = document.querySelector('.demo');
const canvas = document.querySelector('.canvas');
const off = document.querySelector('.layer.off');
const on = document.querySelector('.layer.on');
const sample = document.querySelector('#sample');
const reveal = document.querySelector('#reveal');
const revealValue = document.querySelector('#reveal-value');
const size = document.querySelector('#size');
const sizeValue = document.querySelector('#size-value');
const diff = document.querySelector('#diff');
const sweep = document.querySelector('#sweep');
function setText(value) { off.textContent = value; on.textContent = value; }
function setReveal(value) {
  const clamped = Math.max(0, Math.min(100, Number(value)));
  reveal.value = clamped;
  canvas.style.setProperty('--reveal', `${clamped}%`);
  revealValue.value = `${Math.round(clamped)}%`;
  reveal.setAttribute('aria-valuetext', `${Math.round(clamped)}% calt on`);
}
function setSize(value) {
  const clamped = Math.max(48, Math.min(132, Number(value)));
  size.value = clamped;
  canvas.style.setProperty('--size', `${clamped}px`);
  sizeValue.value = `${clamped}px`;
  size.setAttribute('aria-valuetext', `${clamped} pixels`);
}
let sweepFrame = 0;
function updateDiff() {
  cancelAnimationFrame(sweepFrame);
  demo.classList.toggle('diff', diff.checked);
  reveal.disabled = diff.checked;
  sweep.disabled = diff.checked;
  revealValue.value = diff.checked ? '—' : `${Math.round(Number(reveal.value))}%`;
}
function sweepOnce() {
  cancelAnimationFrame(sweepFrame);
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) { setReveal(50); return; }
  const start = performance.now();
  const frame = now => {
    const t = Math.min(1, (now - start) / 2200);
    setReveal(Math.round((1 - Math.cos(t * Math.PI * 2)) / 2 * 100));
    if (t < 1) sweepFrame = requestAnimationFrame(frame);
    else setReveal(50);
  };
  sweepFrame = requestAnimationFrame(frame);
}
sample.addEventListener('input', () => setText(sample.value));
reveal.addEventListener('input', () => { cancelAnimationFrame(sweepFrame); setReveal(reveal.value); });
size.addEventListener('input', () => setSize(size.value));
diff.addEventListener('change', updateDiff);
sweep.addEventListener('click', sweepOnce);
document.querySelectorAll('[data-sample]').forEach(button => {
  button.addEventListener('click', () => {
    sample.value = button.dataset.sample.replaceAll('|', '\n');
    setText(sample.value);
    sample.focus();
  });
});
setText(sample.value);
setReveal(reveal.value);
setSize(size.value);
updateDiff();
