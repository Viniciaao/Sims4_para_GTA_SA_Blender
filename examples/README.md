# Exemplos

Esta pasta contém exemplos de uso e relatórios de referência.

## Modelo de teste AbbyS

- **Entrada:** `AbbyS.dae` (185 ossos, `Z_UP`, 2 meshes skinned)
- **Intermediário:** `AbbyS_intermediario_debug.dff` (186 frames, 1 Geometry/Atomic)
- **Saída v1.0.8:** `AbbyS_SA_v1.0.8_teste.dff`
- **Relatório:** [`AbbyS_SA_v1.0.8_teste.relatorio.json`](AbbyS_SA_v1.0.8_teste.relatorio.json)

```
vertices: 44368
triangles: 68547
target_bones: 32 (30 com influência)
maximum_bind_frame_error: 4.84e-07
frame-base inferido: rig
validação: aprovada
```

## Como usar este exemplo

1. Baixe `AbbyS.dae` do Drive (link privado)
2. Converta com v1.0.8 e `ground_offset=0.0`
3. Compare seu `relatorio.json` com o de referência — `maximum_bind_frame_error` deve ser `< 0.002` e `validation.passed=true`

## Logs no Drive

Os relatórios completos e DFFs de teste estão no [Google Drive do projeto](https://drive.google.com/drive/folders/17V1Fh-JBunRG_5Vn1SGoyO3Sst5YBesI).

> Os arquivos `.dae` e `.dff` grandes não são versionados aqui para manter o repositório leve. Use o Drive ou Releases.
