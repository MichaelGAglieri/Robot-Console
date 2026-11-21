// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import AppKit
import SceneKit
import ModelIO
import simd

// Camera gestures are local visualization only: no controller request is sent.
final class OrbitSCNView:SCNView {
 var userAdjusted=false
 var orbitTarget=SIMD3<Float>(0,0,0)
 private var distance:Float=1
 private var yaw:Float=0
 private var pitch:Float=0
 private var previous=NSPoint.zero
 override var acceptsFirstResponder:Bool{true}
 override func acceptsFirstMouse(for event:NSEvent?)->Bool{true}
 func setOrbitTarget(_ target:SIMD3<Float>){
  orbitTarget=target
  guard let camera=pointOfView else{return}
  let delta=camera.simdPosition-target
  distance=max(0.08,simd_length(delta))
  yaw=atan2(delta.y,delta.x)
  pitch=asin(max(-1,min(1,delta.z/distance)))
 }
 func rotate(yaw delta:Float,pitch vertical:Float=0){
  guard delta.isFinite,vertical.isFinite else{return}
  userAdjusted=true;yaw+=delta;pitch=max(-1.48,min(1.48,pitch+vertical));updateCamera()
 }
 func zoom(_ amount:Float){
  guard amount.isFinite else{return}
  userAdjusted=true;distance=max(0.08,min(30,distance*exp(max(-2,min(2,amount)))));updateCamera()
 }
 func pan(horizontal:Float,vertical:Float){
  guard let camera=pointOfView,horizontal.isFinite,vertical.isFinite else{return}
  // Perspective scale in world units per screen point, so panning follows zoom.
  let fov=Float(camera.camera?.fieldOfView ?? 45)*Float.pi/180
  let verticalFOV=camera.camera?.projectionDirection == .horizontal ? 2*atan(tan(fov/2)/Float(max(0.1,bounds.width/max(1,bounds.height)))) : fov
  let scale=2*distance*tan(verticalFOV/2)/Float(max(1,bounds.height))
  orbitTarget += (-camera.simdWorldRight*horizontal+camera.simdWorldUp*vertical)*scale
  userAdjusted=true;updateCamera()
 }
 // Keep both precise axes; do not turn a two-finger orbit into wheel zoom.
 // Ignore inertial orbit/pan after fingers lift for predictable positioning.
 func applyScroll(horizontal:Float,vertical:Float,precise:Bool,shift:Bool,momentum:Bool){
  guard horizontal.isFinite,vertical.isFinite else{return}
  if precise {
   guard !momentum else{return}
   if shift{pan(horizontal:horizontal,vertical:vertical)}
   else{rotate(yaw:-horizontal*0.006,pitch:vertical*0.006)}
  }else{zoom(vertical*0.08)}
 }
 private func updateCamera(){
  guard let camera=pointOfView else{return}
  // No implicit easing: rapid trackpad events must not queue camera animations.
  SCNTransaction.begin();SCNTransaction.disableActions=true
  camera.simdPosition=orbitTarget+SIMD3(cos(yaw)*cos(pitch),sin(yaw)*cos(pitch),sin(pitch))*distance
  camera.look(at:SCNVector3(orbitTarget),up:SCNVector3(0,0,1),localFront:SCNVector3(0,0,-1))
  SCNTransaction.commit()
 }
 override func mouseDown(with event:NSEvent){window?.makeFirstResponder(self);previous=convert(event.locationInWindow,from:nil)}
 override func mouseDragged(with event:NSEvent){
  let current=convert(event.locationInWindow,from:nil)
  if event.modifierFlags.contains(.shift){pan(horizontal:Float(current.x-previous.x),vertical:Float(current.y-previous.y))}
  else{rotate(yaw:Float(previous.x-current.x)*0.008,pitch:Float(previous.y-current.y)*0.008)}
  previous=current
 }
 override func rightMouseDown(with event:NSEvent){mouseDown(with:event)}
 override func rightMouseDragged(with event:NSEvent){
  let current=convert(event.locationInWindow,from:nil)
  pan(horizontal:Float(current.x-previous.x),vertical:Float(current.y-previous.y));previous=current
 }
 override func scrollWheel(with event:NSEvent){
  applyScroll(horizontal:Float(event.scrollingDeltaX),vertical:Float(event.scrollingDeltaY),precise:event.hasPreciseScrollingDeltas,shift:event.modifierFlags.contains(.shift),momentum:!event.momentumPhase.isEmpty)
 }
 override func magnify(with event:NSEvent){zoom(-Float(event.magnification))}
}

enum ViewportSurface {
 static func coincidentFrames(_ a:[Double],_ b:[Double])->Bool{
  a.count==16 && b.count==16 && zip(a,b).allSatisfy{abs($0-$1)<1e-6}
 }
 static func isGreen(_ color:[Double])->Bool{
  color.count>=3 && color[1]>0.3 && color[1]>color[0]*1.3 && color[1]>color[2]*1.3
 }
 static func smoothGreenMeshes(in asset:MDLAsset,color:[Double]){
  guard isGreen(color) else{return}
  // Shading normals only. No subdivision, welding, decimation or vertex edits.
  // A 45° crease keeps machined edges/holes crisp while smoothing curved facets.
  for case let mesh as MDLMesh in asset.childObjects(of:MDLMesh.self){
   guard mesh.vertexAttributeData(forAttributeNamed:MDLVertexAttributePosition) != nil else{continue}
   mesh.addNormals(withAttributeNamed:MDLVertexAttributeNormal,creaseThreshold:cos(Float.pi/4))
  }
 }
}
