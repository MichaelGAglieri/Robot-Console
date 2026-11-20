// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI

struct WorkFrameState:Decodable,Identifiable,Equatable {
 let id:String;let name:String;let parent:String;let xyz:[Double];let rpy:[Double];let matrix:[Double]
}
struct CartesianTargetState:Decodable,Identifiable,Equatable {
 let id:String;let name:String;let frame_id:String;let xyz:[Double];let rpy:[Double];let matrix:[Double];let xyz_base:[Double]
}

private struct ScenePoseFields:View {
 @Binding var xyz:[String]
 @Binding var rpy:[String]
 var body:some View {
  VStack(alignment:.leading,spacing:8) {
   HStack(spacing:10) {
    ForEach(0..<3,id:\.self){i in
     VStack(alignment:.leading,spacing:4) {
      RText(["X · mm","Y · mm","Z · mm"][i]).robotCaption()
      TextField("0",text:$xyz[i]).accessibilityLabel(["X · mm","Y · mm","Z · mm"][i])
     }.frame(maxWidth:.infinity)
    }
   }
   HStack(spacing:10) {
    ForEach(0..<3,id:\.self){i in
     VStack(alignment:.leading,spacing:4) {
      RText(["Roll · °","Pitch · °","Yaw · °"][i]).robotCaption()
      TextField("0",text:$rpy[i]).accessibilityLabel(["Roll · °","Pitch · °","Yaw · °"][i])
     }.frame(maxWidth:.infinity)
    }
   }
  }
 }
}

struct WorkSceneEditor:View {
 @ObservedObject var m:Regia
 @State private var kind="frame"
 @State private var frameID=""
 @State private var frameName=""
 @State private var frameXYZ=["0","0","0"]
 @State private var frameRPY=["0","0","0"]
 @State private var targetID=""
 @State private var targetName=""
 @State private var targetFrame="base"
 @State private var targetXYZ=["0","0","0"]
 @State private var targetRPY=["0","0","0"]
 @State private var confirmDelete=false
 @State private var deletingKind=""
 @State private var deletingID=""
 var canEdit:Bool{m.idle && !m.firmware.busy && m.studio?.program_running != true && m.studio?.movej_preview?.running != true}
 var work:[WorkFrameState]{m.studio?.work_frames ?? []}
 var targets:[CartesianTargetState]{m.studio?.cartesian_targets ?? []}
 func number(_ value:String)->Double? {
  guard let value=InputDraft.number(value),value.isFinite else{return nil}
  return value
 }
 func pose(_ xyz:[String],_ rpy:[String])->[String:Any]? {
  let values=(xyz+rpy).map{number($0)}
  guard values.count==6,values.allSatisfy({$0 != nil}) else {
   m.message=T("Completa tutte le coordinate e gli angoli con numeri validi.");return nil
  }
  return ["xyz":values.prefix(3).map{$0!/1000},"rpy":values.suffix(3).map{$0!*Double.pi/180}]
 }
 func loadFrame() {
  if let f=work.first(where:{$0.id==frameID}) {
   frameName=f.name;frameXYZ=f.xyz.map{String(format:"%.6g",$0*1000)};frameRPY=f.rpy.map{String(format:"%.6g",$0*180/Double.pi)}
  }else{frameName="";frameXYZ=["0","0","0"];frameRPY=["0","0","0"]}
 }
 func loadTarget() {
  if let t=targets.first(where:{$0.id==targetID}) {
   targetName=t.name;targetFrame=t.frame_id;targetXYZ=t.xyz.map{String(format:"%.6g",$0*1000)};targetRPY=t.rpy.map{String(format:"%.6g",$0*180/Double.pi)}
   m.send("studio_target_select",["id":t.id])
  }else{targetName="";targetFrame="base";targetXYZ=["0","0","0"];targetRPY=["0","0","0"]}
 }
 func reconcileForms() {
  if !frameID.isEmpty && !work.contains(where:{$0.id==frameID}){frameID=""}
  if !targetID.isEmpty && !targets.contains(where:{$0.id==targetID}){targetID=""}
  if !work.contains(where:{$0.id==targetFrame}){targetFrame="base"}
 }
 func saveFrame() {
  guard canEdit,var data=pose(frameXYZ,frameRPY) else{return}
  let name=frameName.trimmingCharacters(in:.whitespacesAndNewlines)
  data["id"]=frameID;data["name"]=name
  m.send("studio_frame_save",data){ok in if ok,let f=work.first(where:{$0.name==name}){frameID=f.id}}
 }
 func saveTarget() {
  guard canEdit,var data=pose(targetXYZ,targetRPY) else{return}
  let name=targetName.trimmingCharacters(in:.whitespacesAndNewlines)
  data["id"]=targetID;data["name"]=name;data["frame_id"]=targetFrame
  m.send("studio_target_save",data){ok in if ok,let t=targets.first(where:{$0.name==name}){targetID=t.id}}
 }
 func requestDelete(_ category:String,_ id:String){deletingKind=category;deletingID=id;confirmDelete=true}
 var body:some View {
  VStack(alignment:.leading,spacing:14) {
   RText("Riferimenti e target sono geometrici: non avviano movimenti. Puoi modificarli da fermo senza perdere il riferimento del controllore.").robotCaption().foregroundStyle(RobotTheme.secondary)
   ScrollView(.vertical) {
    VStack(alignment:.leading,spacing:9) {
     ForEach(work){f in
      VStack(alignment:.leading,spacing:7) {
       if f.id=="base" {
        Label{RText("Base robot").font(.subheadline.weight(.semibold))}icon:{Image(systemName:"scope")}
       }else{
        Button{kind="frame";frameID=f.id}label:{Label{Text(f.name)}icon:{Image(systemName:"folder")}}
         .accessibilityLabel(T("Modifica riferimento ")+f.name)
       }
       ForEach(targets.filter{$0.frame_id==f.id}){t in
        Button{kind="target";if targetID==t.id{m.send("studio_target_select",["id":t.id])}else{targetID=t.id}}label:{
         HStack{Image(systemName:m.studio?.selected_target==t.id ? "target" : "circle");Text(t.name);Spacer();Text(String(format:"%.1f · %.1f · %.1f mm",t.xyz_base[0]*1000,t.xyz_base[1]*1000,t.xyz_base[2]*1000)).robotCaption(mono:true)}
        }.padding(.leading,f.id=="base" ? 16 : 30).accessibilityLabel(T("Seleziona target ")+t.name)
       }
      }.padding(.leading,f.id=="base" ? 0 : 16)
     }
     if targets.isEmpty{RText("Nessun target: crea un riferimento o salva un punto nella base.").robotCaption().foregroundStyle(RobotTheme.secondary)}
    }.frame(maxWidth:.infinity,alignment:.leading).padding(10)
   }.frame(height:min(280,CGFloat(max(3,work.count+targets.count))*47))
    .background(RobotTheme.black,in:RoundedRectangle(cornerRadius:10))
   RText("TCP attivo: usa il link utensile e l’offset già configurati in Giunti, mapping hardware e TCP.").robotCaption().foregroundStyle(RobotTheme.secondary)
   Picker("Modifica scena",selection:$kind){RText("Riferimento di lavoro").tag("frame");RText("Target locale").tag("target")}.pickerStyle(.segmented).tint(RobotTheme.control)
   if kind=="frame" {
    Picker("Riferimento da modificare",selection:$frameID){RText("Nuovo riferimento").tag("");ForEach(work.filter{$0.id != "base"}){f in Text(f.name).tag(f.id)}}
    TextField("Nome riferimento",text:$frameName).accessibilityLabel("Nome riferimento")
    RText("Posizione e rotazione rispetto alla base robot").robotCaption().foregroundStyle(RobotTheme.secondary)
    ScenePoseFields(xyz:$frameXYZ,rpy:$frameRPY).disabled(!canEdit)
    HStack {
     Button("Salva riferimento"){saveFrame()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!canEdit)
     Button("Elimina riferimento…"){requestDelete("frame",frameID)}.disabled(!canEdit || frameID.isEmpty)
    }
   }else{
    Picker("Target da modificare",selection:$targetID){RText("Nuovo target").tag("");ForEach(targets){t in Text(t.name).tag(t.id)}}
    TextField("Nome target",text:$targetName).accessibilityLabel("Nome target")
    Picker("Riferimento del target",selection:$targetFrame){ForEach(work){f in Text(f.id=="base" ? T("Base robot") : f.name).tag(f.id)}}.disabled(!canEdit)
    RText("Coordinate locali: cambiare riferimento conserva questi numeri e può spostare il punto nella base.").robotCaption().foregroundStyle(RobotTheme.secondary)
    ScenePoseFields(xyz:$targetXYZ,rpy:$targetRPY).disabled(!canEdit)
    HStack {
     Button("Salva target"){saveTarget()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!canEdit)
     Button("Elimina target…"){requestDelete("target",targetID)}.disabled(!canEdit || targetID.isEmpty)
    }
   }
   if let t=targets.first(where:{$0.id==m.studio?.selected_target}) {
    Text(String(format:T("Target nella base: X %.2f · Y %.2f · Z %.2f mm"),t.xyz_base[0]*1000,t.xyz_base[1]*1000,t.xyz_base[2]*1000)).monospacedDigit().foregroundStyle(RobotTheme.accentText)
   }
   RText("In 3D: assi X rosso, Y verde, Z blu; target selezionato arancione. Premi Adatta vista per inquadrare la scena.").robotCaption().foregroundStyle(RobotTheme.secondary)
   RText("RPY: Rz(yaw) · Ry(pitch) · Rx(roll). L’orientamento è salvato e visualizzato; l’IK attuale impone solo la posizione. Nessun MoveJ o MoveL aggiunto.").robotCaption().foregroundStyle(RobotTheme.secondary)
  }.padding(.top,10)
   .onChange(of:frameID){_,_ in loadFrame()}
   .onChange(of:targetID){_,_ in loadTarget()}
   .onChange(of:m.studio?.work_frames){_,_ in reconcileForms()}
   .onChange(of:m.studio?.cartesian_targets){_,_ in reconcileForms()}
   .onChange(of:m.studio?.model.source_hash){_,_ in frameID="";targetID="";loadFrame();loadTarget()}
   .alert("Eliminare elemento della scena?",isPresented:$confirmDelete){
    Button("Elimina",role:.destructive){m.send(deletingKind=="frame" ? "studio_frame_delete" : "studio_target_delete",["id":deletingID])}
    Button("Annulla",role:.cancel){}
   }message:{RText("Un riferimento usato da target non può essere eliminato. L’operazione non modifica pose articolari o programmi.")}
 }
}
