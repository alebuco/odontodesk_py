// Usado por testes/test_convivencia.py: o app em JavaScript (server/store.js) lê e grava no mesmo banco SQLite.
// node convivencia.js <pasta-do-odontodesk-js> <arquivo.db> <acao> [json]
const [, , JSDIR, FILE, ACAO, ARG] = process.argv;
const { createStore } = require(JSDIR + '/server/store.js');
const { createSqliteDriver } = require(JSDIR + '/testes/driver-sqlite.js');
(async () => {
  const st = createStore(createSqliteDriver(FILE), { computer: 'RECEPCAO-JS' });
  let out;
  if (ACAO === 'init') { await st.init(); out = { ok: true }; }
  else if (ACAO === 'load') out = await st.loadAll();
  else if (ACAO === 'changes') out = await st.changes(JSON.parse(ARG || '{}'));
  else if (ACAO === 'apply') out = await st.apply(JSON.parse(ARG));
  else if (ACAO === 'filePut') { const a = JSON.parse(ARG); await st.filePut(a.name, require('fs').readFileSync(a.path)); out = await st.fileMeta(a.name); }
  else if (ACAO === 'fileGet') { const a = JSON.parse(ARG); const b = await st.fileGet(a.name); require('fs').writeFileSync(a.path, b); out = { size: b.length, meta: await st.fileMeta(a.name) }; }
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
