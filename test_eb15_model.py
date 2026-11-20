# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Local EB-15 model: matching by SHA-256, local generation, adoption and variant switch."""
import hashlib, json, struct, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import eb15_model

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def cube_stl(size):
    tris = []
    s = size
    quads = [((0, 0, 0), (s, 0, 0), (s, s, 0), (0, s, 0)), ((0, 0, s), (0, s, s), (s, s, s), (s, 0, s))]
    for q in quads:
        tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    raw = b'test'.ljust(80, b' ') + struct.pack('<I', len(tris))
    for t in tris:
        raw += struct.pack('<12fH', 0, 0, 1, *t[0], *t[1], *t[2], 0)
    return raw


class EB15Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.parts = {'eb15/001': cube_stl(10), 'ebg30/001': cube_stl(20)}
        self.fake = dict(eb15_model.assembly())
        self.fake['sources'] = {k: hashlib.sha256(v).hexdigest() for k, v in self.parts.items()}
        identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        self.fake['parts'] = [dict(file='eb15/001', name='a', link='base', color='#7ee000', R=identity, t=[0, 0, 0]),
                              dict(file='ebg30/001', name='b', link='link5', color='#16191a', R=identity, t=[0, 0, 0])]

    def tearDown(self):
        self.tmp.cleanup()

    def test_sources_are_recognised_by_content_not_by_name(self):
        archive = self.folder / 'download.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('files/renamed-part.stl', self.parts['eb15/001'])
            z.writestr('files/other.stl', cube_stl(5))
        loose = self.folder / 'loose'
        loose.mkdir()
        (loose / 'x.STL').write_bytes(self.parts['ebg30/001'])
        with patch.object(eb15_model, 'assembly', return_value=self.fake):
            found = eb15_model.find_sources([archive, loose])
        self.assertEqual(found, self.parts)

    def test_missing_parts_are_reported(self):
        with patch.object(eb15_model, 'assembly', return_value=self.fake):
            if HAVE_NUMPY:
                with self.assertRaisesRegex(ValueError, 'ebg30/001'):
                    eb15_model.build({'eb15/001': self.parts['eb15/001']})

    @unittest.skipUnless(HAVE_NUMPY, 'numpy not installed')
    def test_install_writes_meshes_into_the_data_folder_only(self):
        source = self.folder / 'src'
        source.mkdir()
        for i, raw in enumerate(self.parts.values()):
            (source / ('%d.stl' % i)).write_bytes(raw)
        self.fake['expected_meshes'] = {'base_link_lime.stl': '0' * 64, 'link_5_nero.stl': '0' * 64}
        with patch.object(eb15_model, 'assembly', return_value=self.fake):
            report = eb15_model.install([source], self.folder / 'data')
            self.assertEqual(report['meshes'], 2)
            self.assertTrue(eb15_model.installed(self.folder / 'data'))
        self.assertFalse(any(Path(eb15_model.HERE / 'models/doc5').glob('*.tmp')))

    def test_adopt_copies_only_matching_earlier_meshes(self):
        data = self.folder / 'data'
        data.mkdir()
        good, bad = data / 'asset-good.stl', data / 'asset-bad.stl'
        good.write_bytes(b'mesh a')
        bad.write_bytes(b'changed')
        expected = {'one.stl': hashlib.sha256(b'mesh a').hexdigest(), 'two.stl': hashlib.sha256(b'mesh b').hexdigest()}
        model = dict(links=[dict(visuals=[dict(source_mesh='meshes/one.stl', mesh=str(good)),
                                          dict(source_mesh='meshes/two.stl', mesh=str(bad))])])
        with patch.object(eb15_model, 'assembly', return_value=dict(expected_meshes=expected)):
            self.assertFalse(eb15_model.adopt(model, data))
            bad.write_bytes(b'mesh b')
            self.assertTrue(eb15_model.adopt(model, data))
            self.assertTrue(eb15_model.installed(data))

    def test_switching_variant_keeps_calibration_and_collision_envelope(self):
        from studio import Studio
        controller = MagicMock(connected=False, busy=False, playing=False, firmware_busy=False, axes_enabled=[True] * 6)
        studio = Studio(self.folder, controller, builtin=True)
        self.assertEqual(studio.model['mesh_variant'], 'schematic')
        before = studio.geometry().bodies
        joint = studio.independent()[1]['name']
        studio.calibration[joint] = dict(sign=-1, offset=0.25)
        studio.save()
        meshes = eb15_model.target(studio.folder) / 'meshes'
        meshes.mkdir(parents=True)
        for name in eb15_model.assembly()['expected_meshes']:
            (meshes / name).write_bytes((eb15_model.HERE / 'models/doc5/meshes' / name).read_bytes())
        again = Studio(self.folder, controller, builtin=True)
        self.assertEqual(again.model['mesh_variant'], 'eb15')
        self.assertEqual(again.calibration[joint], dict(sign=-1, offset=0.25))
        self.assertEqual([(b['link'], b['r']) for b in again.geometry().bodies], [(b['link'], b['r']) for b in before])
        self.assertTrue(all(str(studio.folder.resolve()) in str(Path(v['mesh']).resolve()) for l in again.model['links'] for v in l['visuals'] if v['mesh']))


class ReferenceDataTests(unittest.TestCase):
    def test_repository_ships_no_toolbox_geometry(self):
        folder = eb15_model.HERE / 'models/doc5/meshes'
        expected = eb15_model.assembly()['expected_meshes']
        for path in folder.glob('*.stl'):
            self.assertTrue(path.read_bytes().startswith(b'Robot Console schematic'), path.name)
            self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected.get(path.name))
        self.assertEqual(sorted(p.name for p in folder.glob('*.stl')), sorted(expected))

    def test_schematic_meshes_match_their_specification(self):
        provenance = json.loads((eb15_model.HERE / 'models/doc5/provenance.json').read_text())['meshes']
        for name, digest in provenance.items():
            self.assertEqual(hashlib.sha256((eb15_model.HERE / 'models/doc5/meshes' / name).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
