# SPDX-License-Identifier: GPL-3.0-or-later
"""Sims 4 COLLADA (.dae) -> GTA San Andreas skinned DFF converter.

Pipeline: Blender COLLADA import -> temporary DragonFF DFF -> safe
HAnim/Skin PLG retarget and DFF validation in core.py.
"""

bl_info = {
    'name': 'The Sims 4 -> GTA SA DFF Converter',
    'author': 'Arena - custom tool',
    'version': (1, 0, 8),
    'blender': (4, 2, 0),
    'location': 'View3D > Sidebar (N) > Sims 4 -> SA',
    'description': 'Converts a skinned Sims 4 COLLADA DAE to a GTA SA ped DFF with a 32-bone SA HAnim skeleton',
    'category': 'Import-Export',
}

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from . import core

try:
    import bpy
except ModuleNotFoundError:
    bpy = None


TOOL_NAME = 'Sims 4 -> GTA SA'


def _default_map_path():
    return str(Path(__file__).with_name('sims4_bone_map.json'))


def _operator(path):
    """Resolve an operator by a dotted bpy.ops path, if registered."""
    if bpy is None:
        return None
    op = bpy.ops
    try:
        for name in path.split('.'):
            op = getattr(op, name)
        op.get_rna_type()
        return op
    except (AttributeError, RuntimeError, KeyError):
        return None


def _operator_keys(op):
    return set(op.get_rna_type().properties.keys())


def _collada_importer():
    # Blender 4.2-4.5 ships the legacy COLLADA importer under wm.collada_import.
    return _operator('wm.collada_import') or _operator('import_scene.dae')


def _dragonff_exporter():
    return _operator('export_dff.scene')


def _dragonff_importer():
    return _operator('import_scene.dff')


def _call_collada_import(path):
    op = _collada_importer()
    if op is None:
        raise RuntimeError(
            'Importador COLLADA não encontrado. Use Blender 4.2–4.5 LTS '
            '(o suporte DAE foi removido no Blender 5) ou instale um importador DAE compatível.'
        )
    keys = _operator_keys(op)
    kwargs = {'filepath': str(path)}
    if 'import_units' in keys:
        kwargs['import_units'] = True
    result = op('EXEC_DEFAULT', **kwargs)
    if 'FINISHED' not in result:
        raise RuntimeError('Blender não concluiu a importação do DAE.')


def _ensure_object_mode():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def _select_only(objects):
    _ensure_object_mode()
    for obj in bpy.context.view_layer.objects:
        try:
            obj.select_set(False)
        except RuntimeError:
            pass
    for obj in objects:
        if obj.name in bpy.context.view_layer.objects:
            obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]


def _bone_order_and_flags(armature_obj):
    """Set the metadata DragonFF requires and reject non-parent-first bone order."""
    bones = list(armature_obj.data.bones)
    if not bones:
        raise RuntimeError('O DAE não trouxe ossos para o armature.')
    by_name = {b.name: b for b in bones}
    if len(by_name) != len(bones):
        raise RuntimeError('O armature contém nomes de ossos duplicados.')
    index = {b.name: i for i, b in enumerate(bones)}
    roots = [b for b in bones if b.parent is None]
    if len(roots) != 1:
        raise RuntimeError(f'Esperado um único root no rig do Sims 4; encontrados {len(roots)}.')
    for bone in bones:
        if bone.parent is not None and index[bone.parent.name] >= index[bone.name]:
            raise RuntimeError(
                'A ordem dos ossos importados não é pai-antes-do-filho. '
                'Reimporte o DAE com o importador COLLADA do Blender 4.5 LTS.'
            )

    children = {b.name: [] for b in bones}
    for bone in bones:
        if bone.parent:
            children[bone.parent.name].append(bone)
    # Determine the HAnim stack flags using depth-first order and sibling order.
    flags = {}
    dfs_names = []
    def visit(bone, has_next=False):
        dfs_names.append(bone.name)
        flags[bone.name] = (2 if has_next else 0) | (1 if not children[bone.name] else 0)
        for i, child in enumerate(children[bone.name]):
            visit(child, i < len(children[bone.name]) - 1)
    visit(roots[0])
    if dfs_names != [b.name for b in bones]:
        raise RuntimeError(
            'A ordem dos ossos importados não é DFS HAnim. '
            'A conversão foi cancelada para evitar uma tabela de skeleton inconsistente.'
        )

    for i, bone in enumerate(bones):
        bone['bone_id'] = i
        bone['type'] = flags[bone.name]
    return bones


def _bake_meshes_to_armature_space(armature, meshes):
    """Bake each mesh's object-space offset into its vertices before DFF export.

    Some Sims CAS COLLADA files put the mesh and the rig under different scene
    transforms. DragonFF exports skin vertices in the armature frame and does
    not bake that mesh-object transform, which can rotate the mesh away from
    otherwise valid SA bones. Normalize to armature-local space first.
    """
    from mathutils import Matrix
    armature_world = armature.matrix_world.copy()
    try:
        world_to_armature = armature_world.inverted()
    except ValueError:
        raise RuntimeError('A transformação do armature é singular; não é seguro converter.')
    records = []
    for mesh in meshes:
        relative = world_to_armature @ mesh.matrix_world.copy()
        try:
            mesh.data.transform(relative, shape_keys=True)
        except TypeError:
            mesh.data.transform(relative)
        mesh.data.update()
        records.append({'mesh': mesh.name, 'mesh_to_armature': [list(row) for row in relative]})
        # The vertices are now armature-local; make object and parent frames agree.
        mesh.parent = armature
        mesh.matrix_parent_inverse = Matrix.Identity(4)
        mesh.matrix_basis = Matrix.Identity(4)
    return records


def _join_meshes_preserving_uvs(meshes):
    """Join imported CAS mesh objects into the single ped geometry required by SA.

    Before joining, rebuild every UV layer collection in an identical order.
    The first shared channel copies each object's active UV map; all other
    named UV maps are retained as additional channels. Blender joins material
    slots and remaps polygon material indices into the active mesh.
    """
    if not meshes:
        raise RuntimeError('Não há malhas para juntar.')
    if len(meshes) == 1:
        return meshes[0]

    uv_names = []
    uv_values = {}
    active_uvs = {}
    for obj in meshes:
        layers = obj.data.uv_layers
        active = layers.active if len(layers) else None
        if active is None and len(layers):
            active = layers[0]
        uv_values[obj.name] = {
            layer.name: [tuple(loop.uv) for loop in layer.data]
            for layer in layers
        }
        active_uvs[obj.name] = (
            [tuple(loop.uv) for loop in active.data] if active is not None
            else [(0.0, 0.0)] * len(obj.data.loops)
        )
        for layer in layers:
            if layer.name not in uv_names:
                uv_names.append(layer.name)

    combined_name = 'S4SA_JoinedUV'
    suffix = 1
    while combined_name in uv_names:
        combined_name = f'S4SA_JoinedUV_{suffix:03d}'
        suffix += 1

    if uv_names:
        # Recreate all channels in the same order across objects. The common
        # active UV channel is first so exporters using UV channel 0 get the
        # correct texture coordinates from every source component.
        for obj in meshes:
            layers = obj.data.uv_layers
            for layer in list(layers):
                layers.remove(layer)
            shared = layers.new(name=combined_name)
            for loop, uv in zip(shared.data, active_uvs[obj.name]):
                loop.uv = uv
            for name in uv_names:
                layer = layers.new(name=name)
                values = uv_values[obj.name].get(name, [(0.0, 0.0)] * len(layer.data))
                for loop, uv in zip(layer.data, values):
                    loop.uv = uv
            layers.active_index = 0

    _select_only(meshes)
    result = bpy.ops.object.join()
    if 'FINISHED' not in result:
        raise RuntimeError('Blender não conseguiu juntar as malhas skinned do DAE.')
    joined = bpy.context.view_layer.objects.active
    if joined is None or joined.type != 'MESH':
        raise RuntimeError('A junção não produziu um único objeto de malha.')
    if len(bpy.context.selected_objects) != 1:
        raise RuntimeError('Após juntar, ainda há mais de um objeto de malha selecionado.')
    material_count = len(joined.material_slots)
    if material_count and any(poly.material_index >= material_count for poly in joined.data.polygons):
        raise RuntimeError('A junção deixou índices de material inválidos; DFF não foi exportado.')
    return joined


def _prepare_scene_objects(imported):
    armatures = [o for o in imported if o.type == 'ARMATURE']
    meshes = [o for o in imported if o.type == 'MESH']
    if len(armatures) != 1:
        raise RuntimeError(f'Esperado um único armature Sims 4; encontrados {len(armatures)}.')
    if not meshes:
        raise RuntimeError('O DAE não contém malhas.')
    armature = armatures[0]
    bones = _bone_order_and_flags(armature)
    bone_names = {b.name for b in bones}
    source_mesh_names = [m.name for m in meshes]

    for obj in imported:
        # DragonFF writes only objects with DFF type OBJ in the selected set.
        props = getattr(obj, 'dff', None)
        if props is not None and hasattr(props, 'type'):
            props.type = 'OBJ' if obj.type in {'MESH', 'ARMATURE'} else 'NON'

    weighted_groups = 0
    for mesh in meshes:
        matched = [vg for vg in mesh.vertex_groups if vg.name in bone_names]
        if not matched:
            raise RuntimeError(f'A malha "{mesh.name}" não tem vertex groups que coincidam com os ossos do rig.')
        weighted_groups += len(matched)
        modifiers = [m for m in mesh.modifiers if m.type == 'ARMATURE']
        if modifiers:
            for modifier in modifiers:
                modifier.object = armature
        else:
            modifier = mesh.modifiers.new(name='Sims4ToSA_Armature', type='ARMATURE')
            modifier.object = armature
        if getattr(mesh, 'dff', None) is not None and hasattr(mesh.dff, 'type'):
            mesh.dff.type = 'OBJ'

    corrections = _bake_meshes_to_armature_space(armature, meshes)

    # GTA SA ped output must contain one skinned geometry/atomic. Material
    # boundaries stay as material slots inside that geometry, not extra meshes.
    joined_mesh = _join_meshes_preserving_uvs(meshes)
    meshes = [joined_mesh]

    # Avoid exporting lights/cameras/empty scene helpers from the DAE import.
    _select_only([armature] + meshes)
    return armature, meshes, weighted_groups, source_mesh_names, corrections


def _export_intermediate_dff(path):
    op = _dragonff_exporter()
    if op is None:
        raise RuntimeError('DragonFF não está ativo. Instale/ative o addon DragonFF antes de converter.')
    keys = _operator_keys(op)
    requested = {
        'filepath': str(path),
        'only_selected': True,
        'mass_export': False,
        'export_coll': False,
        'apply_coll_trans': False,
        'export_frame_names': True,
        'exclude_geo_faces': False,
        'preserve_positions': True,
        'preserve_rotations': True,
        'export_version': '0x36003',
    }
    kwargs = {k: v for k, v in requested.items() if k in keys}
    result = op('EXEC_DEFAULT', **kwargs)
    if 'FINISHED' not in result:
        raise RuntimeError('DragonFF não concluiu a criação do DFF intermediário.')
    if not Path(path).is_file() or Path(path).stat().st_size < 32:
        raise RuntimeError('DragonFF não produziu um DFF intermediário válido.')


def _missing_texture_refs(dae_path):
    """Return file paths from COLLADA image nodes that are not beside the DAE."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(str(dae_path)).getroot()
    except (ET.ParseError, OSError):
        return []
    missing = []
    base = Path(dae_path).parent
    for elem in root.iter():
        if elem.tag.rsplit('}', 1)[-1] != 'image':
            continue
        for child in list(elem):
            if child.tag.rsplit('}', 1)[-1] == 'init_from' and child.text:
                rel = child.text.strip().replace('\\', '/')
                if rel and not rel.lower().startswith(('http://', 'https://', 'data:')):
                    if not (base / rel).is_file():
                        missing.append(rel)
    return sorted(set(missing))


def _restore_selection(previous_selection, previous_active):
    try:
        _ensure_object_mode()
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        for obj in previous_selection:
            if obj.name in bpy.context.view_layer.objects:
                obj.select_set(True)
        if previous_active and previous_active.name in bpy.context.view_layer.objects:
            bpy.context.view_layer.objects.active = previous_active
    except Exception:
        pass


def _remove_imported(imported):
    _ensure_object_mode()
    for obj in list(imported):
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)


def _report_text(data, title):
    text = bpy.data.texts.new(title)
    text.write(json.dumps(data, ensure_ascii=False, indent=2))
    return text.name


def _set_result_import_option(path):
    op = _dragonff_importer()
    if op is None:
        raise RuntimeError('DFF gerado, mas DragonFF não está disponível para importar o preview.')
    keys = _operator_keys(op)
    requested = {
        'filepath': str(path),
        'connect_bones': False,
        'read_mat_split': False,
        'load_images': True,
        'import_normals': True,
        'remove_doubles': False,
    }
    kwargs = {k: v for k, v in requested.items() if k in keys}
    result = op('EXEC_DEFAULT', **kwargs)
    if 'FINISHED' not in result:
        raise RuntimeError('DragonFF não concluiu o preview do DFF convertido.')


if bpy is not None:
    class S4SA_Settings(bpy.types.PropertyGroup):
        source_file: bpy.props.StringProperty(
            name='DAE de entrada', subtype='FILE_PATH',
            description='Personagem The Sims 4 em COLLADA/DAE com armature e pesos')
        output_file: bpy.props.StringProperty(
            name='DFF de saída', subtype='FILE_PATH',
            description='Vazio gera <nome>_SA.dff na pasta do DAE')
        reference_file: bpy.props.StringProperty(
            name='Ped SA de referência (opcional)', subtype='FILE_PATH',
            description='DFF PC de ped SA padrão com 32 ossos; vazio usa preset incluído')
        mapping_file: bpy.props.StringProperty(
            name='Mapa JSON customizado (opcional)', subtype='FILE_PATH',
            description='Mapa adicional/substituto de nomes de osso para IDs HAnim SA')
        bake_pose: bpy.props.BoolProperty(
            name='Ajustar membros para pose-base SA', default=True,
            description='Corrige orientação/pose de braços e pernas no retarget; preserva a forma por rebake')
        ground_offset: bpy.props.FloatProperty(
            name='Ajuste vertical do ped', default=0.0, min=-1.5, max=1.5,
            precision=3, step=1,
            description='Correção fina de contato com o chão em unidades SA; negativo abaixa, positivo levanta. Comece em passos de 0,01')
        import_result: bpy.props.BoolProperty(
            name='Importar DFF final na cena', default=True,
            description='Abre uma cópia do DFF convertido com DragonFF ao terminar')
        overwrite_output: bpy.props.BoolProperty(
            name='Permitir sobrescrever a saída', default=False,
            description='Autoriza substituir apenas o DFF de saída e relatório, nunca o DAE')
        last_output: bpy.props.StringProperty(name='Último resultado', subtype='FILE_PATH')
        last_report: bpy.props.StringProperty(name='Relatório no Text Editor')
        status: bpy.props.StringProperty(default='Escolha o DAE e clique em Converter.')


    class S4SA_OT_Convert(bpy.types.Operator):
        bl_idname = 's4sa.convert_dae'
        bl_label = 'Converter DAE -> DFF SA'
        bl_description = 'Importa DAE, reconstrói a malha/skin como DFF e retargeta para 32 ossos HAnim GTA SA'
        bl_options = {'REGISTER'}

        def execute(self, context):
            s = context.scene.s4sa_converter
            source = Path(bpy.path.abspath(s.source_file)).expanduser().resolve() if s.source_file else None
            output = Path(bpy.path.abspath(s.output_file)).expanduser().resolve() if s.output_file else None
            previous_selection = list(context.selected_objects)
            previous_active = context.view_layer.objects.active
            imported = []
            report = None
            try:
                core.require(source is not None and source.is_file(), 'Escolha um arquivo DAE existente.')
                core.require(source.suffix.lower() == '.dae', 'A entrada precisa ser .dae.')
                core.require(source.stat().st_size <= 500 * 1024 * 1024, 'DAE excede 500 MB.')
                output = output or source.with_name(source.stem + '_SA.dff')
                output = output.with_suffix('.dff')
                core.require(os.path.normcase(str(source)) != os.path.normcase(str(output)), 'A saída não pode substituir o DAE original.')
                core.require(s.overwrite_output or (not output.exists() and not output.with_suffix('.relatorio.json').exists()),
                             'DFF/relatório já existem. Altere o nome ou marque Permitir sobrescrever a saída.')
                if s.reference_file:
                    ref = Path(bpy.path.abspath(s.reference_file)).expanduser().resolve()
                    core.require(ref.is_file(), 'DFF de referência não encontrado.')
                else:
                    ref = None
                map_path = Path(bpy.path.abspath(s.mapping_file)).expanduser().resolve() if s.mapping_file else Path(_default_map_path())
                core.require(map_path.is_file(), 'Mapa de ossos Sims 4 incluído não foi encontrado.')

                _ensure_object_mode()
                existing_objects = set(bpy.data.objects)
                _call_collada_import(source)
                imported = [o for o in bpy.data.objects if o not in existing_objects]
                core.require(imported, 'A importação do DAE não criou objetos.')
                armature, meshes, group_count, source_mesh_names, mesh_transforms = _prepare_scene_objects(imported)

                # Create an intermediate DFF only in a private temporary directory.
                # It is deleted after conversion; the DAE remains untouched.
                with tempfile.TemporaryDirectory(prefix='sims4_sa_dff_') as temp_dir:
                    intermediate = Path(temp_dir) / 'sims4_intermediate.dff'
                    _export_intermediate_dff(intermediate)
                    core.require(intermediate.stat().st_size <= core.MAX_FILE_BYTES, 'DFF intermediário excede 100 MB.')
                    intermediate_model = core.read_model(intermediate.read_bytes())
                    topology = core.require_single_ped_mesh(intermediate_model)
                    try:
                        report = core.convert_file(
                            intermediate,
                            output,
                            str(ref) if ref else None,
                            str(map_path),
                            bake_pose=s.bake_pose,
                            overwrite=s.overwrite_output,
                            ground_offset=s.ground_offset,
                        )
                    except Exception as conversion_error:
                        # Keep one clearly labeled diagnostic artifact on failure;
                        # never overwrite an existing debug file.
                        debug_path = output.with_name(output.stem + '_intermediario_debug.dff')
                        suffix = 1
                        while debug_path.exists():
                            debug_path = output.with_name(output.stem + f'_intermediario_debug_{suffix}.dff')
                            suffix += 1
                        shutil.copy2(intermediate, debug_path)
                        raise RuntimeError(
                            f'{conversion_error} DFF intermediário de diagnóstico salvo em: {debug_path}'
                        ) from conversion_error

                # Make the sidecar report describe the real input and the DAE import stage.
                report['intermediate_sha256'] = report.get('input_sha256')
                report['source_dae_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
                report['input_sha256'] = report['source_dae_sha256']
                report['input_file'] = str(source)
                report['intermediate'] = 'Importado pelo Blender COLLADA e exportado temporariamente por DragonFF; removido após conversão.'
                report['pipeline'] = 'DAE (COLLADA) -> Blender armature/mesh -> DFF temporário -> GTA SA DFF com HAnim/Skin PLG.'
                report['imported_meshes'] = source_mesh_names
                report['output_meshes'] = [m.name for m in meshes]
                report['source_armature'] = armature.name
                report['matched_vertex_groups'] = group_count
                report['mesh_to_armature_transforms'] = mesh_transforms
                report['source_meshes_joined'] = True
                report['source_mesh_components'] = len(source_mesh_names)
                report['output_geometry_count'] = topology['geometry_count']
                report['output_atomic_count'] = topology['atomic_count']
                report['output_material_slots'] = len(meshes[0].material_slots)
                report['dff_model_note'] = 'Uma única Geometry/Atomic para o ped; vários materiais são preservados como slots/submateriais da mesma mesh.'
                missing_textures = _missing_texture_refs(source)
                if missing_textures:
                    report['warnings'].append('Texturas referenciadas no DAE não estão junto do arquivo: ' + ', '.join(missing_textures))
                report['warnings'].append('O DFF contém a geometria e o esqueleto; TXD/texturas não são gerados. Forneça as imagens e monte um TXD à parte.')
                report['warnings'].append('Retarget many-to-one: dedos, twist, rosto e slots do rig Sims 4 são agrupados nos 32 ossos do ped SA; alguns canais independentes se perdem.')
                report['warnings'].append('A conversão foi validada estruturalmente pelo conversor; ainda teste o DFF no Blender e no GTA SA com animações de ped.')
                report_path = output.with_suffix('.relatorio.json')
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                s.last_output = str(output)
                s.last_report = _report_text(report, 'S4SA - Relatorio')
                s.status = f"Concluído: {len(report['mapping'])} ossos de origem -> 32 SA; {report['vertices']:,} vértices."
                self.report({'INFO'}, 'DFF SA e relatório gerados. Teste texturas e animações no jogo.')
            except Exception as exc:
                s.status = 'Conversão interrompida: ' + str(exc)
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}
            finally:
                _remove_imported(imported)
                _restore_selection(previous_selection, previous_active)

            if s.import_result:
                try:
                    _set_result_import_option(str(output))
                except Exception as exc:
                    self.report({'WARNING'}, 'DFF foi gerado; preview não importado: ' + str(exc))
            return {'FINISHED'}


    class S4SA_OT_ImportLast(bpy.types.Operator):
        bl_idname = 's4sa.import_last'
        bl_label = 'Importar último DFF'
        bl_description = 'Abre o último resultado com DragonFF'

        def execute(self, context):
            s = context.scene.s4sa_converter
            try:
                core.require(s.last_output and os.path.isfile(s.last_output), 'Último DFF não foi encontrado.')
                _set_result_import_option(s.last_output)
                return {'FINISHED'}
            except Exception as exc:
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}


    class S4SA_PT_Panel(bpy.types.Panel):
        bl_label = 'Sims 4 -> GTA San Andreas'
        bl_idname = 'S4SA_PT_converter'
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = 'Sims 4 -> SA'

        def draw(self, context):
            layout = self.layout
            s = context.scene.s4sa_converter
            box = layout.box()
            box.label(text='DAE Sims 4 -> DFF ped SA', icon='ARMATURE_DATA')
            box.label(text='Rig padrão adulto/CAS com pesos de skin.')
            box.label(text='O DAE original não é alterado.', icon='LOCKED')
            layout.prop(s, 'source_file')
            layout.prop(s, 'output_file')
            layout.prop(s, 'bake_pose')
            layout.prop(s, 'ground_offset')
            layout.label(text='Ajuste vertical recomendado (HFYSTB): -1.060', icon='INFO')
            layout.prop(s, 'import_result')
            layout.operator('s4sa.convert_dae', icon='FILE_REFRESH')
            if s.last_output:
                layout.prop(s, 'last_output')
                layout.operator('s4sa.import_last', icon='IMPORT')
            if s.last_report:
                layout.label(text='Relatório: ' + s.last_report, icon='TEXT')
            if s.status:
                for line in [s.status[i:i + 42] for i in range(0, len(s.status), 42)]:
                    layout.label(text=line)
            advanced = layout.box()
            advanced.label(text='Opções avançadas')
            advanced.prop(s, 'reference_file')
            advanced.prop(s, 'mapping_file')
            advanced.prop(s, 'overwrite_output')
            warning = layout.box()
            warning.label(text='DragonFF + importador DAE do Blender necessários.', icon='INFO')
            warning.label(text='Texturas/TXD não são convertidos.')
            warning.label(text='Sempre teste animações no GTA SA.', icon='ERROR')


    _CLASSES = (S4SA_Settings, S4SA_OT_Convert, S4SA_OT_ImportLast, S4SA_PT_Panel)
else:
    _CLASSES = ()


def register():
    if bpy is None:
        raise RuntimeError('Este addon deve ser instalado e executado dentro do Blender.')
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.s4sa_converter = bpy.props.PointerProperty(type=S4SA_Settings)


def unregister():
    if bpy is None:
        return
    if hasattr(bpy.types.Scene, 's4sa_converter'):
        del bpy.types.Scene.s4sa_converter
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__' and bpy is not None:
    register()
