// Verify docs/parity-board.html without a browser: run the page's own script
// against a five-line DOM stub and let *the page* decide whether it passes.
//
//   node tools/board_check.js docs/parity-board.html
//
// Exit 0 only when the page's SELF-CHECK section says PASS and the table it
// rendered has one row per audited repository plus the "this repo" row.
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');

if (/https?:\/\//.test(html)) {
  console.error('FAIL the board must not reference anything outside the file');
  process.exit(3);
}

const snapJson = html.match(/<script id="snap"[^>]*>([\s\S]*?)<\/script>/);
const jsSrc = html.match(/<script>\s*\n([\s\S]*?)<\/script>/);
if (!snapJson || !jsSrc) {
  console.error('FAIL the board is missing its snapshot block or its script');
  process.exit(4);
}

const nodes = { snap: { id: 'snap', textContent: snapJson[1], innerHTML: '', style: {} } };
const mk = (id) => (nodes[id] = nodes[id] || { id, textContent: '', innerHTML: '', style: {} });
const document = { getElementById: (id) => mk(id) };
const consoleStub = { log: () => {}, error: () => {} };

const fn = new Function('document', 'console', 'JSON', 'Math', 'window', jsSrc[1]);
const win = {};
fn(document, consoleStub, JSON, Math, win);

const sc = nodes['sc'] ? nodes['sc'].textContent : '';
process.stdout.write(sc + '\n');
if (!/SELF-CHECK PASS/.test(sc)) {
  console.error('FAIL the page reported a failing self-check');
  process.exit(1);
}

const snap = JSON.parse(snapJson[1]);
const rows = (nodes['rows'].innerHTML.match(/<tr/g) || []).length;
if (rows !== snap.summary_repos + 1) {
  console.error('FAIL rendered ' + rows + ' rows, expected ' + (snap.summary_repos + 1));
  process.exit(2);
}
console.log('rows=' + rows);
