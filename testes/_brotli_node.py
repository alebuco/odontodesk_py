"""Só para os testes neste ambiente: se o pacote "brotli" não estiver instalado, usa o brotli do Node.js
(o mesmo algoritmo) por um subprocesso. Nos computadores da clínica e no servidor o pacote vem do requirements.txt."""
import subprocess
import sys
import types

JS = r"""
const z = require('zlib'); const [mode, q, w] = process.argv.slice(1);
const chunks = []; process.stdin.on('data', c => chunks.push(c)).on('end', () => {
  const b = Buffer.concat(chunks);
  const out = mode === 'c' ? z.brotliCompressSync(b, { params: { [z.constants.BROTLI_PARAM_QUALITY]: +q, [z.constants.BROTLI_PARAM_LGWIN]: +w } }) : z.brotliDecompressSync(b);
  process.stdout.write(out);
});
"""


def _run(args, data):
    r = subprocess.run(["node", "-e", JS, *args], input=data, capture_output=True, check=True)
    return r.stdout


def instalar():
    try:
        import brotli  # noqa: F401
        return
    except ImportError:
        pass
    m = types.ModuleType("brotli")
    m.compress = lambda data, quality=11, lgwin=22, **k: _run(["c", str(quality), str(lgwin)], bytes(data))
    m.decompress = lambda data: _run(["d", "0", "0"], bytes(data))
    sys.modules["brotli"] = m
