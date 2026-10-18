# Contribuindo

Obrigado por considerar contribuir! 🙏

## Como contribuir

### 1. Reportar bugs

Abra uma [Issue](https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/issues/new) com:

- **Versão do addon** (ex: v1.0.8), **Blender** (ex: 4.5 LTS), **DragonFF** (ex: 1.1.0)
- **DAE de entrada** ou pelo menos o `relatorio.json` + `*_intermediario_debug.dff` gerado
- **Passos para reproduzir** e mensagem de erro completa (copie do `Window → Toggle System Console`)
- **Comportamento esperado vs. obtido**

> Se o erro gerar `_intermediario_debug.dff`, **anexe-o** — ele é essencial para diagnosticar binds.

### 2. Sugerir melhorias

- Novo mapeamento de ossos? Envie PR editando `sims4_bone_map.json` com justificativa e teste.
- Melhorias de documentação, tradução e exemplos são ótimos primeiros PRs.
- Para mudanças grandes, abra uma Issue primeiro para alinharmos.

### 3. Pull Requests

1. Fork o repositório
2. Crie uma branch: `git checkout -b minha-feature`
3. Faça commits descritivos
4. Teste com `python -m pytest tests/` (se houver) e no Blender
5. Abra PR contra `main` com descrição clara

### Padrões

- Código: Python 3.10+, estilo próximo ao PEP 8
- Mensagens de erro: em **pt-BR**, claras para o usuário final
- `core.py` deve permanecer **puro Python** (sem `bpy`) — testável fora do Blender
- `__init__.py` cuida apenas da UI/pipeline Blender

## Desenvolvimento local

```bash
git clone https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender.git
cd Sims4_para_GTA_SA_Blender
# Edite sims4_sa_converter/
# Para testar o núcleo sem Blender:
python -m pytest tests/ -v
```

## Código de conduta

Seja respeitoso. Não toleramos assédio. Mods de personagens devem respeitar direitos autorais de seus criadores (EA, Rockstar, artistas originais).

## Licença

Ao contribuir você concorda que sua contribuição será licenciada sob **GPL-3.0-or-later**, mesma licença do projeto.

