# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [1.0.8] - 2026-10-18

### Corrigido
- **Detecção automática do frame-base do Skin PLG.** O core agora testa todos os frames candidatos contra as matrizes `inverse_bind` e escolhe o único frame que reconcilia todos os binds abaixo do limite `0.002`. Antes, assumia sempre o frame do Atomic (`b__ROOT__`), o que contava a transformação do Root duas vezes quando o Atomic estava anexado a um osso mas os binds estavam no espaço do frame `rig` (caso `AbbyS.dae`).
- Erro de bind em `AbbyS.dae`: `0.0211164` → `4.8427e-07` ✅
- Transformação de vértices agora usa o frame-base inferido, não o Atomic.

### Verificado
- `core.inspect_bytes` do `AbbyS_intermediario_debug.dff`: aprovado, anchor `rig`
- Conversão completa do debug DFF: 44.368 vértices, 68.547 triângulos, 30 ossos com influência, 1 Geometry/Atomic
- 54 testes passaram, 7 pulados

---

## [1.0.7] - 2026-10-18

### Adicionado
- Junção de múltiplas meshes skinned em **única mesh** antes da exportação via DragonFF
- Preservação de material slots como submateriais da mesma Geometry
- Harmonização de UV layers antes do join (canal compartilhado `S4SA_JoinedUV`)
- Validação que o DFF intermediário tem exatamente **1 Geometry e 1 Atomic** — falha com erro se não cumprir
- Relatório: `source_meshes_joined`, `output_geometry_count`, `output_atomic_count`, `output_material_slots`

### Corrigido
- Até v1.0.6, cada objeto mesh virava uma Atomic separada. Agora é 1 Geometry/Atomic como exige o padrão SA ped.

---

## [1.0.6] - 2026-10-18

### Adicionado
- Lembrete no painel: **“Ajuste vertical recomendado (HFYSTB): -1.060”**
- Valor validado pelo usuário para a skin HFYSTB (não aplicado automaticamente)

### Mantido
- Padrão do campo `ground_offset` continua `0.000` (cada modelo tem seu ponto ideal)

---

## [1.0.5] - 2026-10-18

### Adicionado
- Campo **Ajuste vertical do ped** no painel: `−1.5` a `+1.5` unidades (padrão `0.000`)
- Bake de `mesh.matrix_world` → `armature.matrix_world` (corrige rotação/offset de DAEs com transforms diferentes)
- Preservação de UVs no bake

### Documentado
- HFYSTB: entre `-0.25` (flutua) e `-1.23552` (afunda); intermediário `-0.74` testado

---

## [1.0.4] - 2026-10-18

### Corrigido
- Calibração de pivô Akane102 — ajuste fino de posição na hierarquia

---

## [1.0.3] - 2026-10-18

### Testado
- Ponto experimental `-1.23552` para HFYSTB — reportado como afundado (delimita intervalo)

---

## [1.0.2] - 2026-10-18

### Adicionado
- Exportação com **atomics separadas** dentro de um único clump (preserva UV por peça, corrige perda de UV secundário da v1.0.1)
- Transform de cada mesh para espaço local do armature
- Validação de orientação mesh/skeleton
- Salvamento de `_intermediario_debug.dff` se validação falhar

### Documentado
- Fluxo completo DAE → DFF sem exportação manual intermediária

---

## [1.0.1] - 2026-10-18

### Corrigido
- Junção de malhas preservando uma UV (introduziu perda de UV secundário — corrigido em v1.0.2)

---

## [1.0.0] - 2026-10-18

### Adicionado
- Versão inicial: pipeline Blender COLLADA → DragonFF → core retarget → DFF SA v3.6.0.3
- Skeleton HAnim 32 ossos SA, pesos normalizados (até 4 influências/vértice)
- Mapa `sims4_bone_map.json` para rig padrão Sims 4
- Preset `sa_preset.json` conferido com `ballas1`
- Relatório JSON + import preview opcional
- Testes unitários do núcleo

---

[1.0.8]: https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/releases/tag/v1.0.8
[1.0.7]: https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/releases/tag/v1.0.7
[1.0.6]: https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/releases/tag/v1.0.6
[1.0.5]: https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/releases/tag/v1.0.5
