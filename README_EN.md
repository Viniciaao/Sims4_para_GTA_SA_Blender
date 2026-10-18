# The Sims 4 → GTA San Andreas — DFF Converter for Blender

<p align="center">
  <img src="assets/images/banner.jpg" alt="Banner Sims4 to GTA SA" width="100%">
</p>

<p align="center">
  <a href="https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/releases"><img src="https://img.shields.io/github/v/release/Viniciaao/Sims4_para_GTA_SA_Blender?label=version&color=2ea44f&style=for-the-badge" alt="Version"></a>
  <img src="https://img.shields.io/github/license/Viniciaao/Sims4_para_GTA_SA_Blender?color=informational&style=for-the-badge" alt="License GPL-3.0">
  <img src="https://img.shields.io/badge/Blender-4.2--4.5%20LTS-%23F5792A?style=for-the-badge&logo=blender&logoColor=white" alt="Blender 4.2-4.5 LTS">
  <img src="https://img.shields.io/badge/DragonFF-1.1.0-0066cc?style=for-the-badge" alt="DragonFF 1.1.0">
</p>

<p align="center">
  <b>Convert any The Sims 4 character (.dae) into a playable GTA San Andreas ped (.dff) — directly in Blender, in one click.</b>
</p>

> 🇧🇷 **Português é o idioma principal deste projeto.** This is an English summary. For full documentation, see [README.md](README.md) (PT-BR).

## What it does

```
.dae (Sims 4 COLLADA)  →  [ Blender + DragonFF ]  →  .dff (GTA SA PC) + .json (report)
     185 Sims bones            retarget + validation        32 HAnim SA bones
```

- Imports `.dae` with Blender's native COLLADA importer (4.2–4.5)
- Normalizes meshes to armature-local space
- Joins multiple skinned meshes into **single Geometry/Atomic** preserving UVs & materials
- Exports temporary DFF via DragonFF, rebuilds 32-bone SA skeleton with correct HAnim IDs
- Validates binds, weights, topology, UVs before writing
- Generates `.relatorio.json` report

## Requirements

- **Blender 4.2–4.5 LTS** (COLLADA removed in Blender 5)
- **DragonFF 1.1.0** — https://extensions.blender.org/add-ons/dragonff/
- DAE with single Sims 4 armature + skinned meshes

## Quick Start

1. Install DragonFF 1.1.0 in Blender
2. Download `Sims4_para_GTA_SA_Blender_Addon_v1.0.8.zip` from [Releases](https://github.com/Viniciaao/Sims4_para_GTA_SA_Blender/releases)
3. `Edit → Preferences → Add-ons → Install from Disk…` → select ZIP → enable
4. In 3D Viewport press **N** → tab **Sims 4 -> SA**
5. Pick input `.dae`, optional output `.dff`, click **Converter DAE -> DFF SA**

See [README.md](README.md) for full guide, skeleton mapping, vertical adjustment and troubleshooting.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE)
