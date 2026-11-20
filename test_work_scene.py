# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Frame composition, migrations and scene edits, without serial or real motion."""
import copy
import json
import math
import zipfile
from unittest.mock import Mock, patch
from test_studio import StudioFixture, SIMPLE
from studio import Studio
from work_scene import validate_scene, scene_state


def work_frame(**changes):
    return dict(dict(id='table', name='Piano', parent='base', xyz=[.1, .2, 0.], rpy=[0., 0., math.pi / 2]), **changes)


def target(**changes):
    return dict(dict(id='point', name='Presa', frame_id='table', xyz=[.05, 0., 0.], rpy=[math.pi / 2, 0., 0.]), **changes)


class WorkSceneTests(StudioFixture):
    def install_scene(self):
        self.s.save_scene([work_frame()], [target()], 'point')

    def test_composition_rotates_local_offset_and_tool_axes(self):
        work, targets = scene_state(*validate_scene([work_frame()], [target()]))
        self.assertEqual(work[0]['id'], 'base')
        for actual, expected in zip(targets[0]['xyz_base'], [.1, .25, 0.]):
            self.assertAlmostEqual(actual, expected, places=12)
        # Local roll 90 then reference yaw 90: local z becomes base +x.
        matrix = targets[0]['matrix']
        for actual, expected in zip([matrix[2], matrix[6], matrix[10]], [1., 0., 0.]):
            self.assertAlmostEqual(actual, expected, places=12)
        _, direct = scene_state([], [target(frame_id='base')])
        self.assertEqual(direct[0]['xyz_base'], [.05, 0., 0.])

    def test_pitch_and_roll_reference_transform_all_three_coordinates(self):
        _, values = scene_state([work_frame(xyz=[1., 2., 3.], rpy=[math.pi / 2, math.pi / 2, 0.])],
                                [target(xyz=[.1, .2, .3], rpy=[0., 0., 0.])])
        for actual, expected in zip(values[0]['xyz_base'], [1.2, 1.7, 2.9]):
            self.assertAlmostEqual(actual, expected, places=12)

    def test_moving_reference_preserves_local_targets_and_controller(self):
        self.install_scene(); before = copy.deepcopy(self.s.cartesian_targets)
        self.c.pos[0] = 12.; self.c.home = True; self.c.spawn = Mock()
        self.s.action(dict(op='studio_frame_save', id='table', name='Piano', xyz=[.3, .4, .1], rpy=[0., 0., 0.]))
        self.assertEqual(self.s.cartesian_targets, before)
        self.assertEqual(self.s.state()['cartesian_targets'][0]['xyz_base'], [.35, .4, .1])
        self.assertEqual(self.c.pos[0], 12.); self.assertTrue(self.c.home)
        self.c.write.assert_not_called(); self.c.spawn.assert_not_called()

    def test_crud_stable_ids_selection_and_reference_in_use(self):
        self.s.action(dict(op='studio_frame_save', name='Piano', xyz=[.1, 0, 0], rpy=[0, 0, 0]))
        key = self.s.work_frames[0]['id']
        self.s.action(dict(op='studio_target_save', name='Presa', frame_id=key, xyz=[.2, 0, 0], rpy=[0, 0, 0]))
        point = self.s.cartesian_targets[0]['id']
        with self.assertRaisesRegex(ValueError, 'contiene target'):
            self.s.action(dict(op='studio_frame_delete', id=key))
        self.s.action(dict(op='studio_target_save', id=point, name='Presa nuova', frame_id='base', xyz=[.2, 0, 0], rpy=[0, 0, 0]))
        self.s.action(dict(op='studio_frame_delete', id=key))
        self.assertEqual(self.s.cartesian_targets[0]['id'], point)
        self.s.action(dict(op='studio_target_select', id='')); self.assertEqual(self.s.selected_target, '')
        self.s.action(dict(op='studio_target_select', id=point)); self.assertEqual(self.s.selected_target, point)
        self.s.action(dict(op='studio_target_delete', id=point)); self.assertEqual(self.s.selected_target, '')
        self.c.write.assert_not_called()

    def test_reject_invalid_scene_atomically(self):
        self.install_scene(); before = self.s.data(); saved = (self.s.folder / 'project.json').read_bytes()
        invalid = [([work_frame(parent='point')], [target()]),
                   ([work_frame(id='base')], []),
                   ([work_frame(name=' ')], []),
                   ([work_frame(), work_frame(id='other', name='pIANO')], []),
                   ([work_frame(xyz=[True, 0, 0])], []),
                   ([work_frame(rpy=[0, 0, float('nan')])], []),
                   ([work_frame(xyz=[0, 0])], []),
                   ([work_frame()], [target(frame_id='missing')]),
                   ([work_frame()], [target(id='table')]),
                   ([work_frame()], [target(), target()]),
                   ([work_frame()] * 33, []),
                   ([], [target(frame_id='base')] * 257)]
        for work, points in invalid:
            with self.assertRaises((ValueError, TypeError)): self.s.save_scene(work, points, '')
            self.assertEqual(self.s.data(), before)
            self.assertEqual((self.s.folder / 'project.json').read_bytes(), saved)
        self.c.write.assert_not_called()

    def test_connected_and_busy_edits_are_rejected_without_motion(self):
        self.install_scene(); before = self.s.data()
        for field in ('busy', 'playing', 'firmware_busy'):
            setattr(self.c, field, True)
            with self.assertRaises(ValueError): self.s.action(dict(op='studio_target_delete', id='point'))
            setattr(self.c, field, False)
        self.assertEqual(self.s.data(), before); self.c.write.assert_not_called()
        self.c.connected=True;self.c.home=True;self.s.action(dict(op='studio_target_delete',id='point'));self.assertTrue(self.c.home);self.c.write.assert_not_called()

    def test_io_failure_rolls_back_scene_in_memory(self):
        self.install_scene(); before = self.s.data()
        with patch.object(self.s, 'save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.s.action(dict(op='studio_target_delete', id='point'))
        self.assertEqual(self.s.data(), before)

    def test_old_project_migration_backups_original_once_and_preserves_values(self):
        self.s.preview['joint_1'] = .3; self.s.tool = [.01, .02, .03]
        old = self.s.data(); old['schema'] = 1
        for key in ('work_frames', 'cartesian_targets', 'selected_target'): old.pop(key)
        path = self.s.folder / 'project.json'; raw = json.dumps(old).encode(); path.write_bytes(raw)
        migrated = Studio(self.folder, self.c, builtin=False)
        self.assertEqual(migrated.preview, old['preview']); self.assertEqual(migrated.tool, old['tool'])
        self.assertEqual(migrated.mapping, old['mapping']); self.assertEqual(migrated.calibration, old['calibration'])
        self.assertEqual(migrated.work_frames, []); self.assertEqual(migrated.cartesian_targets, [])
        backups = list(self.s.folder.glob('project-prima-schema2-*.json'))
        self.assertEqual(len(backups), 1); self.assertEqual(backups[0].read_bytes(), raw)
        self.assertEqual(json.loads(path.read_text())['schema'], 2)
        Studio(self.folder, self.c, builtin=False)
        self.assertEqual(len(list(self.s.folder.glob('project-prima-schema2-*.json'))), 1)
        self.c.write.assert_not_called()

    def test_portable_roundtrip_derives_matrices_not_imported_cached_values(self):
        self.install_scene(); self.s.verified = True
        archive = self.folder / 'scene.zip'; self.s.export_project(archive)
        self.s.work_frames = []; self.s.cartesian_targets = []; self.s.selected_target = ''
        self.s.import_project(archive)
        self.assertFalse(self.s.verified); self.assertEqual(self.s.selected_target, 'point')
        data = self.s.data(); data['cartesian_targets'][0]['matrix'] = [99] * 16
        data['cartesian_targets'][0]['xyz_base'] = [99] * 3
        self.s.load_data(data)
        self.assertAlmostEqual(self.s.state()['cartesian_targets'][0]['xyz_base'][1], .25)
        self.assertNotIn('matrix', self.s.cartesian_targets[0]); self.c.write.assert_not_called()

    def test_legacy_zip_import_keeps_original_and_current_joint_sequence(self):
        data = self.s.data(); data['schema'] = 1
        for key in ('work_frames', 'cartesian_targets', 'selected_target'): data.pop(key)
        archive = self.folder / 'legacy.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('project.json', json.dumps(data))
            zipped.writestr('robot.urdf', data['urdf'])
        original = archive.read_bytes()
        self.c.sequence = [dict(name='existing pose', pos=[0.] * 6, path=[], dwell=0, grip='apri')]
        self.install_scene(); self.s.import_project(archive)
        self.assertEqual(archive.read_bytes(), original)
        self.assertEqual(json.loads((self.s.folder / 'project.json').read_text())['schema'], 2)
        self.assertEqual(self.s.work_frames, []); self.assertEqual(self.c.sequence[0]['name'], 'existing pose')
        self.c.write.assert_not_called()

    def test_bad_project_rolls_back_every_scene_field(self):
        self.install_scene(); before = self.s.data()
        for change in ({'selected_target': 'missing'}, {'work_frames': None}, {'schema': 3},
                       {'cartesian_targets': [target(frame_id='missing')]}):
            with self.assertRaises(ValueError): self.s.load_data(dict(before, **change))
            self.assertEqual(self.s.data(), before)

    def test_new_urdf_clears_base_dependent_scene(self):
        self.install_scene(); path = self.folder / 'other.urdf'; path.write_bytes(SIMPLE)
        self.s.import_urdf(path)
        self.assertEqual(self.s.work_frames, []); self.assertEqual(self.s.cartesian_targets, [])
        self.assertEqual(self.s.selected_target, ''); self.c.write.assert_not_called()

    def test_bundled_model_upgrade_preserves_work_frames_and_targets(self):
        reference = Studio(self.folder, self.c, builtin=True)
        reference.save_scene([work_frame()], [target()], 'point')
        reference.raw = reference.raw.replace('<robot name="', '<robot name="vecchio '); reference.save()
        upgraded = Studio(self.folder, self.c, builtin=True)
        self.assertEqual(upgraded.work_frames, [work_frame()]); self.assertEqual(upgraded.cartesian_targets, [target()])
        self.assertEqual(upgraded.selected_target, 'point'); self.c.write.assert_not_called()

    def test_saved_reference_restores_meshes_without_false_missing_warnings(self):
        reference = Studio(self.folder, self.c, builtin=True)
        reference.save_scene([work_frame()], [target()], 'point')
        loaded = Studio(self.folder, self.c, builtin=True)
        self.assertEqual(loaded.model['warnings'], [])
        expected = copy.deepcopy(reference.model['links'])
        for link in expected:
            for visual in link['visuals']:
                if visual['mesh']: visual['mesh'] = str(self.s.folder.joinpath(visual['mesh']).resolve())
        self.assertEqual(loaded.model['links'], expected)
        archive = self.folder / 'reference-scene.zip'; loaded.export_project(archive)
        loaded.import_project(archive); self.assertEqual(loaded.model['warnings'], [])
        self.c.write.assert_not_called()

    def test_unrestored_missing_mesh_warning_is_retained(self):
        reference = Studio(self.folder, self.c, builtin=True)
        data = copy.deepcopy(reference.data())
        next(v for link in data['model']['links'] for v in link['visuals'] if v['kind'] == 'mesh')['mesh'] = ''
        reference.load_data(data)
        self.assertTrue(any('Mesh non disponibile' in w for w in reference.model['warnings']))
        self.c.write.assert_not_called()
