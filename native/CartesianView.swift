// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI

struct CartesianFrameReadout:Decodable,Identifiable {let id:String;let name:String;let xyz:[Double];let axis:[Double]}
struct CartesianReadout:Decodable {let frames:[CartesianFrameReadout];let sigma:Double;let singular:Bool}
struct IKJointValue:Decodable {let name:String;let deg:Double}
struct IKSolution:Decodable {
 let labels:[String:String];let change_deg:Double;let position_error_mm:Double;let axis_error_deg:Double?;let roll_error_deg:Double?
 let joints:[IKJointValue];let at_limit:[String];let singular:Bool
}
struct IKReport:Decodable {
 let kind:String;let label:String;let ok:Bool;let applied:Bool;let chosen:Int;let reason:String
 let solutions:[IKSolution];let collisions:[String];let singular:Bool;let message:String;let locked:[String]
}
struct CartesianState:Decodable {let readout:CartesianReadout?;let report:IKReport?}

struct CartesianPanel:View {
 @ObservedObject var m:Regia
 @State private var frame="base"
 @State private var step=5.0
 @State private var turn=5.0
 @State private var keepAxis=true
 @State private var point=["250","0","100"]
 @State private var orientation="down"
 @State private var targetID=""
 @State private var targetOrientation="axis"
 var cartesian:CartesianState?{m.studio?.cartesian}
 var frames:[CartesianFrameReadout]{cartesian?.readout?.frames ?? []}
 var targets:[CartesianTargetState]{m.studio?.cartesian_targets ?? []}
 var ready:Bool{m.idle && !m.firmware.busy && m.studio?.program_running != true && m.studio?.movej_preview?.running != true}
 func number(_ value:String)->Double? {
  guard let value=InputDraft.number(value),value.isFinite else{return nil}
  return value
 }
 // Avoid printing "-0.0" for values that round to zero.
 func clean(_ value:Double,_ step:Double=0.005)->Double{abs(value)<step ? 0 : value}
 func jog(_ axis:Int,_ sign:Double,rotate:Bool=false) {
  var translation=[0.0,0,0];var rotation=[0.0,0,0]
  if rotate{rotation[axis]=sign*turn}else{translation[axis]=sign*step}
  m.send("studio_jog",["frame":frame,"translation":translation,"rotation":rotation,"keep_axis":keepAxis])
 }
 func solvePoint() {
  let values=point.compactMap{number($0)}
  guard values.count==3 else{m.message=T("Inserisci X, Y e Z in millimetri.");return}
  m.send("studio_ik",["target":values.map{$0/1000},"frame":frame,"orientation":orientation])
 }
 func branch(_ s:IKSolution)->String {
  var parts:[String]=[]
  if let reach=s.labels["reach"]{parts.append(T(reach=="front" ? "Braccio in avanti" : "Braccio all’indietro"))}
  if let elbow=s.labels["elbow"]{parts.append(T("gomito")+" "+elbow)}
  return parts.joined(separator:" · ")
 }
 var body:some View {
  Panel(title:"IK e jog cartesiano · anteprima") {
   VStack(alignment:.leading,spacing:12) {
    RText("Sposta la punta in X, Y, Z o chiedi un punto: la console calcola gli angoli dei giunti. Aggiorna solo il modello 3D, nessun comando ai motori.").robotCaption().foregroundStyle(RobotTheme.secondary)
    Picker(selection:$frame){
     RText("Base robot").tag("base")
     ForEach(frames.filter{$0.id != "base"}){f in Text(f.name).tag(f.id)}
     RText("Utensile").tag("tool")
    }label:{RText("Riferimento")}
    if let r=frames.first(where:{$0.id==(frame=="tool" ? "base" : frame)}),r.xyz.count==3,r.axis.count==3 {
     HStack {
      Text(String(format:"X %.1f · Y %.1f · Z %.1f mm",clean(r.xyz[0],0.05),clean(r.xyz[1],0.05),clean(r.xyz[2],0.05))).font(.system(size:14,weight:.semibold,design:.monospaced))
      Spacer()
      HStack(spacing:4){RText("Asse pinza");Text(String(format:"%.2f · %.2f · %.2f",clean(r.axis[0]),clean(r.axis[1]),clean(r.axis[2]))).monospacedDigit()}.robotCaption(mono:true)
     }
     if frame=="tool"{RText("Lettura nella base robot; il jog nell’utensile segue gli assi della pinza.").robotCaption().foregroundStyle(RobotTheme.secondary)}
    }
    if cartesian?.readout?.singular == true {RText("Vicino a una singolarità: alcune direzioni richiedono grandi rotazioni dei giunti.").robotCaption().foregroundStyle(.orange)}
    Divider()
    RText("Jog cartesiano").font(.headline)
    HStack {
     Picker(selection:$step){ForEach([0.5,1,5,10,25],id:\.self){Text(String(format:"%g mm",$0)).tag($0)}}label:{RText("Passo")}.frame(width:190)
     Toggle(isOn:$keepAxis){RText("Mantieni direzione utensile")}
    }
    HStack {
     ForEach(0..<3,id:\.self){i in
      let name=["X","Y","Z"][i]
      Button{jog(i,-1)}label:{Text("−"+name).monospaced()}.accessibilityLabel(T("Jog meno ")+name)
      Button{jog(i,1)}label:{Text("+"+name).monospaced()}.accessibilityLabel(T("Jog più ")+name)
     }
    }.disabled(!ready)
    HStack {
     Picker(selection:$turn){ForEach([1.0,5,15],id:\.self){Text(String(format:"%g°",$0)).tag($0)}}label:{RText("Rotazione")}.frame(width:190)
     ForEach(0..<3,id:\.self){i in
      let name=["Rx","Ry","Rz"][i]
      Button{jog(i,-1,rotate:true)}label:{Text("−"+name).monospaced()}.accessibilityLabel(T("Jog meno ")+name)
      Button{jog(i,1,rotate:true)}label:{Text("+"+name).monospaced()}.accessibilityLabel(T("Jog più ")+name)
     }
    }.disabled(!ready)
    RText("Le rotazioni avvengono attorno alla punta. Con cinque assi alcune inclinazioni non sono realizzabili: il passo viene rifiutato e l’anteprima resta invariata.").robotCaption().foregroundStyle(RobotTheme.secondary)
    Divider()
    RText("IK verso un punto").font(.headline)
    HStack {
     RText("Punto · mm")
     ForEach(0..<3,id:\.self){i in TextField(["X","Y","Z"][i],text:$point[i]).frame(width:80).accessibilityLabel(T("Punto IK ")+["X","Y","Z"][i])}
     Picker(selection:$orientation){RText("Libera").tag("free");RText("Verso −Z del riferimento").tag("down");RText("Mantieni attuale").tag("keep")}label:{RText("Pinza")}.frame(width:280)
     Button{solvePoint()}label:{RText("Calcola IK")}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!ready || frame=="tool")
    }
    if frame=="tool"{RText("Per l’IK scegli la base o un riferimento di lavoro.").robotCaption().foregroundStyle(.orange)}
    if !targets.isEmpty {
     HStack {
      Picker(selection:$targetID){RText("Scegli un target").tag("");ForEach(targets){t in Text(t.name).tag(t.id)}}label:{RText("Target salvato")}
      Picker(selection:$targetOrientation){RText("Solo posizione").tag("position");RText("Posizione e asse Z").tag("axis");RText("Asse Z e rotazione").tag("full")}label:{RText("Orientamento")}.frame(width:300)
      Button{m.send("studio_ik_target",["id":targetID,"orientation":targetOrientation])}label:{RText("Calcola IK sul target")}.disabled(!ready || targetID.isEmpty)
     }
     RText("Nei target l’asse Z è la direzione della pinza (uscente dalla flangia) e l’asse X la sua rotazione.").robotCaption().foregroundStyle(RobotTheme.secondary)
    }
    if let report=cartesian?.report {
     Divider()
     RText(report.message).foregroundStyle(report.ok ? RobotTheme.text : RobotTheme.stop).textSelection(.enabled)
     if report.singular{RText("Vicino a una singolarità: alcune direzioni richiedono grandi rotazioni dei giunti.").robotCaption().foregroundStyle(.orange)}
     if !report.collisions.isEmpty{Text(T("Interferenza con gli ostacoli: ")+report.collisions.joined(separator:", ")).robotCaption().foregroundStyle(.orange)}
     ForEach(Array(report.solutions.enumerated()),id:\.offset){i,s in
      HStack(alignment:.top) {
       Text("\(i+1)").monospacedDigit().foregroundStyle(RobotTheme.secondary)
       VStack(alignment:.leading,spacing:3) {
        Text(branch(s)).font(.subheadline.weight(.semibold))
        Text(s.joints.map{String(format:"%@ %.1f°",$0.name,$0.deg)}.joined(separator:" · ")).robotCaption(mono:true)
        HStack(spacing:4) {
         Text(String(format:T("variazione massima %.1f°"),s.change_deg))
         if let a=s.axis_error_deg{Text("·");Text(String(format:T("scarto asse %.2f°"),a))}
         if let r=s.roll_error_deg{Text("·");Text(String(format:T("scarto rotazione %.2f°"),r))}
        }.robotCaption().foregroundStyle(RobotTheme.secondary)
        if !s.at_limit.isEmpty{Text(T("Al limite: ")+s.at_limit.joined(separator:", ")).robotCaption().foregroundStyle(.orange)}
       }
       Spacer()
       if report.chosen==i{RText("In anteprima").robotCaption().foregroundStyle(RobotTheme.accentText)}
       else{Button{m.send("studio_ik_choose",["index":i])}label:{RText("Usa")}.disabled(!ready)}
      }.padding(6).frame(maxWidth:.infinity,alignment:.leading).background(RobotTheme.surface,in:RoundedRectangle(cornerRadius:6))
     }
    }
    RText("Solo anteprima: il calcolo usa le quote del modello, non misure del robot. Per muovere il braccio usa «Esegui target visualizzato…»: stesso MoveJ condiviso, con conferma.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
   }
  }.onChange(of:targets.map{$0.id}){_,ids in if !targetID.isEmpty && !ids.contains(targetID){targetID=""}}
   .onChange(of:frames.map{$0.id}){_,ids in if frame != "tool" && !ids.contains(frame){frame="base"}}
 }
}
