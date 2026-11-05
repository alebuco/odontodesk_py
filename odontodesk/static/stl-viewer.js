/* Visualizador STL do OdontoDesk — WebGL2 puro, sem dependências.
   STLViewer.parse(ArrayBuffer)  -> malha {positions, normals, triangles, min, max}
   STLViewer.create(canvas)      -> visualizador interativo
   STLViewer.thumbnail(malha)    -> dataURL JPEG para a galeria */
(function () {
  'use strict';

  // ---------- leitura do STL ----------
  function parse(buf) {
    const dv = new DataView(buf);
    if (buf.byteLength >= 84) {
      const n = dv.getUint32(80, true);
      if (n > 0 && 84 + n * 50 === buf.byteLength) {
        const p = new Float32Array(n * 9);
        let o = 84;
        for (let i = 0; i < n; i++) {
          o += 12; // normal do arquivo (recalculada abaixo)
          for (let j = 0; j < 9; j++) { p[i * 9 + j] = dv.getFloat32(o, true); o += 4; }
          o += 2;
        }
        return build(p);
      }
    }
    const text = new TextDecoder().decode(buf);
    const re = /vertex\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)/g;
    const arr = []; let m;
    while ((m = re.exec(text))) arr.push(+m[1], +m[2], +m[3]);
    if (!arr.length || arr.length % 9) throw new Error('Arquivo STL inválido ou corrompido');
    return build(new Float32Array(arr));
  }

  function build(p) {
    const nrm = new Float32Array(p.length);
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < p.length; i += 9) {
      const ax = p[i], ay = p[i + 1], az = p[i + 2];
      const ux = p[i + 3] - ax, uy = p[i + 4] - ay, uz = p[i + 5] - az;
      const vx = p[i + 6] - ax, vy = p[i + 7] - ay, vz = p[i + 8] - az;
      let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;
      for (let k = 0; k < 9; k += 3) {
        nrm[i + k] = nx; nrm[i + k + 1] = ny; nrm[i + k + 2] = nz;
        for (let a = 0; a < 3; a++) { const v = p[i + k + a]; if (v < min[a]) min[a] = v; if (v > max[a]) max[a] = v; }
      }
    }
    if (!isFinite(min[0])) throw new Error('Arquivo STL sem geometria');
    return { positions: p, normals: nrm, triangles: p.length / 9, min, max };
  }

  // ---------- matrizes (coluna-maior) ----------
  const M = {
    id() { const m = new Float32Array(16); m[0] = m[5] = m[10] = m[15] = 1; return m; },
    mul(a, b) { const o = new Float32Array(16); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k]; o[c * 4 + r] = s; } return o; },
    tr(x, y, z) { const m = M.id(); m[12] = x; m[13] = y; m[14] = z; return m; },
    rx(a) { const m = M.id(), c = Math.cos(a), s = Math.sin(a); m[5] = c; m[6] = s; m[9] = -s; m[10] = c; return m; },
    ry(a) { const m = M.id(), c = Math.cos(a), s = Math.sin(a); m[0] = c; m[2] = -s; m[8] = s; m[10] = c; return m; },
    persp(f, asp, n, fa) { const t = 1 / Math.tan(f / 2), m = new Float32Array(16); m[0] = t / asp; m[5] = t; m[10] = (fa + n) / (n - fa); m[11] = -1; m[14] = 2 * fa * n / (n - fa); return m; },
    tvec(R, v) { return [0, 1, 2].map(r => R[r * 4] * v[0] + R[r * 4 + 1] * v[1] + R[r * 4 + 2] * v[2]); } // Rᵀ·v
  };

  const VS = `#version 300 es
  in vec3 aPos; in vec3 aNor; uniform mat4 uP, uMV, uR; out vec3 vN; out vec3 vV;
  void main(){ vec4 p = uMV * vec4(aPos,1.0); vV = -p.xyz; vN = mat3(uR) * aNor; gl_Position = uP * p; }`;
  const FS = `#version 300 es
  precision highp float; in vec3 vN; in vec3 vV; uniform vec3 uColor; uniform float uAlpha; out vec4 o;
  void main(){
    vec3 n = normalize(vN); if(!gl_FrontFacing) n = -n; vec3 v = normalize(vV);
    vec3 l1 = normalize(vec3(0.35,0.55,1.0)), l2 = normalize(vec3(-0.7,-0.3,0.5));
    float d = max(dot(n,l1),0.0)*0.72 + max(dot(n,l2),0.0)*0.28;
    float s = pow(max(dot(n, normalize(l1+v)),0.0), 48.0) * 0.28;
    o = vec4(uColor*(0.24+d) + vec3(s), uAlpha);
  }`;
  const VS2 = `#version 300 es
  in vec3 aPos; uniform mat4 uP, uMV; uniform float uSize; void main(){ gl_Position = uP*uMV*vec4(aPos,1.0); gl_PointSize = uSize; }`;
  const FS2 = `#version 300 es
  precision highp float; uniform vec3 uColor; uniform float uSize; out vec4 o;
  void main(){ if (uSize > 4.0 && length(gl_PointCoord - 0.5) > 0.5) discard; o = vec4(uColor,1.0); }`;

  function program(gl, vs, fs) {
    const sh = (t, s) => { const x = gl.createShader(t); gl.shaderSource(x, s); gl.compileShader(x); if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(x)); return x; };
    const p = gl.createProgram(); gl.attachShader(p, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    const u = {}; ['uP', 'uMV', 'uR', 'uColor', 'uAlpha', 'uSize'].forEach(n => u[n] = gl.getUniformLocation(p, n));
    return { p, u, aPos: gl.getAttribLocation(p, 'aPos'), aNor: gl.getAttribLocation(p, 'aNor') };
  }
  const hex = (h) => { const n = parseInt(h.replace('#', ''), 16); return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255]; };

  // ---------- visualizador ----------
  function create(canvas, opts = {}) {
    const gl = canvas.getContext('webgl2', { antialias: true, preserveDrawingBuffer: true, alpha: false });
    if (!gl) throw new Error('Este computador não suporta WebGL2, necessário para o visualizador 3D.');
    const prog = program(gl, VS, FS), prog2 = program(gl, VS2, FS2);
    const meshes = new Map();
    const FOV = 35 * Math.PI / 180;
    let R = M.id(), center = [0, 0, 0], dist = 100, radius = 50, pan = [0, 0];
    let measuring = false, points = [], raf = 0;
    const markBuf = gl.createBuffer();
    const bg = hex(opts.background || '#e9eef2');
    const api = { onMeasure: null };

    function size() {
      if (opts.fixedSize) return;
      const dpr = window.devicePixelRatio || 1, w = Math.max(1, Math.round(canvas.clientWidth * dpr)), h = Math.max(1, Math.round(canvas.clientHeight * dpr));
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    }
    const mv = () => M.mul(M.tr(pan[0], pan[1], -dist), M.mul(R, M.tr(-center[0], -center[1], -center[2])));
    const proj = () => M.persp(FOV, canvas.width / canvas.height, Math.max(dist - radius * 4, dist / 200), dist + radius * 4);

    function draw() {
      raf = 0; size();
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(bg[0], bg[1], bg[2], 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST);
      const P = proj(), MV = mv();
      gl.useProgram(prog.p);
      gl.uniformMatrix4fv(prog.u.uP, false, P); gl.uniformMatrix4fv(prog.u.uMV, false, MV); gl.uniformMatrix4fv(prog.u.uR, false, R);
      const list = [...meshes.values()].filter(m => m.visible);
      const pass = (arr) => arr.forEach(m => {
        gl.bindVertexArray(m.vao); gl.uniform3fv(prog.u.uColor, hex(m.color)); gl.uniform1f(prog.u.uAlpha, m.alpha);
        gl.drawArrays(gl.TRIANGLES, 0, m.count);
      });
      gl.disable(gl.BLEND); gl.depthMask(true); pass(list.filter(m => m.alpha >= 1));
      const tr = list.filter(m => m.alpha < 1);
      if (tr.length) { gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false); pass(tr); gl.depthMask(true); gl.disable(gl.BLEND); }
      gl.bindVertexArray(null);
      if (points.length) {
        gl.disable(gl.DEPTH_TEST); gl.useProgram(prog2.p);
        gl.uniformMatrix4fv(prog2.u.uP, false, P); gl.uniformMatrix4fv(prog2.u.uMV, false, MV);
        gl.bindBuffer(gl.ARRAY_BUFFER, markBuf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(points.flat()), gl.DYNAMIC_DRAW);
        gl.enableVertexAttribArray(prog2.aPos); gl.vertexAttribPointer(prog2.aPos, 3, gl.FLOAT, false, 0, 0);
        gl.uniform3fv(prog2.u.uColor, [0.86, 0.15, 0.15]); gl.uniform1f(prog2.u.uSize, 3);
        gl.drawArrays(gl.LINES, 0, points.length - (points.length % 2));
        gl.uniform1f(prog2.u.uSize, 9 * (window.devicePixelRatio || 1)); gl.drawArrays(gl.POINTS, 0, points.length);
        gl.disableVertexAttribArray(prog2.aPos);
      }
    }
    const render = () => { if (opts.fixedSize) draw(); else if (!raf) raf = requestAnimationFrame(draw); };

    api.add = (id, mesh, o = {}) => {
      const vao = gl.createVertexArray(); gl.bindVertexArray(vao);
      const pb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, pb); gl.bufferData(gl.ARRAY_BUFFER, mesh.positions, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(prog.aPos); gl.vertexAttribPointer(prog.aPos, 3, gl.FLOAT, false, 0, 0);
      const nb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, nb); gl.bufferData(gl.ARRAY_BUFFER, mesh.normals, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(prog.aNor); gl.vertexAttribPointer(prog.aNor, 3, gl.FLOAT, false, 0, 0);
      gl.bindVertexArray(null);
      meshes.set(id, { mesh, vao, pb, nb, count: mesh.positions.length / 3, color: o.color || '#e8dcc8', alpha: o.alpha ?? 1, visible: o.visible ?? true });
      render();
    };
    api.remove = (id) => { const m = meshes.get(id); if (!m) return; gl.deleteBuffer(m.pb); gl.deleteBuffer(m.nb); gl.deleteVertexArray(m.vao); meshes.delete(id); render(); };
    api.has = (id) => meshes.has(id);
    api.set = (id, o) => { const m = meshes.get(id); if (m) { Object.assign(m, o); render(); } };
    api.fit = () => {
      const vis = [...meshes.values()].filter(m => m.visible); if (!vis.length) return;
      const mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
      vis.forEach(m => { for (let a = 0; a < 3; a++) { mn[a] = Math.min(mn[a], m.mesh.min[a]); mx[a] = Math.max(mx[a], m.mesh.max[a]); } });
      center = mn.map((v, a) => (v + mx[a]) / 2);
      radius = Math.max(1e-3, Math.hypot(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]) / 2);
      dist = radius / Math.sin(FOV / 2) * 1.05; pan = [0, 0]; render();
    };
    const VIEWS = { frente: () => M.id(), tras: () => M.ry(Math.PI), topo: () => M.rx(Math.PI / 2), base: () => M.rx(-Math.PI / 2), esquerda: () => M.ry(Math.PI / 2), direita: () => M.ry(-Math.PI / 2) };
    api.view = (name) => { R = (VIEWS[name] || VIEWS.frente)(); api.fit(); };
    api.rotate = (axis, deg) => { const a = deg * Math.PI / 180; R = M.mul(axis === 'x' ? M.rx(a) : M.ry(a), R); render(); };
    api.render = render;
    api.snapshot = () => { draw(); return canvas.toDataURL('image/png'); };

    // medição
    const measures = () => { const out = []; for (let i = 0; i + 1 < points.length; i += 2) { const [a, b] = [points[i], points[i + 1]]; out.push(Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])); } return out; };
    api.measureMode = (on) => { measuring = on; canvas.style.cursor = on ? 'crosshair' : 'grab'; };
    api.clearMeasures = () => { points = []; api.onMeasure && api.onMeasure([], 0); render(); };
    function pick(cx, cy) {
      const r = canvas.getBoundingClientRect();
      const nx = ((cx - r.left) / r.width) * 2 - 1, ny = 1 - ((cy - r.top) / r.height) * 2;
      const th = Math.tan(FOV / 2), asp = canvas.width / canvas.height;
      const o = M.tvec(R, [-pan[0], -pan[1], dist]).map((v, i) => v + center[i]);
      const d = M.tvec(R, [nx * th * asp, ny * th, -1]);
      let best = Infinity;
      meshes.forEach(m => {
        if (!m.visible) return; const p = m.mesh.positions;
        for (let i = 0; i < p.length; i += 9) {
          const ax = p[i], ay = p[i + 1], az = p[i + 2];
          const e1x = p[i + 3] - ax, e1y = p[i + 4] - ay, e1z = p[i + 5] - az, e2x = p[i + 6] - ax, e2y = p[i + 7] - ay, e2z = p[i + 8] - az;
          const px = d[1] * e2z - d[2] * e2y, py = d[2] * e2x - d[0] * e2z, pz = d[0] * e2y - d[1] * e2x;
          const det = e1x * px + e1y * py + e1z * pz; if (det > -1e-12 && det < 1e-12) continue;
          const inv = 1 / det, tx = o[0] - ax, ty = o[1] - ay, tz = o[2] - az;
          const u = (tx * px + ty * py + tz * pz) * inv; if (u < 0 || u > 1) continue;
          const qx = ty * e1z - tz * e1y, qy = tz * e1x - tx * e1z, qz = tx * e1y - ty * e1x;
          const v = (d[0] * qx + d[1] * qy + d[2] * qz) * inv; if (v < 0 || u + v > 1) continue;
          const t = (e2x * qx + e2y * qy + e2z * qz) * inv; if (t > 1e-9 && t < best) best = t;
        }
      });
      if (!isFinite(best)) return;
      points.push([o[0] + d[0] * best, o[1] + d[1] * best, o[2] + d[2] * best]);
      api.onMeasure && api.onMeasure(measures(), points.length % 2);
      render();
    }

    // interação: esquerdo gira · direito/Shift move · roda aproxima
    let drag = null;
    const down = (e) => { drag = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, pan: e.button !== 0 || e.shiftKey }; canvas.setPointerCapture?.(e.pointerId); if (!measuring) canvas.style.cursor = 'grabbing'; };
    const move = (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY;
      if (drag.pan) { const k = (2 * dist * Math.tan(FOV / 2)) / canvas.clientHeight; pan[0] += dx * k; pan[1] -= dy * k; }
      else R = M.mul(M.ry(dx * 0.01), M.mul(M.rx(dy * 0.01), R));
      render();
    };
    const up = (e) => {
      if (!drag) return;
      const click = Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) < 4 && !drag.pan;
      drag = null; if (!measuring) canvas.style.cursor = 'grab';
      if (click && measuring) pick(e.clientX, e.clientY);
    };
    const wheel = (e) => { e.preventDefault(); dist *= Math.exp(e.deltaY * 0.0012); dist = Math.min(Math.max(dist, radius * 0.05), radius * 40); render(); };
    const ctx = (e) => e.preventDefault();
    if (!opts.fixedSize) {
      canvas.style.cursor = 'grab'; canvas.style.touchAction = 'none';
      canvas.addEventListener('pointerdown', down); window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
      canvas.addEventListener('wheel', wheel, { passive: false }); canvas.addEventListener('contextmenu', ctx);
    }
    const ro = !opts.fixedSize && typeof ResizeObserver !== 'undefined' ? new ResizeObserver(render) : null; ro && ro.observe(canvas);

    api.destroy = () => {
      if (raf) cancelAnimationFrame(raf); ro && ro.disconnect();
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up);
      [...meshes.keys()].forEach(api.remove);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    };
    return api;
  }

  function thumbnail(mesh, color = '#e8dcc8') {
    const c = document.createElement('canvas'); c.width = 360; c.height = 270;
    const v = create(c, { fixedSize: true, background: '#e9eef2' });
    v.add('m', mesh, { color }); v.view('frente');
    const url = c.toDataURL('image/jpeg', 0.85); v.destroy(); return url;
  }

  window.STLViewer = { parse, create, thumbnail };
})();
