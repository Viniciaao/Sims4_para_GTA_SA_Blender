# Solução de Problemas

## Erros no Blender

### `Importador COLLADA não encontrado`
**Causa:** Blender 5.0+ ou COLLADA desativado
**Solução:** Use **Blender 4.2 LTS** ou **4.5 LTS**. O suporte DAE foi removido no Blender 5.

### `DragonFF não está ativo`
**Causa:** DragonFF não instalado
**Solução:**
1. `Edit → Preferences → Get Extensions` → busque `DragonFF` → Install
2. Ou baixe em https://extensions.blender.org/add-ons/dragonff/
3. Ative a caixinha em `Add-ons`

### `Esperado um único armature Sims 4; encontrados X`
**Causa:** DAE com múltiplos armatures ou sem armature
**Solução:** Seu DAE deve ter exatamente 1 armature. Reexporte do Sims 4 Studio com um único rig adulto/CAS.

### `A malha "X" não tem vertex groups que coincidam`
**Causa:** Mesh sem pesos / nomes de grupos diferentes dos ossos
**Solução:** Verifique no Blender que a mesh tem `Vertex Groups` com nomes `b__...__` iguais aos ossos. Reexporte com pesos.

### `A ordem dos ossos importados não é pai-antes-do-filho`
**Causa:** Ordem de ossos incorreta no DAE
**Solução:** Reimporte com o importer COLLADA do Blender 4.5 LTS. Se persistir, reexporte o DAE.

### `Frame contém NaN/infinito` / `Matriz de bind singular`
**Causa:** DAE corrompido ou com transforms inválidos
**Solução:** Reexporte o DAE. Verifique se não há escala zero ou rotação inválida no armature.

### `Skin antigo (RW < 3.4) não suportado`
**Causa:** DFF intermediário com versão antiga
**Solução:** O DragonFF deve exportar como `0x36003` (SA PC). Verifique configurações do DragonFF.

## Erros visuais no jogo

### Personagem branco / sem textura
**Causa:** Sem TXD
**Solução:** Crie TXD com TXD Workshop / Magic TXD usando as texturas do DAE. Salve com mesmo nome do DFF.

### Personagem flutua ou afunda
**Causa:** Altura do rig diferente do SA
**Solução:** Ajuste o campo **Ajuste vertical do ped**:
- Flutua → tente `−0.50`, `−1.00`, `−1.060` (HFYSTB)
- Afunda → tente `−0.30`, `0.00`
- Ajuste em passos de `0.10`

### Mãos/braços tortos ou esticados
**Causa:** Pose não normalizada
**Solução:** Deixe **Ajustar membros para pose-base SA** marcado. Se ainda torto, verifique se o DAE está em pose T/ A correta.

### Partes da roupa sumiram ou UV quebrado
**Causa:** DAE com múltiplas meshes e UVs conflitantes
**Solução:** v1.0.7+ já corrige isso (junta em 1 Geometry). Se usar versão antiga, atualize. Verifique que cada mesh tem UV layer.

### Animações de dedos não funcionam
**Causa:** Limitação do rig SA (32 ossos)
**Solução:** Esperado. O Sims 4 tem dedos independentes, o SA agrupa. Não há como ter 10 dedos independentes com 32 ossos.

## Erros de validação

### `maximum_bind_frame_error > 0.002`
**Causa:** Frame-base incorreto (corrigido em v1.0.8)
**Solução:** Atualize para v1.0.8. Se ainda falhar, anexe `*_intermediario_debug.dff` + `relatorio.json` em uma Issue — é um caso ambíguo que o addon recusa por segurança.

### `HAnim IDs não únicos`
**Causa:** DFF de referência inválido
**Solução:** Use DFF ped padrão SA (32 ossos, não CJ/animal/cutscene).

## FAQ

**Posso converter .package direto?**
Não. Exporte para `.dae` primeiro via Sims 4 Studio.

**Funciona com rig infantil / custom?**
Não garantido. O addon valida rig adulto padrão. Rigs diferentes podem ser recusados.

**Preciso refazer TXD toda vez?**
Só se mudar texturas. O DFF é só geometria/skeleton.

**Posso usar Blender 5?**
Não. Use 4.2 ou 4.5 LTS.

**O addon altera meu DAE?**
Nunca. Ele só lê.

**Onde reporto bug?**
https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/issues — inclua `relatorio.json` e `debug.dff` se houver.
