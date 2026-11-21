
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
