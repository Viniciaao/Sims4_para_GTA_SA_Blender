# SPDX-License-Identifier: GPL-3.0-or-later
"""Conversor de skeleton/skin para DFF PC. Python puro; não precisa de bpy.

Não interpreta YDD/YFT. Reconstrói apenas o rig e o Skin PLG de um ped já
convertido para DFF. UVs, triângulos, materiais e plugins não relacionados
são preservados byte a byte. Rejeita casos ambíguos em vez de adivinhar.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import os
import re
import struct
import tempfile
from datetime import datetime, timezone

VERSION = "1.0.8"
STRUCT, EXTENSION, FRAME_LIST, GEOMETRY, CLUMP, ATOMIC, GEOMETRY_LIST = 1, 3, 14, 15, 16, 20, 26
HANIM, SKIN, FRAME_NAME, RIGHT_TO_RENDER = 0x11E, 0x116, 0x253F2FE, 0x1F
SA_LIBRARY = 0x1803FFFF
SA_IDS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 21, 22, 23, 24, 25, 26, 31, 32,
          33, 34, 35, 36, 41, 42, 43, 44, 51, 52, 53, 54, 201, 301, 302}
MAX_FILE_BYTES = 100 * 1024 * 1024


class ConversionError(ValueError):
    """Erro de validação, legível para o usuário."""


def require(condition, message):
    if not condition:
        raise ConversionError(message)


def identity():
    return [[float(i == j) for j in range(4)] for i in range(4)]


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def inverse(m):
    require(all(math.isfinite(v) for row in m for v in row), "Matriz com NaN/infinito.")
    a = [list(row) + identity()[i] for i, row in enumerate(m)]
    for j in range(4):
        p = max(range(j, 4), key=lambda i: abs(a[i][j]))
        require(abs(a[p][j]) > 1e-12, "Matriz de bind singular: não é possível converter.")
        a[j], a[p] = a[p], a[j]
        d = a[j][j]
        a[j] = [x / d for x in a[j]]
        for i in range(4):
            if i != j:
                d = a[i][j]
                a[i] = [x - d * y for x, y in zip(a[i], a[j])]
    return [row[4:] for row in a]


def point(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) + m[i][3] for i in range(3))


def vector(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def scale(a, s):
    return tuple(x * s for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def normalized(a):
    n = length(a)
    return scale(a, 1.0 / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def head(m):
    return tuple(m[i][3] for i in range(3))


def matrix_error(a, b):
    return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))


def at_position(m, position):
    r = [row[:] for row in m]
    for i in range(3):
        r[i][3] = position[i]
    return r


def swing(a, b):
    """Menor rotação a->b. Não transfere o roll arbitrário entre engines."""
    require(length(a) > 1e-8 and length(b) > 1e-8, "Junta com comprimento zero.")
    a, b = normalized(a), normalized(b)
    c = max(-1.0, min(1.0, dot(a, b)))
    v = cross(a, b)
    if c > 1.0 - 1e-10:
        return identity()
    if c < -1.0 + 1e-8:
        basis = min([(1., 0., 0.), (0., 1., 0.), (0., 0., 1.)], key=lambda x: abs(dot(x, a)))
        u = normalized(cross(a, basis))
        r = identity()
        for i in range(3):
            for j in range(3):
                r[i][j] = 2 * u[i] * u[j] - float(i == j)
        return r
    k = [[0., -v[2], v[1]], [v[2], 0., -v[0]], [-v[1], v[0], 0.]]
    r = identity()
    for i in range(3):
        for j in range(3):
            r[i][j] += k[i][j] + sum(k[i][q] * k[q][j] for q in range(3)) / (1 + c)
    return r


def orientation_to_character(up, left):
    """Snap de eixos: X=direita anatômica esquerda do ped, Z=altura, frente=-Y.

    O snap evita inclinar o modelo usando a posição avançada da cabeça.
    Não redimensiona o modelo nem coloca a origem no chão.
    """
    require(length(up) > 1e-5 and length(left) > 1e-5, "Não consegui determinar os eixos do ped.")
    uz = max(range(3), key=lambda i: abs(up[i]))
    ux = max(range(3), key=lambda i: abs(left[i]))
    require(uz != ux, "Eixos do ped ambíguos. Confira o bind/rest pose de entrada.")
    z = tuple(math.copysign(1., up[i]) if i == uz else 0. for i in range(3))
    x = tuple(math.copysign(1., left[i]) if i == ux else 0. for i in range(3))
    y = cross(z, x)
    m = identity()
    for i, row in enumerate((x, y, z)):
        m[i][:3] = row
    return m


def rw_version(library):
    if library & 0xFFFF0000:
        return ((library >> 14 & 0x3FF00) + 0x30000) | (library >> 16 & 0x3F)
    return library << 8


@dataclass
class Chunk:
    kind: int
    payload: bytes
    library: int = SA_LIBRARY

    def encode(self):
        return struct.pack('<III', self.kind, len(self.payload), self.library) + self.payload


def chunks(data, allow_padding=False):
    p, out = 0, []
    while p < len(data):
        # DFFs extraídos de IMG podem conservar padding de setor no fim.
        # Só se aceita padding 100% zero e somente no nível externo.
        if allow_padding and data[p:p + 12] == b'\0' * min(12, len(data) - p) and not any(data[p:]):
            break
        require(p + 12 <= len(data), "Cabeçalho RenderWare truncado.")
        kind, size, library = struct.unpack_from('<III', data, p)
        require(p + 12 + size <= len(data), "Chunk RenderWare truncado ou tamanho inválido.")
        out.append(Chunk(kind, data[p + 12:p + 12 + size], library))
        p += 12 + size
    return out


def encode_chunks(items):
    return b''.join(c.encode() for c in items)


def one(items, kind, label):
    found = [c for c in items if c.kind == kind]
    require(len(found) == 1, f"Esperado um {label}; encontrei {len(found)}.")
    return found[0]


def replace_chunk(items, original, replacement):
    return [replacement if c is original else c for c in items]


def disk_matrix(values):
    # RW armazena right/up/at e a translação como vetores-linha.
    m = identity()
    for i in range(3):
        for j in range(3):
            m[i][j] = values[3 * j + i]
        m[i][3] = values[9 + i]
    require(all(math.isfinite(v) for row in m for v in row), "Frame contém NaN/infinito.")
    return m


def matrix_disk_values(m):
    return tuple(m[i][j] for j in range(3) for i in range(3)) + head(m)


@dataclass
class Frame:
    matrix: list
    parent: int
    creation_flags: int
    extensions: list
    name: str
    bone_id: int | None
    table: list


def read_frames(chunk):
    cs = chunks(chunk.payload)
    st = one(cs, STRUCT, 'Struct do Frame List')
    require(len(st.payload) >= 4, 'Frame List vazio.')
    n = struct.unpack_from('<I', st.payload)[0]
    require(0 < n <= 512 and len(st.payload) == 4 + n * 56, 'Quantidade/tamanho de frames inválidos.')
    exts = [c for c in cs if c.kind == EXTENSION]
    require(len(exts) == n, 'Um Extension por frame é obrigatório.')
    require(len(cs) == n + 1, 'Frame List com chunks adicionais não suportados.')
    result = []
    for i in range(n):
        vals = struct.unpack_from('<12fiI', st.payload, 4 + i * 56)
        extensions = chunks(exts[i].payload)
        name = f'frame_{i}'
        bid, table = None, []
        for ext in extensions:
            if ext.kind == FRAME_NAME:
                name = ext.payload.split(b'\0', 1)[0].decode('utf-8', 'replace')
            if ext.kind == HANIM:
                require(len(ext.payload) >= 12, 'HAnim PLG truncado.')
                _, bid, nb = struct.unpack_from('<III', ext.payload)
                if nb:
                    require(nb <= 255 and len(ext.payload) == 20 + nb * 12, 'Tabela HAnim inválida.')
                    table = [struct.unpack_from('<III', ext.payload, 20 + j * 12) for j in range(nb)]
        parent = vals[12]
        require(-1 <= parent < n and parent != i, 'Pai de frame inválido.')
        result.append(Frame(disk_matrix(vals[:12]), parent, vals[13], extensions, name, bid, table))
    world_matrices(result)  # também valida ciclos
    return result


def world_matrices(frames):
    cache, visiting = {}, set()
    def get(i):
        if i in cache:
            return cache[i]
        require(i not in visiting, 'Ciclo na hierarquia de frames.')
        visiting.add(i)
        f = frames[i]
        m = f.matrix if f.parent == -1 else mul(get(f.parent), f.matrix)
        visiting.remove(i)
        cache[i] = m
        return m
    return [get(i) for i in range(len(frames))]


@dataclass
class Skin:
    count: int
    indices: list
    weights: list
    inverse_bind: list
    maximum: int


def read_skin(chunk, vertex_count):
    b = chunk.payload
    require(len(b) >= 4, 'Skin PLG truncado.')
    n, used, maximum, _ = struct.unpack_from('<4B', b)
    require(0 < n <= 255 and used <= n and maximum <= 4, 'Cabeçalho Skin inválido.')
    require(rw_version(chunk.library) >= 0x34000, 'Skin antigo (RW < 3.4) não suportado. Reexporte como GTA SA PC.')
    offset = 4 + used
    expected = offset + vertex_count * 20 + n * 64
    require(len(b) in (expected, expected + 12), 'Skin split/native ou Skin PLG truncado não suportado.')
    if len(b) == expected + 12:
        require(b[expected:] == b'\0' * 12, 'Skin split não suportado; reexporte sem split.')
    require(all(i < n for i in b[4:offset]), 'Lista de ossos usados inválida.')
    indices = list(struct.iter_unpack('<4B', b[offset:offset + vertex_count * 4]))
    offset += vertex_count * 4
    weights = list(struct.iter_unpack('<4f', b[offset:offset + vertex_count * 16]))
    offset += vertex_count * 16
    bind = []
    for i in range(n):
        values = struct.unpack_from('<16f', b, offset + i * 64)
        mat = [[values[j * 4 + k] for j in range(4)] for k in range(4)]
        # RwMatrix usa 3 vetores e posição. Os slots W são flags/padding,
        # não uma quarta linha afim confiável em DFFs originais do jogo.
        mat[3] = [0.0, 0.0, 0.0, 1.0]
        require(all(math.isfinite(x) for row in mat for x in row), 'Bind com NaN/infinito.')
        inverse(mat)
        bind.append(mat)
    for inds, ws in zip(indices, weights):
        require(all(math.isfinite(w) and w >= -1e-7 for w in ws), 'Pesos negativos/NaN/infinito.')
        require(all(w <= 0 or idx < n for idx, w in zip(inds, ws)), 'Índice de skin fora da tabela de ossos.')
    return Skin(n, indices, weights, bind, maximum)


@dataclass
class GeometryData:
    chunk: Chunk
    children: list
    struct_chunk: Chunk
    extension_chunk: Chunk
    skin_chunk: Chunk
    vertex_count: int
    triangle_count: int
    morph_offset: int
    vertex_offset: int
    normal_offset: int | None
    vertices: list
    normals: list
    skin: Skin


def read_geometry(chunk):
    cs = chunks(chunk.payload)
    st = one(cs, STRUCT, 'Struct de Geometry')
    ext = one(cs, EXTENSION, 'Extension de Geometry')
    b = st.payload
    require(len(b) >= 40, 'Geometry truncada.')
    flags, nt, nv, morphs = struct.unpack_from('<4I', b)
    require(not (flags & 0x01000000), 'DFF native/console não suportado. Use DFF PC não-native.')
    require(morphs == 1, 'Múltiplos morph targets não suportados; não vou descartar seus morphs.')
    require(0 < nv <= 65535, 'Uma Geometry precisa ter de 1 a 65535 vértices para este conversor.')
    require(rw_version(st.library) >= 0x34000, 'Geometry RW < 3.4 não suportada.')
    p = 16 + (nv * 4 if flags & 8 else 0)
    uv_count = (flags >> 16) & 255
    if not uv_count:
        uv_count = 2 if flags & 128 else 1 if flags & 4 else 0
    p += uv_count * nv * 8 + nt * 8
    require(p + 24 <= len(b), 'UVs/triângulos/morph truncados.')
    hv, hn = struct.unpack_from('<II', b, p + 16)
    require(hv == 1 and hn in (0, 1), 'Geometry sem posições ou com morph inválido.')
    vo, no = p + 24, p + 24 + nv * 12 if hn else None
    require(vo + nv * 12 * (1 + hn) == len(b), 'Geometry Struct com dados adicionais/truncados.')
    vertices = list(struct.iter_unpack('<3f', b[vo:vo + nv * 12]))
    normals = list(struct.iter_unpack('<3f', b[no:no + nv * 12])) if no is not None else []
    require(all(math.isfinite(x) for v in vertices + normals for x in v), 'Malha contém NaN/infinito.')
    ecs = chunks(ext.payload)
    require(not any(c.kind in (0x122, 0x510) or (c.kind == 0x253F2FD and c.payload != b'\0' * 4) for c in ecs),
            'Delta morph, breakable ativo ou dados native não suportados; reexporte uma malha estática com skin.')
    sk = one(ecs, SKIN, 'Skin PLG (malha precisa estar pesada)')
    return GeometryData(chunk, cs, st, ext, sk, nv, nt, p, vo, no, vertices, normals, read_skin(sk, nv))


@dataclass
class Model:
    top: list
    clump: Chunk
    children: list
    frame_chunk: Chunk
    frames: list
    worlds: list
    geometry_list: Chunk
    geometry_children: list
    geometries: list
    atomics: list


def read_model(data):
    require(len(data) <= MAX_FILE_BYTES, 'Arquivo excede o limite de 100 MB.')
    top = chunks(data, allow_padding=True)
    clump = one(top, CLUMP, 'Clump (peds multi-clump não suportados)')
    cs = chunks(clump.payload)
    st = one(cs, STRUCT, 'Struct de Clump')
    require(len(st.payload) >= 12, 'Clump antigo/truncado.')
    n_atomic, n_lights, n_cameras = struct.unpack_from('<3I', st.payload)
    require(n_lights == 0 and n_cameras == 0, 'Clump com luzes/câmeras não suportado.')
    fl = one(cs, FRAME_LIST, 'Frame List')
    frames = read_frames(fl)
    worlds = world_matrices(frames)
    gl = one(cs, GEOMETRY_LIST, 'Geometry List')
    gcs = chunks(gl.payload)
    gs = one(gcs, STRUCT, 'Struct de Geometry List')
    require(len(gs.payload) == 4, 'Struct de Geometry List inválido.')
    geometries = [read_geometry(c) for c in gcs if c.kind == GEOMETRY]
    require(len(geometries) == struct.unpack('<I', gs.payload)[0] and geometries, 'Lista de geometrias inconsistente.')
    atomics = [c for c in cs if c.kind == ATOMIC]
    require(len(atomics) == n_atomic and atomics, 'Lista de atomics inconsistente.')
    for a in atomics:
        ast = one(chunks(a.payload), STRUCT, 'Struct de Atomic')
        require(len(ast.payload) == 16, 'Atomic Struct inválido.')
        fi, gi, _, _ = struct.unpack('<4I', ast.payload)
        require(fi < len(frames) and gi < len(geometries), 'Atomic com índice inválido.')
    return Model(top, clump, cs, fl, frames, worlds, gl, gcs, geometries, atomics)


def require_single_ped_mesh(model):
    """Enforce one geometry/atomic for the GTA SA ped export path."""
    geometry_count = len(model.geometries)
    atomic_count = len(model.atomics)
    require(geometry_count == 1 and atomic_count == 1,
            f'O ped precisa sair com uma única mesh (1 Geometry/Atomic); '
            f'o DFF intermediário tem {geometry_count} geometrias e {atomic_count} atomics. '
            'Junte as malhas skinned no Blender e mantenha os materiais como slots da mesma mesh.')
    return {'geometry_count': geometry_count, 'atomic_count': atomic_count}


def name_key(name):
    name = name.rsplit(':', 1)[-1]
    name = re.sub(r'\.\d{3}$', '', name)
    return re.sub(r'[^a-z0-9]', '', name.lower())


PRIMARY = {
    0: ['SKEL_ROOT'], 1: ['SKEL_Pelvis'], 2: ['SKEL_Spine0', 'SKEL_Spine_Root'],
    3: ['SKEL_Spine2', 'SKEL_Spine3', 'SKEL_Spine1'], 4: ['SKEL_Neck_1'], 5: ['SKEL_Head'],
    6: ['FB_L_Brow_Out_000'], 7: ['FB_R_Brow_Out_000'], 8: ['FB_Jaw_000'],
    21: ['SKEL_R_Clavicle'], 22: ['SKEL_R_UpperArm'], 23: ['SKEL_R_Forearm'], 24: ['SKEL_R_Hand'],
    25: ['SKEL_R_Finger20', 'SKEL_R_Finger10'], 26: ['SKEL_R_Finger21', 'SKEL_R_Finger11'],
    31: ['SKEL_L_Clavicle'], 32: ['SKEL_L_UpperArm'], 33: ['SKEL_L_Forearm'], 34: ['SKEL_L_Hand'],
    35: ['SKEL_L_Finger20', 'SKEL_L_Finger10'], 36: ['SKEL_L_Finger21', 'SKEL_L_Finger11'],
    41: ['SKEL_L_Thigh'], 42: ['SKEL_L_Calf'], 43: ['SKEL_L_Foot'], 44: ['SKEL_L_Toe0'],
    51: ['SKEL_R_Thigh'], 52: ['SKEL_R_Calf'], 53: ['SKEL_R_Foot'], 54: ['SKEL_R_Toe0'],
}
REQUIRED_PRIMARY = {0, 1, 2, 3, 4, 5, 21, 22, 23, 24, 31, 32, 33, 34, 41, 42, 43, 51, 52, 53}
DIRECT = {}
for bid, names in PRIMARY.items():
    for name in names:
        DIRECT[name_key(name)] = bid
DIRECT.update({name_key(k): v for k, v in {
    'SKEL_Spine_Root': 2, 'SKEL_Spine0': 2, 'SKEL_Spine1': 2, 'SKEL_Spine2': 3, 'SKEL_Spine3': 3,
    'IK_Root': 0, 'IK_Head': 5, 'RB_Neck_1': 4,
    'RB_L_ThighRoll': 41, 'RB_R_ThighRoll': 51,
    'RB_L_ArmRoll': 32, 'RB_R_ArmRoll': 22, 'RB_L_ForeArmRoll': 33, 'RB_R_ForeArmRoll': 23,
    'MH_L_Knee': 41, 'MH_R_Knee': 51, 'MH_L_Elbow': 32, 'MH_R_Elbow': 22,
    'PH_L_Hand': 34, 'IK_L_Hand': 34, 'PH_R_Hand': 24, 'IK_R_Hand': 24,
    'PH_L_Foot': 43, 'IK_L_Foot': 43, 'PH_R_Foot': 53, 'IK_R_Foot': 53,
    'FACIAL_facialRoot': 5, 'FB_LowerLipRoot_000': 8, 'FB_LowerLip_000': 8,
    'FB_L_Lip_Bot_000': 8, 'FB_R_Lip_Bot_000': 8, 'FB_Tongue_000': 8,
}.items()})


def map_name(name, overrides=None):
    key = name_key(name)
    if overrides and key in overrides:
        return overrides[key]
    if key in DIRECT:
        return DIRECT[key]
    finger = re.fullmatch(r'skel([lr])finger([0-4])([0-2])', key)
    if finger:
        side, digit, segment = finger.groups()
        base = 34 if side == 'l' else 24
        return base if digit == '0' else base + (1 if segment == '0' else 2)
    if key.startswith('fb') or key.startswith('facial'):
        return 5
    return None


def infer_bind_reference_frame(model, geometry, ordered):
    """Find the frame whose coordinate space the Skin inverse-bind matrices use.

    Some Blender/DragonFF COLLADA imports attach an Atomic to the skeleton Root
    bone while the mesh and inverse-bind matrices remain in the armature-object
    frame. Using the Atomic frame in that case adds the Root transform twice.
    Select the unique frame that makes every inverse bind agree with its HAnim
    bone frame; reject if no unambiguous coordinate anchor fits.
    """
    require(len(ordered) == geometry.skin.count, 'Bind/HAnim com contagens diferentes.')
    scored = []
    for candidate in range(len(model.frames)):
        errors = [
            matrix_error(
                mul(model.worlds[candidate], inverse(geometry.skin.inverse_bind[index])),
                model.worlds[frame_index],
            )
            for index, frame_index in enumerate(ordered)
        ]
        scored.append((max(errors, default=float('inf')), candidate))
    scored.sort(key=lambda item: (
        item[0],
        0 if model.frames[item[1]].parent == -1 else 1,
        item[1],
    ))
    best_error, best_index = scored[0]
    require(best_error < 0.002,
            'A ordem/IDs dos ossos não coincide com o bind (>0,002), mesmo após procurar o frame-base da malha. '
            'Conversão interrompida para não trocar pesos.')
    near_matches = [idx for error, idx in scored if error <= best_error + 1e-7]
    require(all(matrix_error(model.worlds[best_index], model.worlds[idx]) < 1e-5 for idx in near_matches),
            'Mais de um frame-base incompatível com os binds; conversão interrompida por ambiguidade.')
    return best_index, best_error


def source_association(model):
    tables = [(i, f.table) for i, f in enumerate(model.frames) if f.table]
    require(len(tables) == 1, 'É necessário um único skeleton HAnim de entrada.')
    table_frame, table = tables[0]
    n = len(table)
    require({t[1] for t in table} == set(range(n)), 'Índices da tabela HAnim não são únicos/contíguos.')
    require(all(g.skin.count == n for g in model.geometries), 'Skin e HAnim têm quantidades diferentes de ossos.')
    ids = Counter(f.bone_id for f in model.frames if f.bone_id is not None)
    by_id = {f.bone_id: i for i, f in enumerate(model.frames) if f.bone_id is not None and ids[f.bone_id] == 1}
    ordered = [None] * n
    valid = len({t[0] for t in table}) == n and all(t[0] in by_id for t in table)
    if valid:
        for bid, index, _ in table:
            ordered[index] = by_id[bid]
        method = 'IDs HAnim únicos + índices da tabela'
    else:
        candidates = [i for i, f in enumerate(model.frames) if f.bone_id is not None and i != table_frame]
        # O caso comum é tabela no frame dummy, com todos os IDs de frames zerados.
        if len(candidates) != n:
            candidates = [i for i, f in enumerate(model.frames) if f.bone_id is not None]
        require(len(candidates) == n, 'HAnim quebrado e quantidade de frames ambígua. Reexporte do arquivo-fonte.')
        ordered = candidates
        method = 'Recuperação por ordem de frames, confirmada pelas matrizes de bind'

    bind_frames, errors = {}, []
    for gi, geometry in enumerate(model.geometries):
        bind_frame, error = infer_bind_reference_frame(model, geometry, ordered)
        bind_frames[gi] = bind_frame
        errors.append(error)

    # Repeated Atomics may instance one Geometry, but not at different transforms.
    atomic_frames = {}
    for atomic in model.atomics:
        afi, agi, _, _ = struct.unpack('<4I', one(chunks(atomic.payload), STRUCT, 'Atomic Struct').payload)
        if agi in atomic_frames:
            prior = atomic_frames[agi]
            require(matrix_error(model.worlds[prior], model.worlds[afi]) < 1e-5,
                    'Geometry instanciada com transforms distintos não suportada.')
        else:
            atomic_frames[agi] = afi
    require(set(atomic_frames) == set(range(len(model.geometries))),
            'Geometry sem Atomic de referência não suportada.')

    leftovers = [i for i in range(len(model.frames)) if i not in ordered]
    require(len(leftovers) == 1 and model.frames[leftovers[0]].parent == -1,
            'Frames/props externos ao skeleton não suportados; separe os acessórios antes de converter.')
    return ordered, method, max(errors, default=0), bind_frames


def load_mapping(path):
    if not path:
        return {}
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    require(isinstance(raw, dict), 'O mapa JSON deve ser um objeto nome_do_osso: ID_SA.')
    result = {}
    for k, v in raw.items():
        require(isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v in SA_IDS,
                'Mapa inválido: use nomes de ossos e IDs HAnim SA válidos.')
        result[name_key(k)] = v
    return result


def source_mapping(model, ordered, overrides):
    destinations, methods = {}, {}
    by_frame = {frame_idx: i for i, frame_idx in enumerate(ordered)}
    for index, frame_idx in enumerate(ordered):
        dest = map_name(model.frames[frame_idx].name, overrides)
        if dest is not None:
            destinations[index] = dest
            methods[index] = 'mapa personalizado' if name_key(model.frames[frame_idx].name) in overrides else 'nome GTA V'
    for index, frame_idx in enumerate(ordered):
        if index in destinations:
            continue
        p = model.frames[frame_idx].parent
        while p != -1:
            parent_index = by_frame.get(p)
            if parent_index in destinations:
                destinations[index] = destinations[parent_index]
                methods[index] = 'ancestral reconhecido (aproximação)'
                break
            p = model.frames[p].parent
        require(index in destinations, f'Osso sem destino seguro: {model.frames[frame_idx].name}. Use um mapa JSON.')
    return destinations, methods


def primary_sources(model, ordered, overrides):
    by_name = {name_key(model.frames[fi].name): fi for fi in ordered}
    require(len(by_name) == len(ordered), 'Nomes de ossos duplicados após normalização; mapeamento ambíguo.')
    result = {}
    for bid, names in PRIMARY.items():
        for n in names:
            if name_key(n) in by_name:
                result[bid] = by_name[name_key(n)]
                break
    # Um mapa customizado também pode identificar uma junta principal ausente.
    for n, bid in overrides.items():
        if bid not in result and n in by_name:
            result[bid] = by_name[n]
    missing = sorted(REQUIRED_PRIMARY - result.keys())
    require(not missing, f'Juntas principais GTA V ausentes (IDs SA {missing}). Use nomes SKEL_* ou um mapa personalizado.')
    return result


def validate_preset(preset):
    require(preset.get('format') == 'GTA_SA_RIG_PRESET_V1', 'Preset SA incompatível.')
    bones = preset.get('bones', [])
    require(len(bones) == 32 and {b['id'] for b in bones} == SA_IDS, 'A referência precisa ter os 32 IDs de ped SA padrão.')
    by_id = {b['id']: b for b in bones}
    require(len({b['name'] for b in bones}) == 32, 'Nomes repetidos no preset SA.')
    require(by_id[0]['parent_id'] is None and all(b['parent_id'] in SA_IDS for b in bones if b['id'] != 0),
            'Hierarquia do preset SA inválida.')
    order = preset['table_order']
    require(len(order) == 32 and set(order) == SA_IDS and order[0] == 0, 'Ordem HAnim do preset inválida.')
    seen = set()
    for bid in order:
        require(bid == 0 or by_id[bid]['parent_id'] in seen, 'Preset não está em ordem pai->filho.')
        inverse(by_id[bid]['world_matrix'])
        seen.add(bid)
    return preset


def preset_from_dff(path):
    model = read_model(Path(path).read_bytes())
    tf = [f for f in model.frames if f.table]
    require(len(tf) == 1, 'Referência SA precisa de uma única tabela HAnim.')
    table = sorted(tf[0].table, key=lambda t: t[1])
    require(len(table) == 32 and {t[0] for t in table} == SA_IDS, 'Escolha um ped SA padrão de 32 ossos, não CJ modular/cutscene.')
    by_id = {f.bone_id: i for i, f in enumerate(model.frames) if f.bone_id is not None}
    require(len(by_id) == 32, 'IDs duplicados na referência SA.')
    bones = []
    for bid, _, flags in table:
        fi = by_id[bid]
        f = model.frames[fi]
        parent_id = model.frames[f.parent].bone_id if f.parent >= 0 else None
        bones.append({'id': bid, 'name': f.name.strip(), 'parent_id': parent_id,
                      'world_matrix': model.worlds[fi], 'flags': flags})
    roots = [f for f in model.frames if f.parent == -1]
    require(len(roots) == 1, 'Referência com múltiplos roots não suportada.')
    p = {'format': 'GTA_SA_RIG_PRESET_V1', 'provenance': Path(path).name,
         'dummy_matrix': roots[0].matrix, 'bones': bones, 'table_order': [t[0] for t in table]}
    return validate_preset(p)


def load_preset(reference_path=None):
    if reference_path:
        return preset_from_dff(reference_path)
    return validate_preset(json.loads(Path(__file__).with_name('sa_preset.json').read_text(encoding='utf-8')))


def rig_plan(model, ordered, primary, preset, bake_pose=True):
    source_raw = {bid: model.worlds[fi] for bid, fi in primary.items()}
    s_axis = orientation_to_character(sub(head(source_raw[5]), head(source_raw[1])),
                                      sub(head(source_raw[32]), head(source_raw[22])))
    source = {bid: mul(s_axis, mat) for bid, mat in source_raw.items()}
    ref = {b['id']: b for b in preset['bones']}
    r_axis = orientation_to_character(sub(head(ref[5]['world_matrix']), head(ref[1]['world_matrix'])),
                                      sub(head(ref[32]['world_matrix']), head(ref[22]['world_matrix'])))
    canonical = {bid: mul(r_axis, b['world_matrix']) for bid, b in ref.items()}
    positions = {bid: head(mat) for bid, mat in source.items()}
    rotations = {bid: identity() for bid in SA_IDS}
    # Torso/cabeça preservam posições anatômicas; membros usam swing mínimo,
    # não a rotação completa dos eixos GTA V (isso torceria a malha em 180°).
    if bake_pose:
        for chain in [(31, 32, 33, 34), (21, 22, 23, 24), (41, 42, 43, 44), (51, 52, 53, 54)]:
            carry = identity()
            for parent, child in zip(chain, chain[1:]):
                if parent not in source or child not in source:
                    break
                sv = sub(head(source[child]), head(source[parent]))
                rv = sub(head(canonical[child]), head(canonical[parent]))
                delta = swing(vector(carry, sv), rv)
                carry = mul(delta, carry)
                rotations[parent] = carry
                positions[child] = add(positions[parent], vector(carry, sv))
            if chain[-1] in source:
                rotations[chain[-1]] = carry
            elif chain[-2] in source:
                rotations[chain[-2]] = carry
    # Os dedos continuam separados na geometria, apesar de compartilhar 2 joints SA.
    for hand, fingers in [(34, (35, 36)), (24, (25, 26))]:
        for bid in fingers:
            rotations[bid] = rotations[hand]
            if bid in source:
                positions[bid] = add(positions[hand], vector(rotations[hand], sub(head(source[bid]), head(source[hand]))))
    height_source = length(sub(head(source[5]), head(source[43])))
    height_ref = length(sub(head(canonical[5]), head(canonical[43])))
    factor = height_source / height_ref
    for bid in preset['table_order']:
        if bid not in positions:
            parent = ref[bid]['parent_id']
            positions[bid] = add(positions[parent], scale(sub(head(canonical[bid]), head(canonical[parent])), factor))
            rotations[bid] = rotations[parent]
    target_character = {bid: at_position(canonical[bid], positions[bid]) for bid in SA_IDS}
    motions = {}
    for bid in preset['table_order']:
        if bid in source:
            motion = rotations[bid]
            translation = sub(positions[bid], vector(motion, head(source[bid])))
            motions[bid] = at_position(motion, translation)
        else:
            parent = ref[bid]['parent_id']
            motions[bid] = motions.get(parent, identity())
    target_rw = {bid: mul(inverse(r_axis), mat) for bid, mat in target_character.items()}
    anchor = target_rw[1]
    character_to_mesh = mul(inverse(anchor), inverse(r_axis))
    target_bind = {bid: inverse(mul(inverse(anchor), mat)) for bid, mat in target_rw.items()}
    return {'source_axis': s_axis, 'reference_axis': r_axis, 'source': source,
            'target_rw': target_rw, 'target_bind': target_bind,
            'character_to_mesh': character_to_mesh, 'motions': motions, 'ref': ref}


def traversal_flags(order, ref):
    # Pilha HAnim usa DFS. Push se há um irmão posterior; pop em cada folha.
    children = {bid: [] for bid in order}
    for bid in order:
        if ref[bid]['parent_id'] is not None:
            children[ref[bid]['parent_id']].append(bid)
    result = {}
    expected = []
    def visit(bid, has_next=False):
        expected.append(bid)
        result[bid] = (2 if has_next else 0) | (1 if not children[bid] else 0)
        for i, child in enumerate(children[bid]):
            visit(child, i < len(children[bid]) - 1)
    visit(0)
    require(expected == order, 'A ordem HAnim precisa ser depth-first (DFS).')
    return result


def build_frames(preset, plan):
    order, ref = preset['table_order'], plan['ref']
    flags = traversal_flags(order, ref)
    index = {bid: i + 1 for i, bid in enumerate(order)}
    dummy = preset.get('dummy_matrix', identity())
    payload = bytearray(struct.pack('<I', 33))
    payload.extend(struct.pack('<12fiI', *matrix_disk_values(dummy), -1, 0))
    extensions = [Chunk(EXTENSION, Chunk(FRAME_NAME, b'SA_Dummy').encode())]
    for bid in order:
        parent_id = ref[bid]['parent_id']
        parent_world = dummy if parent_id is None else plan['target_rw'][parent_id]
        local = mul(inverse(parent_world), plan['target_rw'][bid])
        payload.extend(struct.pack('<12fiI', *matrix_disk_values(local), 0 if parent_id is None else index[parent_id], 0))
        anim = struct.pack('<III', 0x100, bid, 32 if bid == 0 else 0)
        if bid == 0:
            anim += struct.pack('<II', 0, 36)
            anim += b''.join(struct.pack('<III', child_id, i, flags[child_id]) for i, child_id in enumerate(order))
        exts = [Chunk(HANIM, anim), Chunk(FRAME_NAME, ref[bid]['name'].encode('utf-8'))]
        extensions.append(Chunk(EXTENSION, encode_chunks(exts)))
    return Chunk(FRAME_LIST, Chunk(STRUCT, bytes(payload)).encode() + encode_chunks(extensions)), index


def compact_weights(indices, weights, destinations, target_indices):
    combined = {}
    for idx, w in zip(indices, weights):
        if w > 0:
            dest = target_indices[destinations[idx]]
            combined[dest] = combined.get(dest, 0.0) + w
    repaired_zero = not combined
    if repaired_zero:
        combined[target_indices[1]] = 1.0
    entries = sorted(combined.items(), key=lambda x: (-x[1], x[0]))[:4]
    total = sum(w for _, w in entries)
    inds = [i for i, _ in entries] + [0] * (4 - len(entries))
    ws = [w / total for _, w in entries] + [0.0] * (4 - len(entries))
    return tuple(inds), tuple(ws), repaired_zero


def encode_skin(indices, weights, matrices):
    used = sorted({i for inds, ws in zip(indices, weights) for i, w in zip(inds, ws) if w > 0})
    maximum = max(sum(w > 0 for w in ws) for ws in weights)
    data = bytearray(struct.pack('<4B', len(matrices), len(used), maximum, 0))
    data.extend(bytes(used))
    data.extend(b''.join(struct.pack('<4B', *row) for row in indices))
    data.extend(b''.join(struct.pack('<4f', *row) for row in weights))
    for m in matrices:
        data.extend(struct.pack('<16f', *(m[i][j] for j in range(4) for i in range(4))))
    data.extend(b'\0' * 12)
    return Chunk(SKIN, bytes(data))


def transform_geometry(g, source_mesh_to_character, plan, destinations, preset):
    target_indices = {bid: i for i, bid in enumerate(preset['table_order'])}
    # Todas as rotações e offsets por osso são calculados antes do loop de vértices.
    transforms = {}
    for source_index, bid in destinations.items():
        transforms[source_index] = mul(plan['character_to_mesh'], mul(plan['motions'][bid], source_mesh_to_character))
    vertices, normals, indices, weights = [], [], [], []
    fixed = 0
    for vi, (old_indices, old_weights, v) in enumerate(zip(g.skin.indices, g.skin.weights, g.vertices)):
        ws = [max(w, 0.0) for w in old_weights]
        total = sum(ws)
        if total <= 1e-12:
            # Nenhum osso de origem move o vértice; conserva coordenadas globais.
            mat = mul(plan['character_to_mesh'], source_mesh_to_character)
            new_v = point(mat, v)
            new_n = normalized(vector(mat, g.normals[vi])) if g.normals else None
        else:
            new_v = (0.0, 0.0, 0.0)
            new_n = (0.0, 0.0, 0.0) if g.normals else None
            for idx, w in zip(old_indices, ws):
                if w <= 0:
                    continue
                mat, fraction = transforms[idx], w / total
                new_v = add(new_v, scale(point(mat, v), fraction))
                if g.normals:
                    new_n = add(new_n, scale(vector(mat, g.normals[vi]), fraction))
        require(all(math.isfinite(x) for x in new_v), 'Deformação produziu posição não finita.')
        vertices.append(new_v)
        if new_n is not None:
            normals.append(normalized(new_n))
        inds, row_weights, zero = compact_weights(old_indices, ws, destinations, target_indices)
        indices.append(inds)
        weights.append(row_weights)
        fixed += zero
    data = bytearray(g.struct_chunk.payload)
    center = tuple((min(v[i] for v in vertices) + max(v[i] for v in vertices)) * 0.5 for i in range(3))
    radius = max(length(sub(v, center)) for v in vertices)
    struct.pack_into('<4f', data, g.morph_offset, *center, radius)
    data[g.vertex_offset:g.vertex_offset + g.vertex_count * 12] = b''.join(struct.pack('<3f', *v) for v in vertices)
    if g.normal_offset is not None:
        data[g.normal_offset:g.normal_offset + g.vertex_count * 12] = b''.join(struct.pack('<3f', *v) for v in normals)
    matrices = [plan['target_bind'][bid] for bid in preset['table_order']]
    new_skin = encode_skin(indices, weights, matrices)
    new_exts = [new_skin if c.kind == SKIN else c for c in chunks(g.extension_chunk.payload)]
    new_cs = [Chunk(STRUCT, bytes(data)) if c is g.struct_chunk else
              Chunk(EXTENSION, encode_chunks(new_exts)) if c is g.extension_chunk else c for c in g.children]
    return Chunk(GEOMETRY, encode_chunks(new_cs)), {'vertices': g.vertex_count, 'triangles': g.triangle_count,
        'zero_weight_vertices_repaired': fixed, 'used_bones': len({i for row, ws in zip(indices, weights) for i, w in zip(row, ws) if w > 0}),
        'maximum_influences': max(sum(w > 0 for w in row) for row in weights),
        'maximum_weight_sum_error': max(abs(sum(row) - 1.0) for row in weights),
        'uv_triangles_prelight_sha256': hashlib.sha256(g.struct_chunk.payload[:g.morph_offset]).hexdigest()}


def inspect_bytes(data, mapping_path=None):
    model = read_model(data)
    ordered, method, error, bind_frames = source_association(model)
    overrides = load_mapping(mapping_path)
    dest, methods = source_mapping(model, ordered, overrides)
    primary_sources(model, ordered, overrides)
    influences = Counter()
    for g in model.geometries:
        for inds, ws in zip(g.skin.indices, g.skin.weights):
            for i, w in zip(inds, ws):
                if w > 0:
                    influences[i] += 1
    mapping = [{'source_index': i, 'source_name': model.frames[fi].name, 'target_id': dest[i],
                'method': methods[i], 'positive_influences': influences[i]} for i, fi in enumerate(ordered)]
    frame_ids = [f.bone_id for f in model.frames if f.bone_id is not None]
    table = next(f.table for f in model.frames if f.table)
    warnings = []
    if len(set(frame_ids)) != len(frame_ids) or len({b[0] for b in table}) != len(table):
        warnings.append('IDs HAnim duplicados/quebrados detectados; bind confirmado antes do remapeamento.')
    if any('aproximação' in row['method'] and row['positive_influences'] for row in mapping):
        warnings.append('Há ossos extras com peso enviados ao ancestral reconhecido. Revise roupas/acessórios.')
    return {'tool_version': VERSION, 'input_sha256': hashlib.sha256(data).hexdigest(),
            'input_rw_version': hex(rw_version(model.clump.library)), 'source_bones': len(ordered),
            'source_frames': len(model.frames), 'unique_hanim_frame_ids': len(set(frame_ids)),
            'unique_hanim_table_ids': len({b[0] for b in table}), 'association': method,
            'maximum_bind_frame_error': error,
            'skin_bind_reference_frames': [
                {'geometry_index': gi, 'frame_index': fi, 'frame_name': model.frames[fi].name}
                for gi, fi in sorted(bind_frames.items())
            ],
            'target_bones': 32,
            'vertices': sum(g.vertex_count for g in model.geometries),
            'triangles': sum(g.triangle_count for g in model.geometries), 'mapping': mapping, 'warnings': warnings}


def convert_bytes(data, reference_path=None, mapping_path=None, bake_pose=True, ground_offset=0.0):
    require(math.isfinite(ground_offset) and -1.5 <= ground_offset <= 1.5,
            'Ajuste vertical deve ficar entre -1,5 e +1,5 unidades.')
    report = inspect_bytes(data, mapping_path)
    model = read_model(data)
    ordered, _, _, bind_frames = source_association(model)
    overrides = load_mapping(mapping_path)
    dest, _ = source_mapping(model, ordered, overrides)
    primary = primary_sources(model, ordered, overrides)
    preset = load_preset(reference_path)
    plan = rig_plan(model, ordered, primary, preset, bake_pose)
    new_frames, frame_indices = build_frames(preset, plan)
    geometry_sources = {}
    new_atomics = {}
    for a in model.atomics:
        acs = chunks(a.payload)
        ast = one(acs, STRUCT, 'Atomic Struct')
        fi, gi, flags, unused = struct.unpack('<4I', ast.payload)
        source_transform = mul(plan['source_axis'], model.worlds[bind_frames[gi]])
        if gi in geometry_sources:
            require(matrix_error(geometry_sources[gi], source_transform) < 1e-5,
                    'Geometry instanciada com transforms distintos não suportada.')
        geometry_sources[gi] = source_transform
        acs = [Chunk(STRUCT, struct.pack('<4I', frame_indices[1], gi, flags, unused)) if c is ast else c for c in acs]
        ae = one(acs, EXTENSION, 'Extension de Atomic')
        ae_cs = chunks(ae.payload)
        ae_cs = [c for c in ae_cs if c.kind != RIGHT_TO_RENDER] + [Chunk(RIGHT_TO_RENDER, struct.pack('<II', SKIN, 1))]
        acs = replace_chunk(acs, ae, Chunk(EXTENSION, encode_chunks(ae_cs)))
        new_atomics[id(a)] = Chunk(ATOMIC, encode_chunks(acs))
    require(set(geometry_sources) == set(range(len(model.geometries))), 'Geometry sem Atomic de referência não suportada.')
    new_geometries, stats = {}, []
    for gi, g in enumerate(model.geometries):
        new_geometries[id(g.chunk)], st = transform_geometry(g, geometry_sources[gi], plan, dest, preset)
        stats.append(st)
    new_gl = Chunk(GEOMETRY_LIST, encode_chunks([new_geometries.get(id(c), c) for c in model.geometry_children]))
    cs = [new_frames if c is model.frame_chunk else new_gl if c is model.geometry_list else new_atomics.get(id(c), c)
          for c in model.children]
    new_clump = Chunk(CLUMP, encode_chunks(cs))
    output = encode_chunks(replace_chunk(model.top, model.clump, new_clump))
    if abs(ground_offset) > 1e-9:
        output_model = read_model(output)
        out_by_id = {f.bone_id: i for i, f in enumerate(output_model.frames) if f.bone_id is not None}
        up = normalized(sub(head(output_model.worlds[out_by_id[5]]), head(output_model.worlds[out_by_id[1]])))
        output = translate_dff_nonroot(output, scale(up, ground_offset))
    validation = validate_output(output, model)
    report.update({'created_utc': datetime.now(timezone.utc).isoformat(), 'pose_baked': bool(bake_pose),
                   'ground_offset': float(ground_offset),
                   'reference': str(reference_path) if reference_path else 'preset SA padrão incluído (somente skeleton)',
                   'reference_provenance': preset.get('provenance', ''),
                   'output_rw_version': '0x36003', 'output_sha256': hashlib.sha256(output).hexdigest(),
                   'geometries': stats, 'validation': validation,
                   'source_axis_to_character': plan['source_axis'], 'reference_axis_to_character': plan['reference_axis']})
    report['warnings'].extend([
        'Retarget many-to-one: dedos extras, twist/roll e parte do rosto perdem canais independentes de animação.',
        'Não houve teste dentro do GTA SA. Revise andar/correr, mira, mãos, ombros e roupas no jogo.',
        'Texturas/arquivo TXD não são convertidos por esta ferramenta.'
    ])
    pivot_offset = validation['mesh_skeleton_alignment']['root_pelvis_offset']
    if pivot_offset > 0.05:
        report['warnings'].append(
            f'Root/Pelvis separados por {pivot_offset:.4f} unidades. Não foi aplicado rebase automático; '
            'se houver diferença de contato com o chão no jogo, ajuste em passos pequenos no campo Ajuste vertical do ped.'
        )
    if abs(ground_offset) > 1e-9:
        report['warnings'].append(f'Ajuste vertical aplicado: {ground_offset:+.3f} unidades SA.')
    if not bake_pose:
        report['warnings'].append('Ajuste de pose desligado: bone axes SA corrigidos, mas a pose V foi mantida. Pode exigir ajuste manual.')
    return output, report


def translate_dff_nonroot(data, delta):
    """Apply a small vertical correction to the skinned ped, keeping Root fixed.

    All non-Root bone frames and their atomics move together; the Root inverse
    bind is repaired so skin validation remains consistent. This is an explicit
    user adjustment, not an automatic pelvis-to-floor rebase.
    """
    require(len(delta) == 3 and all(math.isfinite(x) for x in delta), 'Offset vertical inválido.')
    if length(delta) < 1e-9:
        return data
    model = read_model(data)
    by_id = {f.bone_id: i for i, f in enumerate(model.frames) if f.bone_id is not None}
    require(0 in by_id and 1 in by_id, 'DFF sem osso Root/Pelvis para ajustar a altura.')

    new_worlds = []
    for i, frame in enumerate(model.frames):
        world = model.worlds[i]
        if frame.bone_id is not None and frame.bone_id != 0:
            world = at_position(world, add(head(world), delta))
        new_worlds.append(world)

    frame_children = chunks(model.frame_chunk.payload)
    frame_struct = one(frame_children, STRUCT, 'Struct do Frame List')
    payload = bytearray(struct.pack('<I', len(model.frames)))
    for i, frame in enumerate(model.frames):
        local = new_worlds[i] if frame.parent == -1 else mul(inverse(new_worlds[frame.parent]), new_worlds[i])
        payload.extend(struct.pack('<12fiI', *matrix_disk_values(local), frame.parent, frame.creation_flags))
    new_frame_chunk = Chunk(FRAME_LIST, encode_chunks(replace_chunk(
        frame_children, frame_struct, Chunk(STRUCT, bytes(payload)))))

    tables = [frame.table for frame in model.frames if frame.table]
    require(len(tables) == 1, 'DFF sem tabela HAnim única para rebase do pivô.')
    root_skin_index = next((index for bid, index, _ in tables[0] if bid == 0), None)
    require(root_skin_index is not None, 'Tabela HAnim sem o índice do Root.')
    geometry_by_chunk = {}
    for gi, geometry in enumerate(model.geometries):
        attached = []
        for atomic in model.atomics:
            afi, agi, _, _ = struct.unpack('<4I', one(chunks(atomic.payload), STRUCT, 'Atomic Struct').payload)
            if agi == gi:
                attached.append(afi)
        require(attached, 'Geometria sem Atomic para rebase do pivô.')
        require(all(matrix_error(new_worlds[attached[0]], new_worlds[fi]) < 1e-5 for fi in attached[1:]),
                'Geometria instanciada com pivôs diferentes não suportada.')
        root_bind = mul(inverse(new_worlds[by_id[0]]), new_worlds[attached[0]])
        matrices = list(geometry.skin.inverse_bind)
        matrices[root_skin_index] = root_bind
        new_skin = encode_skin(geometry.skin.indices, geometry.skin.weights, matrices)
        ext_children = chunks(geometry.extension_chunk.payload)
        old_skin = one(ext_children, SKIN, 'Skin PLG')
        new_ext = Chunk(EXTENSION, encode_chunks(replace_chunk(ext_children, old_skin, new_skin)))
        geometry_children = [new_ext if c is geometry.extension_chunk else c for c in geometry.children]
        geometry_by_chunk[id(geometry.chunk)] = Chunk(GEOMETRY, encode_chunks(geometry_children))

    new_geometry_list = Chunk(GEOMETRY_LIST, encode_chunks([
        geometry_by_chunk.get(id(c), c) for c in model.geometry_children]))
    clump_children = [new_frame_chunk if c is model.frame_chunk else
                      new_geometry_list if c is model.geometry_list else c for c in model.children]
    new_clump = Chunk(CLUMP, encode_chunks(clump_children))
    return encode_chunks(replace_chunk(model.top, model.clump, new_clump))


def mesh_skeleton_alignment(model):
    """Check that the skinned geometry's vertical axis agrees with the SA rig.

    Bind matrices can be internally self-consistent while an imported DAE mesh
    has an object-space rotation that differs from its armature. This catches
    the common 90-degree mesh-vs-rig failure before writing a DFF.
    """
    by_id = {f.bone_id: i for i, f in enumerate(model.frames) if f.bone_id is not None}
    require({0, 1, 5, 21, 31} <= by_id.keys(), 'Não foi possível medir o alinhamento mesh/skeleton SA.')
    root_pelvis_offset = length(sub(head(model.worlds[by_id[0]]), head(model.worlds[by_id[1]])))
    up = normalized(sub(head(model.worlds[by_id[5]]), head(model.worlds[by_id[1]])))
    left = normalized(sub(head(model.worlds[by_id[31]]), head(model.worlds[by_id[21]])))
    depth = normalized(cross(up, left))
    points = []
    for atomic in model.atomics:
        ast = one(chunks(atomic.payload), STRUCT, 'Atomic Struct')
        frame_index, geometry_index, _, _ = struct.unpack('<4I', ast.payload)
        geometry = model.geometries[geometry_index]
        points.extend(point(model.worlds[frame_index], v) for v in geometry.vertices)
    require(points, 'DFF sem vértices para validar o alinhamento do rig.')
    def extent(axis):
        projected = [dot(p, axis) for p in points]
        return max(projected) - min(projected)
    measures = {
        'height': extent(up),
        'width': extent(left),
        'depth': extent(depth),
        'root_pelvis_offset': root_pelvis_offset,
    }
    measures['up_axis_to_width_depth_ratio'] = measures['height'] / max(measures['width'], measures['depth'], 1e-12)
    require(measures['height'] > 0.6 * max(measures['width'], measures['depth']),
            'A geometria está girada/deslocada em relação ao skeleton SA (eixo de altura da malha incompatível). '
            'Ajuste/aplique o transform da malha para o espaço do armature antes de exportar o DFF intermediário.')
    return measures


def validate_output(output, original=None):
    m = read_model(output)
    alignment = mesh_skeleton_alignment(m)
    tables = [f.table for f in m.frames if f.table]
    require(len(tables) == 1 and len(tables[0]) == 32, 'Saída sem HAnim de 32 ossos.')
    table = tables[0]
    require({b[0] for b in table} == SA_IDS and {b[1] for b in table} == set(range(32)), 'IDs/índices de saída incorretos.')
    ids = [f.bone_id for f in m.frames if f.bone_id is not None]
    require(len(ids) == 32 and set(ids) == SA_IDS, 'Frames HAnim de saída duplicados/incompletos.')
    by_id = {f.bone_id: i for i, f in enumerate(m.frames) if f.bone_id is not None}
    max_weight_error = 0.0
    for a in m.atomics:
        fi, gi, _, _ = struct.unpack('<4I', one(chunks(a.payload), STRUCT, 'Atomic Struct').payload)
        g = m.geometries[gi]
        require(g.skin.count == 32, 'Skin de saída sem 32 ossos.')
        for inds, ws in zip(g.skin.indices, g.skin.weights):
            err = abs(sum(ws) - 1)
            max_weight_error = max(max_weight_error, err)
            require(err < 1e-5 and all(i < 32 for i in inds), 'Pesos/índices de saída inválidos.')
        for bid, idx, _ in table:
            skin_world = mul(m.worlds[fi], inverse(g.skin.inverse_bind[idx]))
            require(matrix_error(skin_world, m.worlds[by_id[bid]]) < 0.002, 'Frames e binds de saída incoerentes.')
    preserved = False
    if original:
        require(len(original.geometries) == len(m.geometries), 'Quantidade de geometrias alterada.')
        for old, new in zip(original.geometries, m.geometries):
            require(old.vertex_count == new.vertex_count and old.triangle_count == new.triangle_count, 'Topologia alterada.')
            require(old.struct_chunk.payload[:old.morph_offset] == new.struct_chunk.payload[:new.morph_offset], 'UVs, triângulos ou vertex colors alterados.')
            require([c.encode() for c in old.children if c.kind not in (STRUCT, EXTENSION)] ==
                    [c.encode() for c in new.children if c.kind not in (STRUCT, EXTENSION)], 'Materiais alterados.')
            require([c.encode() for c in chunks(old.extension_chunk.payload) if c.kind != SKIN] ==
                    [c.encode() for c in chunks(new.extension_chunk.payload) if c.kind != SKIN], 'Plugins não relacionados ao skin alterados.')
        preserved = True
    return {'passed': True, 'hanim_ids_unique': True, 'skin_frames_bind_consistent': True,
            'mesh_skeleton_alignment': alignment,
            'maximum_weight_sum_error_float32': max_weight_error, 'topology_uv_materials_other_geometry_plugins_byte_preserved': preserved}


def _same_path(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def convert_file(source_path, output_path=None, reference_path=None, mapping_path=None, bake_pose=True, overwrite=False, ground_offset=0.0):
    source = Path(source_path).expanduser().resolve()
    require(source.is_file() and source.suffix.lower() == '.dff', 'Escolha o DFF de entrada, não YDD/YFT.')
    require(source.stat().st_size <= MAX_FILE_BYTES, 'DFF maior que 100 MB.')
    output = Path(output_path).expanduser().resolve() if output_path else source.with_name(source.stem + '_sa.dff')
    require(output.suffix.lower() == '.dff', 'A saída precisa ter extensão .dff.')
    require(not _same_path(source, output), 'A saída não pode ser o arquivo original.')
    require(not reference_path or not _same_path(reference_path, output), 'A saída não pode substituir a referência SA.')
    require(not mapping_path or not _same_path(mapping_path, output), 'A saída não pode substituir o mapa JSON.')
    report_path = output.with_suffix('.relatorio.json')
    require(overwrite or (not output.exists() and not report_path.exists()), 'Saída/relatório já existem. Escolha outro nome ou permita sobrescrever somente a saída.')
    data = source.read_bytes()
    converted, report = convert_bytes(data, reference_path, mapping_path, bake_pose, ground_offset)
    report.update({'input_file': str(source), 'output_file': str(output), 'report_file': str(report_path)})
    # Validação terminada antes de escrever. O DFF de origem nunca é aberto para escrita.
    _atomic_write(output, converted)
    _atomic_write(report_path, (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return report
