const activeParticles = new Set(['呢','啊','嗯','呃','哎','唉','哦']);

function escapeRegex(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

const PUNCT = '[，,、；;\\s]';

function applyParticles(text) {
  if (activeParticles.size === 0) return text;
  const pats = [...activeParticles].map(p => escapeRegex(p));
  const pGroup = '(?:' + pats.join('|') + ')';

  // Three cases (applied in order):
  // 1. particle(s) at start followed by punct: "嗯，" → ""
  // 2. particle(s) at end optionally preceded by punct: "，啊" or "啊" → ""
  // 3. particle(s) in middle with punct on both sides: "，呃，" → "，"
  let r = text;

  // case 3: punct + particle(s) + punct  →  keep only the first punct
  r = r.replace(new RegExp('(' + PUNCT + '+)' + pGroup + '+' + '(' + PUNCT + '+)', 'g'),
    (_, pre) => pre);

  // case 1: start of string, particle(s) + optional punct
  r = r.replace(new RegExp('^' + pGroup + '+' + PUNCT + '*', 'g'), '');

  // case 2: optional punct + particle(s) at end of string
  r = r.replace(new RegExp(PUNCT + '*' + pGroup + '+$', 'g'), '');

  // case 1b: particle standalone (no surrounding punct caught above)
  r = r.replace(new RegExp(pGroup + '+', 'g'), '');

  // clean up leading/trailing punct
  r = r.replace(new RegExp('^' + PUNCT + '+'), '').replace(new RegExp(PUNCT + '+$'), '');

  return r;
}

const tests = [
  ['嗯', ''],
  ['嗯，今天我们来做这个', '今天我们来做这个'],
  ['看到还真是有点套路啊', '看到还真是有点套路'],
  ['然后呢，我们要证明', '然后，我们要证明'],
  ['那个上次我们做这个，呃', '那个上次我们做这个'],
  ['这个，呃， A 、 D 啊', '这个，A 、 D'],
  ['嗯，然后呢', '然后'],
  ['哎，所以呢', '所以'],
  ['60，哎，60，60', '60，60，60'],
  ['对，然后呢，我们就看', '对，然后，我们就看'],
];

let pass = true;
tests.forEach(([input, expected]) => {
  const got = applyParticles(input);
  const ok = got === expected;
  if (!ok) pass = false;
  console.log((ok ? '✓' : '✗') + ' ' + JSON.stringify(input) + ' → ' + JSON.stringify(got) + (ok ? '' : '  (expected: ' + JSON.stringify(expected) + ')'));
});
console.log(pass ? '\n全部通过' : '\n有失败项');
