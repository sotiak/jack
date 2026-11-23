const root = document.documentElement;
const poster = new URLSearchParams(location.search).get('poster');
if (['hero', 'grid', 'design', 'features'].includes(poster)) root.dataset.poster = poster;
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
const charItalic = document.querySelector('#characters-italic');
function updateItalicUI() {
  charItalic.checked = root.dataset.italic === 'on';
}
function setItalic(on) {
  if (on) root.dataset.italic = 'on';
  else delete root.dataset.italic;
  try { localStorage.setItem('italic', on ? '1' : '0'); } catch {}
  updateItalicUI();
}
charItalic.addEventListener('change', () => setItalic(charItalic.checked));
updateItalicUI();
const charactersSection = document.querySelector('#characters');
const weightButtons = [...charactersSection.querySelectorAll('[data-weight]')];
function setWeight(weight) {
  charactersSection.dataset.weight = weight;
  weightButtons.forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.weight === weight));
  });
}
weightButtons.forEach(button => button.addEventListener('click', () => setWeight(button.dataset.weight)));
setWeight('regular');
const compareStage = document.querySelector('.compare-stage');
const compareSplit = document.querySelector('#compare-split');
const compareFont = document.querySelector('#compare-font');
const compareTargetLabel = document.querySelector('.compare-target-label');
const compareTargetImage = document.querySelector('.compare-layer.target img');
const compareTargets = {
  iosevka: 'compare/iosevka.png',
  jetbrains: 'compare/jetbrains.png',
  consolas: 'compare/consolas.png',
};
function setSplit(value) {
  const clamped = Math.max(0, Math.min(100, Number(value)));
  compareSplit.value = clamped;
  compareStage.style.setProperty('--split', String(clamped / 100));
}
function setCompareFont(name) {
  compareStage.dataset.target = name;
  compareFont.value = name;
  compareTargetImage.src = compareTargets[name];
  compareTargetLabel.textContent = compareFont.selectedOptions[0].textContent;
}
compareSplit.addEventListener('input', () => setSplit(compareSplit.value));
compareFont.addEventListener('change', () => setCompareFont(compareFont.value));
setSplit(compareSplit.value);
setCompareFont('iosevka');
window.addEventListener('storage', event => {
  if (event.key === 'theme') {
    if (['light', 'dark'].includes(event.newValue)) root.dataset.theme = event.newValue;
    else delete root.dataset.theme;
    updateThemeLabel();
  } else if (event.key === 'italic') {
    if (event.newValue === '1') root.dataset.italic = 'on';
    else delete root.dataset.italic;
    updateItalicUI();
  }
});
updateThemeLabel();
document.querySelector('aside details').open = !matchMedia('(max-width: 860px)').matches;
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
