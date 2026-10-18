# Referência Técnica

## Formato DFF

- **Versão:** RenderWare `0x36003` (GTA SA PC v3.6.0.3)
- **Estrutura:** Clump → Frame List → Geometry List → Atomic → HAnim PLG → Skin PLG
- **Validação:** `core.py` verifica chunks, tamanhos, versões, e rejeita DFFs com padding não-zero, Skin split ou RW < 3.4

## Pipeline interno

```
DAE → bpy.ops.wm.collada_import → _prepare_scene_objects()
    → _bake_meshes_to_armature_space() → _join_meshes_preserving_uvs()
    → _export_intermediate_dff() via DragonFF → core.convert_dff()
    → valida + escreve DFF final → relatório JSON
```

### Etapas Blender (`__init__.py`)

| Função | O que faz |
|---|---|
| `_call_collada_import` | Importa DAE com `import_units=True` |
| `_bone_order_and_flags` | Valida ordem pai-antes-filho, DFS HAnim, define `bone_id`/`type` |
| `_bake_meshes_to_armature_space` | `mesh.data.transform(world_to_armature @ mesh_world)` |
| `_join_meshes_preserving_uvs` | Recria UV layers idênticas, `bpy.ops.object.join()` |
| `_prepare_scene_objects` | Filtra ARMATURE/MESH, cria modifiers, seleciona para export |
| `_export_intermediate_dff` | `export_dff.scene(only_selected=True, export_version=0x36003)` |

### Núcleo (`core.py`)

Puro Python, sem `bpy` — testável isoladamente:

| Função | O que faz |
|---|---|
| `read_frames` | Lê Frame List, valida hierarquia, detecta ciclos |
| `world_matrices` | Calcula matrizes world recursivas |
| `read_skin` | Lê Skin PLG, valida `inverse_bind`, pesos |
| `inspect_bytes` | Inspeciona DFF intermediário, infere frame-base do Skin |
| `convert_dff` | Retarget skeleton SA, remapeia pesos, escreve DFF final |
| `validate_output` | Verifica HAnim únicos, bind error < 0.002, topology/UV preservados |

**Frame-base inference (v1.0.8):** Testa cada frame candidato calculando `bone_world = frame_world × inverse(inverse_bind)` e mede erro máximo. Escolhe único frame com erro `< 0.002`; se ambíguo ou nenhum, falha.

## Relatório JSON

Campos principais:

```json
{
  "tool_version": "1.0.8",
  "input_sha256": "...",
  "source_bones": 185,
  "source_frames": 186,
  "unique_hanim_frame_ids": 185,
  "maximum_bind_frame_error": 4.8e-07,
  "skin_bind_reference_frames": [{"geometry_index":0,"frame_index":0,"frame_name":"rig"}],
  "target_bones": 32,
  "vertices": 44368,
  "triangles": 68547,
  "mapping": [...],
  "warnings": [...],
  "ground_offset": -1.06,
  "validation": { "passed": true, "hanim_ids_unique": true, "skin_frames_bind_consistent": true },
  "output_sha256": "..."
}
```

## API do core

```python
from sims4_sa_converter import core

# Inspecionar DFF intermediário
info = core.inspect_bytes(open("intermediario.dff","rb").read())
print(info["maximum_bind_frame_error"], info["skin_bind_reference_frames"])

# Converter
core.convert_dff(
    input_path="intermediario.dff",
    output_path="saida_SA.dff",
    report_path="saida_SA.relatorio.json",
    map_path="sims4_bone_map.json",  # opcional
    reference_path=None,              # usa preset; ou "ballas.dff"
    ground_offset=-1.06,
    pose_baked=True
)
```

## Testes

```bash
python -m pytest tests/ -v
# 54 passed, 7 skipped (sem Blender/DragonFF)
```

Testes cobrem: parsing de chunks, validação de Frame List, Skin PLG, retarget, preservação de UV/triângulos/materiais, inferência de frame-base.

## Limites

- Máx. 512 frames, 255 bones, 4 influências/vértice
- Arquivo máx. 100 MB
- RW < 3.4 rejeitado
- Skin split não suportado
- Padding de setor IMG: só zero é tolerado
