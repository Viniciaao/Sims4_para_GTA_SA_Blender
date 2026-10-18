# Instalação Detalhada

## Pré-requisitos

| Item | Versão exigida | Notas |
|---|---|---|
| Blender | 4.2 – 4.5 LTS | COLLADA removido no Blender 5 |
| DragonFF | 1.1.0 | Dependência externa |
| SO | Windows / Linux / macOS | Testado em Windows 10/11 |

## Passo 1 — Instalar Blender LTS

1. Acesse https://www.blender.org/download/lts/
2. Baixe **Blender 4.2 LTS** ou **4.5 LTS** (recomendado 4.5)
3. Instale normalmente
4. Abra o Blender → confirme a versão em `Help → About`

> Se você já tem Blender 4.2+, pode pular.

## Passo 2 — Instalar DragonFF 1.1.0

DragonFF é o addon que lê/escreve DFF. Nosso conversor depende dele.

**Via Extensions (recomendado):**
1. No Blender: `Edit → Preferences → Get Extensions`
2. Busque `DragonFF` → `Install` → ative a caixinha

**Via ZIP:**
1. Baixe em https://extensions.blender.org/add-ons/dragonff/
2. No Blender: `Edit → Preferences → Add-ons → Install from Disk…` → selecione o ZIP do DragonFF → ative

**Verificação:** Em `Preferences → Add-ons` deve aparecer **DragonFF** ativado. No Viewport 3D, `File → Import` deve mostrar `DFF (.dff)` e `File → Export` deve mostrar `DFF`.

## Passo 3 — Instalar este addon

1. Baixe `Sims4_para_GTA_SA_Blender_Addon_v1.0.8.zip` em [Releases](https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/releases/latest)
   - Não descompacte o ZIP manualmente!
2. No Blender: `Edit → Preferences → Add-ons → Install from Disk…` (ou `Get Extensions → Install from Disk…`)
3. Selecione o ZIP baixado → `Install`
4. Ative **The Sims 4 -> GTA SA DFF Converter**
5. No Viewport 3D pressione **N** → procure a aba **Sims 4 -> SA** na lateral direita

Se a aba não aparecer, verifique:
- DragonFF está ativo?
- Você está no `Viewport 3D` (não no `Shader Editor`)?
- Reinicie o Blender

## Passo 4 — Verificar instalação

1. Abra a aba `Sims 4 -> SA`
2. Você deve ver:
   - `DAE de entrada` (file picker)
   - `DFF de saída` (file picker)
   - ☑ `Ajustar membros para pose-base SA`
   - `Ajuste vertical do ped: 0.000`
   - Botão `Converter DAE -> DFF SA`

Pronto para converter! → [Guia de uso](uso.md)

## Atualizar

1. Baixe o novo ZIP da release
2. No Blender: `Preferences → Add-ons` → remova a versão antiga (ou apenas instale por cima)
3. `Install from Disk…` → selecione novo ZIP → ative
4. Reinicie o Blender

## Desinstalar

`Preferences → Add-ons` → procure `Sims 4 -> GTA SA` → `Remove`
