// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import AppKit
import SceneKit
import ModelIO
import SceneKit.ModelIO
import UniformTypeIdentifiers
import Charts
import simd

struct ArmVisual:Decodable {let kind:String;let xyz:[Double];let rpy:[Double];let color:[Double];let size:[Double];let mesh:String}
struct ArmLink:Decodable {let name:String;let visuals:[ArmVisual]}
struct ArmJoint:Decodable,Identifiable {
 let name:String;let kind:String;let parent:String;let child:String;let axis:[Double];let lower:Double;let upper:Double;let xyz:[Double];let rpy:[Double];let mimic:String
 var id:String{name}
 var rotary:Bool{kind != "prismatic"}
}
struct ArmModel:Decodable {let name:String;let root:String;let tip:String;let links:[ArmLink];let joints:[ArmJoint];let warnings:[String];let source_hash:String;let approximate:Bool?;let schematic:Bool?}
struct HomePreview:Decodable {let frames:[ArmFrame];let tcp:[Double];let model_hash:String}
struct ArmFrame:Decodable {let name:String;let matrix:[Double]}
struct ArmCalibration:Decodable {let sign:Double;let offset:Double}
struct WorkcellBox:Codable,Identifiable {var name:String;var center:[Double];var size:[Double];var id:String{name}}
struct ProgramBlock:Codable,Identifiable {
 var kind:String;var name:String;var enabled:Bool=true;var index:Int?;var command:String?;var seconds:Double?;var sensor:String?;var expected:Double?;var timeout:Double?;var start:Int?;var count:Int?
 var id:String{name+kind+String(index ?? -1)}
}
struct SensorReading:Decodable,Identifiable {
 let name:String;let kind:String;let valueText:String;let stamp:Double;let source:String;let age:Double
 var id:String{name}
 enum CodingKeys:String,CodingKey{case name,kind,value,stamp,source,age}
 init(from decoder:Decoder)throws {
  let c=try decoder.container(keyedBy:CodingKeys.self)
  name=try c.decode(String.self,forKey:.name);kind=try c.decode(String.self,forKey:.kind);stamp=try c.decode(Double.self,forKey:.stamp);source=try c.decode(String.self,forKey:.source);age=try c.decode(Double.self,forKey:.age)
  if let b=try? c.decode(Bool.self,forKey:.value){valueText=b ? "1" : "0"}else if let n=try? c.decode(Double.self,forKey:.value){valueText=String(format:"%g",n)}else{valueText="—"}
 }
}
struct TelemetryPoint:Decodable {let time:Double;let values:[Double]}
struct StudioState:Decodable {
 let name:String;let model:ArmModel;let positions:[String:Double];let enabled:[String:Bool];let mapping:[String:Int];let calibration:[String:ArmCalibration];let tool:[Double];let tip:String;let verified:Bool;let selected:String;let follow:Bool;let status:String
 let frames:[ArmFrame];let live_frames:[ArmFrame];let tcp:[Double];let collisions:[String];let obstacles:[WorkcellBox];let blocks:[ProgramBlock];let sensors:[SensorReading];let recording:Bool;let sample_count:Int;let program_running:Bool;let program_index:Int;let program_error:String;let telemetry:[TelemetryPoint]
 var movable:[ArmJoint]{model.joints.filter{$0.kind != "fixed" && $0.mimic.isEmpty}}
}

extension Regia {
 func chooseURDF(){
  let p=NSOpenPanel();p.allowedContentTypes=[UTType(filenameExtension:"urdf") ?? .xml];p.allowsMultipleSelection=false;p.message="Scegli un URDF già espanso. Lascia le mesh nella cartella del pacchetto vicino al file."
  if p.runModal() == .OK,let url=p.url{send("studio_import",["path":url.path])}
 }
 func studioFile(_ operation:String){
  if operation == "studio_open" {
   let p=NSOpenPanel();p.allowedContentTypes=[.zip];if p.runModal() == .OK,let url=p.url{send(operation,["path":url.path])}
  }else{
   let p=NSSavePanel();p.allowedContentTypes=operation == "studio_export_csv" ? [.commaSeparatedText] : [.zip];p.nameFieldStringValue=operation == "studio_export_csv" ? "robot-session.csv" : "robot-project.zip"
   if p.runModal() == .OK,let url=p.url{send(operation,["path":url.path])}
  }
 }
 func blocks(_ blocks:[ProgramBlock]){
  guard let raw=try? JSONEncoder().encode(blocks),let value=try? JSONSerialization.jsonObject(with:raw) else{return}
  send("studio_blocks",["blocks":value])
 }
}

// Camera gestures are local visualization only: no controller request is sent.
final class OrbitSCNView:SCNView {
 var userAdjusted=false
 var orbitTarget=SIMD3<Float>(0,0,0);private var distance:Float=1;private var yaw:Float=0;private var pitch:Float=0;private var previous=NSPoint.zero
 override var acceptsFirstResponder:Bool{true}
 override func acceptsFirstMouse(for event:NSEvent?)->Bool{true}
 func setOrbitTarget(_ target:SIMD3<Float>){orbitTarget=target;guard let camera=pointOfView else{return};let delta=camera.simdPosition-target;distance=max(0.08,simd_length(delta));yaw=atan2(delta.y,delta.x);pitch=asin(max(-1,min(1,delta.z/distance)))}
 func rotate(yaw delta:Float,pitch vertical:Float=0){userAdjusted=true;yaw+=delta;pitch=max(-1.48,min(1.48,pitch+vertical));updateCamera()}
 private func updateCamera(){guard let camera=pointOfView else{return};camera.simdPosition=orbitTarget+SIMD3(cos(yaw)*cos(pitch),sin(yaw)*cos(pitch),sin(pitch))*distance;camera.look(at:SCNVector3(orbitTarget),up:SCNVector3(0,0,1),localFront:SCNVector3(0,0,-1))}
 override func mouseDown(with event:NSEvent){window?.makeFirstResponder(self);previous=convert(event.locationInWindow,from:nil)}
 override func mouseDragged(with event:NSEvent){let current=convert(event.locationInWindow,from:nil);rotate(yaw:Float(previous.x-current.x)*0.008,pitch:Float(previous.y-current.y)*0.008);previous=current}
 override func scrollWheel(with event:NSEvent){userAdjusted=true;distance=max(0.08,min(30,distance*exp(Float(event.scrollingDeltaY)*0.015)));updateCamera()}
 override func magnify(with event:NSEvent){userAdjusted=true;distance=max(0.08,min(30,distance*exp(-Float(event.magnification))));updateCamera()}
}

struct ArmScene:NSViewRepresentable {
 let studio:StudioState
 let camera:String
 let grip:String
 var orbitStep:Int=0
 var homePreview:HomePreview?=nil
 @Environment(\.colorScheme) var colorScheme
 func makeCoordinator()->Coordinator{Coordinator()}
 func makeNSView(context:Context)->OrbitSCNView {
  let view=OrbitSCNView();view.scene=SCNScene();view.allowsCameraControl=false;view.autoenablesDefaultLighting=false;view.antialiasingMode = .multisampling4X
  view.defaultCameraController.worldUp=SCNVector3(0,0,1);view.defaultCameraController.interactionMode = .orbitTurntable
  context.coordinator.setup(view);return view
 }
 func updateNSView(_ view:OrbitSCNView,context:Context){context.coordinator.update(view,studio,camera,colorScheme,grip,orbitStep,homePreview)}
 final class Coordinator {
  var viewport=CGSize.zero
  var lastOrbitStep=0;var key="";var nodes:[String:SCNNode]=[:];var ghosts:[String:SCNNode]=[:];var jaws:[SCNNode]=[];var cameraNode=SCNNode();var objects=SCNNode();var jointGuide=SCNNode();var marker=SCNNode();var cameraPreset="";var path=SCNNode();var points:[SCNVector3]=[]
  func setup(_ view:SCNView){
   guard let scene=view.scene else{return}
   cameraNode.camera=SCNCamera();cameraNode.camera?.zNear = 0.001;cameraNode.camera?.zFar=200;scene.rootNode.addChildNode(cameraNode);view.pointOfView=cameraNode
   let ambient=SCNNode();ambient.light=SCNLight();ambient.light?.type = .ambient;ambient.light?.intensity=180;scene.rootNode.addChildNode(ambient)
   let lamp=SCNNode();lamp.light=SCNLight();lamp.light?.type = .omni;lamp.light?.intensity=450;lamp.position=SCNVector3(1,-1,2);scene.rootNode.addChildNode(lamp)
   scene.rootNode.addChildNode(objects);scene.rootNode.addChildNode(jointGuide);scene.rootNode.addChildNode(marker);scene.rootNode.addChildNode(path)
   let grid=SCNNode()
   for i in -10...10 {let x=Float(i)*0.1;grid.addChildNode(lines([SCNVector3(x,-1,0),SCNVector3(x,1,0),SCNVector3(-1,x,0),SCNVector3(1,x,0)],NSColor.gray.withAlphaComponent(0.25)))}
   scene.rootNode.addChildNode(grid)
   for (end,color) in [(SCNVector3(0.16,0,0),NSColor.systemRed),(SCNVector3(0,0.16,0),NSColor.systemGreen),(SCNVector3(0,0,0.16),NSColor.systemBlue)]{scene.rootNode.addChildNode(lines([SCNVector3(0,0,0.002),end],color))}
   let dot=SCNSphere(radius:0.009);dot.firstMaterial?.diffuse.contents=NSColor.systemCyan;marker.geometry=dot
  }
  func lines(_ points:[SCNVector3],_ color:NSColor)->SCNNode {
   let source=SCNGeometrySource(vertices:points);let element=SCNGeometryElement(indices:Array(0..<Int32(points.count)),primitiveType:.line)
   let geometry=SCNGeometry(sources:[source],elements:[element]);let m=SCNMaterial();m.diffuse.contents=color;m.emission.contents=color;m.lightingModel = .constant;geometry.materials=[m];return SCNNode(geometry:geometry)
  }
  func transform(_ values:[Double])->simd_float4x4 {
   simd_float4x4(columns:(SIMD4(Float(values[0]),Float(values[4]),Float(values[8]),Float(values[12])),SIMD4(Float(values[1]),Float(values[5]),Float(values[9]),Float(values[13])),SIMD4(Float(values[2]),Float(values[6]),Float(values[10]),Float(values[14])),SIMD4(Float(values[3]),Float(values[7]),Float(values[11]),Float(values[15]))))
  }
  func material(_ color:[Double])->SCNMaterial {
   let dark=max(color[0],max(color[1],color[2]))<0.2
   let c=dark ? [0.25,0.28,0.24,color[3]] : color
   let m=SCNMaterial();m.diffuse.contents=NSColor(srgbRed:c[0],green:c[1],blue:c[2],alpha:c[3]);if dark{m.emission.contents=NSColor(srgbRed:0.055,green:0.065,blue:0.05,alpha:1)};m.lightingModel = .lambert;m.roughness.contents = 0.7;m.metalness.contents = 0.15;return m
  }
  func geometry(_ v:ArmVisual)->SCNNode {
   let node=SCNNode()
   switch v.kind {
    case "box":node.geometry=SCNBox(width:v.size[0],height:v.size[1],length:v.size[2],chamferRadius:0.002)
    case "sphere":node.geometry=SCNSphere(radius:v.size[0])
    case "cylinder":let cylinder=SCNNode(geometry:SCNCylinder(radius:v.size[0],height:v.size[1]));cylinder.eulerAngles.x = .pi/2;node.addChildNode(cylinder)
    case "mesh":
     if !v.mesh.isEmpty,FileManager.default.fileExists(atPath:v.mesh) {
      if v.mesh.lowercased().hasSuffix(".dae"),let scene=try? SCNScene(url:URL(fileURLWithPath:v.mesh)){for child in scene.rootNode.childNodes{node.addChildNode(child.clone())}}
      else{let asset=MDLAsset(url:URL(fileURLWithPath:v.mesh));let scene=SCNScene(mdlAsset:asset);for child in scene.rootNode.childNodes{node.addChildNode(child.clone())}}
      node.scale=SCNVector3(v.size[0],v.size[1],v.size[2])
     }
     if node.childNodes.isEmpty{node.geometry=SCNBox(width:0.04,height:0.04,length:0.04,chamferRadius:0);node.geometry?.firstMaterial?.fillMode = .lines}
    default:break
   }
   node.position=SCNVector3(v.xyz[0],v.xyz[1],v.xyz[2])
   node.simdOrientation=simd_quatf(angle:Float(v.rpy[2]),axis:SIMD3(0,0,1))*simd_quatf(angle:Float(v.rpy[1]),axis:SIMD3(0,1,0))*simd_quatf(angle:Float(v.rpy[0]),axis:SIMD3(1,0,0))
   let m=material(v.color);node.enumerateChildNodes{child,_ in if child.geometry != nil {child.geometry=child.geometry?.copy() as? SCNGeometry;child.geometry?.materials=[m]}}
   node.geometry?.materials=[m];return node
  }
  func update(_ view:SCNView,_ state:StudioState,_ preset:String,_ scheme:ColorScheme,_ grip:String,_ orbitStep:Int,_ home:HomePreview?){
   guard let scene=view.scene else{return}
   view.backgroundColor=scheme == .dark ? NSColor(srgbRed:0.045,green:0.06,blue:0.04,alpha:1) : NSColor(srgbRed:0.91,green:0.94,blue:0.90,alpha:1)
   let newKey=state.model.source_hash+state.model.links.flatMap{$0.visuals.map{$0.mesh}}.joined()
   if key != newKey {
    for node in nodes.values{node.removeFromParentNode()};for node in ghosts.values{node.removeFromParentNode()};ghosts=[:];nodes=[:];jaws=[];key=newKey;points=[];cameraPreset=""
    for link in state.model.links {
     let node=SCNNode();node.name=link.name
     for visual in link.visuals{node.addChildNode(geometry(visual))}
     if state.model.joints.contains(where:{$0.child==link.name && $0.kind != "fixed" && $0.mimic.isEmpty}) {let axis=SCNNode(geometry:SCNSphere(radius:0.007));axis.name="jointMarker";axis.geometry?.firstMaterial?.diffuse.contents=NSColor.gray;node.addChildNode(axis)}
     nodes[link.name]=node;scene.rootNode.addChildNode(node)
     let ghost=node.clone();ghost.enumerateChildNodes{child,_ in if let geometry=child.geometry{child.geometry=geometry.copy() as? SCNGeometry;let mat=SCNMaterial();mat.diffuse.contents=NSColor.systemGray.withAlphaComponent(0.35);mat.fillMode = .lines;child.geometry?.materials=[mat]}}
     ghosts[link.name]=ghost;scene.rootNode.addChildNode(ghost)
    }
   }
   if state.model.schematic == true,jaws.isEmpty,let hand=nodes[state.model.tip] {
    for _ in 0..<3 {let jaw=SCNNode(geometry:SCNBox(width:0.014,height:0.014,length:0.065,chamferRadius:0.002));jaw.geometry?.firstMaterial?.diffuse.contents=NSColor(srgbRed:0.66,green:1,blue:0.16,alpha:1);hand.addChildNode(jaw);jaws.append(jaw)}
   }
   let shownFrames=home?.frames ?? state.frames
   SCNTransaction.begin();SCNTransaction.animationDuration = 0.28
   for (i,jaw) in jaws.enumerated(){let angle=Double(i)*2*Double.pi/3;let radius=grip=="chiudi" ? 0.012 : 0.04;jaw.position=SCNVector3(cos(angle)*radius,sin(angle)*radius,0.13)}
   for frame in state.live_frames where frame.matrix.count==16{ghosts[frame.name]?.simdTransform=transform(frame.matrix);ghosts[frame.name]?.isHidden=state.follow || home != nil}
   for f in shownFrames where f.matrix.count==16{nodes[f.name]?.simdTransform=transform(f.matrix)}
   for j in state.model.joints {
    let m=nodes[j.child]?.childNode(withName:"jointMarker",recursively:false)
    m?.geometry?.firstMaterial?.diffuse.contents=j.name == state.selected ? NSColor.systemCyan : NSColor.gray;m?.scale=j.name == state.selected ? SCNVector3(1.8,1.8,1.8) : SCNVector3(1,1,1)
   }
   jointGuide.childNodes.forEach{$0.removeFromParentNode()}
   if let j=state.model.joints.first(where:{$0.name==state.selected}),let f=shownFrames.first(where:{$0.name==j.child}) {
    jointGuide.simdTransform=transform(f.matrix)
    let axis=simd_normalize(SIMD3(Float(j.axis[0]),Float(j.axis[1]),Float(j.axis[2])))
    let tip=axis*0.10;let guide=lines([SCNVector3(-tip),SCNVector3(tip)],.systemCyan);jointGuide.addChildNode(guide)
    if j.rotary {
     let helper=abs(axis.z)<0.9 ? SIMD3<Float>(0,0,1) : SIMD3<Float>(1,0,0);let u=simd_normalize(simd_cross(axis,helper));let v=simd_cross(axis,u)
     let q=state.positions[j.name] ?? 0;let span=Float(max(-2*Double.pi,min(2*Double.pi,q)));var arc:[SCNVector3]=[]
     for k in 0..<32{let a=span*Float(k)/32;let b=span*Float(k+1)/32;arc.append(SCNVector3((u*cos(a)+v*sin(a))*0.065));arc.append(SCNVector3((u*cos(b)+v*sin(b))*0.065))}
     jointGuide.addChildNode(lines(arc,.systemOrange))
    }
   }
   let shownTCP=home?.tcp ?? state.tcp
   marker.position=SCNVector3(shownTCP[0],shownTCP[1],shownTCP[2]);SCNTransaction.commit()
   let point=marker.position
   if points.last.map({hypot(hypot($0.x-point.x,$0.y-point.y),$0.z-point.z)>0.005}) ?? true {
    points.append(point);points=Array(points.suffix(80));path.childNodes.forEach{$0.removeFromParentNode()}
    for p in points {let dot=SCNNode(geometry:SCNSphere(radius:0.002));dot.position=p;dot.geometry?.firstMaterial?.diffuse.contents=NSColor.systemCyan.withAlphaComponent(0.45);path.addChildNode(dot)}
   }
   objects.childNodes.forEach{$0.removeFromParentNode()}
   for box in state.obstacles {
    let node=SCNNode(geometry:SCNBox(width:box.size[0],height:box.size[1],length:box.size[2],chamferRadius:0));node.position=SCNVector3(box.center[0],box.center[1],box.center[2]);node.geometry?.firstMaterial?.diffuse.contents=NSColor.systemOrange.withAlphaComponent(0.35);objects.addChildNode(node)
   }
   if orbitStep != lastOrbitStep{(view as? OrbitSCNView)?.rotate(yaw:Float(orbitStep-lastOrbitStep)*Float.pi/12);lastOrbitStep=orbitStep}
   let validViewport=view.bounds.width>10 && view.bounds.height>10
   let resized=abs(view.bounds.width-viewport.width)>2 || abs(view.bounds.height-viewport.height)>2
   let userAdjusted=(view as? OrbitSCNView)?.userAdjusted ?? false
   if validViewport && (cameraPreset != preset || (resized && !userAdjusted)) {
    cameraPreset=preset
    (view as? OrbitSCNView)?.userAdjusted=false
    var corners:[SIMD3<Float>]=[]
    for node in nodes.values{let box=node.boundingBox;for x in [box.min.x,box.max.x]{for y in [box.min.y,box.max.y]{for z in [box.min.z,box.max.z]{corners.append(node.simdConvertPosition(SIMD3(Float(x),Float(y),Float(z)),to:nil))}}}}
    let minimum=SIMD3(corners.map{$0.x}.min() ?? -0.2,corners.map{$0.y}.min() ?? -0.2,corners.map{$0.z}.min() ?? 0)
    let maximum=SIMD3(corners.map{$0.x}.max() ?? 0.2,corners.map{$0.y}.max() ?? 0.2,corners.map{$0.z}.max() ?? 0.7)
    let center=(minimum+maximum)/2;let radius=max(0.15,simd_length(maximum-minimum)/2);let aspect=max(0.35,Float(view.bounds.width/max(1,view.bounds.height)));let distance=radius/max(0.1,sin(Float.pi/8)*min(1,aspect))*1.15
    var direction=SIMD3<Float>(1,-1,0.65)
    switch String(preset.split(separator:"#")[0]){case "front":direction=SIMD3(0,-1,0.04);case "side":direction=SIMD3(1,0,0.04);case "top":direction=SIMD3(0,-0.001,1);default:break}
    cameraNode.camera?.fieldOfView=45;cameraNode.simdPosition=center+simd_normalize(direction)*distance
    cameraNode.look(at:SCNVector3(center),up:SCNVector3(0,0,1),localFront:SCNVector3(0,0,-1));view.defaultCameraController.target=SCNVector3(center);(view as? OrbitSCNView)?.setOrbitTarget(center)
   }
   if validViewport {viewport=view.bounds.size}
  }
 }
}

struct ArmMiniView:View {
 @ObservedObject var m:Regia
 @State private var camera="perspective"
 @State private var fit=0
 @State private var rotation=0
 @State private var showHome=false
 var body:some View {
  VStack(alignment:.leading,spacing:8){
   HStack{RText("Anteprima 3D").font(.headline).lineLimit(1);Spacer();if let s=m.studio{Toggle("Segui comandi",isOn:Binding(get:{s.follow},set:{m.send("studio_follow",["enabled":$0])})).toggleStyle(.switch).controlSize(.small).robotCaption().fixedSize()}}
   HStack{Button("HOME del modello…"){showHome=true}.disabled(m.state.connected || !m.idle || m.firmware.busy);Spacer()}
   if m.state.connected {RText("Scollega il controllo per allineare la HOME del modello.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)}
   HStack{Button("Adatta vista"){fit+=1}.fixedSize();Button("↺"){rotation-=1}.help("Ruota a sinistra");Button("↻"){rotation+=1}.help("Ruota a destra");Spacer()}
   if let s=m.studio {
    RText("\(s.movable.count) giunti mobili nel modello").robotCaption().foregroundStyle(RobotTheme.accentText)
    ArmScene(studio:s,camera:camera+"#"+String(fit),grip:m.state.grip,orbitStep:rotation).clipShape(RoundedRectangle(cornerRadius:12)).frame(minHeight:340,maxHeight:.infinity)
    RText("Trascina per ruotare · rotella o pizzico per zoom").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
    Picker("Vista",selection:$camera){RText("3D").tag("perspective");RText("Fronte").tag("front");RText("Lato").tag("side");RText("Alto").tag("top")}.pickerStyle(.segmented)
    RText(s.follow ? "Animazione stimata dai comandi · senza feedback fisico" : "Target virtuale · il robot non viene mosso").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
    RText("TCP: X \(s.tcp[0]*1000,specifier:"%.1f") · Y \(s.tcp[1]*1000,specifier:"%.1f") · Z \(s.tcp[2]*1000,specifier:"%.1f") mm").font(.caption.monospacedDigit())
    if !s.collisions.isEmpty{RText("Interferenza geometrica: "+s.collisions.joined(separator:", ")).robotCaption().foregroundStyle(RobotTheme.stop)}
   }else{ProgressView("Caricamento modello…").frame(height:250)}
  }.padding(12).background(RobotTheme.surface,in:RoundedRectangle(cornerRadius:14))
   .sheet(isPresented:$showHome){ModelHomeEditor(m:m)}
 }
}

struct ModelHomeEditor:View {
 @ObservedObject var m:Regia
 @Environment(\.dismiss) private var dismiss
 @State private var offsets:[String:Double]=[:]
 @State private var source=""
 @State private var fit=0
 @State private var camera="perspective"
 @State private var pending:DispatchWorkItem?
 @State private var session=UUID()
 func refresh(){
  pending?.cancel();m.homeRevision+=1;m.homePreview=nil
  let revision=m.homeRevision;let values=offsets;let hash=source
  let work=DispatchWorkItem{m.send("studio_home_preview",["offsets":values,"model_hash":hash,"revision":revision])}
  pending=work;DispatchQueue.main.asyncAfter(deadline:.now()+0.12,execute:work)
 }
 var body:some View {
  VStack(alignment:.leading,spacing:14) {
   HStack{RText("Allinea HOME del modello").font(.title2.bold());Spacer();Button{dismiss()}label:{RText("Annulla")}}
   RText("Regola i giunti finché il modello assomiglia al braccio reale nella sua HOME. Sono offset del modello a zero comandato: non muovono i motori e non misurano la calibrazione.").font(.callout).foregroundStyle(RobotTheme.secondary)
   if let s=m.studio {
    HStack(alignment:.top,spacing:16) {
     VStack {
      ArmScene(studio:s,camera:camera+"#"+String(fit),grip:m.state.grip,homePreview:m.homePreview).clipShape(RoundedRectangle(cornerRadius:12)).frame(minHeight:440,maxHeight:.infinity)
      HStack{Button{fit+=1}label:{RText("Adatta vista")};Picker("Vista",selection:$camera){RText("3D").tag("perspective");RText("Fronte").tag("front");RText("Lato").tag("side");RText("Alto").tag("top")}.pickerStyle(.segmented)}
      RText("Trascina per ruotare · rotella o pizzico per zoom").robotCaption()
     }.frame(maxWidth:.infinity)
     ScrollView {
      VStack(alignment:.leading,spacing:18) {
       ForEach(s.movable){joint in
        let multiplier=joint.rotary ? 180 / Double.pi : 1000.0
        VStack(alignment:.leading,spacing:6) {
         RText(joint.name).font(.subheadline.bold())
         HStack{TextField("HOME",value:Binding(get:{(offsets[joint.name] ?? 0)*multiplier},set:{offsets[joint.name]=max(joint.lower,min(joint.upper,$0/multiplier))}),format:.number.precision(.fractionLength(1))).accessibilityLabel(T("HOME modello ")+joint.name);RText(joint.rotary ? "°" : "mm")}
         Slider(value:Binding(get:{offsets[joint.name] ?? 0},set:{offsets[joint.name]=$0}),in:joint.lower...max(joint.lower+0.000001,joint.upper)).accessibilityLabel(T("HOME modello ")+joint.name)
        }
       }
      }.padding(4)
     }.frame(width:240)
    }
    HStack {
     Button{offsets=s.calibration.mapValues{$0.offset}}label:{RText("Ripristina valori iniziali")}
     Spacer()
     Button {
      m.send("studio_home_apply",["offsets":offsets,"model_hash":source,"confirmed":true]){ok in if ok {dismiss()}}
     }label:{RText("Salva HOME del modello")}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(m.state.connected || !m.idle || m.homePreview == nil)
    }
   }
  }.padding(22).frame(width:980,height:720).background(RobotTheme.surface).foregroundStyle(RobotTheme.text)
   .onAppear{if let s=m.studio {source=s.model.source_hash;offsets=s.calibration.mapValues{$0.offset};refresh()}}
   .onChange(of:offsets){_,_ in refresh()}
   .onDisappear{pending?.cancel();m.homeRevision+=1;m.homePreview=nil}
 }
}

struct ArmJointRow:View {
 @ObservedObject var m:Regia
 let joint:ArmJoint;let studio:StudioState
 @State private var confirmRelease=false
 @State private var angle="";@State private var offset="";@State private var axis = -1;@State private var sign=1.0
 var multiplier:Double{joint.rotary ? 180 / .pi : 1000}
 var current:Double{studio.positions[joint.name] ?? 0}
 var bounds:ClosedRange<Double>{let c=studio.calibration[joint.name];let sign=c?.sign ?? 1;let offset=c?.offset ?? 0;let a=(joint.lower-offset)/sign;let b=(joint.upper-offset)/sign;return min(a,b)...max(min(a,b)+0.0001,max(a,b))}
 func apply(){guard let o=Double(offset.replacingOccurrences(of:",",with:".")) else{m.message="Offset non valido";return};m.send("studio_joint",["joint":joint.name,"axis":axis,"sign":sign,"offset":o/multiplier])}
 var body:some View {
  VStack(alignment:.leading,spacing:8){
   HStack{
    Toggle(joint.name,isOn:Binding(get:{studio.enabled[joint.name] ?? true},set:{value in
     let channel=studio.mapping[joint.name] ?? -1
     if !value && channel>=0 && m.state.mode=="robot" && m.state.connected && m.state.drive_caps?[channel]==true && m.state.drive_state?[channel] != false {m.send("axis_stop",["axis":channel]);confirmRelease=true}
     else {m.send("studio_joint",["joint":joint.name,"enabled":value])}
    })).toggleStyle(.checkbox).frame(minWidth:140,alignment:.leading).disabled((!m.idle && studio.enabled[joint.name]==false) || (m.state.connected && m.state.mode=="robot" && m.state.axis_control != true && (studio.mapping[joint.name] ?? -1)>=0))
    Button("Evidenzia"){m.send("studio_select",["joint":joint.name])}.robotCaption()
    RText(joint.kind).robotCaption().foregroundStyle(RobotTheme.secondary)
    Spacer();RText("\(current*multiplier,specifier:"%.1f") \(joint.rotary ? "°" : "mm")").monospacedDigit()
    TextField("Target",text:$angle).frame(width:75)
    Button("Anteprima"){if let v=Double(angle.replacingOccurrences(of:",",with:".")){m.send("studio_preview",["joint":joint.name,"value":v/multiplier])}}.disabled(!(studio.enabled[joint.name] ?? true))
   }
   Slider(value:Binding(get:{min(bounds.upperBound,max(bounds.lowerBound,current))},set:{m.send("studio_preview",["joint":joint.name,"value":$0])}),in:bounds).disabled(!(studio.enabled[joint.name] ?? true))
   HStack {
    Picker("Motore",selection:$axis){RText("Solo modello").tag(-1);ForEach(0..<6,id:\.self){RText("J\($0+1)").tag($0)}}.frame(width:175)
    Picker("Verso",selection:$sign){RText("+1").tag(1.0);RText("−1").tag(-1.0)}.frame(width:125)
    RText("Offset").robotCaption();TextField("Offset",text:$offset).frame(width:70);RText(joint.rotary ? "°" : "mm").robotCaption()
    Button("Applica mapping"){apply()}.disabled(m.state.connected || !m.idle)
   }
  }.padding(10).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:10))
   .alert("Rilascia la tenuta del giunto?",isPresented:$confirmRelease){Button("Disabilita ENABLE",role:.destructive){m.send("studio_joint",["joint":joint.name,"enabled":false])};Button("Annulla",role:.cancel){}}message:{RText("Il movimento è stato fermato se il giunto era attivo. Disabilitare ENABLE toglie la corrente alle bobine: un asse sotto carico può cadere. Sostienilo prima di confermare. La sequenza verrà interrotta e HOME dovrà essere ristabilita.")}
   .onAppear{angle=String(format:"%.1f",current*multiplier);axis=studio.mapping[joint.name] ?? -1;let c=studio.calibration[joint.name];offset=String(format:"%.1f",(c?.offset ?? 0)*multiplier);sign=c?.sign ?? 1}
 }
}
struct StudioSetupPanel:View {
 @ObservedObject var m:Regia
 @State private var expanded=false;@State private var x="0";@State private var y="0";@State private var z="0";@State private var tip="";@State private var ikX="200";@State private var ikY="0";@State private var ikZ="300";@State private var projectName="";@State private var obstacleJSON="[]"
 var canConfigure:Bool{!m.state.connected && m.idle && !m.firmware.busy}
 var body:some View {
  Panel(title:"Modello del braccio · URDF e calibrazione") {
   if let s=m.studio {
    HStack {RText(s.model.name).font(.headline).foregroundStyle(RobotTheme.accentText);Spacer();Button("Importa URDF…"){m.chooseURDF()}.disabled(!canConfigure);Button("Apri progetto…"){m.studioFile("studio_open")}.disabled(!canConfigure);Button("Esporta progetto…"){m.studioFile("studio_export")}.disabled(!canConfigure)}
    RText(s.status).robotCaption().foregroundStyle(RobotTheme.secondary)
    if s.model.schematic == true{RText("DOC schematico: geometria indicativa, non una calibrazione del robot fisico.").robotCaption().foregroundStyle(.orange)}
    DisclosureGroup("Giunti, mapping hardware e TCP",isExpanded:$expanded){
     VStack(alignment:.leading,spacing:12){
      RText("Escludere un giunto blocca i comandi e le sequenze che lo richiedono. Non disabilita elettricamente il driver. Per cambiare mapping o calibrazione scollega il controllo.").robotCaption().foregroundStyle(RobotTheme.secondary)
      ForEach(s.movable){j in ArmJointRow(m:m,joint:j,studio:s)}
      HStack {TextField("Nome progetto",text:$projectName);Button("Salva progetto"){m.send("studio_save",["name":projectName])};Button("Carica DOC 5 DOF"){m.send("studio_default")}.disabled(!canConfigure)}
      HStack {
       Picker("Link utensile",selection:$tip){ForEach(s.model.links,id:\.name){RText($0.name).tag($0.name)}}
       TextField("X mm",text:$x).frame(width:75);TextField("Y mm",text:$y).frame(width:75);TextField("Z mm",text:$z).frame(width:75)
       Button("Salva TCP"){if let a=Double(x),let b=Double(y),let c=Double(z){m.send("studio_tcp",["tip":tip,"tool":[a/1000,b/1000,c/1000]])}}.disabled(!canConfigure)
      }
      Toggle("Ho verificato fisicamente modello, mapping, versi e offset",isOn:Binding(get:{s.verified},set:{m.send("studio_verified",["confirmed":$0])})).disabled(!canConfigure)
      if !s.model.warnings.isEmpty{RText(s.model.warnings.joined(separator:"\n")).robotCaption().foregroundStyle(.orange)}
     }.padding(.top,10)
    }
    DisclosureGroup("Target cartesiano e ambiente di lavoro"){
     VStack(alignment:.leading,spacing:10){
      HStack {RText("Target punta · mm");TextField("X",text:$ikX);TextField("Y",text:$ikY);TextField("Z",text:$ikZ);Button("Calcola anteprima IK"){if let a=Double(ikX),let b=Double(ikY),let c=Double(ikZ){m.send("studio_ik",["target":[a/1000,b/1000,c/1000]])}}}
      RText("IK di posizione: l’orientamento non è imposto. La raggiungibilità dipende dai giunti e dal modello importato. Il calcolo aggiorna solo il modello.").robotCaption().foregroundStyle(RobotTheme.secondary)
      Button("Esegui target visualizzato…"){m.confirmStudioTarget=true}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.state.home || !m.idle || s.follow)
      RText("Ostacoli: elenco JSON con name, center [x,y,z] e size [x,y,z] in metri. Controllo conservativo dei segmenti dei link; non è una certificazione di collisione.").robotCaption().foregroundStyle(RobotTheme.secondary)
      TextEditor(text:$obstacleJSON).font(.system(size:12,design:.monospaced)).frame(height:100)
      Button("Applica ostacoli"){if let data=obstacleJSON.data(using:.utf8),let boxes=try? JSONSerialization.jsonObject(with:data){m.send("studio_obstacles",["boxes":boxes])}else{m.message="JSON ostacoli non valido."}}.disabled(!canConfigure)
     }
    }
   }else{ProgressView("Caricamento progetto…")}
  }.onAppear{loadFields()}
   .onChange(of:m.studio?.model.source_hash){_,_ in loadFields()}
 }
 func loadFields(){if let s=m.studio{projectName=s.name;tip=s.tip;x=String(format:"%g",s.tool[0]*1000);y=String(format:"%g",s.tool[1]*1000);z=String(format:"%g",s.tool[2]*1000);if let d=try? JSONEncoder().encode(s.obstacles){obstacleJSON=String(data:d,encoding:.utf8) ?? "[]"}}}
}

struct ProgramPanel:View {
 @ObservedObject var m:Regia
 @State private var blockJSON="[]"
 @State private var kind="pose";@State private var pose=0;@State private var seconds="1";@State private var sensor="";@State private var expected="1";@State private var count="2";@State private var previewPose=0;@State private var fraction=0.0
 func add(){
  guard let s=m.studio else{return};var b=ProgramBlock(kind:kind,name:kind+" "+String(s.blocks.count+1))
  switch kind {
   case "pose":b.index=pose;b.name="Posa \(pose+1)"
   case "grip":b.command=seconds == "chiudi" ? "chiudi" : "apri";b.name=b.command ?? "Pinza"
   case "wait":guard let n=Double(seconds) else{return};b.seconds=n;b.name="Attendi \(seconds) s"
   case "sensor":guard let n=Double(expected),let t=Double(seconds) else{return};b.sensor=sensor;b.expected=n;b.timeout=t;b.name="Attendi "+sensor
   case "repeat":b.start=0;b.count=Int(count) ?? 2;b.name="Ripeti dal primo blocco"
   default:b.name=seconds
  };m.blocks(s.blocks+[b])
 }
 var body:some View {
  Panel(title:"Programmi · blocchi e anteprima") {
   if let s=m.studio {
    HStack {
     Picker("Aggiungi",selection:$kind){RText("Posa").tag("pose");RText("Pinza").tag("grip");RText("Attesa").tag("wait");RText("Sensore").tag("sensor");RText("Ripeti").tag("repeat");RText("Nota").tag("note")}.frame(width:190)
     if kind == "pose"{Picker("Posa",selection:$pose){ForEach(Array(m.state.sequence.enumerated()),id:\.offset){i,p in RText(p.name).tag(i)}}}
     else if kind == "repeat"{TextField("Ripetizioni",text:$count).frame(width:95)}
     else {TextField(kind == "grip" ? "apri / chiudi" : "Secondi / nota",text:$seconds).frame(width:140)}
     if kind == "sensor"{TextField("Nome sensore",text:$sensor);TextField("Valore",text:$expected).frame(width:75)}
     Button("Aggiungi blocco"){add()}.disabled(s.program_running || !m.idle)
    }
    ForEach(Array(s.blocks.enumerated()),id:\.offset){i,b in
     HStack {
      Toggle("Blocco \(i+1)",isOn:Binding(get:{b.enabled},set:{var a=s.blocks;a[i].enabled=$0;m.blocks(a)})).labelsHidden()
      RText("\(i+1). "+b.name).frame(maxWidth:.infinity,alignment:.leading)
      Button("↑"){var a=s.blocks;a.swapAt(i,i-1);m.blocks(a)}.disabled(i==0)
      Button("↓"){var a=s.blocks;a.swapAt(i,i+1);m.blocks(a)}.disabled(i==s.blocks.count-1)
      Button("Elimina"){var a=s.blocks;a.remove(at:i);m.blocks(a)}
     }.padding(8).background(s.program_index==i ? RobotTheme.lime.opacity(0.15) : RobotTheme.black,in:RoundedRectangle(cornerRadius:8)).disabled(s.program_running || !m.idle)
    }
    HStack{Button("Esegui programma…"){m.confirmStudioProgram=true}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.state.home || !m.idle || s.blocks.isEmpty);Button("Interrompi programma"){m.send("studio_cancel")}.disabled(!s.program_running);Spacer();RText(s.program_running ? "In esecuzione" : "Da fermo").robotCaption()}
    if !s.program_error.isEmpty{RText(s.program_error).foregroundStyle(RobotTheme.stop)}
    DisclosureGroup("Editor dei blocchi JSON") {
     TextEditor(text:$blockJSON).font(.system(size:12,design:.monospaced)).frame(height:180)
     HStack{Button("Rileggi blocchi"){let e=JSONEncoder();e.outputFormatting=[.prettyPrinted,.sortedKeys];if let d=try? e.encode(s.blocks){blockJSON=String(data:d,encoding:.utf8) ?? "[]"}};Button("Valida e salva blocchi"){if let d=blockJSON.data(using:.utf8),let b=try? JSONDecoder().decode([ProgramBlock].self,from:d){m.blocks(b)}else{m.message="Formato dei blocchi non valido."}}}.disabled(s.program_running || !m.idle)
    }
    RText("Esecuzione tramite il controllore esistente, un asse alla volta, con controlli dei limiti e ritorno sul percorso registrato. Ripetizioni limitate; un sensore scaduto o mancante interrompe il programma.").robotCaption().foregroundStyle(RobotTheme.secondary)
    if !m.state.sequence.isEmpty {
     Divider();HStack{RText("Anteprima pose");Picker("Tappa",selection:$previewPose){ForEach(Array(m.state.sequence.filter{$0.isEnabled}.enumerated()),id:\.offset){i,p in RText(p.name).tag(i)}};Slider(value:$fraction,in:0...1).onChange(of:fraction){_,v in m.send("studio_sequence",["index":previewPose,"fraction":v])};RText("\(fraction*100,specifier:"%.0f")%")}
    }
   }
  }
 }
}
struct TelemetryPanel:View {
 @ObservedObject var m:Regia
 @State private var sensorName="contatto_pinza";@State private var sensorKind="digital"
 var body:some View {
  Panel(title:"Diagnostica · registrazioni e sensori") {
   if let s=m.studio {
    HStack {RText("Origine: "+(m.state.mode=="demo" ? "virtuale" : "impulsi comandati · senza encoder")).robotCaption();Spacer();Toggle("Registra sessione",isOn:Binding(get:{s.recording},set:{m.send("studio_record",["enabled":$0])}));RText("\(s.sample_count) campioni");Button("Esporta CSV…"){m.studioFile("studio_export_csv")}.disabled(s.sample_count==0)}
    if !s.telemetry.isEmpty {
     Chart {ForEach(Array(s.telemetry.enumerated()),id:\.offset){_,p in ForEach(0..<min(6,p.values.count),id:\.self){i in LineMark(x:.value("Tempo",Date(timeIntervalSince1970:p.time)),y:.value("Gradi",p.values[i])).foregroundStyle(by:.value("Giunto","J\(i+1)"))}}}.frame(height:150)
    }
    HStack {TextField("Nome ingresso",text:$sensorName);Picker("Tipo",selection:$sensorKind){ForEach(["digital","distance","force","encoder","temperature"],id:\.self){RText($0)}};Button("Definisci sensore"){m.send("studio_sensor_add",["name":sensorName,"kind":sensorKind])}}
    ForEach(s.sensors){sensor in
     HStack {RText(sensor.name).bold();RText(sensor.kind).robotCaption();RText(sensor.valueText).monospacedDigit();RText(sensor.source).robotCaption().foregroundStyle(RobotTheme.secondary);Spacer();RText(sensor.age<0 ? "Nessun dato" : "\(sensor.age,specifier:"%.1f") s").robotCaption();if m.state.mode=="demo"{Button("Simula 0"){m.send("studio_sensor_value",["name":sensor.name,"value":0])};Button("Simula 1"){m.send("studio_sensor_value",["name":sensor.name,"value":1])}}}
    }
    RText("I dati sintetici sono marcati come simulati e non soddisfano attese di sensori sul robot reale. Gli encoder e gli altri sensori richiedono un adattatore connesso e dati aggiornati.").robotCaption().foregroundStyle(RobotTheme.secondary)
   }
  }
 }
}

struct StudioGuide:View {
 @Environment(\.dismiss) private var dismiss
 private var source:String{guard let url=Bundle.main.resourceURL?.appendingPathComponent(AppLanguage.current == .english ? "docs/STUDIO.en.md" : "docs/STUDIO.md") else{return "Guida non disponibile."};return (try? String(contentsOf:url,encoding:.utf8)) ?? "Guida non disponibile."}
 var body:some View {VStack(alignment:.leading){HStack{RText("Guida Robot Console Studio").font(.title2.bold());Spacer();Button("Chiudi"){dismiss()}};Divider();ScrollView{RText(source).font(.system(size:13)).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading).padding(8)}}.padding(24).frame(width:820,height:650).background(RobotTheme.surface).foregroundStyle(RobotTheme.text)}
}
