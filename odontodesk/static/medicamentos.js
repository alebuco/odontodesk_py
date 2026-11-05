/* Banco de medicamentos do OdontoDesk.
   - Lista embutida com os medicamentos mais usados em odontologia: nome genérico (DCB), nomes comerciais
     de referência, apresentações/dosagens, tipo de receita exigido e posologia USUAL EM ADULTOS (sugestão:
     o dentista revisa e ajusta para cada paciente).
   - Pode ser ampliada com a lista oficial de preços da CMED/ANVISA (planilha) e com itens cadastrados pela clínica.
   Tipos de receita:
     simples        → receituário comum (1 via)
     antimicrobiano → RDC 471/2021: 2 vias (1ª paciente, 2ª retida na farmácia), validade 10 dias
     controle       → Receita de Controle Especial (Portaria 344/98, modelo da RDC 1.000/2025): 2 vias, CPF do paciente
     notificacao    → exige Notificação de Receita (A amarela / B azul) do talonário da Vigilância — não é impressa pelo app */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Medicamentos = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  const M = (id, g, brands, tipo, grupo, apres, extra = {}) => ({ id, g, brands, tipo, grupo, apres, ...extra });
  const A = (a, uso, qtd, pos) => ({ a, uso, qtd, pos });
  const LIST = [
    // ---------- antimicrobianos ----------
    M('amox', 'Amoxicilina', ['Amoxil', 'Novocilin'], 'antimicrobiano', 'penicilina', [
      A('500 mg, cápsula', 'oral', '21 cápsulas', ['Tomar 1 cápsula de 8 em 8 horas por 7 dias.', 'Profilaxia: tomar 4 cápsulas (2 g) 1 hora antes do procedimento.']),
      A('875 mg, comprimido', 'oral', '14 comprimidos', ['Tomar 1 comprimido de 12 em 12 horas por 7 dias.']),
      A('250 mg/5 mL, pó para suspensão oral', 'oral', '1 frasco', ['Dose conforme o peso (pediátrico): ___ mL de 8 em 8 horas por 7 dias.']),
      A('500 mg/5 mL, pó para suspensão oral', 'oral', '1 frasco', ['Dose conforme o peso (pediátrico): ___ mL de 8 em 8 horas por 7 dias.'])]),
    M('amoxclav', 'Amoxicilina + clavulanato de potássio', ['Clavulin'], 'antimicrobiano', 'penicilina', [
      A('875 mg + 125 mg, comprimido', 'oral', '14 comprimidos', ['Tomar 1 comprimido de 12 em 12 horas por 7 dias, no início das refeições.']),
      A('500 mg + 125 mg, comprimido', 'oral', '21 comprimidos', ['Tomar 1 comprimido de 8 em 8 horas por 7 dias, no início das refeições.']),
      A('250 mg + 62,5 mg/5 mL, pó para suspensão oral', 'oral', '1 frasco', ['Dose conforme o peso (pediátrico): ___ mL de 8 em 8 horas por 7 dias.'])]),
    M('azitro', 'Azitromicina', ['Zitromax', 'Azi'], 'antimicrobiano', 'macrolideo', [
      A('500 mg, comprimido', 'oral', '3 comprimidos', ['Tomar 1 comprimido uma vez ao dia por 3 dias.', 'Profilaxia (alérgicos à penicilina): tomar 1 comprimido (500 mg) 1 hora antes do procedimento.']),
      A('200 mg/5 mL, pó para suspensão oral', 'oral', '1 frasco', ['Dose conforme o peso (pediátrico): ___ mL uma vez ao dia por 3 dias.'])]),
    M('clinda', 'Cloridrato de clindamicina', ['Dalacin C'], 'antimicrobiano', 'lincosamida', [
      A('300 mg, cápsula', 'oral', '21 cápsulas', ['Tomar 1 cápsula de 8 em 8 horas por 7 dias.', 'Profilaxia (alérgicos à penicilina): tomar 2 cápsulas (600 mg) 1 hora antes do procedimento.']),
      A('150 mg, cápsula', 'oral', '28 cápsulas', ['Tomar ___ cápsula(s) de 6 em 6 horas por 7 dias.'])]),
    M('metro', 'Metronidazol', ['Flagyl'], 'antimicrobiano', 'nitroimidazol', [
      A('400 mg, comprimido', 'oral', '21 comprimidos', ['Tomar 1 comprimido de 8 em 8 horas por 7 dias. Não ingerir bebida alcoólica durante o tratamento e até 2 dias após.']),
      A('250 mg, comprimido', 'oral', '21 comprimidos', ['Tomar 1 comprimido de 8 em 8 horas por 7 dias. Não ingerir bebida alcoólica durante o tratamento e até 2 dias após.'])]),
    M('cefalex', 'Cefalexina', ['Keflex'], 'antimicrobiano', 'cefalosporina', [
      A('500 mg, cápsula', 'oral', '28 cápsulas', ['Tomar 1 cápsula de 6 em 6 horas por 7 dias.']),
      A('250 mg/5 mL, pó para suspensão oral', 'oral', '1 frasco', ['Dose conforme o peso (pediátrico): ___ mL de 6 em 6 horas por 7 dias.'])]),
    M('doxi', 'Cloridrato de doxiciclina', ['Vibramicina'], 'antimicrobiano', 'tetraciclina', [
      A('100 mg, comprimido', 'oral', '8 comprimidos', ['Tomar 2 comprimidos no primeiro dia e, depois, 1 comprimido ao dia por mais 6 dias.'])]),
    // ---------- analgésicos e anti-inflamatórios ----------
    M('dipirona', 'Dipirona monoidratada', ['Novalgina', 'Anador'], 'simples', 'dipirona', [
      A('500 mg, comprimido', 'oral', '12 comprimidos', ['Tomar 1 comprimido de 6 em 6 horas, se houver dor.']),
      A('1 g, comprimido', 'oral', '8 comprimidos', ['Tomar 1 comprimido de 6 em 6 horas, se houver dor.']),
      A('500 mg/mL, solução oral (gotas)', 'oral', '1 frasco', ['Tomar 40 gotas de 6 em 6 horas, se houver dor.'])]),
    M('paracet', 'Paracetamol', ['Tylenol'], 'simples', 'paracetamol', [
      A('750 mg, comprimido', 'oral', '12 comprimidos', ['Tomar 1 comprimido de 6 em 6 horas, se houver dor. Não ultrapassar 4 comprimidos por dia.']),
      A('500 mg, comprimido', 'oral', '12 comprimidos', ['Tomar 1 a 2 comprimidos de 6 em 6 horas, se houver dor.']),
      A('200 mg/mL, solução oral (gotas)', 'oral', '1 frasco', ['Dose conforme o peso (pediátrico): ___ gotas de 6 em 6 horas, se houver dor.'])]),
    M('ibupro', 'Ibuprofeno', ['Advil', 'Alivium'], 'simples', 'aine', [
      A('400 mg, comprimido', 'oral', '9 comprimidos', ['Tomar 1 comprimido de 8 em 8 horas por 3 dias, após as refeições.']),
      A('600 mg, comprimido', 'oral', '9 comprimidos', ['Tomar 1 comprimido de 8 em 8 horas por 3 dias, após as refeições.']),
      A('50 mg/mL, suspensão oral (gotas)', 'oral', '1 frasco', ['Dose conforme o peso (pediátrico): ___ gotas de 8 em 8 horas, se houver dor.'])]),
    M('nimesu', 'Nimesulida', ['Nisulid'], 'simples', 'aine', [
      A('100 mg, comprimido', 'oral', '6 comprimidos', ['Tomar 1 comprimido de 12 em 12 horas por 3 dias, após as refeições.'])]),
    M('diclo', 'Diclofenaco potássico', ['Cataflam'], 'simples', 'aine', [
      A('50 mg, comprimido', 'oral', '9 comprimidos', ['Tomar 1 comprimido de 8 em 8 horas por 3 dias, após as refeições.'])]),
    M('cetoro', 'Trometamol cetorolaco', ['Toragesic'], 'simples', 'aine', [
      A('10 mg, comprimido sublingual', 'sublingual', '10 comprimidos', ['Colocar 1 comprimido sob a língua de 8 em 8 horas, se houver dor, por no máximo 3 dias.'])]),
    M('dexa', 'Dexametasona', ['Decadron'], 'simples', 'corticoide', [
      A('4 mg, comprimido', 'oral', '2 comprimidos', ['Tomar 2 comprimidos (8 mg) 1 hora antes do procedimento, em dose única.'])]),
    // ---------- uso bucal / tópico ----------
    M('clorex', 'Digluconato de clorexidina', ['Periogard'], 'simples', 'antisseptico', [
      A('0,12%, solução para bochecho', 'bucal', '1 frasco', ['Bochechar 15 mL, sem diluir, por 1 minuto, 2 vezes ao dia, por 7 dias. Não engolir. Aguardar 30 minutos após a escovação.'])]),
    M('nista', 'Nistatina', ['Micostatin'], 'simples', 'antifungico', [
      A('100.000 UI/mL, suspensão oral', 'bucal', '1 frasco', ['Bochechar 5 mL por 1 minuto, 4 vezes ao dia, e engolir, por 14 dias.'])]),
    M('micona', 'Nitrato de miconazol', ['Daktarin gel oral'], 'simples', 'antifungico', [
      A('20 mg/g, gel oral', 'bucal', '1 bisnaga', ['Aplicar sobre a lesão 4 vezes ao dia, após as refeições, por 7 a 14 dias.'])]),
    M('aciclo', 'Aciclovir', ['Zovirax'], 'simples', 'antiviral', [
      A('50 mg/g (5%), creme', 'topico', '1 bisnaga', ['Aplicar sobre a lesão 5 vezes ao dia por 5 dias, iniciando aos primeiros sintomas.']),
      A('200 mg, comprimido', 'oral', '25 comprimidos', ['Tomar 1 comprimido 5 vezes ao dia por 5 dias.'])]),
    M('trianc', 'Triancinolona acetonida', ['Omcilon-A Orabase'], 'simples', 'corticoide', [
      A('1 mg/g, pomada orabase', 'bucal', '1 bisnaga', ['Aplicar uma fina camada sobre a lesão 2 a 3 vezes ao dia, após as refeições, por 7 dias.'])]),
    // ---------- controle especial (Portaria 344/98) ----------
    M('codeina', 'Paracetamol + fosfato de codeína', ['Tylex'], 'controle', 'opioide', [
      A('500 mg + 30 mg, comprimido', 'oral', '12 comprimidos', ['Tomar 1 comprimido de 6 em 6 horas, se houver dor intensa, por no máximo 3 dias.'])], { lista: 'A2 (adendo) — Receita de Controle Especial' }),
    M('tramadol', 'Cloridrato de tramadol', ['Tramal'], 'controle', 'opioide', [
      A('50 mg, cápsula', 'oral', '10 cápsulas', ['Tomar 1 cápsula de 8 em 8 horas, se houver dor intensa.'])], { lista: 'A2 (adendo) — Receita de Controle Especial' }),
    M('carbama', 'Carbamazepina', ['Tegretol'], 'controle', 'anticonvulsivante', [
      A('200 mg, comprimido', 'oral', '___ comprimidos', ['Conforme orientação: ___'])], { lista: 'C1 — Receita de Controle Especial' }),
    // ---------- notificação B (sedação) ----------
    M('diazep', 'Diazepam', ['Valium'], 'notificacao', 'benzodiazepinico', [
      A('5 mg, comprimido', 'oral', '1 comprimido', ['Tomar 1 comprimido 1 hora antes do procedimento.']),
      A('10 mg, comprimido', 'oral', '1 comprimido', ['Tomar 1 comprimido 1 hora antes do procedimento.'])], { lista: 'B1 — Notificação de Receita B (azul)' }),
    M('midaz', 'Midazolam', ['Dormonid'], 'notificacao', 'benzodiazepinico', [
      A('15 mg, comprimido', 'oral', '1 comprimido', ['Tomar 1 comprimido 30 minutos antes do procedimento.'])], { lista: 'B1 — Notificação de Receita B (azul)' })
  ];
  const TIPOS = {
    simples: { label: 'Receita simples', curto: 'Simples', cls: '' },
    antimicrobiano: { label: 'Antimicrobiano (RDC 471/2021 — 2 vias)', curto: 'Antimicrobiano', cls: 'warn' },
    controle: { label: 'Controle especial (Portaria 344 — Receita de Controle Especial)', curto: 'Controle especial', cls: 'bad' },
    notificacao: { label: 'Notificação de Receita (A/B) — talonário da Vigilância', curto: 'Notificação', cls: 'bad' }
  };
  const USOS = { oral: 'Uso oral', bucal: 'Uso bucal (oral tópico)', topico: 'Uso tópico', sublingual: 'Uso sublingual', outro: 'Outro uso' };
  // grupos para alerta de alergia: palavras que, no cadastro/anamnese, indicam alergia a este medicamento
  const ALERGIA = {
    penicilina: ['penicilin', 'amoxicilin', 'ampicilin', 'amoxil', 'clavulin', 'benzetacil'],
    cefalosporina: ['cefalosporin', 'cefalexin', 'keflex'],
    macrolideo: ['azitromicin', 'eritromicin', 'claritromicin'],
    lincosamida: ['clindamicin'], nitroimidazol: ['metronidazol'], tetraciclina: ['tetraciclin', 'doxiciclin'],
    dipirona: ['dipirona', 'novalgina', 'metamizol'], paracetamol: ['paracetamol', 'tylenol'],
    aine: ['ibuprofen', 'nimesulid', 'diclofenac', 'cetorolac', 'cetoprofen', 'naproxen', 'anti-inflamat', 'antiinflamat', 'aine', 'aspirin', 'ácido acetilsalic', 'aas'],
    opioide: ['codein', 'tramadol', 'morfin', 'opio'], corticoide: ['dexametason', 'corticoide', 'triancinolon'],
    antisseptico: ['clorexidin'], antifungico: ['nistatin', 'miconazol'], antiviral: ['aciclovir'],
    anticonvulsivante: ['carbamazepin'], benzodiazepinico: ['diazepam', 'midazolam', 'benzodiazep']
  };
  const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  // nomes de substâncias que definem o tipo, para itens vindos da CMED ou digitados
  const RULES = [
    [/amoxicilin|ampicilin|penicilin|cefalexin|cefadroxil|cefuroxim|ceftriaxon|azitromicin|claritromicin|eritromicin|clindamicin|metronidazol|doxiciclin|tetraciclin|minociclin|ciprofloxacin|levofloxacin|moxifloxacin|sulfametoxazol|trimetoprim|nitrofurantoin|linezolid|vancomicin|gentamicin|amicacin/, 'antimicrobiano'],
    [/diazepam|midazolam|alprazolam|clonazepam|lorazepam|bromazepam|zolpidem|triazolam|nitrazepam|flunitrazepam|morfin|oxicodon|metadon|fentanil|petidin|buprenorfin/, 'notificacao'],
    [/codein|tramadol|carbamazepin|gabapentin|pregabalin|amitriptilin|nortriptilin|fluoxetin|sertralin|paroxetin|citalopram|escitalopram|venlafaxin|duloxetin|topiramato|fenitoin|acido valproico|valproato|lamotrigin|haloperidol|quetiapin|risperidon|olanzapin/, 'controle']
  ];
  function tipoPorNome(name) { const n = norm(name); for (const [re, t] of RULES) if (re.test(n)) return t; return ''; }

  // Lista oficial de preços (CMED/ANVISA): acha a linha de títulos e converte. Retorna {itens, ignorados}.
  function fromCMED(rows) {
    const H = (r) => r.map(c => norm(c).replace(/\s+/g, ' ').trim());
    let hi = -1, h = [];
    for (let i = 0; i < Math.min(rows.length, 120); i++) { h = H(rows[i] || []); if (h.includes('substancia') && h.includes('produto') && h.some(x => x.startsWith('apresentacao'))) { hi = i; break; } }
    if (hi < 0) throw new Error('Não encontrei as colunas SUBSTÂNCIA, PRODUTO e APRESENTAÇÃO. Use a planilha da lista de preços da CMED (ANVISA).');
    const col = (pred) => h.findIndex(pred);
    const cS = col(x => x === 'substancia'), cP = col(x => x === 'produto'), cA = col(x => x.startsWith('apresentacao')), cL = col(x => x.startsWith('laboratorio'));
    const cC = col(x => x.startsWith('classe terapeutica')), cT = col(x => x.startsWith('tarja')), cTipo = col(x => x.startsWith('tipo de produto')), cR = col(x => x.startsWith('restricao hospitalar'));
    const seen = new Set(), out = []; let ignored = 0;
    for (const r of rows.slice(hi + 1)) {
      const g = String(r[cS] || '').trim(), p = String(r[cP] || '').trim(), a = String(r[cA] || '').trim();
      if (!g || !p || !a) { ignored++; continue; }
      if (cR >= 0 && /^sim/i.test(String(r[cR] || ''))) { ignored++; continue; } // uso hospitalar
      const key = norm(g + '|' + p + '|' + a); if (seen.has(key)) continue; seen.add(key);
      const cls = String(r[cC] || ''), tarja = String(r[cT] || '');
      let tipo = tipoPorNome(g) || (/^\s*J1/i.test(cls) ? 'antimicrobiano' : /preta/i.test(tarja) ? 'controle' : 'simples');
      out.push({ g: cap(g), p, a, l: cL >= 0 ? String(r[cL] || '').trim() : '', tipo, tarja: tarja.trim(), cls: cls.trim(), status: cTipo >= 0 ? String(r[cTipo] || '').trim() : '' });
    }
    return { itens: out, ignorados: ignored };
  }
  function cap(s) { s = String(s).toLowerCase(); return s.replace(/(^|[\s+(/-])([a-zà-ú])/g, (m, a, b) => a + b.toUpperCase()).replace(/\b(De|Da|Do|Das|Dos|E|Com)\b/g, (w) => w.toLowerCase()); }

  // Busca por genérico, comercial ou dosagem. catalogo/proprios: listas extras.
  function search(q, { catalogo = [], proprios = [], limit = 30 } = {}) {
    const t = norm(q).trim(); if (t.length < 2) return [];
    const words = t.split(/\s+/);
    const hit = (txt) => { const n = norm(txt); return words.every(w => n.includes(w)); };
    const out = [];
    for (const m of [...proprios, ...LIST]) {
      const txt = [m.g, ...(m.brands || []), ...m.apres.map(a => a.a)].join(' ');
      if (hit(txt)) out.push({ src: m.proprio ? 'clinica' : 'base', med: m, score: norm(m.g).startsWith(words[0]) || (m.brands || []).some(b => norm(b).startsWith(words[0])) ? 0 : 1 });
    }
    for (const c of catalogo) {
      if (out.length > 400) break;
      if (hit(c.g + ' ' + c.p + ' ' + c.a)) out.push({ src: 'cmed', item: c, score: norm(c.p).startsWith(words[0]) || norm(c.g).startsWith(words[0]) ? 2 : 3 });
    }
    return out.sort((a, b) => a.score - b.score).slice(0, limit);
  }
  // Alergias registradas no cadastro/anamnese que batem com o medicamento
  function allergyHits(grupo, nomeMed, texto) {
    const t = norm(texto); if (!t) return [];
    const words = [...(ALERGIA[grupo] || []), ...norm(nomeMed).split(/[^a-z0-9]+/).filter(w => w.length > 5).map(w => w.slice(0, -1))];
    if (!/alerg|reac|intoler|hipersens/.test(t)) return [];
    return [...new Set(words.filter(w => t.includes(w)))];
  }
  function grupoPorNome(name) { const n = norm(name); for (const [g, ws] of Object.entries(ALERGIA)) if (ws.some(w => n.includes(w))) return g; return ''; }

  // Quantidade por extenso (ajuda contra adulteração): "21 cápsulas" → "21 (vinte e uma) cápsulas"
  const UN = ['zero', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove', 'dez', 'onze', 'doze', 'treze', 'quatorze', 'quinze', 'dezesseis', 'dezessete', 'dezoito', 'dezenove'];
  const DZ = ['', '', 'vinte', 'trinta', 'quarenta', 'cinquenta', 'sessenta', 'setenta', 'oitenta', 'noventa'];
  const CT = ['', 'cento', 'duzentos', 'trezentos', 'quatrocentos', 'quinhentos', 'seiscentos', 'setecentos', 'oitocentos', 'novecentos'];
  function extenso(n, fem) {
    if (n === 100) return 'cem';
    const f = (w) => fem ? w.replace(/^um$/, 'uma').replace(/^dois$/, 'duas').replace(/entos$/, 'entas') : w;
    if (n < 20) return f(UN[n]);
    if (n < 100) return DZ[Math.floor(n / 10)] + (n % 10 ? ' e ' + f(UN[n % 10]) : '');
    if (n < 1000) return f(CT[Math.floor(n / 100)]) + (n % 100 ? ' e ' + extenso(n % 100, fem) : '');
    return String(n);
  }
  const FEM = /^(c[aá]psulas?|dr[aá]geas?|ampolas?|bisnagas?|gotas?|unidades?|pastilhas?|seringas?|caixas?|cartelas?)\b/i;
  function qtdExtenso(q) {
    const m = /^\s*(\d{1,3})\s+(.+)$/.exec(String(q || '')); if (!m) return q;
    const n = Number(m[1]); if (!n) return q;
    return `${n} (${extenso(n, FEM.test(m[2]))}) ${m[2]}`;
  }
  return { LIST, TIPOS, USOS, search, fromCMED, tipoPorNome, grupoPorNome, allergyHits, qtdExtenso, extenso, norm };
});
