// Formulário de receita (o mesmo do app do computador): busca de medicamentos, itens, dados exigidos por tipo,
// alertas de alergia e conferências. O servidor confere tudo de novo antes de gravar.
(function () {
  'use strict';
  var CFG = window.RX_CFG, MED = window.Medicamentos, rx = CFG.rx, catalogo = { itens: [] };
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var uid = function () { return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4); };
  var dig = function (s) { return String(s || '').replace(/\D/g, ''); };
  function cpfValido(v) { var d = dig(v); if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false; function dv(n) { var s = 0; for (var i = 0; i < n; i++) s += +d[i] * (n + 1 - i); var r = (s * 10) % 11; return r === 10 ? 0 : r; } return dv(9) === +d[9] && dv(10) === +d[10]; }
  var KIND = { simples: 'Receita simples · 1 via', antimicrobiano: 'Receita de antimicrobiano · 2 vias (RDC 471/2021)', controle: 'Receita de Controle Especial · 2 vias' };
  function docs(items) {
    var por = function (t) { return items.filter(function (i) { return i.tipo === t; }); }, out = [], ce = por('controle'), am = por('antimicrobiano'), si = por('simples');
    for (var i = 0; i < ce.length; i += 3) out.push({ kind: 'controle', items: ce.slice(i, i + 3) });
    if (am.length) out.push({ kind: 'antimicrobiano', items: am.concat(si) }); else if (si.length) out.push({ kind: 'simples', items: si });
    return out;
  }
  // ----- cabeçalho -----
  $('#rxDen').innerHTML = '<option value="">Selecione…</option>' + CFG.dentistas.map(function (d) { return '<option value="' + d.id + '"' + (d.id === rx.dentistId ? ' selected' : '') + '>' + esc(d.name + (d.cro ? ' — ' + d.cro : '')) + '</option>'; }).join('');
  $('#rxDate').value = rx.date; $('#rxLayout').value = rx.layout || 'duas';
  fetch(CFG.catalogo, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (c) { catalogo = c || { itens: [] }; base(); }).catch(base);
  function base() { var n = (catalogo.itens || []).length; $('#rxBase').textContent = MED.LIST.length + ' medicamentos odontológicos' + (n ? ' + ' + n.toLocaleString('pt-BR') + ' da lista CMED/ANVISA' : '') + (CFG.proprios.length ? ' + ' + CFG.proprios.length + ' da clínica' : '') + '.'; }
  // ----- busca -----
  var q = $('#rxQ'), res = $('#rxRes'), linhas = [];
  var tag = function (t) { return '<span class="tag ' + ((MED.TIPOS[t] || {}).cls || '') + '">' + esc((MED.TIPOS[t] || {}).curto || t) + '</span>'; };
  q.oninput = function () {
    var r = MED.search(q.value, { catalogo: catalogo.itens || [], proprios: CFG.proprios.map(function (m) { return Object.assign({}, m, { proprio: true }); }), limit: 40 });
    linhas = [];
    r.forEach(function (x) {
      if (x.med) x.med.apres.forEach(function (a, k) { linhas.push({ r: x, k: k, html: '<b>' + esc(x.med.g) + '</b> ' + esc(a.a) + ' ' + tag(x.med.tipo) + '<div class="muted small">' + esc((x.med.brands || []).join(', ')) + (x.src === 'clinica' ? ' · cadastrado pela clínica' : '') + '</div>' }); });
      else linhas.push({ r: x, html: '<b>' + esc(x.item.p) + '</b> <span class="muted">(' + esc(x.item.g) + ')</span> ' + tag(x.item.tipo) + '<div class="muted small">' + esc(x.item.a) + ' · ' + esc(x.item.l) + ' · CMED</div>' });
    });
    res.innerHTML = linhas.length ? linhas.slice(0, 40).map(function (x, i) { return '<div class="rx-opt" data-i="' + i + '">' + x.html + '</div>'; }).join('') : (q.value.trim().length >= 2 ? '<div class="rx-opt muted">Nada encontrado. Use "+ Medicamento sem cadastro".</div>' : '');
    res.classList.toggle('hidden', !res.innerHTML);
    $$('[data-i]', res).forEach(function (o) { o.onmousedown = function (e) { e.preventDefault(); adicionar(linhas[+o.dataset.i]); }; });
  };
  q.onblur = function () { setTimeout(function () { res.classList.add('hidden'); }, 150); };
  q.onkeydown = function (e) { if (e.key === 'Enter') { e.preventDefault(); var f = $('[data-i]', res); if (f) f.dispatchEvent(new MouseEvent('mousedown')); } };
  function adicionar(row) {
    ler();
    if (row.r.med) { var m = row.r.med, a = m.apres[row.k]; rx.items.push({ id: uid(), medId: m.id, src: row.r.src, g: m.g, brand: (m.brands || [])[0] || '', brandPrint: false, a: a.a, uso: a.uso, qtd: a.qtd, pos: a.pos[0] || '', posOpts: a.pos, tipo: m.tipo, grupo: m.grupo, lista: m.lista || '', continuo: false }); }
    else { var c = row.r.item, cap = function (s) { return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase(); }; rx.items.push({ id: uid(), src: 'cmed', g: c.g, brand: cap(c.p), brandPrint: true, a: c.a.toLowerCase(), uso: 'oral', qtd: '', pos: '', posOpts: [], tipo: c.tipo, grupo: MED.grupoPorNome(c.g), lista: c.tarja && /preta/i.test(c.tarja) ? 'Tarja preta — confira a lista da Portaria 344' : '', continuo: false }); }
    q.value = ''; res.classList.add('hidden'); desenhar();
    var ult = $$('.rx-item').pop(); if (ult) { var f = ult.querySelector(row.r.med ? '[data-k=pos]' : '[data-k=qtd]'); if (f) f.focus(); }
  }
  $('#rxFree').onclick = function () { ler(); rx.items.push({ id: uid(), src: 'livre', g: '', brand: '', a: '', uso: 'oral', qtd: '', pos: '', posOpts: [], tipo: 'simples', grupo: '', continuo: false }); desenhar(); $$('.rx-item [data-k=g]').pop().focus(); };
  // ----- itens -----
  function ler() {
    $$('.rx-item').forEach(function (el) { var it = rx.items.find(function (x) { return x.id === el.dataset.id; }); if (!it) return; $$('[data-k]', el).forEach(function (f) { it[f.dataset.k] = f.type === 'checkbox' ? f.checked : f.value; }); });
    if ($('#rxSexo')) rx.sexo = $('#rxSexo').value; if ($('#rxIdade')) rx.idade = $('#rxIdade').value;
    if ($('#rxCpf')) rx.cpf = $('#rxCpf').value; if ($('#rxSemCpf')) rx.cpfNaoPossui = $('#rxSemCpf').checked;
    rx.dentistId = $('#rxDen').value; rx.date = $('#rxDate').value; rx.layout = $('#rxLayout').value;
  }
  var opts = function (pairs, cur) { return pairs.map(function (p) { return '<option value="' + esc(p[0]) + '"' + (p[0] === cur ? ' selected' : '') + '>' + esc(p[1]) + '</option>'; }).join(''); };
  function desenhar() {
    $('#rxItems').innerHTML = rx.items.length ? rx.items.map(function (it, n) {
      return '<div class="rx-item" data-id="' + it.id + '"><div class="rx-ih"><b>' + (n + 1) + '.</b> <select data-k="tipo" class="rx-tipo">' + opts(Object.keys(MED.TIPOS).map(function (k) { return [k, MED.TIPOS[k].curto]; }), it.tipo) + '</select>' +
        (it.lista ? ' <span class="muted small">' + esc(it.lista) + '</span>' : '') + '<span class="grow"></span>' +
        '<button type="button" class="btn sm icon-b" data-up="' + n + '"' + (n ? '' : ' disabled') + ' title="Subir">↑</button><button type="button" class="btn sm icon-b" data-rm="' + n + '" title="Remover">×</button></div>' +
        '<div class="form rx-if"><label>Medicamento (nome genérico)<input data-k="g" value="' + esc(it.g) + '" placeholder="ex.: Amoxicilina"></label>' +
        '<label>Concentração e forma<input data-k="a" value="' + esc(it.a) + '" placeholder="ex.: 500 mg, cápsula"></label>' +
        '<label>Quantidade<input data-k="qtd" value="' + esc(it.qtd) + '" placeholder="ex.: 21 cápsulas"></label>' +
        '<label>Uso<select data-k="uso">' + opts(Object.keys(MED.USOS).map(function (k) { return [k, MED.USOS[k]]; }), it.uso || 'oral') + '</select></label>' +
        '<label class="full">Posologia' + (it.posOpts && it.posOpts.length > 1 ? ' <select class="rx-posopt" data-po="' + n + '"><option value="">outras sugestões…</option>' + it.posOpts.map(function (x, k) { return '<option value="' + k + '">' + esc(x.slice(0, 70)) + (x.length > 70 ? '…' : '') + '</option>'; }).join('') + '</select>' : '') +
        '<textarea data-k="pos" rows="2">' + esc(it.pos) + '</textarea></label>' +
        '<div class="full row rx-checks">' + (it.brand ? '<label class="check"><input type="checkbox" data-k="brandPrint"' + (it.brandPrint ? ' checked' : '') + '> Imprimir também o nome comercial (' + esc(it.brand) + ')</label>' : '') +
        (it.tipo === 'antimicrobiano' ? '<label class="check"><input type="checkbox" data-k="continuo"' + (it.continuo ? ' checked' : '') + '> Uso prolongado (receita vale 90 dias; informe a quantidade para 30 dias)</label>' : '') + '</div>' +
        (it.src === 'base' || it.src === 'clinica' ? '<div class="full muted small">Posologia usual em adultos — revise para este paciente.</div>' : '') + '</div></div>';
    }).join('') : '<div class="empty">Busque um medicamento acima para começar.</div>';
    $$('#rxItems [data-k]').forEach(function (f) {
      if (f.tagName === 'SELECT' || f.type === 'checkbox') f.addEventListener('change', function () { ler(); if (f.dataset.k === 'tipo' || f.dataset.k === 'continuo') desenhar(); else conferir(); });
      else f.addEventListener('input', reconferir);
    });
    $$('#rxItems [data-rm]').forEach(function (b) { b.onclick = function () { ler(); rx.items.splice(+b.dataset.rm, 1); desenhar(); }; });
    $$('#rxItems [data-up]').forEach(function (b) { b.onclick = function () { ler(); var i = +b.dataset.up, t = rx.items[i - 1]; rx.items[i - 1] = rx.items[i]; rx.items[i] = t; desenhar(); }; });
    $$('#rxItems [data-po]').forEach(function (s) { s.onchange = function () { ler(); var it = rx.items[+s.dataset.po]; if (s.value !== '') { it.pos = it.posOpts[+s.value]; desenhar(); } }; });
    paciente(); conferir();
  }
  function paciente() {
    var tipos = rx.items.map(function (i) { return i.tipo; }), am = tipos.indexOf('antimicrobiano') >= 0, ce = tipos.indexOf('controle') >= 0, el = $('#rxPat');
    if (!am && !ce) { el.innerHTML = ''; return; }
    el.innerHTML = '<div class="card rx-patcard"><b>Dados do paciente exigidos</b> <span class="muted small">' + (am ? 'antimicrobiano: idade e sexo' : '') + (am && ce ? ' · ' : '') + (ce ? 'controle especial: CPF e endereço' : '') + '</span><div class="form" style="margin-top:6px">' +
      (am ? '<label>Idade<input id="rxIdade" value="' + esc(rx.idade) + '" inputmode="numeric" placeholder="anos"></label><label>Sexo<select id="rxSexo">' + opts([['', 'Selecione…'], ['F', 'Feminino'], ['M', 'Masculino']], rx.sexo) + '</select></label>' : '') +
      (ce ? '<label>CPF<input id="rxCpf" value="' + esc(rx.cpf) + '"' + (rx.cpfNaoPossui ? ' disabled' : '') + ' placeholder="000.000.000-00"></label><label class="check"><input type="checkbox" id="rxSemCpf"' + (rx.cpfNaoPossui ? ' checked' : '') + '> Paciente não possui CPF</label>' +
        '<label class="full">Endereço completo<input value="' + esc(CFG.endereco) + '" disabled placeholder="(cadastre o endereço na ficha do paciente)"></label>' : '') + '</div></div>';
    $$('input, select', el).forEach(function (f) {
      if (f.tagName === 'SELECT' || f.type === 'checkbox') f.addEventListener('change', function () { ler(); if (f.id === 'rxSemCpf') paciente(); conferir(); });
      else f.addEventListener('input', reconferir);
    });
  }
  var t0 = 0; function reconferir() { clearTimeout(t0); t0 = setTimeout(function () { ler(); conferir(); }, 250); }
  function conferir() {
    var errs = [], avisos = [], den = CFG.dentistas.find(function (d) { return d.id === $('#rxDen').value; });
    if (!den) errs.push('Selecione o dentista.'); else if (!den.cro) errs.push('Cadastre o CRO de ' + esc(den.name) + ' (Configurações → Dentistas).');
    rx.items.forEach(function (it) {
      var h = MED.allergyHits(it.grupo || MED.grupoPorNome(it.g), it.g, CFG.alergia);
      if (h.length) avisos.push('<b>Atenção — possível alergia:</b> ' + esc(it.g || '') + ' (o cadastro/anamnese menciona “' + esc(h[0]) + '”).');
      if (it.tipo === 'notificacao') errs.push('<b>' + esc(it.g) + '</b> exige <b>Notificação de Receita</b> (' + esc(it.lista || 'A amarela ou B azul') + '), do talonário numerado da Vigilância Sanitária. Retire da receita e preencha a notificação à mão.');
    });
    var d = docs(rx.items.filter(function (i) { return i.tipo !== 'notificacao'; }));
    if (d.some(function (x) { return x.kind !== 'simples'; }) && !CFG.clinicaOk) errs.push('Antimicrobianos e controle especial exigem endereço completo e telefone da clínica no cabeçalho (Configurações → Clínica).');
    var ce = rx.items.filter(function (i) { return i.tipo === 'controle'; });
    if (ce.length) {
      if (!rx.cpfNaoPossui && !cpfValido(rx.cpf)) errs.push('Receita de controle especial: informe um CPF válido ou marque "não possui".');
      if (!CFG.endereco) errs.push('Receita de controle especial: cadastre o endereço completo do paciente na ficha.');
      if (ce.length > 3) avisos.push(ce.length + ' medicamentos de controle especial: serão impressas ' + Math.ceil(ce.length / 3) + ' receitas (até 3 por receita).');
    }
    if (rx.items.some(function (i) { return i.tipo === 'antimicrobiano'; })) {
      if (!String(rx.idade || '').trim()) errs.push('Antimicrobiano: informe a idade do paciente.');
      if (!rx.sexo) errs.push('Antimicrobiano: informe o sexo do paciente.');
    }
    $('#rxAlerts').innerHTML = avisos.map(function (w) { return '<div class="alert">' + w + '</div>'; }).join('') + errs.map(function (e) { return '<div class="alert rx-err">' + e + '</div>'; }).join('');
    $('#rxSum').innerHTML = d.length ? '<b>Será impresso:</b> ' + d.map(function (x) { return '<span class="tag ' + (x.kind === 'simples' ? '' : x.kind === 'antimicrobiano' ? 'warn' : 'bad') + '">' + KIND[x.kind] + '</span>'; }).join(' ') : '';
    return errs;
  }
  $('#rxDen').onchange = function () { ler(); conferir(); };
  $('#ok').onclick = function () {
    ler();
    var itens = rx.items.filter(function (i) { return i.g.trim() || i.pos.trim(); });
    if (!itens.length) return alert('Inclua ao menos um medicamento');
    for (var k = 0; k < itens.length; k++) {
      var i = itens[k];
      if (!i.g.trim()) return alert('Item ' + (k + 1) + ': informe o medicamento');
      if (!String(i.qtd).trim()) return alert(i.g + ': informe a quantidade');
      if (!i.pos.trim()) return alert(i.g + ': informe a posologia');
    }
    rx.items = itens;
    if (conferir().length) { $('#rxAlerts').scrollIntoView({ block: 'center' }); return; }
    var f = new FormData(); f.append('_csrf', window.RX_CSRF); f.append('dados', JSON.stringify(rx));
    $('#ok').disabled = true;
    fetch(CFG.salvar, { method: 'POST', body: f, credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok) { $('#ok').disabled = false; $('#rxAlerts').innerHTML = (j.erros || ['Não foi possível salvar']).map(function (e) { return '<div class="alert rx-err">' + esc(e) + '</div>'; }).join(''); return; }
      window.open(j.imprimir, '_blank'); location.href = j.voltar;
    }).catch(function () { $('#ok').disabled = false; alert('Sem conexão com o servidor. Tente de novo.'); });
  };
  desenhar();
  setTimeout(function () { q.focus(); }, 50);
})();
