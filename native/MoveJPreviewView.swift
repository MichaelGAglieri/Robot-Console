// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI

struct MoveJSample:Decodable {let time:Double;let q:[Double];let tcp:[Double]}
struct ProgramCallFrame:Decodable,Equatable {let function:String;let definition:Int;let call_index:Int;let iteration:String}
struct MoveJStage:Decodable {
 let kind:String;let name:String;let block_index:Int;let start_time:Double;let end_time:Double;let duration:Double
 let axes:[Int]?;let peaks:[Double]?;let speed:Double?;let call_path:[ProgramCallFrame]?
}
struct MoveLInfo:Decodable {
 let length_mm:Double;let segments:Int;let max_deviation_mm:Double;let end_error_mm:Double;let tolerance_mm:Double;let orientation:String
 let axis_error_deg:Double?;let roll_error_deg:Double?;let singular:Bool
}
struct MoveJMeasure:Decodable {let index:Int;let kind:String;let planned:Double;let actual:Double}
struct MoveJPlan:Decodable {
 let controller_context:String?;let id:String;let starts:[Double];let targets:[Double];let stages:[MoveJStage];let samples:[MoveJSample]
 let duration:Double;let sample_count:Int;let source:String;let preview_only:Bool;let movel:MoveLInfo?;let program:ProgramSummary?
}
struct MoveJPlayback:Decodable {
 let plan:MoveJPlan?;let running:Bool;let elapsed:Double;let error:String;let valid:Bool;let visual_active:Bool;let grip:String;let stage:Int
 let executing:Bool?;let exec_stage:Int?;let exec_error:String?;let exec_done:Bool?;let exec_measured:[MoveJMeasure]?
 let problem:ProgramProblem?;let step_mode:Bool?;let step_waiting:Bool?
 let exec_block:Int?;let exec_next_block:Int?;let exec_name:String?;let exec_next_name:String?;let exec_decisions:[ProgramTaken]?
}

struct MoveJPreviewPanel:View {
 @ObservedObject var m:Regia
 @State private var source="joints"
 @State private var angles=Array(repeating:"0",count:6)
 @State private var poseIndex=0
 @State private var returnToStart=false
 @State private var cursor=0.0
 @State private var scrubbing=false
 @State private var confirmExecute=false
 @State private var lineFrame="base"
 @State private var linePoint=["250","50","100"]
 @State private var lineOrientation="keep"
 @State private var lineTolerance=0.5
 @State private var lineTarget=""
 var playback:MoveJPlayback?{m.studio?.movej_preview}
 var plan:MoveJPlan?{playback?.plan}
 var executing:Bool{playback?.executing==true}
 var ready:Bool{m.idle && !m.firmware.busy && m.studio?.program_running != true && !executing}
 var canExecute:Bool{ready && m.state.home && playback?.valid==true && playback?.running != true && m.speedEdits.isEmpty}
 func discard(){if plan != nil{m.send("studio_movej_clear")}}
 func prepare(){
  var request:[String:Any]=["source":source,"return_to_start":returnToStart]
  if source=="joints" {
   let numbers=angles.compactMap{InputDraft.number($0)}
   guard numbers.count==6,numbers.allSatisfy({$0.isFinite}) else{m.message="Inserisci sei angoli validi in gradi.";return}
   request["targets"]=numbers
  }
  if source=="pose"{request["index"]=poseIndex}
  if source=="movel" {
   let values=linePoint.compactMap{InputDraft.number($0)}.filter{$0.isFinite}
   guard values.count==3 else{m.message=T("Inserisci X, Y e Z in millimetri.");return}
   request["target"]=values.map{$0/1000};request["frame"]=lineFrame;request["orientation"]=lineOrientation;request["tolerance"]=lineTolerance
  }
  m.send("studio_movej_plan",request)
 }
 var body:some View {
  Panel(title:"MoveJ · anteprima del percorso") {
   VStack(alignment:.leading,spacing:12) {
    RText("Pianifica un movimento articolare simultaneo, osserva il TCP in 3D, poi eseguilo con lo stesso piano. Le velocità sono quelle di Muovi e osserva.").robotCaption().foregroundStyle(RobotTheme.secondary)
    Picker("Sorgente MoveJ",selection:$source){RText("Angoli assoluti").tag("joints");RText("Giunti Studio").tag("studio");RText("Posa salvata").tag("pose");RText("Programma").tag("program");RText("Retta MoveL").tag("movel")}.pickerStyle(.segmented).tint(RobotTheme.control).disabled(playback?.running==true)
    if source=="joints" {
     LazyVGrid(columns:Array(repeating:GridItem(.flexible()),count:3),spacing:8) {
      ForEach(0..<6,id:\.self){i in
       HStack{Text("J\(i+1) · °").font(.caption.monospacedDigit());TextField("0",text:$angles[i]).accessibilityLabel("MoveJ J\(i+1)").disabled(playback?.running==true)}
      }
     }
     Button("Usa angoli attuali"){angles=m.state.pos.map{String(format:"%.2f",$0)}}.disabled(playback?.running==true)
    }else if source=="movel" {
     RText("La punta va in linea retta dalla posizione comandata al punto scelto. Il percorso è diviso nei movimenti simultanei necessari per restare entro la tolleranza; tra un tratto e l’altro il braccio si ferma brevemente.").robotCaption().foregroundStyle(RobotTheme.secondary)
     HStack {
      Picker(selection:$lineFrame){RText("Base robot").tag("base");ForEach((m.studio?.work_frames ?? []).filter{$0.id != "base"}){f in Text(f.name).tag(f.id)}}label:{RText("Riferimento")}.frame(width:260)
      RText("Arrivo · mm")
      ForEach(0..<3,id:\.self){i in TextField(["X","Y","Z"][i],text:$linePoint[i]).frame(width:80).accessibilityLabel(T("Arrivo MoveL ")+["X","Y","Z"][i])}
     }.disabled(playback?.running==true)
     HStack {
      Picker(selection:$lineOrientation){RText("Mantieni").tag("keep");RText("Libera").tag("free")}label:{RText("Pinza")}.frame(width:200)
      Picker(selection:$lineTolerance){ForEach([0.1,0.2,0.5,1,2],id:\.self){Text(String(format:"%g mm",$0)).tag($0)}}label:{RText("Tolleranza")}.frame(width:210)
      Button{if let r=m.studio?.cartesian?.readout?.frames.first(where:{$0.id==lineFrame}),r.xyz.count==3{linePoint=r.xyz.map{String(format:"%.1f",$0)}}}label:{RText("Usa punto attuale")}
     }.disabled(playback?.running==true)
     if !(m.studio?.cartesian_targets ?? []).isEmpty {
      Picker(selection:$lineTarget){RText("Scegli un target").tag("");ForEach(m.studio?.cartesian_targets ?? []){t in Text(t.name).tag(t.id)}}label:{RText("Usa target salvato")}.frame(width:360)
       .onChange(of:lineTarget){_,id in if let t=(m.studio?.cartesian_targets ?? []).first(where:{$0.id==id}){lineFrame=t.frame_id;linePoint=t.xyz.map{String(format:"%.1f",$0*1000)}}}
     }
    }else if source=="pose" {
     Picker("Posa da pianificare",selection:$poseIndex){ForEach(Array(m.state.sequence.enumerated()),id:\.offset){i,p in Text("\(i+1) · \(p.name)").tag(i)}}.disabled(playback?.running==true)
    }
    Toggle("Includi ritorno al punto iniziale",isOn:$returnToStart).disabled(playback?.running==true)
    HStack {
     Button("Pianifica MoveJ"){prepare()}.disabled(!ready || playback?.running==true || !m.speedEdits.isEmpty)
     if plan != nil{Button("Cancella piano"){m.send("studio_movej_clear")}}
     Spacer()
     Button{confirmExecute=true}label:{RText("Esegui MoveJ…")}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!canExecute)
     if executing{Button{m.send("stop")}label:{RText("STOP")}.buttonStyle(RobotButtonStyle(danger:true))}
    }
    if !ready && !executing{RText("Attendi il controllore fermo per pianificare o eseguire MoveJ.").robotCaption().foregroundStyle(.orange)}
    if plan != nil && !m.state.home && !executing{RText("Conferma HOME per eseguire il piano; l’anteprima resta disponibile.").robotCaption().foregroundStyle(.orange)}
    if executing,let p=plan{Text(String(format:T("Esecuzione MoveJ · tratto %lld di %lld"),min(max(playback?.exec_stage ?? 0,0)+1,p.stages.count),p.stages.count)).font(.headline).foregroundStyle(RobotTheme.accentText)}
    if playback?.exec_done==true{RText(m.state.mode=="demo" ? "MoveJ eseguito in Anteprima." : "MoveJ eseguito: DONE dalla Mega per ogni gruppo; posizione non misurata.").foregroundStyle(RobotTheme.accentText)}
    if let error=playback?.exec_error,!error.isEmpty{Text(T("MoveJ interrotto: ")+T(error)+(error.hasSuffix(".") ? " " : ". ")+T("Nessuna ripresa automatica: verifica il braccio e ristabilisci HOME.")).robotCaption().foregroundStyle(RobotTheme.stop).textSelection(.enabled)}
    if !m.speedEdits.isEmpty{RText("Applica le velocità modificate prima di pianificare.").robotCaption().foregroundStyle(.orange)}
    if let p=plan,let line=p.movel {
     VStack(alignment:.leading,spacing:3) {
      Text(String(format:T("Retta di %.1f mm · %lld tratti · deviazione massima %.2f mm (tolleranza %.2f mm) · arrivo entro %.2f mm"),line.length_mm,line.segments,line.max_deviation_mm,line.tolerance_mm,line.end_error_mm)).font(.subheadline.weight(.semibold))
      if let a=line.axis_error_deg{Text(String(format:T("Orientamento mantenuto: scarto asse massimo %.2f°, rotazione %.2f°"),a,line.roll_error_deg ?? 0)).robotCaption().foregroundStyle(a > 0.5 ? Color.orange : RobotTheme.secondary)}
      else{RText("Orientamento libero: la pinza ruota come serve per seguire la retta.").robotCaption().foregroundStyle(RobotTheme.secondary)}
      if line.singular{RText("Vicino a una singolarità: alcune direzioni richiedono grandi rotazioni dei giunti.").robotCaption().foregroundStyle(.orange)}
     }
    }
    if let measured=playback?.exec_measured,!measured.isEmpty,!executing {
     let moves=measured.filter{$0.kind=="movej"}
     Text(String(format:T("Durata misurata %.2f s · stimata %.2f s · scarto medio per tratto %.2f s"),measured.reduce(0){$0+$1.actual},measured.reduce(0){$0+$1.planned},moves.isEmpty ? 0 : moves.reduce(0){$0+$1.actual-$1.planned}/Double(moves.count))).robotCaption(mono:true).foregroundStyle(RobotTheme.secondary)
    }
    if let p=plan {
     Divider()
     HStack{RText("Durata stimata: \(p.duration,specifier:"%.2f") s").monospacedDigit();Spacer();RText("\(p.sample_count) campioni · passo massimo 1°").robotCaption().foregroundStyle(RobotTheme.secondary)}
     Slider(value:$cursor,in:0...max(p.duration,0.001),onEditingChanged:{editing in
      scrubbing=editing
      if editing{m.send("studio_movej_stop")}else{m.send("studio_movej_seek",["id":p.id,"elapsed":min(cursor,p.duration)])}
     }).accessibilityLabel("Tempo MoveJ").disabled(playback?.valid != true)
     HStack {
      Button("Riproduci anteprima"){m.send("studio_movej_play",["id":p.id])}.disabled(!ready || playback?.valid != true || playback?.running==true)
      Button("Arresta anteprima"){m.send("studio_movej_stop")}.buttonStyle(RobotButtonStyle(danger:true)).disabled(playback?.running != true)
      Spacer();Text(String(format:"%.2f / %.2f s",cursor,p.duration)).font(.caption.monospacedDigit())
     }
     ScrollView {
      VStack(alignment:.leading,spacing:6) {
       ForEach(Array(p.stages.enumerated()),id:\.offset){i,stage in
        HStack(alignment:.top){Text("\(i+1)").monospacedDigit().foregroundStyle(RobotTheme.secondary);VStack(alignment:.leading,spacing:2){RText(stage.name);Text(String(format:"%.2f–%.2f s",stage.start_time,stage.end_time)).font(.caption.monospacedDigit()).foregroundStyle(RobotTheme.secondary)
         if let axes=stage.axes,let peaks=stage.peaks,!axes.isEmpty{Text(axes.map{axis in "J\(axis+1) \(String(format:"%.2f",peaks[axis])) °/s"}.joined(separator:" · ")).font(.caption.monospacedDigit())}
        };Spacer();if executing && playback?.exec_stage==i{Image(systemName:"bolt.fill").foregroundStyle(RobotTheme.accentText)}else if playback?.running==true && playback?.stage==i{Image(systemName:"play.fill").foregroundStyle(RobotTheme.accentText)}}.padding(6).frame(maxWidth:.infinity,alignment:.leading).background(RobotTheme.surface,in:RoundedRectangle(cornerRadius:6))
       }
      }
     }.frame(height:min(190,CGFloat(p.stages.count)*74))
    }
    if let error=playback?.error,!error.isEmpty{RText(error).robotCaption().foregroundStyle(RobotTheme.stop).textSelection(.enabled)}
    RText("Partenza dagli angoli del controllore. Traccia campionata: non verifica collisioni complete delle mesh. Le sequenze collegano direttamente le pose abilitate, senza ripercorrere la cronologia.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
   }
  }.alert("Eseguire il piano MoveJ?",isPresented:$confirmExecute){
    Button{if let p=plan{m.send("studio_movej_execute",["id":p.id,"confirmed":true])}}label:{RText("Esegui MoveJ")}
    Button(role:.cancel){}label:{RText("Annulla")}
   }message:{
    if let p=plan{Text(String(format:T(m.state.mode=="demo" ? "Anteprima: %lld tratti, durata stimata %.1f s. Esecuzione con il controllore simulato." : "ROBOT REALE: %lld tratti, durata stimata %.1f s. Il braccio si muove con movimenti simultanei, uno per tratto, e attende il DONE della Mega. Tieni pronto lo STOP."),p.stages.count,p.duration))}
   }
   .onChange(of:source){_,_ in discard()}.onChange(of:angles){_,_ in discard()}.onChange(of:poseIndex){_,_ in discard()}.onChange(of:returnToStart){_,_ in discard()}.onChange(of:linePoint){_,_ in discard()}.onChange(of:lineFrame){_,_ in discard()}.onChange(of:lineOrientation){_,_ in discard()}.onChange(of:lineTolerance){_,_ in discard()}
   .onChange(of:playback?.elapsed){_,value in if !scrubbing{cursor=value ?? 0}}
   .onChange(of:plan?.id){_,_ in cursor=0}
 }
}
