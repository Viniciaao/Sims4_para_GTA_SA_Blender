# Guia de Uso

## Conversão básica

1. **Prepare seu DAE**
   - Exporte do Sims 4 Studio ou Blender com armature + meshes skinned
   - Nomeie de forma clara: `MeuPersonagem.dae`
   - Mantenha as texturas (`.png`) na mesma pasta do DAE se quiser referência

2. **Abra o Blender 4.2–4.5 LTS** com DragonFF e este addon ativos

3. **No painel Sims 4 -> SA** (`N` → aba `Sims 4 -> SA`):
   - **DAE de entrada:** selecione `MeuPersonagem.dae`
   - **DFF de saída:** deixe vazio para gerar `MeuPersonagem_SA.dff` ao lado do DAE, ou escolha caminho customizado
   - **Ajustar membros para pose-base SA:** deixe marcado (recomendado)
   - **Ajuste vertical:** `0.000` na primeira tentativa
   - **Permitir sobrescrever:** desmarcado por segurança

4. **Clique `Converter DAE -> DFF SA`** e aguarde

5. **Resultado:**
   ```
   MeuPersonagem_SA.dff           ← use no jogo
   MeuPersonagem_SA.relatorio.json← auditoria técnica
   ```

## Entendendo o relatório JSON

```json
{
  "tool_version": "1.0.8",
  "source_bones": 185,
  "target_bones": 32,
  "vertices": 44368,
  "triangles": 68547,
  "maximum_bind_frame_error": 4.8e-07,
  "ground_offset": 0.0,
  "validation": { "passed": true },
  "warnings": ["..."],
  "output_sha256": "395b0ac6..."
}
```

- `maximum_bind_frame_error` deve ser `< 0.002` (se maior, conversão falha)
- `validation.passed` deve ser `true`
- `warnings` explica perdas esperadas (dedos, faciais)
- `ground_offset` é o ajuste vertical aplicado

Guarde o JSON para reportar bugs.

## Ajuste vertical

Se o personagem flutuar ou afundar no GTA SA:

| Sintoma | Ação |
|---|---|
| Pés acima do chão | Diminua: `−0.50`, `−1.00`, `−1.060` (HFYSTB) |
| Pés abaixo do chão | Aumente: `−0.30`, `0.00`, `+0.20` |

Ajuste em passos de `0.10` até acertar. Cada modelo tem ponto diferente.

Exemplo HFYSTB: `0.00` flutua → `−0.74` ainda flutua → `−1.060` perfeito.

## Pós-processamento para o jogo

O DFF contém geometria + skeleton. Você precisa:

1. **Criar TXD** (texturas):
   - Use **TXD Workshop** ou **Magic TXD**
   - Importe as texturas do DAE (`*_diffuse.png`, etc.)
   - Salve como `meu_ped.txd` (mesmo basename do DFF)

2. **Instalar com ModLoader:**
   ```
   GTA San Andreas/
   └── ModLoader/
       └── MeuPersonagem/
           ├── meu_ped.dff
           ├── meu_ped.txd
           └── peds.ide  (opcional, para ped personalizado)
   ```

3. **Testar:**
   - Parado, andar, correr, pular
   - Mira com arma, agachar
   - Mãos, joelhos, pés no chão
   - Roupas/acessórios

## Dicas

- Teste primeiro **sem TXD** (modelo branco) para validar skeleton
- Use `Importar DFF final na cena` para inspecionar no Blender antes de ir ao jogo
- Faça backup do DFF original do jogo
- Se o modelo tiver múltiplas roupas, cada DAE gera um DFF separado

## Tratamento de erros

Se a conversão falhar, um `*_intermediario_debug.dff` é salvo. **Não use no jogo.** Anexe-o junto com o `relatorio.json` em uma [Issue](https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/issues/new).

Veja [Troubleshooting](troubleshooting.md) para erros comuns.
