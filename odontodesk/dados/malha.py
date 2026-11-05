"""Malha indexada do OdontoDesk: o mesmo formato de server/mesh-pack.js (app em JavaScript).

O STL binário repete cada ponto ~6 vezes. Aqui cada ponto é guardado uma vez (bits exatos do float32), os
triângulos apontam para os pontos e as normais são recalculadas na reconstrução — com as MESMAS contas do app em
JavaScript (float64, gravadas em float32), para o arquivo reconstruído ser idêntico byte a byte nos dois apps.

Formato: "ODMESH1\\n" | versão u8 | flags u8 (1 = atributos) | 2 reservados | triângulos u32 | pontos u32 |
         cabeçalho STL (80 bytes) | brotli(pontos em planos de bytes + índices codificados + atributos)
"""
import struct

import numpy as np

MAGIC = b"ODMESH1\n"
HEAD = len(MAGIC) + 4 + 8 + 80


def _brotli():
    import brotli  # pacote "Brotli" (requirements.txt)
    return brotli


def eh_compactada(buf):
    return bool(buf) and len(buf) >= HEAD and buf[:len(MAGIC)] == MAGIC


def eh_stl_binario(buf):
    if not buf or len(buf) < 134:
        return False
    t = struct.unpack_from("<I", buf, 80)[0]
    return t > 0 and len(buf) == 84 + t * 50


def _planos(b, s):
    """Separa os bytes por posição (todos os 1ºs bytes, depois os 2ºs…): compacta muito melhor."""
    return np.frombuffer(b, dtype=np.uint8).reshape(-1, s).T.copy().tobytes()


def _de_planos(b, s):
    return np.frombuffer(b, dtype=np.uint8).reshape(s, -1).T.copy().tobytes()


def _triangulos(stl):
    t = struct.unpack_from("<I", stl, 80)[0]
    rec = np.frombuffer(stl, dtype=np.uint8, offset=84, count=t * 50).reshape(t, 50)
    return t, rec


def compactar(stl):
    """STL → (compactado, canônico) ou None se não for STL binário. Confere a reconstrução antes de aceitar."""
    if not eh_stl_binario(stl):
        return None
    T, rec = _triangulos(stl)
    cantos = np.ascontiguousarray(rec[:, 12:48]).reshape(T * 3, 12)
    chaves = cantos.view(np.dtype((np.void, 12))).ravel()
    # cada ponto distinto recebe um número na ordem em que aparece pela 1ª vez
    _, primeiro, inverso = np.unique(chaves, return_index=True, return_inverse=True)
    ordem = np.argsort(primeiro, kind="stable")            # números na ordem de aparição
    numero = np.empty_like(ordem)
    numero[ordem] = np.arange(len(ordem))
    ids = numero[inverso.ravel()]                           # número do ponto de cada canto
    V = len(ordem)
    pos_primeira = primeiro[ordem]                          # canto onde cada ponto aparece pela 1ª vez
    novo = np.zeros(T * 3, dtype=bool)
    novo[pos_primeira] = True
    # código: 0 = ponto novo; n ≥ 1 = ponto já visto, n posições atrás (contando os pontos já numerados)
    vistos = np.cumsum(novo) - novo                         # quantos pontos já existiam antes deste canto
    codes = np.where(novo, 0, vistos - ids).astype("<u4")
    pontos = cantos[pos_primeira].tobytes()
    attrs = bool(np.any(rec[:, 48:50]))
    partes = [_planos(pontos, 4), _planos(codes.tobytes(), 4)]
    if attrs:
        partes.append(_planos(np.ascontiguousarray(rec[:, 48:50]).tobytes(), 2))
    raw = b"".join(partes)
    z = _brotli().compress(raw, quality=8, lgwin=24)
    head = bytearray(HEAD)
    head[0:8] = MAGIC
    head[8] = 1
    head[9] = 1 if attrs else 0
    struct.pack_into("<II", head, 12, T, V)
    head[20:100] = stl[0:80]
    packed = bytes(head) + z
    canon = descompactar(packed)
    if len(canon) != len(stl) or canon[:84] != stl[:84]:
        raise ValueError("Falha na conferência da malha (cabeçalho)")
    a = np.frombuffer(canon, dtype=np.uint8, offset=84).reshape(T, 50)[:, 12:50]
    if not np.array_equal(a, rec[:, 12:50]):
        raise ValueError("Falha na conferência da malha (triângulos)")
    return packed, canon


def descompactar(packed):
    if not eh_compactada(packed):
        raise ValueError("Não é uma malha compactada do OdontoDesk")
    if packed[8] != 1:
        raise ValueError("Versão de malha não suportada — atualize o OdontoDesk")
    attrs = packed[9] & 1
    T, V = struct.unpack_from("<II", packed, 12)
    raw = _brotli().decompress(packed[HEAD:])
    if len(raw) != V * 12 + T * 12 + (T * 2 if attrs else 0):
        raise ValueError("Malha compactada corrompida")
    vb = _de_planos(raw[:V * 12], 4)
    codes = np.frombuffer(_de_planos(raw[V * 12:V * 12 + T * 12], 4), dtype="<u4").astype(np.int64)
    # reconstrói os números dos pontos: código 0 = próximo ponto novo; n = n posições atrás
    novo = codes == 0
    hw = np.cumsum(novo) - novo                             # quantos pontos novos antes deste canto
    ids = np.where(novo, hw, hw - codes)
    if ids.min(initial=0) < 0 or ids.max(initial=0) >= V:
        raise ValueError("Malha compactada corrompida (índice)")
    pts = np.frombuffer(vb, dtype="<f4").reshape(V, 3)
    out = np.zeros((T, 50), dtype=np.uint8)
    out[:, 12:48] = np.frombuffer(vb, dtype=np.uint8).reshape(V, 12)[ids].reshape(T, 36)
    tri = ids.reshape(T, 3)
    a, b, c = (pts[tri[:, k]].astype(np.float64) for k in range(3))
    u, w = b - a, c - a
    # normal = (b−a)×(c−a) normalizada, em float64 e gravada em float32 (as mesmas contas do app em JavaScript)
    nx = u[:, 1] * w[:, 2] - u[:, 2] * w[:, 1]
    ny = u[:, 2] * w[:, 0] - u[:, 0] * w[:, 2]
    nz = u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0]
    with np.errstate(invalid="ignore", over="ignore"):
        l = np.sqrt(nx * nx + ny * ny + nz * nz)
        ok = (l > 0) & np.isfinite(l)
        lsafe = np.where(ok, l, 1.0)
        n = np.where(ok[:, None], np.stack([nx / lsafe, ny / lsafe, nz / lsafe], axis=1), 0.0)
    out[:, 0:12] = n.astype("<f4").view(np.uint8).reshape(T, 12)
    if attrs:
        out[:, 48:50] = np.frombuffer(_de_planos(raw[V * 12 + T * 12:], 2), dtype=np.uint8).reshape(T, 2)
    return bytes(packed[20:100]) + struct.pack("<I", T) + out.tobytes()


def medidas(stl):
    """(triângulos, [dx, dy, dz] em mm) de um STL binário."""
    T, rec = _triangulos(stl)
    p = np.frombuffer(np.ascontiguousarray(rec[:, 12:48]).tobytes(), dtype="<f4").reshape(-1, 3)
    return T, [round(float(x), 1) for x in (p.max(axis=0) - p.min(axis=0))]
