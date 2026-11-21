# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""3D arm view with Qt Quick 3D (Metal on macOS, Direct3D on Windows, Vulkan/OpenGL on Linux).

The controller sends link frames as row-major 4x4 matrices in metres (URDF, Z up).
The scene works in millimetres inside a node rotated so that Z points up on screen.
Nothing here commands the robot.
"""
import math, os, struct
from pathlib import Path
import numpy as np
from PySide6.QtCore import QByteArray, QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QMatrix3x3, QQuaternion, QVector3D
from PySide6.QtQml import QmlElement
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuick3D import QQuick3DGeometry
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget
from . import theme

QML_IMPORT_NAME = 'RobotConsole'
QML_IMPORT_MAJOR_VERSION = 1
MM = 1000.0
_MESHES = {}  # key -> (vertex bytes, count, primitive, lo, hi)


# --- geometry sources -----------------------------------------------------------------
def _store(key, triangles, primitive='triangles'):
    data = np.asarray(triangles, dtype=np.float32)
    if primitive == 'triangles':
        tris = data.reshape(-1, 3, 3)
        normal = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        length = np.linalg.norm(normal, axis=1)
        keep = length > 1e-12
        tris, normal = tris[keep], normal[keep] / length[keep, None]
        vertices = np.concatenate([tris, np.repeat(normal[:, None, :], 3, axis=1)], axis=2).reshape(-1, 6)
        points = tris.reshape(-1, 3)
    else:
        points = data.reshape(-1, 3)
        vertices = np.concatenate([points, np.zeros_like(points)], axis=1)
    if not len(points):
        points = np.zeros((1, 3), np.float32)
    _MESHES[key] = (vertices.astype(np.float32).tobytes(), len(vertices), primitive,
                    points.min(0).tolist(), points.max(0).tolist())
    return key


def load_mesh(path):
    """STL (binary or ASCII) or OBJ in millimetres; None when unreadable."""
    key = 'file:' + str(path)
    if key in _MESHES:
        return key
    try:
        raw = Path(path).read_bytes()
        suffix = Path(path).suffix.lower()
        if suffix == '.obj':
            vertices, faces = [], []
            for row in raw.decode(errors='replace').splitlines():
                parts = row.split()
                if not parts:
                    continue
                if parts[0] == 'v':
                    vertices.append([float(v) for v in parts[1:4]])
                elif parts[0] == 'f':
                    idx = [int(p.split('/')[0]) for p in parts[1:]]
                    idx = [i - 1 if i > 0 else len(vertices) + i for i in idx]
                    faces += [(idx[0], idx[k], idx[k + 1]) for k in range(1, len(idx) - 1)]
            tris = np.array(vertices, np.float64)[np.array(faces, int)] if faces else np.zeros((0, 3, 3))
        elif suffix == '.stl':
            count = struct.unpack('<I', raw[80:84])[0] if len(raw) >= 84 else 0
            if len(raw) == 84 + 50 * count:
                record = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
                tris = np.frombuffer(raw, dtype=record, offset=84, count=count)['v'].astype(np.float64)
            else:
                values = [list(map(float, l.split()[1:4])) for l in raw.decode(errors='replace').splitlines() if l.strip().startswith('vertex')]
                tris = np.array(values, np.float64).reshape(-1, 3, 3)
        else:
            return None
    except (OSError, ValueError, IndexError, struct.error):
        return None
    if not len(tris):
        return None
    return _store(key, tris * MM)


def box_mesh(size):
    key = 'box:%g,%g,%g' % tuple(size)
    if key not in _MESHES:
        x, y, z = (s * MM / 2 for s in size)
        c = [(sx * x, sy * y, sz * z) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
        tris = []
        for a, b, cc, d in faces:
            tris += [(c[a], c[b], c[cc]), (c[a], c[cc], c[d])]
        _store(key, tris)
    return key


def cylinder_mesh(radius, length, segments=36):
    key = 'cyl:%g,%g' % (radius, length)
    if key not in _MESHES:
        r, h = radius * MM, length * MM / 2
        ring = [(r * math.cos(2 * math.pi * k / segments), r * math.sin(2 * math.pi * k / segments)) for k in range(segments)]
        tris = []
        for k in range(segments):
            (x0, y0), (x1, y1) = ring[k], ring[(k + 1) % segments]
            tris += [((x0, y0, -h), (x1, y1, -h), (x1, y1, h)), ((x0, y0, -h), (x1, y1, h), (x0, y0, h)),
                     ((0, 0, h), (x0, y0, h), (x1, y1, h)), ((0, 0, -h), (x1, y1, -h), (x0, y0, -h))]
        _store(key, tris)
    return key


def sphere_mesh(radius, rings=14, segments=24):
    key = 'sph:%g' % radius
    if key not in _MESHES:
        r = radius * MM
        p = lambda i, k: (r * math.sin(math.pi * i / rings) * math.cos(2 * math.pi * k / segments),
                          r * math.sin(math.pi * i / rings) * math.sin(2 * math.pi * k / segments), r * math.cos(math.pi * i / rings))
        tris = []
        for i in range(rings):
            for k in range(segments):
                a, b, c, d = p(i, k), p(i, k + 1), p(i + 1, k + 1), p(i + 1, k)
                tris += [(a, d, c), (a, c, b)]
        _store(key, tris)
    return key


_versions = {}


def fresh_line_mesh(name, segments_mm):
    """Line mesh whose content changes: a new cache key each time, the old one released."""
    version = _versions.get(name, 0) + 1
    _MESHES.pop('%s#%d' % (name, version - 1), None)
    _versions[name] = version
    return line_mesh('%s#%d' % (name, version), segments_mm)


def line_mesh(key, segments_mm):
    """segments_mm: flat list of points, two per segment."""
    return _store(key, np.asarray(segments_mm, np.float32).reshape(-1, 3), 'lines')


@QmlElement
class MeshGeometry(QQuick3DGeometry):
    """QML geometry fed from the Python mesh cache by key."""
    sourceChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = ''

    def _get(self):
        return self._source

    def _set(self, key):
        if key == self._source:
            return
        self._source = key
        self.clear()
        entry = _MESHES.get(key)
        if entry:
            data, count, primitive, lo, hi = entry
            self.setStride(24)
            self.setVertexData(QByteArray(data))
            self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Lines if primitive == 'lines' else QQuick3DGeometry.PrimitiveType.Triangles)
            self.addAttribute(QQuick3DGeometry.Attribute.PositionSemantic, 0, QQuick3DGeometry.Attribute.F32Type)
            self.addAttribute(QQuick3DGeometry.Attribute.NormalSemantic, 12, QQuick3DGeometry.Attribute.F32Type)
            self.setBounds(QVector3D(*lo), QVector3D(*hi))
        self.update()
        self.sourceChanged.emit()

    source = Property(str, _get, _set, notify=sourceChanged)


# --- scene items ------------------------------------------------------------------------
class Part(QObject):
    changed = Signal()

    def __init__(self, mesh, color, unlit=False, opacity=1.0, local=None, scale=(1, 1, 1), link=''):
        super().__init__()
        self._mesh, self._color, self._unlit, self._opacity = mesh, QColor(color), unlit, opacity
        self._position, self._rotation, self._scale, self._visible = QVector3D(), QQuaternion(), QVector3D(*scale), True
        self.local = local if local is not None else np.eye(4)
        self.link = link

    def place(self, matrix):
        """matrix: 4x4 numpy, metres, robot frame."""
        m = matrix @ self.local
        position = QVector3D(*(m[:3, 3] * MM))
        rotation = QQuaternion.fromRotationMatrix(QMatrix3x3([float(v) for v in m[:3, :3].reshape(-1)]))
        if position != self._position or rotation != self._rotation:
            self._position, self._rotation = position, rotation
            self.changed.emit()

    def set_mesh(self, mesh):
        if mesh != self._mesh:
            self._mesh = mesh
            self.changed.emit()

    def set_visible(self, value):
        if value != self._visible:
            self._visible = value
            self.changed.emit()

    def set_color(self, value, opacity=None):
        value = QColor(value)
        if value != self._color or (opacity is not None and opacity != self._opacity):
            self._color = value
            if opacity is not None:
                self._opacity = opacity
            self.changed.emit()

    mesh = Property(str, lambda self: self._mesh, notify=changed)
    color = Property(QColor, lambda self: self._color, notify=changed)
    unlit = Property(bool, lambda self: self._unlit, notify=changed)
    opacity = Property(float, lambda self: self._opacity, notify=changed)
    position = Property(QVector3D, lambda self: self._position, notify=changed)
    rotation = Property(QQuaternion, lambda self: self._rotation, notify=changed)
    scale = Property(QVector3D, lambda self: self._scale, notify=changed)
    visible = Property(bool, lambda self: self._visible, notify=changed)


def matrix16(values):
    return np.array(values, float).reshape(4, 4)


def visual_local(visual):
    xyz, (r, p, y) = visual.get('xyz', [0, 0, 0]), visual.get('rpy', [0, 0, 0])
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    m = np.eye(4)
    m[:3, :3] = [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr], [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr], [-sp, cp * sr, cp * cr]]
    m[:3, 3] = xyz
    return m


def display_color(rgba):
    """Very dark materials are lifted slightly so shapes stay readable, as on macOS."""
    r, g, b = rgba[:3]
    if max(r, g, b) < .2:
        r, g, b = .25, .28, .24
    return QColor.fromRgbF(min(1, r), min(1, g), min(1, b), 1)


class Scene(QObject):
    partsChanged = Signal()
    overlaysChanged = Signal()
    cameraChanged = Signal()
    backgroundChanged = Signal()

    def __init__(self):
        super().__init__()
        self._parts = []
        self._overlay = []
        self.link_parts = {}
        self.ghost_parts = {}
        self.key = None
        self._yaw, self._pitch, self._distance, self._target, self._fov = 45.0, 24.7, 1200.0, QVector3D(0, 0, 300), 45.0
        self._background = QColor('#0E1114')
        self.user_adjusted = False
        self.bounds = None
        self.tcp_trail = []
        self.marker = None
        self.overlay_parts = {}

    # QML-facing properties
    parts = Property('QVariantList', lambda self: self._parts, notify=partsChanged)
    overlays = Property('QVariantList', lambda self: self._overlay, notify=overlaysChanged)
    yaw = Property(float, lambda self: self._yaw, notify=cameraChanged)
    pitch = Property(float, lambda self: self._pitch, notify=cameraChanged)
    distance = Property(float, lambda self: self._distance, notify=cameraChanged)
    target = Property(QVector3D, lambda self: self._target, notify=cameraChanged)
    fov = Property(float, lambda self: self._fov, notify=cameraChanged)
    background = Property(QColor, lambda self: self._background, notify=backgroundChanged)
    # Light levels matched by eye to the macOS SceneKit view (ambient 180, omni 450).
    lamp = Property(float, lambda self: float(os.environ.get('ROBOT_CONSOLE_LAMP', 0.85)), constant=True)
    ambient = Property(float, lambda self: float(os.environ.get('ROBOT_CONSOLE_AMBIENT', 0.3)), constant=True)

    @Slot(float, float)
    def orbit(self, dx, dy):
        self._yaw -= dx * .4
        self._pitch = max(-89.0, min(89.0, self._pitch + dy * .4))
        self.user_adjusted = True
        self.cameraChanged.emit()

    @Slot(float, float)
    def pan(self, dx, dy):
        yaw, pitch = math.radians(self._yaw), math.radians(self._pitch)
        right = np.array([math.cos(yaw), -math.sin(yaw), 0.0])
        up = np.array([math.sin(yaw) * math.sin(pitch), math.cos(yaw) * math.sin(pitch), math.cos(pitch)])
        scale = self._distance * .0016
        t = np.array([self._target.x(), self._target.y(), self._target.z()]) - right * dx * scale + up * dy * scale
        self._target = QVector3D(*t)
        self.user_adjusted = True
        self.cameraChanged.emit()

    @Slot(float)
    def zoom(self, steps):
        self._distance = max(60.0, min(20000.0, self._distance * (0.9 ** steps)))
        self.user_adjusted = True
        self.cameraChanged.emit()

    def set_background(self, color):
        color = QColor(color)
        if color != self._background:
            self._background = color
            self.backgroundChanged.emit()

    # Scene content
    def rebuild(self, studio):
        model = studio['model']
        parts, links, ghosts = [], {}, {}
        for link in model['links']:
            for visual in link.get('visuals', []):
                kind, size = visual.get('kind'), visual.get('size', [1, 1, 1])
                mesh = None
                scale = (1, 1, 1)
                if kind == 'mesh' and visual.get('mesh'):
                    mesh = load_mesh(visual['mesh'])
                    scale = tuple(size)
                elif kind == 'box':
                    mesh = box_mesh(size)
                elif kind == 'cylinder':
                    mesh = cylinder_mesh(size[0], size[1])
                elif kind == 'sphere':
                    mesh = sphere_mesh(size[0])
                if mesh is None:
                    mesh = box_mesh([.04, .04, .04])
                color = display_color(visual.get('color', [.66, 1, .16, 1]))
                part = Part(mesh, color, local=visual_local(visual), scale=scale, link=link['name'])
                ghost = Part(mesh, QColor(150, 150, 160), opacity=.22, local=visual_local(visual), scale=scale, link=link['name'])
                ghost.set_visible(False)
                links.setdefault(link['name'], []).append(part)
                ghosts.setdefault(link['name'], []).append(ghost)
                parts += [part, ghost]
        self.link_parts, self.ghost_parts = links, ghosts
        self._parts = parts
        self.tcp_trail = []
        self.partsChanged.emit()

    def set_overlay(self, name, mesh, color, unlit=True, opacity=1.0, matrix=None, visible=True):
        """Lines, markers and obstacles drawn above the arm; created once, then updated."""
        part = self.overlay_parts.get(name)
        if part is None:
            part = Part(mesh, color, unlit=unlit, opacity=opacity)
            self.overlay_parts[name] = part
            self._overlay = list(self.overlay_parts.values())
            self.overlaysChanged.emit()
        part.set_mesh(mesh)
        part.set_color(color, opacity)
        part.place(matrix if matrix is not None else np.eye(4))
        part.set_visible(visible)

    def drop_overlays(self, prefix):
        names = [n for n in self.overlay_parts if n.startswith(prefix)]
        if names:
            for n in names:
                del self.overlay_parts[n]
            self._overlay = list(self.overlay_parts.values())
            self.overlaysChanged.emit()

    def fit(self, points_m, preset, width, height):
        pts = np.array(points_m, float) if len(points_m) else np.array([[-.2, -.2, 0], [.2, .2, .7]])
        lo, hi = pts.min(0), pts.max(0)
        center = (lo + hi) / 2
        radius = max(.15, float(np.linalg.norm(hi - lo)) / 2)
        aspect = max(.35, width / max(1, height))
        distance = radius / max(.1, math.sin(math.pi / 8) * min(1, aspect)) * 1.15
        # Same directions as the macOS app: 3D (1, -1, 0.65), front (0, -1, 0.04), side (1, 0, 0.04), top.
        self._yaw, self._pitch = {'front': (0.0, 2.3), 'side': (90.0, 2.3), 'top': (0.0, 89.9)}.get(preset, (45.0, 24.7))
        self._target = QVector3D(*(center * MM))
        self._distance = distance * MM
        self.user_adjusted = False
        self.cameraChanged.emit()


QML = r'''
import QtQuick
import QtQuick3D
import RobotConsole

Item {
    id: root
    View3D {
        id: view
        anchors.fill: parent
        environment: SceneEnvironment {
            clearColor: scene.background
            backgroundMode: SceneEnvironment.Color
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }
        Node {
            // Robot frame (Z up) -> Qt Quick 3D frame (Y up).
            eulerRotation.x: -90
            Node {
                id: pivot
                position: scene.target
                eulerRotation.z: scene.yaw
                Node {
                    eulerRotation.x: 90 - scene.pitch
                    PerspectiveCamera {
                        id: camera
                        position: Qt.vector3d(0, 0, scene.distance)
                        fieldOfView: scene.fov
                        clipNear: 5
                        clipFar: 60000
                    }
                }
            }
            // Same light rig as the macOS app (SceneKit): soft ambient plus one lamp at (1, -1, 2) m,
            // without distance falloff, on matte (Lambert) materials.
            PointLight {
                position: Qt.vector3d(1000, -1000, 2000)
                brightness: scene.lamp
                constantFade: 1; linearFade: 0; quadraticFade: 0
                ambientColor: Qt.rgba(scene.ambient, scene.ambient, scene.ambient, 1)
            }
            Repeater3D {
                model: scene.parts
                delegate: Model {
                    required property var modelData
                    geometry: MeshGeometry { source: modelData.mesh }
                    position: modelData.position
                    rotation: modelData.rotation
                    scale: modelData.scale
                    visible: modelData.visible
                    materials: DefaultMaterial {
                        diffuseColor: modelData.color
                        specularAmount: 0
                        opacity: modelData.opacity
                        lighting: modelData.unlit ? DefaultMaterial.NoLighting : DefaultMaterial.FragmentLighting
                        cullMode: Material.NoCulling
                    }
                }
            }
            Repeater3D {
                model: scene.overlays
                delegate: Model {
                    required property var modelData
                    geometry: MeshGeometry { source: modelData.mesh }
                    position: modelData.position
                    rotation: modelData.rotation
                    scale: modelData.scale
                    visible: modelData.visible
                    materials: DefaultMaterial {
                        diffuseColor: modelData.color
                        specularAmount: 0
                        opacity: modelData.opacity
                        lighting: modelData.unlit ? DefaultMaterial.NoLighting : DefaultMaterial.FragmentLighting
                        cullMode: Material.NoCulling
                    }
                }
            }
        }
        camera: camera
    }
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        property real lastX: 0
        property real lastY: 0
        onPressed: (m) => { lastX = m.x; lastY = m.y }
        onPositionChanged: (m) => {
            var dx = m.x - lastX, dy = m.y - lastY
            lastX = m.x; lastY = m.y
            if ((m.buttons & Qt.LeftButton) && !(m.modifiers & Qt.ShiftModifier)) scene.orbit(dx, dy)
            else scene.pan(dx, dy)
        }
        onWheel: (w) => {
            if (w.pixelDelta.y !== 0 && (w.modifiers & Qt.ShiftModifier)) scene.pan(w.pixelDelta.x, w.pixelDelta.y)
            else if (w.pixelDelta.y !== 0 && !(w.modifiers & Qt.ControlModifier) && Math.abs(w.pixelDelta.x) > 0) scene.orbit(-w.pixelDelta.x * 0.5, -w.pixelDelta.y * 0.5)
            else scene.zoom(w.angleDelta.y / 120)
        }
    }
    PinchHandler {
        target: null
        property real last: 1
        onActiveChanged: last = 1
        onActiveScaleChanged: { scene.zoom(Math.log(activeScale / last) / Math.log(1 / 0.9)); last = activeScale }
    }
}
'''


class ArmView(QWidget):
    """Arm, ghost of the live pose, planned path, TCP trail, work frames and obstacles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = Scene()
        self.view = QQuickWidget(self)
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.view.rootContext().setContextProperty('scene', self.scene)
        self.view.setClearColor(QColor('#0E1114'))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        qml = Path(__file__).with_name('viewport.qml')
        if not qml.exists() or qml.read_text() != QML:
            try:
                qml.write_text(QML)
            except OSError:
                pass
        self.view.setSource(QUrl.fromLocalFile(str(qml)))
        # Unload the QML before the context object goes away at shutdown.
        from PySide6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(lambda: self.view.setSource(QUrl()))
        self.preset = 'perspective'
        self.fit_requested = True
        self.last_size = (0, 0)
        self.state_key = None
        self.plan_key = None
        self.reference_key = None
        self.obstacle_key = None
        self.trail = []
        self.studio = None
        self.home = None
        self.grip = ''
        self.setMinimumHeight(280)

    def errors(self):
        return [e.toString() for e in self.view.errors()]

    def set_preset(self, name):
        self.preset = name
        self.fit_requested = True
        self.refresh()

    def fit(self):
        self.fit_requested = True
        self.refresh()

    def rotate(self, steps):
        self.scene.orbit(-steps * 15 / .4, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.scene.user_adjusted:
            self.fit_requested = True
            self.refresh()

    def update_studio(self, studio, grip='', home_preview=None):
        self.studio, self.home, self.grip = studio, home_preview, grip
        self.refresh()

    def refresh(self):
        studio = self.studio
        self.scene.set_background(theme.color('viewport'))
        self._static_overlays()
        if not studio:
            return
        model = studio['model']
        key = model.get('source_hash', '') + '|'.join(v.get('mesh', '') for l in model['links'] for v in l.get('visuals', []))
        if key != self.state_key:
            self.state_key = key
            self.scene.rebuild(studio)
            self.trail = []
            self.fit_requested = True
        home = self.home
        shown = {f['name']: matrix16(f['matrix']) for f in (home or {}).get('frames') or studio.get('frames', []) if len(f.get('matrix', [])) == 16}
        live = {f['name']: matrix16(f['matrix']) for f in studio.get('live_frames', []) if len(f.get('matrix', [])) == 16}
        for name, parts in self.scene.link_parts.items():
            m = shown.get(name)
            for part in parts:
                if m is not None:
                    part.place(m)
                part.set_visible(m is not None)
        for name, parts in self.scene.ghost_parts.items():
            m = live.get(name)
            same = m is not None and name in shown and np.allclose(m, shown[name], atol=1e-4)
            for part in parts:
                if m is not None:
                    part.place(m)
                part.set_visible(m is not None and not studio.get('follow') and home is None and not same)
        self._dynamic_overlays(studio, shown, home)
        size = (self.width(), self.height())
        if self.fit_requested and size[0] > 10 and size[1] > 10:
            self.fit_requested = False
            self.scene.fit(self._fit_points(studio, shown, home), self.preset, *size)
        self.last_size = size

    def _fit_points(self, studio, shown, home):
        points = []
        for name, parts in self.scene.link_parts.items():
            m = shown.get(name)
            if m is None:
                continue
            for part in parts:
                entry = _MESHES.get(part._mesh)
                if not entry:
                    continue
                lo, hi = np.array(entry[3]) / MM * np.array([part._scale.x(), part._scale.y(), part._scale.z()]), np.array(entry[4]) / MM * np.array([part._scale.x(), part._scale.y(), part._scale.z()])
                full = m @ part.local
                for x in (lo[0], hi[0]):
                    for y in (lo[1], hi[1]):
                        for z in (lo[2], hi[2]):
                            points.append((full @ np.array([x, y, z, 1.0]))[:3])
        if home is None:
            plan = ((studio.get('movej_preview') or {}).get('plan') or {})
            if (studio.get('movej_preview') or {}).get('valid'):
                points += [s['tcp'] for s in plan.get('samples', []) if len(s.get('tcp', [])) == 3]
        return points

    def _static_overlays(self):
        if 'grid' in self.scene.overlay_parts:
            self.scene.overlay_parts['grid'].set_color(theme.color('grid'), .6)
            return
        segments = []
        for i in range(-10, 11):
            x = i * 100.0
            segments += [(x, -1000, 0), (x, 1000, 0), (-1000, x, 0), (1000, x, 0)]
        self.scene.set_overlay('grid', line_mesh('grid', segments), theme.color('grid'), opacity=.6)
        for name, end, color in (('axis-x', (160, 0, 2), '#E5484D'), ('axis-y', (0, 160, 2), '#46A758'), ('axis-z', (0, 0, 160), '#3E8EF7')):
            self.scene.set_overlay(name, line_mesh(name, [(0, 0, 2), end]), color)

    def _dynamic_overlays(self, studio, shown, home):
        # TCP marker and trail.
        tcp = (home or {}).get('tcp') or studio.get('tcp') or [0, 0, 0]
        marker = np.eye(4)
        marker[:3, 3] = tcp
        self.scene.set_overlay('tcp', sphere_mesh(.009), '#22C3E6', unlit=False, matrix=marker)
        point = np.array(tcp) * MM
        if not self.trail or np.linalg.norm(self.trail[-1] - point) > 5:
            self.trail = (self.trail + [point])[-80:]
            if len(self.trail) > 1:
                segments = [p for a, b in zip(self.trail, self.trail[1:]) for p in (a, b)]
                self.scene.set_overlay('trail', fresh_line_mesh('trail:%d' % id(self), segments), '#22C3E6', opacity=.55)
        # Planned MoveJ path (orange).
        playback = studio.get('movej_preview') or {}
        plan = playback.get('plan') or {}
        plan_key = plan.get('id', '') if playback.get('valid') and home is None else ''
        if plan_key != self.plan_key:
            self.plan_key = plan_key
            samples = [s['tcp'] for s in plan.get('samples', []) if len(s.get('tcp', [])) == 3] if plan_key else []
            if len(samples) > 1:
                segments = [np.array(p) * MM for a, b in zip(samples, samples[1:]) for p in (a, b)]
                self.scene.set_overlay('plan', line_mesh('plan:' + plan_key, segments), '#FF9F0A')
            else:
                self.scene.drop_overlays('plan')
        # Selected joint axis and arc.
        joints = studio['model']['joints']
        selected = next((j for j in joints if j['name'] == studio.get('selected')), None)
        frame = shown.get(selected['child']) if selected else None
        if frame is not None:
            axis = np.array(selected['axis'], float)
            axis = axis / (np.linalg.norm(axis) or 1)
            guide = [(-axis * 100).tolist(), (axis * 100).tolist()]
            self.scene.set_overlay('guide', line_mesh('guide:' + selected['name'], guide), '#22C3E6', matrix=frame)
            if selected['kind'] != 'prismatic':
                helper = np.array([0, 0, 1.0]) if abs(axis[2]) < .9 else np.array([1.0, 0, 0])
                u = np.cross(axis, helper)
                u /= np.linalg.norm(u)
                v = np.cross(axis, u)
                q = max(-2 * math.pi, min(2 * math.pi, (studio.get('positions') or {}).get(selected['name'], 0)))
                arc = []
                for k in range(32):
                    a, b = q * k / 32, q * (k + 1) / 32
                    arc += [((u * math.cos(a) + v * math.sin(a)) * 65).tolist(), ((u * math.cos(b) + v * math.sin(b)) * 65).tolist()]
                self.scene.set_overlay('arc', fresh_line_mesh('arc:%d' % id(self), arc), '#FF9F0A', matrix=frame)
            else:
                self.scene.drop_overlays('arc')
        else:
            self.scene.drop_overlays('guide')
            self.scene.drop_overlays('arc')
        # Obstacles (orange, translucent).
        obstacles = studio.get('obstacles') or []
        key = repr(obstacles)
        if key != self.obstacle_key:
            self.obstacle_key = key
            self.scene.drop_overlays('box:')
            for index, box in enumerate(obstacles):
                m = np.eye(4)
                m[:3, 3] = box['center']
                self.scene.set_overlay('box:%d' % index, box_mesh(box['size']), '#FF9F0A', unlit=False, opacity=.35, matrix=m)
        # Work frames and Cartesian targets.
        refs = [(f.get('id'), f.get('matrix'), .06, None) for f in studio.get('work_frames') or [] if f.get('id') != 'base']
        refs += [(t.get('id'), t.get('matrix'), .035 if t.get('id') == studio.get('selected_target') else .02, t.get('id') == studio.get('selected_target'))
                 for t in studio.get('cartesian_targets') or []]
        ref_key = repr(refs) + repr(home is None)
        if ref_key != self.reference_key:
            self.reference_key = ref_key
            self.scene.drop_overlays('ref:')
            if home is None:
                for index, (ident, matrix, length, selected_target) in enumerate(refs):
                    if not matrix or len(matrix) != 16:
                        continue
                    m = matrix16(matrix)
                    for axis_index, color in enumerate(('#E5484D', '#46A758', '#3E8EF7')):
                        end = [0, 0, 0]
                        end[axis_index] = length * MM
                        self.scene.set_overlay('ref:%d:%d' % (index, axis_index), line_mesh('ref-axis:%d:%g' % (axis_index, length), [(0, 0, 0), end]), color, matrix=m)
                    if selected_target is not None:
                        self.scene.set_overlay('ref:%d:dot' % index, sphere_mesh(.006 if selected_target else .004),
                                               '#FF9F0A' if selected_target else '#22C3E6', unlit=False, matrix=m)


def configure_graphics():
    """Call before creating QApplication: a renderer that works on every system."""
    QQuickWindow.setDefaultAlphaBuffer(False)
