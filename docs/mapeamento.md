# Mapeamento de Skeleton

## Visão geral

- **Origem (Sims 4):** ~185 ossos, incluindo dedos, faciais, twists, slots
- **Destino (GTA SA):** 32 ossos HAnim padrão de ped (IDs oficiais Rockstar)

O mapeamento é **many-to-one**: vários ossos Sims 4 → um osso SA.

## Tabela completa (mapa padrão)

O arquivo [`sims4_bone_map.json`](../sims4_sa_converter/sims4_bone_map.json) contém 107 entradas:

### Tronco e cabeça

| Sims 4 | SA | ID |
|---|---|---|
| `b__ROOT__`, `b__ROOT_bind__` | Root | 0 |
| `b__Pelvis__` | Pelvis | 1 |
| `b__Spine0__`, `b__Spine1__` | Spine | 2 |
| `b__Spine2__` (+ `Spine3`) | Spine1 | 3 |
| `b__Neck__` | Neck | 4 |
| `b__Head__` | Head | 5 |
| `b__L/R_OutBrow__`, `L/R_InBrow`, `L/R_MidBrow` | Brow | 6 / 7 |
| `b__Jaw__`, `LoLip`, `UpLip`, `CAS_JawComp`, etc. | Jaw | 8 |

### Braços

| Sims 4 | SA | ID |
|---|---|---|
| `b__R_Clavicle__` | R Clavicle | 21 |
| `b__R_UpperArm__` + `ShoulderTwist`, `Elbow` | R UpperArm | 22 |
| `b__R_Forearm__` + `ForearmTwist` | R Forearm | 23 |
| `b__R_Hand__` | R Hand | 24 |
| `b__R_Index0__` + `Thumb0/1/2` | R Finger | 25 |
| `b__R_Index1__` + `Middle/Ring/Pinky 0/1/2` | R Finger1 | 26 |
| `b__L_Clavicle__` | L Clavicle | 31 |
| `b__L_UpperArm__` | L UpperArm | 32 |
| `b__L_Forearm__` | L Forearm | 33 |
| `b__L_Hand__` | L Hand | 34 |
| `b__L_Index0__` | L Finger | 35 |
| `b__L_Index1__` | L Finger1 | 36 |

### Pernas

| Sims 4 | SA | ID |
|---|---|---|
| `b__L_Thigh__` + `ThighTwist` | L Thigh | 41 |
| `b__L_Calf__` | L Calf | 42 |
| `b__L_Foot__` | L Foot | 43 |
| `b__L_Toe__` | L Toe | 44 |
| `b__R_Thigh__` | R Thigh | 51 |
| `b__R_Calf__` | R Calf | 52 |
| `b__R_Foot__` | R Foot | 53 |
| `b__R_Toe__` | R Toe | 54 |

### Extras

| Sims 4 | SA | ID |
|---|---|---|
| `b__Belly__` | Belly | 201 |
| `b__CAS_R_Breast__` | Breast R | 301 |
| `b__CAS_L_Breast__` | Breast L | 302 |

## Ossos agrupados (perda esperada)

Faciais (`Cheek`, `Squint`, `Eye`, `Nose`, `MouthArea`, `Eyebrow`), twists, dedos extras e slots (`Earring_slot`, `Neck_slot`, `Prop`) são enviados ao **ancestral reconhecido** mais próximo (Head, Spine, Hand, etc.).

Resultado: animações de dedos individuais e expressões faciais não terão canais independentes no GTA SA — é limitação do rig de 32 ossos, não bug.

## Mapa customizado

Se seu DAE usa nomes diferentes (ex: rig customizado ou outro jogo), crie um JSON no formato:

```json
{
  "meu_root": 0,
  "meu_spine_01": 2,
  "meu_hand_R": 24
}
```

Chaves = nomes exatos dos ossos no DAE, valores = IDs HAnim SA (0,1,2,3,4,5,6,7,8,21,22,23,24,25,26,31,32,33,34,35,36,41,42,43,44,51,52,53,54,201,301,302).

Indique o arquivo no campo **Mapa JSON customizado** do painel. Ele **substitui** totalmente o mapa padrão.

## DFF de referência customizado

Por padrão o addon usa `sa_preset.json` (hieraquia conferida com `ballas1`). Você pode indicar um DFF PC de ped SA padrão (32 ossos) no campo **Ped SA de referência**. Requisitos:

- DFF PC (RW 3.6.0.3 `0x36003`)
- 32 ossos ped padrão (não CJ modular, animal, cutscene ou rig custom)
- Um Frame List + uma Geometry + um Atomic (ped de rua)

O addon valida que o DFF de referência tem exatamente 32 ossos com IDs HAnim únicos.

## Preset SA

`sa_preset.json` contém:
- `dummy_matrix`, `bones[]` com `id`, `name`, `parent_id`, `world_matrix`, `flags`
- Proveniência: conferido com `ballas1` (sem malha/texturas)

Não edite manualmente a menos que saiba o que faz — um preset quebrado gera DFF inválido.
