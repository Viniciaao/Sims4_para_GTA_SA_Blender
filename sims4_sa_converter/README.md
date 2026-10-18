# The Sims 4 → GTA San Andreas DFF Converter — v1.0.8

Addon para Blender que transforma um personagem Sims 4 em `.dae` (COLLADA) em um `.dff` de ped para GTA San Andreas, com skeleton HAnim padrão SA de 32 ossos e pesos de skin remapeados.

**v1.0.8:** identifica automaticamente, pelas matrizes de bind, o frame-base usado pelo Skin. Corrige casos como `AbbyS.dae`, em que o Atomic fica anexado ao osso Root mas os binds continuam no frame do objeto/armature; isso evita contar a transformação do Root duas vezes. A conversão continua recusando binds ambíguos ou incoerentes.

**v1.0.7:** junta os objetos mesh skinned importados em uma só mesh antes da exportação. Mantém os slots de material e harmoniza os nomes/canais UV antes do join; valida que o DFF intermediário tenha exatamente **1 Geometry e 1 Atomic**. Se o exportador não cumprir isso, a conversão para com erro em vez de entregar um ped com várias meshes.

**v1.0.6:** acrescenta no painel do addon o lembrete **“Ajuste vertical recomendado (HFYSTB): -1.060”**. O campo continua manual e o padrão permanece `0,000`; a recomendação não é aplicada automaticamente.

**v1.0.5:** preserva UVs e bake mesh-to-armature, e amplia o campo opcional **Ajuste vertical do ped** para `−1,5` a `+1,5` unidades (padrão `0,000`). Valores negativos abaixam; positivos levantam. O comportamento anterior de exportar vários atomics, mantido até v1.0.6, foi corrigido na v1.0.7. Se a validação estrutural falhar, salva o intermediário com sufixo `_intermediario_debug.dff`.

## Requisitos

- **Blender 4.2–4.5 LTS**. A importação COLLADA é nativa nessas versões; foi removida no Blender 5.
- **DragonFF 1.1.0** instalado e ativado. O addon DragonFF é dependência externa e não está incluído aqui.
- DAE com um único armature Sims 4, malha(s) skinned e vertex groups compatíveis com o rig padrão adulto/CAS.

O addon faz tudo a partir do DAE selecionado: importa a cena, converte cada mesh para o espaço local do armature, junta os objetos skinned em uma única mesh, exporta um DFF intermediário temporário via DragonFF, reconstrói o skeleton/skin SA e valida binds, pesos, alinhamento e contagem de Geometry/Atomic antes de gravar o DFF final. Materiais diferentes permanecem como slots/submateriais dentro da mesma Geometry; UVs são alinhados e preservados no join. O campo de ajuste vertical permite uma correção fina no resultado do jogo. O intermediário fica em uma pasta temporária e é removido. **Não é necessário exportar manualmente um DFF intermediário.**

## Instalação

1. Instale/ative o **DragonFF 1.1.0** pelo Blender Extensions ou pelo pacote oficial: <https://extensions.blender.org/add-ons/dragonff/>.
2. No Blender, abra **Edit → Preferences → Add-ons → Install from Disk…** (ou **Get Extensions → Install from Disk…**).
3. Selecione `sims4_sa_converter.zip` e ative **The Sims 4 -> GTA SA DFF Converter**.
4. No Viewport 3D pressione **N** e abra a aba **Sims 4 -> SA**.

## Converter

1. Em **DAE de entrada**, selecione seu personagem `.dae`.
2. Em **DFF de saída**, escolha um destino/nome. Se deixar vazio, o addon cria `<nome>_SA.dff` ao lado do DAE.
3. Deixe **Ajustar membros para pose-base SA** marcado na primeira tentativa.
4. Deixe **Ajuste vertical do ped** em `0,000` para novos modelos. Para a HFYSTB, o ponto recomendado pelo usuário é `−1,060` (o painel exibe esse lembrete). Se outra instalação ainda flutuar ou afundar, ajuste em passos pequenos.
5. Clique **Converter DAE -> DFF SA**.
6. O resultado é acompanhado por `<nome>_SA.relatorio.json`, que registra o ajuste aplicado. Com **Importar DFF final na cena** ligado, o addon também abre o resultado com DragonFF para inspeção.

Por segurança, uma saída que já existe não é substituída sem marcar **Permitir sobrescrever a saída**. O arquivo DAE de entrada nunca é alterado.

## Mapeamento de skeleton

O mapa `sims4_bone_map.json` incluído reconhece nomes comuns do rig Sims 4 (nomes `b__...__`). Ele envia pelve, coluna, cabeça, braços, mãos e pernas aos IDs HAnim correspondentes do ped SA; dedos, twists, ossos faciais, pálpebras e ossos auxiliares são agrupados nos canais equivalentes mais próximos. A saída reconstrói os 32 ossos, os IDs HAnim, hierarquia, binds e pesos normalizados (até quatro influências por vértice).

**Isso é um retarget many-to-one**, não uma preservação de todos os 185 canais do Sims 4. Dedos, expressões faciais, twists e slots não têm equivalentes um-para-um no rig SA, então parte dos movimentos perde independência. Para um DAE com nomes diferentes, indique um JSON próprio em **Mapa JSON customizado**. Esse mapa substitui o mapa Sims 4 incluído e deve conter os nomes das juntas principais e os IDs HAnim GTA SA.

O preset padrão de skeleton SA está incluído. É possível selecionar um DFF de referência próprio, desde que seja um ped PC padrão com os 32 ossos SA (não CJ modular, animal, cutscene ou rig customizado).

## Investigação `AbbyS`

O DAE usa `Z_UP` e tem um frame de objeto/armature `rig` na raiz, seguido pelo osso `b__ROOT__`. O DragonFF anexou o Atomic ao frame `b__ROOT__`, embora os inverse-bind matrices da pele estejam no espaço do frame `rig`. A versão anterior multiplicava pelo frame do Atomic e contava a transformação do Root duas vezes: o erro aparente chegava a `0,021116`, acima do limite `0,002`, apesar de IDs/ordem coerentes. A v1.0.8 procura o frame que melhor reconcilia todos os binds: para o debug DFF, escolheu `rig` e obteve erro máximo `0,000000485`. A conversão do debug DFF foi executada com sucesso: 44.368 vértices, 68.547 triângulos, 1 Geometry/Atomic e validação aprovada.

## Arquivo de teste `Akane102`

O DFF antigo e o relatório v1.0.2 de `Akane102` registram **2 atomics** porque a junção estava desativada. Esse comportamento era inadequado para o requisito de ped com uma única mesh e foi corrigido na v1.0.7. Não encontrei no Drive um arquivo-fonte chamado `Akane102.dae`; não substituí o teste por AkaneSa nem por outro DAE. Para repetir a conversão ponta a ponta com Akane102, é necessário disponibilizar esse DAE.

No teste visual, o usuário encontrou `−1,060` como ponto bom para a HFYSTB e pediu que o painel mostre esse valor como lembrete. A v1.0.6 e posteriores não aplicam o ajuste automaticamente; ele continua manual. A adequação de outros modelos deve ser calibrada separadamente.

## Limites e validação

- Entrada: `.dae` COLLADA com um único skeleton e malhas rigadas. Modelos sem pesos, múltiplos armatures, rigs infantis/customizados ou acessórios de skeleton separado podem ser recusados para evitar uma conversão silenciosamente errada.
- Saída: DFF PC / RenderWare GTA SA v3.6.0.3, skeleton HAnim padrão de ped SA.
- Não converte `.package`, `.sim`, `.blend`, animações IFP, texturas para TXD nem os recursos nativos do The Sims 4.
- O relatório registra número de ossos, geometria, mapeamento, pesos, hashes e resultado das validações internas.
- Faça teste visual e no jogo: parado, andar/correr, mira, mãos, joelhos, contato dos pés e acessórios/roupas. Ajustes manuais podem ser necessários.

## Arquivos do pacote

- `__init__.py` — interface e pipeline Blender/DragonFF.
- `core.py` — leitura/validação DFF, retarget e escrita do skeleton/skin SA.
- `sa_preset.json` — preset de rig SA padrão.
- `sims4_bone_map.json` — mapa para o rig Sims 4 do teste.
- `tests/` — testes unitários herdados do núcleo do conversor de esqueleto.
- `LICENSE.txt` — GPL-3.0-or-later para o código incluído.

DragonFF é projeto independente, não redistribuído neste ZIP. Direitos sobre personagens, malhas, texturas e marcas continuam com seus respectivos titulares.
