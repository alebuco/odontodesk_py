// Odontograma: clicar num dente seleciona o dente; clicar nas faces marca/desmarca a face.
// A seleção vai para os campos escondidos do formulário "Adicionar".
(function () {
  var sel = { tooth: null, faces: [] };
  var info = document.getElementById('selInfo'), tooth = document.getElementById('selTooth'), faces = document.getElementById('selFaces');
  var add = document.getElementById('addBtn'), clr = document.getElementById('clrSel');
  if (!tooth) return;
  function pinta() {
    document.querySelectorAll('#odonto .tooth').forEach(function (t) {
      var n = Number(t.dataset.n), ativo = n === sel.tooth;
      t.classList.toggle('selected', ativo);
      t.querySelectorAll('[data-face]').forEach(function (f) {
        if (!f.dataset.orig) f.dataset.orig = f.getAttribute('class') || '';
        f.setAttribute('class', ativo && sel.faces.indexOf(f.dataset.face) >= 0 ? 'sel' : f.dataset.orig);
      });
    });
    tooth.value = sel.tooth || ''; faces.value = sel.faces.join(',');
    info.innerHTML = '<b>' + (sel.tooth ? 'Dente ' + sel.tooth : 'Clique num dente/face') + '</b>' + (sel.faces.length ? ' · faces: ' + sel.faces.join(', ') : '');
    add.textContent = sel.tooth ? 'Adicionar ao dente' : 'Adicionar (geral / arcada)';
    clr.classList.toggle('hidden', !sel.tooth);
  }
  document.querySelectorAll('#odonto svg[data-tooth]').forEach(function (svg) {
    svg.addEventListener('click', function (e) {
      var n = Number(svg.dataset.tooth), face = e.target.dataset && e.target.dataset.face;
      if (sel.tooth !== n) { sel.tooth = n; sel.faces = []; }
      if (face) { var i = sel.faces.indexOf(face); if (i >= 0) sel.faces.splice(i, 1); else sel.faces.push(face); }
      pinta();
    });
  });
  clr.addEventListener('click', function () { sel = { tooth: null, faces: [] }; pinta(); });
})();
