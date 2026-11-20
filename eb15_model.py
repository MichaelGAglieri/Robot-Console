#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Build the detailed DOC model locally from the original ToolBox Robotics STL parts.

The EB-15 arm and EBG-30 gripper parts are licensed CC BY-NC-ND 4.0: the merged and
simplified meshes are an adaptation and must not be redistributed. This module never
downloads anything. The operator downloads the two Thingiverse packages, then this
module recognises the parts by SHA-256, places them with the GPL assembly data in
models/doc5/eb15_assembly.json and writes the display meshes into the user's own data
folder. The repository and the release packages only ship the schematic model.

Usage: python3 eb15_model.py EB-15.zip EBG-30.zip   (zip files or extracted folders)
Requires numpy (optional dependency, only for this import).
"""
import hashlib, json, os, struct, sys, tempfile, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSEMBLY = HERE / 'models/doc5/eb15_assembly.json'
MESH_HEADER = b'DOC 5 assi da STL ToolBox EB-15/EBG-30 (CC BY-NC-ND)'.ljust(80, b' ')
LINK_OF = {'base': 'base_link', 'link1': 'link_1', 'link2': 'link_2', 'link3': 'link_3', 'link4': 'link_4', 'link5': 'link_5',
           'finger1': 'lab_finger_1', 'finger2': 'lab_finger_2', 'finger3': 'lab_finger_3'}
MAX_STL = 64 * 1024 * 1024
NOTICE = """# DOC five-axis model, EB-15 parts (generated on this computer)

Generated locally by Robot Console from the original STL parts of the ToolBox
Robotics EB-15 arm (https://www.thingiverse.com/thing:6488872) and EBG-30 gripper
(https://www.thingiverse.com/thing:6460300), by ToolBoxRobotics, licensed
CC BY-NC-ND 4.0. Parts are placed with the D.O.C. assembly data, merged per link and
colour and simplified for display. This folder is for personal, non-commercial use on
this computer: do not share or publish these generated meshes.
"""


def assembly():
    return json.loads(ASSEMBLY.read_text())


def target(folder):
    return Path(folder) / 'models' / 'eb15'


def installed(folder):
    """Folder with a complete generated mesh set, or None. Checks names, not content."""
    out = target(folder)
    try:
        expected = assembly()['expected_meshes']
    except (OSError, ValueError, KeyError):
        return None
    return out if all((out / 'meshes' / name).is_file() for name in expected) else None


def _candidates(paths):
    """Yield (label, bytes) for every .stl inside the given zip files or folders."""
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            for item in sorted(path.rglob('*')):
                if item.suffix.lower() == '.stl' and item.is_file() and item.stat().st_size <= MAX_STL:
                    yield str(item), item.read_bytes()
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    name = info.filename
                    if name.lower().endswith('.stl') and not info.is_dir() and info.file_size <= MAX_STL:
                        yield path.name + ':' + name, archive.read(info)
                    elif name.lower().endswith('.zip') and info.file_size <= 4 * MAX_STL:
                        # Thingiverse packages sometimes nest the files archive.
                        with tempfile.TemporaryDirectory() as tmp:
                            inner = Path(tmp) / 'inner.zip'
                            inner.write_bytes(archive.read(info))
                            yield from _candidates([inner])
        elif path.suffix.lower() == '.stl' and path.is_file():
            yield str(path), path.read_bytes()
        else:
            raise ValueError('Not a zip file, folder or STL: ' + str(path))


def find_sources(paths):
    """Map assembly file ids (e.g. 'eb15/003') to STL bytes, matched by SHA-256 only."""
    wanted = {digest: key for key, digest in assembly()['sources'].items()}
    found = {}
    for _label, data in _candidates(paths):
        key = wanted.get(hashlib.sha256(data).hexdigest())
        if key:
            found[key] = data
    return found


def _load(np, raw):
    if raw[:5] == b'solid' and b'facet' in raw[:400]:
        values = [list(map(float, line.split()[1:])) for line in raw.decode(errors='ignore').splitlines()
                  if line.strip().startswith('vertex')]
        return np.array(values, dtype=np.float64).reshape(-1, 3, 3)
    count = int.from_bytes(raw[80:84], 'little')
    record = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
    return np.frombuffer(raw, dtype=record, offset=84, count=count)['v'].astype(np.float64).reshape(-1, 3, 3)


def _decimate(np, tris, grid):
    """Vertex clustering on a regular grid (metres), as used for the display meshes."""
    v = tris.reshape(-1, 3)
    q = np.round(v / grid).astype(np.int64)
    key, inv = np.unique(q, axis=0, return_inverse=True)
    inv = inv.reshape(-1, 3)
    pos = np.zeros((len(key), 3))
    np.add.at(pos, inv.reshape(-1), v)
    pos /= np.bincount(inv.reshape(-1), minlength=len(key))[:, None]
    inv = inv[(inv[:, 0] != inv[:, 1]) & (inv[:, 1] != inv[:, 2]) & (inv[:, 0] != inv[:, 2])]
    _, first = np.unique(np.sort(inv, axis=1), axis=0, return_index=True)
    return pos[inv[np.sort(first)]]


def _stl_bytes(np, tris):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(n, axis=1)
    length[length == 0] = 1
    n /= length[:, None]
    record = np.zeros(len(tris), dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))
    record['n'] = n
    record['v'] = tris
    return MESH_HEADER + struct.pack('<I', len(tris)) + record.tobytes()


def build(sources):
    """Return {mesh file name: STL bytes} from the matched source parts."""
    try:
        import numpy as np
    except ImportError as error:
        raise ValueError('The EB-15 import needs numpy: python3 -m pip install numpy') from error
    data = assembly()
    missing = sorted(set(data['sources']) - set(sources))
    if missing:
        raise ValueError('Missing original STL parts: ' + ', '.join(missing))
    origin = {'base_link': np.zeros(3)}
    for i in range(1, 6):
        origin['link_%d' % i] = np.array(data['joints']['J%d' % i]['origin'], float)
    for k in (1, 2, 3):
        origin['lab_finger_%d' % k] = origin['link_5']
    groups = {}
    cache = {}
    for part in data['parts']:
        if part['file'] not in cache:
            cache[part['file']] = _load(np, sources[part['file']]).reshape(-1, 3)
        world = cache[part['file']] @ np.array(part['R']).T + np.array(part['t'])
        link = LINK_OF[part['link']]
        groups.setdefault((link, part['color']), []).append(((world - origin[link]) / 1000.0).reshape(-1, 3, 3))
    meshes = {}
    for (link, color), chunks in sorted(groups.items()):
        name = '%s_%s.stl' % (link, data['color_names'][color])
        tris = _decimate(np, np.concatenate(chunks), data['grid_m'])
        # Pads and lime parts share one file: append, as the reference generator does.
        # The first set goes through the float32 STL record before appending, like the reference build.
        meshes[name] = np.concatenate([meshes[name].astype(np.float32).astype(np.float64), tris]) if name in meshes else tris
    return {name: _stl_bytes(np, tris) for name, tris in meshes.items()}


def install(paths, folder):
    """Generate the detailed model into <folder>/models/eb15. Returns a short report."""
    sources = find_sources(paths)
    meshes = build(sources)
    expected = assembly()['expected_meshes']
    if set(meshes) != set(expected):
        raise ValueError('Generated mesh set does not match the DOC URDF.')
    out = target(folder)
    staging = out.with_name('eb15.tmp')
    if staging.exists():
        for item in sorted(staging.rglob('*'), reverse=True):
            item.unlink() if item.is_file() else item.rmdir()
    (staging / 'meshes').mkdir(parents=True)
    hashes = {}
    for name, raw in meshes.items():
        (staging / 'meshes' / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    identical = sum(hashes[name] == expected[name] for name in expected)
    (staging / 'NOTICE.md').write_text(NOTICE)
    (staging / 'provenance.json').write_text(json.dumps(dict(generator='eb15_model.py', meshes=hashes,
                                                             identical_to_reference=identical), indent=1) + '\n')
    if out.exists():
        old = out.with_name('eb15.old')
        if old.exists():
            for item in sorted(old.rglob('*'), reverse=True):
                item.unlink() if item.is_file() else item.rmdir()
        os.replace(out, old)
    os.replace(staging, out)
    return dict(folder=str(out), meshes=len(hashes), identical=identical, total=len(expected))


def adopt(model, folder):
    """Reuse EB-15 meshes already present in the user's own data (earlier local builds bundled
    them). Copies only files whose SHA-256 matches the reference build; never downloads."""
    if installed(folder):
        return True
    expected = assembly()['expected_meshes']
    found = {}
    for link in model.get('links', []):
        for visual in link.get('visuals', []):
            name = Path(visual.get('source_mesh', '')).name
            mesh = Path(visual.get('mesh') or '')
            if name in expected and name not in found and mesh.is_file() and mesh.resolve().is_relative_to(Path(folder).resolve()):
                raw = mesh.read_bytes()
                if hashlib.sha256(raw).hexdigest() == expected[name]:
                    found[name] = raw
    if set(found) != set(expected):
        return False
    out = target(folder)
    staging = out.with_name('eb15.tmp')
    (staging / 'meshes').mkdir(parents=True, exist_ok=True)
    for name, raw in found.items():
        (staging / 'meshes' / name).write_bytes(raw)
    (staging / 'NOTICE.md').write_text(NOTICE)
    (staging / 'provenance.json').write_text(json.dumps(dict(generator='adopted from an earlier local build',
                                                             meshes={n: expected[n] for n in found}), indent=1) + '\n')
    os.replace(staging, out)
    return True


def default_data_folder():
    from platform_support import data_folder
    return data_folder()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__.strip())
        raise SystemExit(2)
    try:
        # Robot Console keeps Studio data, including models, in <data folder>/studio.
        report = install(sys.argv[1:], Path(os.environ.get('DOC_REGIA_DATA') or default_data_folder()) / 'studio')
    except ValueError as error:
        print('Error:', error)
        raise SystemExit(1)
    print('Detailed DOC model installed in', report['folder'])
    print('%(identical)d of %(total)d meshes identical to the reference build.' % report)
