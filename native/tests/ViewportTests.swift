// SPDX-License-Identifier: GPL-3.0-only
import AppKit
import SceneKit
import ModelIO
import simd

@main struct ViewportTests {
 static func vectors(_ mesh:MDLMesh,_ name:String)->[SIMD3<Float>]{
  guard let a=mesh.vertexAttributeData(forAttributeNamed:name,as:.float3) else{return []}
  return (0..<mesh.vertexCount).map{i in SIMD3((0..<3).map{a.dataStart.advanced(by:i*a.stride+$0*4).load(as:Float.self)})}
 }
 static func indices(_ mesh:MDLMesh)->[Data]{
  (mesh.submeshes as? [MDLSubmesh] ?? []).map{let buffer=$0.indexBuffer;return Data(bytes:buffer.map().bytes,count:buffer.length)}
 }
 static func main()throws{
  let view=OrbitSCNView(frame:NSRect(x:0,y:0,width:800,height:500))
  view.scene=SCNScene();let camera=SCNNode();camera.camera=SCNCamera();camera.simdPosition=SIMD3(1,-1,1)
  view.scene?.rootNode.addChildNode(camera);view.pointOfView=camera;view.setOrbitTarget(.zero)
  let original=camera.simdPosition;let radius=simd_length(original)
  view.applyScroll(horizontal:20,vertical:0,precise:true,shift:false,momentum:false)
  precondition(simd_distance(original,camera.simdPosition)>0.01,"Horizontal trackpad must orbit")
  precondition(abs(simd_length(camera.simdPosition)-radius)<0.0001,"Orbit must not zoom")
  let horizontal=camera.simdPosition
  view.applyScroll(horizontal:0,vertical:20,precise:true,shift:false,momentum:false)
  precondition(abs(camera.simdPosition.z-horizontal.z)>0.01,"Vertical trackpad must orbit")
  let after=camera.simdPosition
  view.applyScroll(horizontal:100,vertical:100,precise:true,shift:false,momentum:true)
  precondition(camera.simdPosition==after,"No inertial drift")
  view.applyScroll(horizontal:10,vertical:15,precise:true,shift:true,momentum:false)
  precondition(simd_length(view.orbitTarget)>0.01,"Shift must pan")
  precondition(abs(simd_length(camera.simdPosition-view.orbitTarget)-radius)<0.0001)
  view.zoom(-0.2)
  precondition(simd_length(camera.simdPosition-view.orbitTarget)<radius,"Pinch zoom")
  let beforeWheel=simd_length(camera.simdPosition-view.orbitTarget)
  view.applyScroll(horizontal:0,vertical:1,precise:false,shift:false,momentum:false)
  precondition(simd_length(camera.simdPosition-view.orbitTarget)>beforeWheel,"Wheel zoom")
  for _ in 0..<50{view.rotate(yaw:1,pitch:1);view.zoom(-2)}
  precondition(camera.simdPosition.x.isFinite && camera.simdPosition.z.isFinite,"Limits stay finite")
  precondition(simd_length(camera.simdPosition-view.orbitTarget)>=0.0799)
  print("PASS camera: two axes orbit, pan, pinch/wheel zoom, no momentum drift, finite limits")

  let identity:[Double]=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
  precondition(ViewportSurface.coincidentFrames(identity,identity))
  var displaced=identity;displaced[3]=0.001
  precondition(!ViewportSurface.coincidentFrames(identity,displaced))
  precondition(!ViewportSurface.coincidentFrames([],identity))
  print("PASS coincident reference hidden; distinct poses keep their ghost")
  let folder=URL(fileURLWithPath:CommandLine.arguments[1])
  let files=try FileManager.default.contentsOfDirectory(at:folder,includingPropertiesForKeys:nil)
  var count=0
  for url in files where url.pathExtension=="stl" {
   let green=url.lastPathComponent.contains("_lime") || url.lastPathComponent.contains("_verde")
   let color:[Double]=green ? [0.4,0.88,0.012,1] : [0.018,0.022,0.018,1]
   let asset=MDLAsset(url:url)
   for case let mesh as MDLMesh in asset.childObjects(of:MDLMesh.self){
    let pos=vectors(mesh,MDLVertexAttributePosition),normals=vectors(mesh,MDLVertexAttributeNormal),idx=indices(mesh)
    ViewportSurface.smoothGreenMeshes(in:asset,color:color)
    let next=vectors(mesh,MDLVertexAttributeNormal)
    precondition(vectors(mesh,MDLVertexAttributePosition)==pos,"Vertex positions changed: "+url.lastPathComponent)
    precondition(indices(mesh)==idx,"Triangle indices changed")
    precondition(next.allSatisfy{$0.x.isFinite && $0.y.isFinite && $0.z.isFinite},"Invalid normals")
    if green {
     precondition(next.count==pos.count)
     precondition(zip(normals,next).contains{simd_distance($0,$1)>0.001},"Facets were not smoothed")
     // Coincident vertices at a sharp crease must retain distinct normals.
     struct P:Hashable{let x:Float;let y:Float;let z:Float}
     var groups:[P:[SIMD3<Float>]]=[:]
     for (p,n) in zip(pos,next){groups[P(x:p.x,y:p.y,z:p.z),default:[]].append(n)}
     let curved=groups.values.filter{ns in ns.count>1 && ns.dropFirst().allSatisfy{simd_distance($0,ns[0])<0.001}}.count
     let creases=groups.values.filter{ns in ns.contains{simd_dot($0,ns[0])<0.7}}.count
     precondition(curved>0 && creases>0,"Smooth curves and sharp edges must coexist")
     count+=1;print("PASS shading",url.lastPathComponent,"smooth vertices",curved,"creases",creases,"geometry unchanged")
    }else{precondition(next==normals,"Non-green shading changed")}
   }
  }
  precondition(count==8,"Expected all eight green meshes")
  print("PASS all model coordinates, triangle indices and non-green normals preserved")
 }
}
