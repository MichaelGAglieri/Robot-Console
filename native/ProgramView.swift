// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI

struct ProgramBlockTime:Decodable {let index:Int;let start_time:Double;let duration:Double;let stages:Int}
struct ProgramLine:Decodable {let block_index:Int;let length_mm:Double;let segments:Int;let max_deviation_mm:Double;let end_error_mm:Double;let axis_error_deg:Double?}
struct ProgramDecision:Decodable {let block_index:Int;let condition:String;let preview:Bool;let occurrences:Int}
struct ProgramSummary:Decodable {let blocks:[ProgramBlockTime];let lines:[ProgramLine];let cartesian:Bool;let decisions:[ProgramDecision]?;let branches:Int?;let checked_samples:Int?}
struct ProgramTaken:Decodable {let block_index:Int;let result:Bool}

/// Ripeti/Se … Fine: matching blocks and indentation, as program_lang.structure on the bridge.
enum ProgramStructure {
 static func opens(_ kind:String)->Bool{kind=="loop" || kind=="if" || kind=="function"}
 static func depths(_ blocks:[ProgramBlock])->[Int] {
  var level=0;return blocks.map{b in
   if b.kind=="end" || b.kind=="else"{level=max(0,level-1)}
   let here=level;if opens(b.kind) || b.kind=="else"{level+=1};return here
  }
 }
 /// Indices of the else/end blocks that belong to the opening block at `index`.
 static func markers(_ blocks:[ProgramBlock],_ index:Int)->[Int] {
  var level=0;var result:[Int]=[]
  for i in index+1..<blocks.count {
   let kind=blocks[i].kind
   if opens(kind){level+=1}
   else if kind=="else" && level==0 {result.append(i)}
   else if kind=="end"{if level==0{result.append(i);break};level-=1}
  }
  return result
 }
}
struct ProgramProblem:Decodable {let block:Int;let `where`:String;let detail:String;let angles:[Double]}

/// Offline programs: MoveJ/MoveL instructions planned once; preview, validation and execution share that plan.
struct ProgramPanel:View {
 @ObservedObject var m:Regia
 @State private var blockJSON="[]"
 @State private var kind="movej"
 @State private var destination="target"
 @State private var targetID=""
 @State private var above="60"
 @State private var orientation="axis"
 @State private var lineOrientation="keep"
 @State private var tolerance=0.5
 @State private var speed=100.0
 @State private var name=""
 @State private var pose=0;@State private var seconds="1";@State private var gripCommand="chiudi";@State private var sensor="";@State private var expected="1";@State private var count="2";@State private var note=""
 @State private var previewPose=0;@State private var fraction=0.0
 @State private var cursor=0.0;@State private var scrubbing=false
 @State private var confirmRun=false;@State private var confirmStep=false
 @State private var selected:Int?=nil
 @State private var times="3";@State private var loopVariable="";@State private var condition="";@State private var withElse=false;@State private var variable="";@State private var value="0"
 @State private var outputName="";@State private var outputValue=true
 @State private var functionName="";@State private var parameterText="";@State private var calledFunction="";@State private var argumentDraft:[String:String]=[:];@State private var resultVariable="";@State private var returnValue="";@State private var editing:Int?=nil
 @State private var scenario:[String:Bool]=[:]

 var studio:StudioState?{m.studio}
 var playback:MoveJPlayback?{studio?.movej_preview}
 /// Only program plans belong here; MoveJ panel plans stay in their own panel.
 var plan:MoveJPlan?{playback?.plan?.program != nil ? playback?.plan : nil}
 var motion:Bool{plan != nil || (studio?.blocks ?? []).contains{$0.enabled && ["movej","movel","loop","if","set","output","function","call","return"].contains($0.kind)}}
 var executing:Bool{playback?.executing==true && plan != nil}
 var ready:Bool{m.idle && !m.firmware.busy && studio?.program_running != true && playback?.executing != true}
 var canPreview:Bool{plan != nil && playback?.valid==true && ready}
 var canExecute:Bool{canPreview && m.state.home && playback?.running != true && m.speedEdits.isEmpty}
 var functions:[ProgramBlock]{(studio?.blocks ?? []).filter{$0.kind=="function"}}
 var chosenFunction:ProgramBlock?{functions.first{$0.function==calledFunction}}
 var targets:[CartesianTargetState]{studio?.cartesian_targets ?? []}
 var activeBlock:Int? {
  if executing {
   let block=playback?.step_waiting==true ? playback?.exec_next_block : playback?.exec_block
   return (block ?? -1)>=0 ? block : nil
  }
  if let p=plan,playback?.visual_active==true,let i=playback?.stage,p.stages.indices.contains(i){return p.stages[i].block_index}
  if let s=studio,s.program_index>=0{return s.program_index}
  return nil
 }

 func number(_ text:String)->Double?{InputDraft.number(text)}
 func add(){
  guard let s=studio else{return}
  var b=ProgramBlock(kind:kind,name:"")
  // «Z sopra» accepts a number or an expression with variables, e.g. 60 + strato*20.
  if (kind=="movej" && destination=="target") || kind=="movel"{guard !above.trimmingCharacters(in:.whitespaces).isEmpty else{m.message=T("Completa la quota Z prima di aggiungere il movimento.");return}}
  let z=number(above) ?? 0;let targetName=targets.first{$0.id==targetID}?.name ?? ""
  let expression=number(above)==nil && !above.trimmingCharacters(in:.whitespaces).isEmpty
  let zExpression:[String]?=expression ? ["","",above.trimmingCharacters(in:.whitespaces)] : nil
  let height=expression ? " Z "+above : (z==0 ? "" : String(format:" %+.0f mm",z))
  switch kind {
   case "movej":
    b.to=destination;b.speed=speed
    switch destination {
     case "target":
      guard !targetID.isEmpty else{m.message=T("Scegli un target della scena.");return}
      b.target=targetID;b.offset=[0,0,z];b.offset_expr=zExpression;b.orientation=orientation;b.name="MoveJ → "+targetName+height
     case "pose":b.index=pose;b.name="MoveJ → "+(m.state.sequence.indices.contains(pose) ? m.state.sequence[pose].name : "posa")
     case "joints":b.angles=m.state.pos;b.name="MoveJ → "+m.state.pos.prefix(5).map{String(format:"%.0f°",$0)}.joined(separator:" ")
     default:b.name="MoveJ → HOME"
    }
   case "movel":
    guard !targetID.isEmpty else{m.message=T("Scegli un target della scena.");return}
    b.to="target";b.target=targetID;b.offset=[0,0,z];b.offset_expr=zExpression;b.orientation=lineOrientation;b.tolerance=tolerance;b.speed=speed;b.name="MoveL → "+targetName+height
   case "pose":b.index=pose;b.name=m.state.sequence.indices.contains(pose) ? m.state.sequence[pose].name : "Posa \(pose+1)"
   case "grip":b.command=gripCommand;b.name=gripCommand=="chiudi" ? "Chiudi pinza" : "Apri pinza"
   case "wait":guard let n=number(seconds) else{m.message=T("Secondi non validi.");return};b.seconds=n;b.name="Attendi \(seconds) s"
   case "sensor":guard let n=number(expected),let t=number(seconds) else{m.message=T("Completa valore e timeout del sensore con numeri validi.");return};b.sensor=sensor;b.expected=n;b.timeout=t;b.name="Attendi "+sensor
   case "output":
    guard !outputName.isEmpty,let timeout=number(seconds) else{m.message=T("Scegli un’uscita e un timeout valido.");return}
    b.output=outputName;b.output_value=outputValue;b.timeout=timeout;b.name=T("Uscita")+" "+outputName+" = "+(outputValue ? "1" : "0")
   case "function":
    b.function=functionName.trimmingCharacters(in:.whitespaces);b.parameters=parameterText.trimmingCharacters(in:.whitespaces).isEmpty ? [] : parameterText.split(separator:",",omittingEmptySubsequences:false).map{$0.trimmingCharacters(in:.whitespaces)};b.name=T("Funzione")+" "+(b.function ?? "")
   case "call":
    guard let definition=chosenFunction else{m.message=T("Scegli una funzione definita nel progetto.");return}
    b.function=calledFunction;b.arguments=Dictionary(uniqueKeysWithValues:(definition.parameters ?? []).map{($0,argumentDraft[$0] ?? "")});b.result=resultVariable.trimmingCharacters(in:.whitespaces).isEmpty ? nil : resultVariable.trimmingCharacters(in:.whitespaces);b.name=T("Richiama")+" "+calledFunction
   case "return":b.value=returnValue.trimmingCharacters(in:.whitespaces);b.name=T("Restituisci")+(b.value?.isEmpty==false ? " "+(b.value ?? "") : "")
   case "repeat":guard let n=InputDraft.integer(count,range:1...100) else{m.message=T("Ripetizioni: inserisci un intero da 1 a 100.");return};b.start=0;b.count=n;b.name="Ripeti dal primo blocco"
   case "loop":b.times=times;b.variable=loopVariable.isEmpty ? nil : loopVariable;b.name="Ripeti "+times+" volte"
   case "if":guard !condition.isEmpty else{m.message=T("Scrivi la condizione, per esempio presente == 1.");return};b.condition=condition;b.name="Se "+condition
   case "set":guard !variable.isEmpty else{m.message=T("Scrivi il nome della variabile.");return};b.variable=variable;b.value=value;b.name=variable+" = "+value
   default:b.name=note.isEmpty ? "Nota" : note
  }
  if !name.trimmingCharacters(in:.whitespaces).isEmpty{b.name=name}
  // Insert after the selected row: right after a Ripeti/Se opening, the instruction goes inside it.
  var list=s.blocks
  if let i=editing,list.indices.contains(i) {
   let previous=list[i];list[i]=b
   if previous.kind=="function",previous.function != b.function {
    for j in list.indices where list[j].kind=="call" && list[j].function==previous.function{list[j].function=b.function}
   }
   m.blocks(list);editing=nil;selected=i;name="";return
  }
  let at=kind=="function" ? list.count : min((selected ?? list.count-1)+1,list.count)
  var added=[b]
  if ProgramStructure.opens(b.kind) {
   if b.kind=="if" && withElse{added.append(ProgramBlock(kind:"else",name:"Altrimenti"))}
   added.append(ProgramBlock(kind:"end",name:b.kind=="function" ? T("Fine funzione") : (b.kind=="loop" ? "Fine ripeti" : "Fine se")))
  }
  list.insert(contentsOf:added,at:at);m.blocks(list);name="";selected=at
 }
 func remove(_ s:StudioState,_ i:Int) {
  // Removing a Ripeti/Se keeps its body and removes its Altrimenti/Fine.
  var list=s.blocks
  if list[i].kind=="function",let end=ProgramStructure.markers(list,i).last {
   list.removeSubrange(i...end);m.blocks(list);selected=nil;editing=nil;return
  }
  let indices=([i]+(ProgramStructure.opens(list[i].kind) ? ProgramStructure.markers(list,i) : [])).sorted(by:>)
  for k in indices{list.remove(at:k)};m.blocks(list);selected=nil
 }
 func edit(_ b:ProgramBlock,_ index:Int){
  editing=index;selected=index;kind=b.kind;name=b.name
  if b.kind=="function"{functionName=b.function ?? "";parameterText=(b.parameters ?? []).joined(separator:", ")}
  else{calledFunction=b.function ?? "";argumentDraft=b.arguments ?? [:];resultVariable=b.result ?? ""}
 }
 func replan(_ choices:[String:Bool]){m.send("studio_program_plan",["scenario":choices])}
 func offsetText(_ b:ProgramBlock)->String? {
  let o=b.offset ?? [0,0,0];let e=b.offset_expr ?? ["","",""]
  let parts=(0..<3).compactMap{k->String? in
   if e.indices.contains(k),!e[k].isEmpty{return ["X","Y","Z"][k]+" = "+e[k]+" mm"}
   return o.indices.contains(k) && o[k] != 0 ? String(format:"%@ %+.0f mm",["X","Y","Z"][k],o[k]) : nil
  }
  return parts.isEmpty ? nil : parts.joined(separator:" ")
 }
 func detail(_ b:ProgramBlock)->String {
  let pace=String(format:"%.0f%%",b.speed ?? 100)+" "+T("velocità")
  let target=targets.first{$0.id==b.target}.map{T("target")+" "+$0.name} ?? T("target mancante")
  switch b.kind {
   case "movej":
    switch b.to ?? "" {
     case "target":return ([target,offsetText(b),b.orientation=="position" ? T("solo posizione") : T("asse del target"),pace].compactMap{$0}).joined(separator:" · ")
     case "pose":return T("angoli della posa")+" · "+pace
     case "joints":return (b.angles ?? []).prefix(6).enumerated().map{String(format:"J%d %.1f°",$0.offset+1,$0.element)}.joined(separator:" ")+" · "+pace
     default:return T("tutti i giunti a 0°")+" · "+pace
    }
   case "movel":return ([T("linea retta"),target,offsetText(b),b.orientation=="free" ? T("pinza libera") : T("pinza mantenuta"),String(format:"± %.2g mm",b.tolerance ?? 0.5),pace].compactMap{$0}).joined(separator:" · ")
   case "pose":return motion ? T("MoveJ agli angoli della posa") : T("percorso insegnato")
   case "grip":return b.command=="chiudi" ? T("chiude · 1,5 s") : T("apre · 1,5 s")
   case "wait":return String(format:"%.1f s",b.seconds ?? 0)
   case "sensor":return String(format:T("attende %@ = %@, al massimo %@ s"),b.sensor ?? "",String(format:"%g",b.expected ?? 1),String(format:"%g",b.timeout ?? 10))
   case "output":return String(format:T("%@ = %@ · conferma entro %@ s"),b.output ?? "",b.output_value==true ? "1" : "0",String(format:"%g",b.timeout ?? 10))
   case "function":return (b.function ?? "")+"("+(b.parameters ?? []).joined(separator:", ")+") · "+T("corpo eseguito solo dai richiami")
   case "call":return (b.function ?? "")+"("+(b.arguments ?? [:]).sorted{$0.key<$1.key}.map{$0.key+" = "+$0.value}.joined(separator:", ")+")"+(b.result.map{" → "+$0} ?? "")
   case "return":return b.value?.isEmpty==false ? T("valore restituito")+" "+(b.value ?? "") : T("rientra nel chiamante senza valore")
   case "loop":return (b.variable.map{String(format:T("%@ volte · contatore %@ da 0"),b.times ?? "",$0)} ?? String(format:T("%@ volte"),b.times ?? ""))
   case "if":return T("condizione")+" "+(b.condition ?? "")
   case "else":return T("se la condizione è falsa")
   case "end":return T("fine del blocco")
   case "set":return T("variabile")+" "+(b.variable ?? "")+" = "+(b.value ?? "")
   case "repeat":return String(format:T("%lld volte dal blocco %lld"),b.count ?? 2,(b.start ?? 0)+1)
   default:return T("nota nel registro")
  }
 }
 func icon(_ kind:String)->String {
  ["movej":"arrow.triangle.turn.up.right.diamond","movel":"line.diagonal.arrow","pose":"figure.arms.open","grip":"hand.raised","wait":"timer","sensor":"sensor","output":"switch.2","function":"curlybraces","call":"arrow.turn.down.right","return":"arrow.uturn.backward","repeat":"repeat","note":"note.text","loop":"repeat","if":"arrow.triangle.branch","else":"arrow.uturn.right","end":"arrow.turn.down.left","set":"x.squareroot"][kind] ?? "square"
 }
 func boundaries(_ p:MoveJPlan)->[Double] {
  var result:[Double]=[0]
  for (i,stage) in p.stages.enumerated() where i>0 && (stage.block_index != p.stages[i-1].block_index || stage.call_path != p.stages[i-1].call_path) {result.append(stage.start_time)}
  result.append(p.duration);return result
 }
 func step(_ forward:Bool) {
  guard let p=plan else{return}
  let b=boundaries(p);let t=forward ? (b.first{$0>cursor+0.001} ?? p.duration) : (b.last{$0<cursor-0.001} ?? 0)
  cursor=t;m.send("studio_movej_seek",["id":p.id,"elapsed":t])
 }
 func runMessage(_ stepwise:Bool)->String {
  guard let p=plan,let program=p.program else{return ""}
  var text=String(format:T(m.state.mode=="demo" ? "Anteprima: %lld istruzioni, durata stimata %.1f s, con il controllore simulato." : "ROBOT REALE: %lld istruzioni, durata stimata %.1f s. Il braccio esegue esattamente il piano mostrato, un movimento simultaneo per tratto. Tieni pronto lo STOP."),program.blocks.count,p.duration)
  if let branches=program.branches,branches>1{text+=" "+String(format:T("Il percorso dipende dai sensori: segue uno dei %lld rami verificati."),branches)}
  if stepwise{text+=" "+T("Si ferma prima di ogni istruzione: premi «Istruzione successiva» per proseguire.")}
  return text
 }

 @ViewBuilder func editor(_ s:StudioState)->some View {
  VStack(alignment:.leading,spacing:8) {
   HStack {
    Picker(selection:$kind){RText("MoveJ").tag("movej");RText("MoveL").tag("movel");RText("Pinza").tag("grip");RText("Attesa").tag("wait");RText("Posa registrata").tag("pose");RText("Attesa sensore").tag("sensor");RText("Uscita digitale").tag("output");RText("Ripeti N volte").tag("loop");RText("Se (condizione)").tag("if");RText("Variabile").tag("set");RText("Funzione").tag("function");RText("Richiama funzione").tag("call");RText("Restituisci").tag("return");RText("Nota").tag("note")}label:{RText("Istruzione")}.fixedSize().disabled(editing != nil)
    TextField(T("Nome (facoltativo)"),text:$name).frame(maxWidth:220)
    Spacer()
    Button{add()}label:{Label{RText(editing==nil ? "Aggiungi istruzione" : "Salva modifica")}icon:{Image(systemName:"plus")}}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(s.program_running || !ready)
   }
   if editing != nil{Button{editing=nil;name=""}label:{RText("Annulla modifica")}.disabled(!ready)}
   // Destination on one line, options on the next: fits a narrow panel without clipping.
   HStack(spacing:14) {
    switch kind {
     case "movej":
      Picker(selection:$destination){RText("Target della scena").tag("target");RText("HOME").tag("home");RText("Posa salvata").tag("pose");RText("Angoli attuali").tag("joints")}label:{RText("Verso")}.fixedSize()
      if destination=="target"{targetFields}
      if destination=="pose"{posePicker}
     case "movel":targetFields
     case "pose":posePicker
     case "grip":Picker(selection:$gripCommand){RText("Chiudi").tag("chiudi");RText("Apri").tag("apri")}label:{RText("Pinza")}.pickerStyle(.segmented).frame(width:220)
     case "wait":RText("Secondi");TextField("1",text:$seconds).frame(width:70)
     case "sensor":TextField(T("Nome sensore"),text:$sensor).frame(width:160);TextField(T("Valore"),text:$expected).frame(width:60);RText("Timeout s");TextField("10",text:$seconds).frame(width:60)
     case "output":
      Picker(selection:$outputName){RText("Scegli uscita").tag("");ForEach(s.io?.outputs ?? []){o in Text(o.name).tag(o.name)}}label:{RText("Uscita digitale")}.frame(width:200)
      Toggle(isOn:$outputValue){RText("Valore 1")};RText("Timeout s");TextField("10",text:$seconds).frame(width:60)
     case "function":
      TextField(T("Nome funzione, es. prendi"),text:$functionName).frame(width:200).accessibilityLabel(T("Nome funzione"))
      TextField(T("Parametri separati da virgole"),text:$parameterText).frame(minWidth:180,maxWidth:320).accessibilityLabel(T("Parametri funzione"))
     case "call":
      Picker(selection:$calledFunction){RText("Scegli funzione").tag("");ForEach(functions,id:\.function){f in Text(f.function ?? "").tag(f.function ?? "")}}label:{RText("Funzione")}.frame(width:220)
      TextField(T("Variabile risultato (facoltativa)"),text:$resultVariable).frame(width:210)
     case "return":TextField(T("Espressione restituita (facoltativa)"),text:$returnValue).frame(minWidth:220,maxWidth:440)
     case "repeat":RText("Ripetizioni");TextField("2",text:$count).frame(width:60)
     case "loop":RText("Volte");TextField("3",text:$times).frame(width:90);RText("Contatore");TextField(T("facoltativo, es. strato"),text:$loopVariable).frame(width:170)
     case "if":RText("Condizione");TextField(T("es. presente == 1"),text:$condition).frame(minWidth:180,maxWidth:300);Toggle(isOn:$withElse){RText("con Altrimenti")}
     case "set":TextField(T("nome, es. passo"),text:$variable).frame(width:150);Text("=");TextField("0",text:$value).frame(minWidth:120,maxWidth:240)
     default:TextField(T("Testo della nota"),text:$note)
    }
    Spacer(minLength:0)
   }
   if kind=="call",let definition=chosenFunction {
    LazyVGrid(columns:[GridItem(.adaptive(minimum:190,maximum:300))],alignment:.leading){
     ForEach(definition.parameters ?? [],id:\.self){parameter in
      HStack{Text(parameter).robotCaption();TextField(T("Valore o espressione"),text:Binding(get:{argumentDraft[parameter] ?? ""},set:{argumentDraft[parameter]=$0})).accessibilityLabel(T("Argomento")+" "+parameter)}
     }
    }
   }
   if ["function","call","return"].contains(kind){RText("Definisci la funzione una volta, seleziona il suo inizio e aggiungi il corpo. Richiamala passando i parametri; le variabili sono locali. Restituisci è facoltativo. Le nuove definizioni sono aggiunte in fondo, al livello principale.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)}
   if kind=="movej" || kind=="movel" {
    HStack(spacing:14) {
     if kind=="movej" && destination=="target"{Picker(selection:$orientation){RText("Asse del target").tag("axis");RText("Solo posizione").tag("position")}label:{RText("Pinza")}.fixedSize()}
     if kind=="movel" {
      Picker(selection:$lineOrientation){RText("Mantieni").tag("keep");RText("Libera").tag("free")}label:{RText("Pinza")}.fixedSize()
      Picker(selection:$tolerance){ForEach([0.1,0.2,0.5,1,2],id:\.self){Text(String(format:"%g mm",$0)).tag($0)}}label:{RText("Tolleranza")}.fixedSize()
     }
     Picker(selection:$speed){ForEach([10.0,20,30,40,50,60,70,80,90,100],id:\.self){Text(String(format:"%.0f%%",$0)).tag($0)}}label:{RText("Velocità")}.fixedSize().help(T("Percentuale delle velocità dei giunti di Muovi e osserva; minimo 1 °/s per asse."))
     Spacer(minLength:0)
    }
   }
   if !s.blocks.isEmpty {
    RText(selected == nil ? "La nuova istruzione va in fondo. Seleziona una riga per inserirla dopo; subito dopo «Ripeti» o «Se» finisce al loro interno." : "La nuova istruzione va dopo la riga selezionata.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
   }
   if ["loop","if","set"].contains(kind) {
    RText("Espressioni: numeri, variabili, sensori (solo nelle condizioni), operazioni + - * /, confronti == != < <= > >=, and or not. Le quote «Z sopra» accettano anche espressioni come 60 + strato*20.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
   }
   if (kind=="movej" && destination=="target") || kind=="movel", targets.isEmpty {
    RText("Crea prima i target nella scena di lavoro (pannello Target cartesiani): punto e orientamento della pinza.").robotCaption().foregroundStyle(RobotTheme.warning)
   }
  }.padding(10).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:8))
 }
 var targetFields:some View {
  Group {
   Picker(selection:$targetID){RText("Scegli").tag("");ForEach(targets){t in Text(t.name).tag(t.id)}}label:{RText("Target")}.fixedSize()
   HStack(spacing:6){RText("Z sopra · mm");TextField("0",text:$above).frame(width:60).accessibilityLabel(T("Scostamento Z dal target in millimetri"))}
  }
 }
 var posePicker:some View {
  Picker(selection:$pose){ForEach(Array(m.state.sequence.enumerated()),id:\.offset){i,p in Text("\(i+1) · \(p.name)").tag(i)}}label:{RText("Posa")}.fixedSize()
 }

 func row(_ s:StudioState,_ i:Int,_ b:ProgramBlock)->some View {
  let active=activeBlock==i;let problem=playback?.problem?.block==i
  let time=plan?.program?.blocks.first{$0.index==i}
  let depth=ProgramStructure.depths(s.blocks)[i];let marker=b.kind=="else" || b.kind=="end"
  return HStack(spacing:10) {
   if depth>0{Rectangle().fill(RobotTheme.border).frame(width:CGFloat(depth)*18,height:1).opacity(0)}
   if marker{Toggle("",isOn:.constant(true)).labelsHidden().disabled(true).opacity(0)}
   else{Toggle("Blocco \(i+1)",isOn:Binding(get:{b.enabled},set:{var a=s.blocks;a[i].enabled=$0;m.blocks(a)})).labelsHidden()}
   Text("\(i+1)").font(.system(size:12,weight:.semibold).monospacedDigit()).foregroundStyle(RobotTheme.secondary).frame(width:22,alignment:.trailing)
   Image(systemName:icon(b.kind)).frame(width:20).foregroundStyle(b.kind=="movej" || b.kind=="movel" ? RobotTheme.accentText : RobotTheme.secondary)
   VStack(alignment:.leading,spacing:2) {
    RText(b.name).font(.system(size:13,weight:.semibold)).lineLimit(1)
    Text(detail(b)).robotCaption(small:true).foregroundStyle(RobotTheme.secondary).lineLimit(1)
   }.frame(maxWidth:.infinity,alignment:.leading).opacity(b.enabled ? 1 : 0.45)
   if let time{Text(String(format:"%.1f s",time.duration)).font(.caption.monospacedDigit()).foregroundStyle(RobotTheme.secondary)}
   if active{Image(systemName:executing ? (playback?.step_waiting==true ? "pause.fill" : "bolt.fill") : "play.fill").foregroundStyle(RobotTheme.accentText)}
   if problem{Image(systemName:"exclamationmark.triangle.fill").foregroundStyle(RobotTheme.stop)}
   if b.kind=="function" || b.kind=="call"{Button{edit(b,i)}label:{Image(systemName:"pencil")}.buttonStyle(RobotButtonStyle(compact:true)).help(T("Modifica funzione o richiamo"))}
   if b.kind=="movej" || b.kind=="movel" {
    Menu{ForEach([10,20,30,40,50,60,70,80,90,100],id:\.self){v in Button("\(v)%"){var a=s.blocks;a[i].speed=Double(v);m.blocks(a)}}}label:{Text(String(format:"%.0f%%",b.speed ?? 100)).font(.caption.monospacedDigit())}
     .menuStyle(.borderlessButton).fixedSize().help(T("Velocità rispetto a Muovi e osserva"))
   }
   Button{var a=s.blocks;a.swapAt(i,i-1);m.blocks(a)}label:{Image(systemName:"chevron.up")}.buttonStyle(RobotButtonStyle(compact:true)).disabled(i==0)
   Button{var a=s.blocks;a.swapAt(i,i+1);m.blocks(a)}label:{Image(systemName:"chevron.down")}.buttonStyle(RobotButtonStyle(compact:true)).disabled(i==s.blocks.count-1)
   Button{remove(s,i)}label:{Image(systemName:"trash")}.buttonStyle(RobotButtonStyle(compact:true)).help(T(b.kind=="function" ? "Elimina funzione e corpo; i richiami rimasti devono essere corretti" : (ProgramStructure.opens(b.kind) ? "Elimina il blocco e la sua Fine; le istruzioni interne restano" : "Elimina istruzione"))).disabled(marker)
  }
  .padding(.horizontal,10).padding(.vertical,marker ? 4 : 7)
  .background(active ? RobotTheme.lime.opacity(0.16) : (marker || ProgramStructure.opens(b.kind) ? RobotTheme.black : RobotTheme.surface),in:RoundedRectangle(cornerRadius:8))
  .overlay(RoundedRectangle(cornerRadius:8).strokeBorder(problem ? RobotTheme.stop : (active || selected==i ? RobotTheme.accentText : RobotTheme.border),lineWidth:problem || active || selected==i ? 1.5 : 1))
  .contentShape(Rectangle()).onTapGesture{selected = selected==i ? nil : i}
  .disabled(s.program_running || !ready || editing != nil)
 }

 @ViewBuilder func planSection(_ s:StudioState)->some View {
  VStack(alignment:.leading,spacing:10) {
   HStack(spacing:8) {
    Button{replan(scenario)}label:{Label{RText("Pianifica programma")}icon:{Image(systemName:"point.topleft.down.to.point.bottomright.curvepath")}}.disabled(!ready || playback?.running==true || !m.speedEdits.isEmpty)
    Button{if let p=plan{m.send("studio_movej_play",["id":p.id])}}label:{Label{RText("Anteprima")}icon:{Image(systemName:"play.fill")}}.disabled(!canPreview || playback?.running==true)
    Button{step(false)}label:{Image(systemName:"backward.end.fill")}.help(T("Istruzione precedente nell’anteprima")).disabled(!canPreview)
    Button{step(true)}label:{Image(systemName:"forward.end.fill")}.help(T("Istruzione successiva nell’anteprima")).disabled(!canPreview)
    Button{m.send("studio_movej_stop")}label:{Image(systemName:"stop.fill")}.help(T("Arresta anteprima")).disabled(playback?.running != true)
    Spacer()
    Button{confirmStep=true}label:{Label{RText("Passo passo…")}icon:{Image(systemName:"forward.frame")}}.disabled(!canExecute)
    Button{confirmRun=true}label:{RText("Esegui programma…")}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!canExecute)
   }
   if !m.speedEdits.isEmpty{RText("Applica le velocità modificate prima di pianificare.").robotCaption().foregroundStyle(RobotTheme.warning)}
   if plan != nil && !m.state.home && !executing{RText("Conferma HOME per eseguire il piano; l’anteprima resta disponibile.").robotCaption().foregroundStyle(RobotTheme.warning)}
   if let problem=playback?.problem {
    Label{VStack(alignment:.leading,spacing:2){RText(problem.where).font(.subheadline.weight(.semibold));RText(problem.detail).robotCaption();Text(problem.angles.prefix(6).enumerated().map{String(format:"J%d %.1f°",$0.offset+1,$0.element)}.joined(separator:" · ")).robotCaption(small:true,mono:true).foregroundStyle(RobotTheme.secondary)}}icon:{Image(systemName:"exclamationmark.triangle.fill")}
     .foregroundStyle(RobotTheme.stop).padding(8).frame(maxWidth:.infinity,alignment:.leading).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:8)).textSelection(.enabled)
   }
   if executing {
    // The branch actually run can differ from the preview path: show what the executor reports.
    let waiting=playback?.step_waiting==true;let block=(waiting ? playback?.exec_next_block : playback?.exec_block) ?? -1
    HStack {
     VStack(alignment:.leading,spacing:2) {
      if block>=0{Text(String(format:T(waiting ? "In attesa · prossima istruzione %lld" : "In esecuzione · istruzione %lld"),block+1)).font(.headline).foregroundStyle(RobotTheme.accentText)}
      let label=waiting ? (playback?.exec_next_name ?? (s.blocks.indices.contains(block) ? s.blocks[block].name : "")) : (playback?.exec_name ?? "")
      if !label.isEmpty{RText(label).robotCaption().foregroundStyle(RobotTheme.secondary)}
     }
     Spacer()
     if playback?.step_mode==true {
      Button{m.send("studio_program_step")}label:{Label{RText("Istruzione successiva")}icon:{Image(systemName:"forward.frame.fill")}}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(playback?.step_waiting != true)
      Button{m.send("studio_program_continue")}label:{RText("Continua fino alla fine")}
     }
     Button{m.send("stop")}label:{RText("STOP")}.buttonStyle(RobotButtonStyle(danger:true))
    }
   }
   if playback?.exec_done==true,plan != nil{RText(m.state.mode=="demo" ? "Programma eseguito in Anteprima." : "Programma eseguito: DONE dalla Mega per ogni tratto; posizione non misurata.").foregroundStyle(RobotTheme.accentText)}
   if let error=playback?.exec_error,!error.isEmpty,plan != nil{Text(T("Programma interrotto: ")+T(error)+(error.hasSuffix(".") ? " " : ". ")+T("Nessuna ripresa automatica: verifica il braccio e ristabilisci HOME.")).robotCaption().foregroundStyle(RobotTheme.stop).textSelection(.enabled)}
   if let p=plan,let program=p.program {
    HStack {
     Text(String(format:T("Durata stimata %.1f s · %lld istruzioni · %lld tratti"),p.duration,program.blocks.count,p.stages.filter{$0.kind=="movej" && !($0.axes ?? []).isEmpty}.count)).font(.subheadline.weight(.semibold).monospacedDigit())
     Spacer()
     Text(String(format:T("%lld campioni · passo massimo 1°"),p.sample_count)).robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
    }
    Slider(value:$cursor,in:0...max(p.duration,0.001),onEditingChanged:{editing in
     scrubbing=editing
     if editing{m.send("studio_movej_stop")}else{m.send("studio_movej_seek",["id":p.id,"elapsed":min(cursor,p.duration)])}
    }).accessibilityLabel(T("Tempo del programma")).disabled(playback?.valid != true)
    if let decisions=program.decisions,!decisions.isEmpty {
     VStack(alignment:.leading,spacing:6) {
      Text(String(format:T("Condizioni sui sensori: %lld rami verificati, %lld campioni. L’esecuzione segue i sensori, sempre su un ramo verificato; l’anteprima mostra il ramo scelto qui."),program.branches ?? 1,program.checked_samples ?? p.sample_count)).robotCaption().foregroundStyle(RobotTheme.secondary)
      ForEach(decisions,id:\.block_index){d in
       HStack {
        Image(systemName:"arrow.triangle.branch").foregroundStyle(RobotTheme.accentText)
        Text(String(format:T("Istruzione %lld · se %@"),d.block_index+1,d.condition)).font(.caption.monospaced())
        Spacer()
        Picker(selection:Binding(get:{d.preview},set:{v in scenario[String(d.block_index)]=v;replan(scenario)})){RText("Vero").tag(true);RText("Falso").tag(false)}label:{RText("Anteprima")}.pickerStyle(.segmented).frame(width:220).disabled(!ready || playback?.running==true)
       }
      }
     }.padding(8).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:8))
    }
    if let taken=playback?.exec_decisions,!taken.isEmpty {
     Text(T("Condizioni lette: ")+taken.suffix(6).map{String(format:T("istruzione %lld %@"),$0.block_index+1,T($0.result ? "vera" : "falsa"))}.joined(separator:" · ")).robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
    }
    ForEach(Array(program.lines.enumerated()),id:\.offset){_,line in
     Text(String(format:T("Istruzione %lld · retta di %.1f mm in %lld tratti · deviazione massima %.2f mm · arrivo entro %.2f mm"),line.block_index+1,line.length_mm,line.segments,line.max_deviation_mm,line.end_error_mm)).robotCaption(small:true,mono:true).foregroundStyle(RobotTheme.secondary)
    }
    if let measured=playback?.exec_measured,!measured.isEmpty,!executing {
     Text(String(format:T("Durata misurata %.2f s · stimata %.2f s"),measured.reduce(0){$0+$1.actual},measured.reduce(0){$0+$1.planned})).robotCaption(mono:true).foregroundStyle(RobotTheme.secondary)
    }
    if playback?.valid != true && playback?.exec_done != true && !executing,let error=playback?.error,!error.isEmpty{RText(error).robotCaption().foregroundStyle(RobotTheme.warning)}
   }
  }
 }

 var body:some View {
  Panel(title:"Programmi · istruzioni e anteprima") {
   if let s=studio {
    VStack(alignment:.leading,spacing:12) {
     HStack(spacing:8) {
      Image(systemName:motion ? "point.3.connected.trianglepath.dotted" : "list.bullet.rectangle").foregroundStyle(RobotTheme.accentText)
      RText(motion ? "Programma offline · movimenti, cicli e condizioni" : "Programma a pose registrate").font(.headline)
      Spacer()
      RText(s.program_running || executing ? "In esecuzione" : "Da fermo").robotCaption()
     }
     RText(motion ? "Ogni istruzione parte da dove finisce la precedente. Pianifica una volta: anteprima 3D, durata, validazione ed esecuzione usano lo stesso piano, controllato ogni grado. Le velocità sono una percentuale di quelle di Muovi e osserva." : "Le pose vengono raggiunte direttamente dalla posizione corrente. Aggiungi un’istruzione MoveJ o MoveL per pianificare il programma con anteprima ed esecuzione identiche.").robotCaption().foregroundStyle(RobotTheme.secondary)
     editor(s)
     if s.blocks.isEmpty {
      RText("Nessuna istruzione. Esempio di presa: MoveJ sopra il pezzo, MoveL giù, chiudi la pinza, MoveL su, MoveJ sopra il deposito, MoveL giù, apri, MoveL su.").robotCaption().foregroundStyle(RobotTheme.secondary)
     }
     VStack(spacing:6){ForEach(Array(s.blocks.enumerated()),id:\.offset){i,b in row(s,i,b)}}
     if motion {
      planSection(s)
     }else{
      HStack{Button("Esegui programma…"){m.confirmStudioProgram=true}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.state.home || !m.idle || s.blocks.isEmpty);Button("Interrompi programma"){m.send("studio_cancel")}.disabled(!s.program_running);Spacer()}
      if !s.program_error.isEmpty{RText(s.program_error).foregroundStyle(RobotTheme.stop)}
     }
     Divider()
     ValidationView(m:m)
     DisclosureGroup("Editor delle istruzioni JSON") {
      TextEditor(text:$blockJSON).font(.system(size:12,design:.monospaced)).frame(height:180)
      HStack{Button("Rileggi istruzioni"){let e=JSONEncoder();e.outputFormatting=[.prettyPrinted,.sortedKeys];if let d=try? e.encode(s.blocks){blockJSON=String(data:d,encoding:.utf8) ?? "[]"}};Button("Valida e salva istruzioni"){if let d=blockJSON.data(using:.utf8),let b=try? JSONDecoder().decode([ProgramBlock].self,from:d){m.blocks(b)}else{m.message="Formato dei blocchi non valido."}}}.disabled(s.program_running || !ready || editing != nil)
     }
     RText("Il programma è salvato nel progetto a ogni modifica. Le istruzioni posa collegano direttamente le destinazioni salvate e includono pausa e comando pinza.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
     if !motion && !m.state.sequence.isEmpty {
      Divider();HStack{RText("Anteprima pose");Picker("Tappa",selection:$previewPose){ForEach(Array(m.state.sequence.filter{$0.isEnabled}.enumerated()),id:\.offset){i,p in RText(p.name).tag(i)}};Slider(value:$fraction,in:0...1).onChange(of:fraction){_,v in m.send("studio_sequence",["index":previewPose,"fraction":v])};RText("\(fraction*100,specifier:"%.0f")%")}
     }
    }
   }
  }
  .alert("Eseguire il programma?",isPresented:$confirmRun){
   Button{if let p=plan{m.send("studio_program_execute",["id":p.id,"confirmed":true,"step":false])}}label:{RText("Esegui programma")}
   Button(role:.cancel){}label:{RText("Annulla")}
  }message:{Text(runMessage(false))}
  .alert("Eseguire passo passo?",isPresented:$confirmStep){
   Button{if let p=plan{m.send("studio_program_execute",["id":p.id,"confirmed":true,"step":true])}}label:{RText("Esegui passo passo")}
   Button(role:.cancel){}label:{RText("Annulla")}
  }message:{Text(runMessage(true))}
  .onChange(of:playback?.elapsed){_,value in if !scrubbing && plan != nil{cursor=value ?? 0}}
  .onChange(of:plan?.id){_,_ in cursor=0}
 }
}
