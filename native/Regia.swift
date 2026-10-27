// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import AppKit

struct RobotButtonStyle: ButtonStyle {
 var prominent = false
 var danger = false
 @Environment(\.isEnabled) private var enabled
 @Environment(\.colorScheme) private var scheme
 func makeBody(configuration:Configuration)->some View {
  let shape=RoundedRectangle(cornerRadius:9,style:.continuous)
  let fill=danger ? RobotTheme.stop : (prominent ? RobotTheme.buttonLime : RobotTheme.graphite)
  let foreground=danger ? RobotTheme.onStop : (prominent ? RobotTheme.ink : RobotTheme.text)
  let outline=danger ? RobotTheme.stop : (scheme == .light ? RobotTheme.secondary : RobotTheme.lime)
  return configuration.label
   .font(.system(size:13,weight:.semibold))
   .padding(.horizontal,14).padding(.vertical,9)
   .foregroundStyle(foreground.opacity(enabled ? 1 : (scheme == .light ? 0.70 : 0.45)))
   .background(shape.fill(fill.opacity(enabled ? (configuration.isPressed ? 0.82 : 1) : (scheme == .light ? 0.60 : 0.18))))
   .overlay(shape.strokeBorder(outline.opacity(enabled ? (scheme == .light ? 0.48 : 0.40) : (scheme == .light ? 0.24 : 0.10)),lineWidth:1))
   .contentShape(shape)
 }
}

struct Pose: Decodable { let name: String; let pos: [Double]; let dwell: Double; let grip: String?; let enabled: Bool?; let angles_edited: Bool?
 var isEnabled: Bool {enabled ?? true}
}
struct RobotEvent:Decodable,Identifiable {let id:Int;let time:Double;let mode:String;let text:String}
struct RobotState: Decodable {
 var robot_events:[RobotEvent]? = nil
 var mode: String; var connected: Bool; var home: Bool; var pos: [Double]
 var limits: [[Double]]; var trail: Int; var sequence: [Pose]; var events: [String]
 var busy: Bool; var playing: Bool; var paused: Bool; var error: String; var grip: String
 var hardware_ok:Bool? = nil
 var multi_axis:Bool? = nil
 var active_axes:[Int]? = nil
 var axis_speeds:[Double]? = nil
 var axis_control:Bool? = nil
 var drive_caps:[Bool]? = nil
 var drive_state:[Bool?]? = nil
 var pending_off:[Int]? = nil
 var active_axis:Int? = nil
 var axes_enabled:[Bool]? = nil
 var axes_available:[Bool]? = nil
 var preview_pos:[Double]? = nil
 var cycle: Int; var ports: [String]
 var can_undo: Bool; var max_speed: Double; var sequence_revision: Int; var identified: Bool; var firmware: String; var speed: Double; var speed_confirmed: Bool; var guidance: String
 static let empty = RobotState(mode:"demo",connected:false,home:false,pos:Array(repeating:0,count:6),limits:Array(repeating:[0,0],count:6),trail:0,sequence:[],events:[],busy:false,playing:false,paused:false,error:"",grip:"non comandata",cycle:0,ports:[],can_undo:false,max_speed:20,sequence_revision:0,identified:false,firmware:"",speed:5,speed_confirmed:false,guidance:"1 · Avvia Anteprima per provare senza hardware.")
}
struct MemoryEntry:Decodable,Identifiable {
 let id:Int; let time:String; let kind:String; let source:String; let text:String
}
struct LocalModel:Decodable,Identifiable {
 let name:String;let size:Int64
 var id:String {name}
}
struct OllamaState:Decodable {
 let installed:Bool;let running:Bool;let busy:Bool
 let status:String;let error:String;let version:String
 let models:[LocalModel];let loaded:[String];let selected:String
 static let empty=OllamaState(installed:false,running:false,busy:false,status:"Verifica Ollama…",error:"",version:"",models:[],loaded:[],selected:"")
}
struct FirmwareBoard:Decodable,Identifiable {
 let port:String;let name:String;let compatible:Bool
 var id:String {port}
}
struct FirmwareState:Decodable {
 let available:Bool;let tool:String;let busy:Bool;let phase:String
 let status:String;let error:String;let logs:[String];let boards:[FirmwareBoard];let success:Bool
 static let empty=FirmwareState(available:false,tool:"",busy:false,phase:"idle",status:"Verifica strumenti firmware…",error:"",logs:[],boards:[],success:false)
}
struct VoiceCommand:Decodable {let token:String;let summary:String;let text:String}
struct MultiPlan:Decodable {
 let valid:Bool;let error:String;let deltas:[Double];let targets:[Double];let axes:[Int]
 let requested:[Double];let effective:[Double];let peaks:[Double];let duration:Double;let budget_limited:Bool;let context:String
 static func invalid(_ error:String)->MultiPlan{MultiPlan(valid:false,error:error,deltas:[],targets:[],axes:[],requested:[],effective:[],peaks:[],duration:0,budget_limited:false,context:"")}
}
struct Reply: Decodable {
 let home_preview:HomePreview?
 let multi_plan:MultiPlan?
 let voice_command:VoiceCommand?
 let ros_health:ROSHealth?;let tools:ToolsState?;let local_api:LocalAPIState?;let firmware_workspace:FirmwareWorkspaceState?;let firmware_file:String?;let firmware_text:String?;let studio:StudioState?;let state:RobotState?;let error:String?;let ollama:OllamaState?;let firmware:FirmwareState?;let last_limits:[String:[[Double]]]?
 let chat:[MemoryEntry]?;let diary:[MemoryEntry]?
 let assistant_busy:Bool?;let ros_status:String?;let ros_event:String?
}
@MainActor final class Regia: ObservableObject {
 @Published var rosHealth:ROSHealth?
 @Published var tools:ToolsState?
 @Published var localAPI:LocalAPIState?
 @Published var homePreview:HomePreview?
 var homeRevision=0
 var homeRefresh:DispatchWorkItem?
 @Published var speedEdits:Set<Int>=[]
 @Published var showExtraJoints=false
 var controlAxes:[Int] {
  if showExtraJoints {return Array(0..<6)}
  let mapped=Set(studio?.mapping.values.filter{$0>=0 && $0<6} ?? [])
  return mapped.isEmpty ? Array(0..<5) : mapped.sorted()
 }
 @Published var multiMode=false
 @Published var multiDrafts=Array(repeating:"0",count:6)
 @Published var multiPlan:MultiPlan?
 var multiRevision=0
 var multiRefresh:DispatchWorkItem?
 @Published var voiceCommand:VoiceCommand?
 @Published var firmwareWorkspace:FirmwareWorkspaceState?
 @Published var firmwareFile="RegiaDemo.ino"
 @Published var firmwareText=""
 @Published var studio:StudioState?
 @Published var confirmStudioTarget=false
 @Published var confirmStudioProgram=false
 @Published var keyboardAxis=0
 var keyboardEnabled=true
 @Published var state = RobotState.empty
 @Published var message = "Avvio del controllo locale…"
 @Published var mode = "demo"
 @Published var port = ""
 @Published var step = 1.0
 @Published var stepText = "1"
 @Published var chatDraft = ""
 @Published var chat:[MemoryEntry]=[]
 @Published var diary:[MemoryEntry]=[]
 @Published var assistantBusy=false
 @Published var useLLM=false
 @Published var ollama=OllamaState.empty
 @Published var firmware=FirmwareState.empty
 @Published var firmwarePort=""
 @Published var confirmUpload=false
 @Published var confirmToolSetup=false
 @Published var firmwareExpanded=false
 @Published var limitPreset=5
 @Published var lastLimits:[String:[[Double]]]=[:]
 let limitPresets=[0,5,15,30,45,90,180,360]
 @Published var rosStatus="Disconnesso"
 @Published var rosEvent=""
 @Published var projectPath=UserDefaults.standard.string(forKey:"rosProjectPath") ?? ""
 var speech:Process?
 @Published var name = ""
 @Published var dwell = "1"
 @Published var poseGrip = "auto"
 @Published var speedDraft = 5.0
 @Published var minima = Array(repeating:"0",count:6)
 @Published var maxima = Array(repeating:"0",count:6)
 @Published var confirmConnect = false
 @Published var confirmHome = false
 @Published var confirmPlay = false
 @Published var confirmClear = false
 @Published var confirmQuit = false
 @Published var verifyQuit = false
 var repeatPlay = false
 var returningToQuit = false
 var returnRequestAccepted = false
 var timer: Timer?
 var process: Process?
 let queue = DispatchQueue(label:"it.doc.regia.control")
 var input: FileHandle?
 var output: FileHandle?
 var pendingPoll = false
 let lineReader=BridgeLineReader()
 var delegate: AppDelegate?
 var idle: Bool { !state.busy && !state.playing }
 var zero: Bool { state.home && state.trail == 0 && state.pos.allSatisfy { abs($0)<0.01 } }
 init() {
  do {
   let p = Process(), a = Pipe(), b = Pipe()
   let framework="/Library/Frameworks/Python.framework/Versions"
   let versions=(try? FileManager.default.contentsOfDirectory(atPath:framework)) ?? []
   let candidates = ["/opt/homebrew/bin/python3","/usr/local/bin/python3",framework+"/Current/bin/python3"]+versions.sorted().reversed().map{framework+"/"+$0+"/bin/python3"}+["/usr/bin/python3"]
   guard let python = candidates.first(where:{FileManager.default.isExecutableFile(atPath:$0)}), let resources = Bundle.main.resourceURL else { throw NSError(domain:"Python 3 non disponibile",code:1) }
   p.executableURL = URL(fileURLWithPath:python)
   p.arguments = ["-u",resources.appendingPathComponent("native_bridge.py").path]
   p.currentDirectoryURL = resources
   if Bundle.main.bundleIdentifier?.hasSuffix(".studiopreview") == true {
    var env=ProcessInfo.processInfo.environment
    env["DOC_REGIA_DATA"]="/private/tmp/robot-console-studio-preview-data"
    env["DOC_REGIA_NO_HARDWARE"]="1"
    p.environment=env
   }
   p.standardInput = a; p.standardOutput = b; p.standardError = FileHandle.nullDevice
   try p.run(); process=p;input=a.fileHandleForWriting;output=b.fileHandleForReading
   let heartbeat = Timer(timeInterval:0.4,repeats:true) { [weak self] _ in
    // AppKit tracking loops must not suspend the interface heartbeat.
    MainActor.assumeIsolated { self?.poll() }
   }
   RunLoop.main.add(heartbeat,forMode:.common)
   timer=heartbeat
   poll()
  } catch { message="Impossibile avviare il controllo: \(error.localizedDescription)" }
 }
 func poll() { if !pendingPoll { pendingPoll=true; send("heartbeat",poll:true) } }
 func send(_ op:String,_ values:[String:Any]=[:],poll:Bool=false,completion:((Bool)->Void)?=nil) {
  guard let input, let output else {completion?(false);return}
  var request=values;request["op"]=op;request["language"]=AppLanguage.current.rawValue
  guard let data=try? JSONSerialization.data(withJSONObject:request) else{completion?(false);return}
  let lineReader=self.lineReader
  queue.async { [weak self] in
   do {
    try input.write(contentsOf:data+Data([10]))
    let line=try lineReader.read(output)
    let reply=try JSONDecoder().decode(Reply.self,from:line)
    Task { @MainActor [weak self] in
     guard let self else{return}
     if let s=reply.state { self.state=s }
     if let home=reply.home_preview,(values["revision"] as? Int)==self.homeRevision {self.homePreview=home}
     if let plan=reply.multi_plan,(values["revision"] as? Int)==self.multiRevision {self.multiPlan=plan}
     if let command=reply.voice_command {self.voiceCommand=command}
     if let studio=reply.studio {self.studio=studio}
     if let w=reply.firmware_workspace {self.firmwareWorkspace=w}
     if let h=reply.ros_health{self.rosHealth=h}
     if let t=reply.tools{self.tools=t}
     if let a=reply.local_api{self.localAPI=a}
     if let text=reply.firmware_text {self.firmwareText=text}
     if let file=reply.firmware_file {self.firmwareFile=file}
     self.speedDraft=min(self.speedDraft,self.state.max_speed)
     if let ai=reply.ollama {self.ollama=ai}
     if let fw=reply.firmware {self.firmware=fw}
     if let limits=reply.last_limits {self.lastLimits=limits}
     if let chat=reply.chat {self.chat=chat}
     if let diary=reply.diary {self.diary=diary}
     self.assistantBusy=reply.assistant_busy ?? false
     self.rosStatus=reply.ros_status ?? "Disconnesso"
     self.rosEvent=reply.ros_event ?? ""
     if let e=reply.error {self.message=e;if op == "home" || op == "end_cycle" {self.returningToQuit=false;NSApp.reply(toApplicationShouldTerminate:false)}} else if !poll || self.message == "Avvio del controllo locale…" {self.message=""}
     completion?(reply.error == nil)
     if poll { self.pendingPoll=false }
     if op == "home" && reply.error == nil && self.returningToQuit { self.returnRequestAccepted=true }
     if self.returningToQuit && self.returnRequestAccepted && self.idle {
      self.returningToQuit=false
      if self.zero {self.verifyQuit=true} else {self.message="Ritorno interrotto. Verifica la posizione del robot."}
     }
    }
   } catch {
    Task { @MainActor [weak self] in self?.message="Controllo locale non disponibile: \(error.localizedDescription)";self?.timer?.invalidate();self?.pendingPoll=false;completion?(false) }
   }
  }
 }
 func ask() {
  let text=chatDraft.trimmingCharacters(in:.whitespacesAndNewlines)
  guard !text.isEmpty,!assistantBusy else{return}
  send("chat",["text":text,"llm":useLLM]);chatDraft=""
 }
 func speak() {
  speech?.terminate()
  guard let answer=chat.last(where:{$0.kind=="assistant"})?.text else{return}
  let text=AssistantSpeech.spokenText(answer)
  guard !text.isEmpty else{return}
  let p=Process();p.executableURL=URL(fileURLWithPath:"/usr/bin/say");p.arguments=["-v",AppLanguage.current == .english ? "Samantha" : "Alice",text]
  try? p.run();speech=p
 }
 func chooseProject() {
  let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.allowsMultipleSelection=false
  if panel.runModal() == .OK,let url=panel.url {
   projectPath=url.path;UserDefaults.standard.set(projectPath,forKey:"rosProjectPath")
  }
 }
 func connect() { if mode == "robot" {confirmConnect=true} else {connectNow()} }
 func connectNow() { minima=Array(repeating:"0",count:6);speedDraft=5;maxima=minima;send("connect",["mode":mode,"port":port]) }
 var connectionStatus:String {
  if !state.connected {return "Non connesso"}
  if !state.identified {return "Porta USB aperta · firmware da verificare"}
  if !state.speed_confirmed {return "Verifica velocità"}
  if !state.home {return "Conferma HOME"}
  return state.busy ? "Movimento in corso" : "Pronto"
 }
 func number(_ text:String,_ field:String)->Double? {
  let value=text.trimmingCharacters(in:.whitespacesAndNewlines).replacingOccurrences(of:",",with:".")
  guard !value.isEmpty,let n=Double(value),n.isFinite else {message="Completa \(field) con un numero valido. Puoi usare punto o virgola.";return nil}
  return n
 }
 func setPreset(_ span:Int,axis:Int?=nil) {
  for i in axis.map({[$0]}) ?? Array(0..<6) {minima[i]=String(-span);maxima[i]=String(span)}
 }
 var limitsMode:String {state.connected ? state.mode : mode}
 func restoreLimits() {
  guard let limits=lastLimits[limitsMode],limits.count==5 else{return}
  for i in 0..<6 {minima[i]=String(format:"%g",limits[i][0]);maxima[i]=String(format:"%g",limits[i][1])}
  message="Ultimi limiti recuperati nei campi: premi Applica limiti per usarli."
 }
 func firmwareAction(_ operation:String) {
  send("firmware",["operation":operation,"port":firmwarePort,"confirmed":operation=="upload"])
 }
 func selectStep(_ value:Double) {
  step=value
  stepText=String(format:"%g",value)
 }
 func applyStep() {
  guard let value=number(stepText,"lo spostamento"),value >= 1,value <= 360 else {
   message="Inserisci uno spostamento da 1° a 360°.";return
  }
  selectStep((value*100).rounded()/100)
 }
 func applyLimits() {
  var limits=[[Double]]()
  for i in 0..<6 {
   guard let lo=number(minima[i],"J\(i+1) minimo"),let hi=number(maxima[i],"J\(i+1) massimo") else {return}
   guard lo >= -360,hi <= 360,lo <= 0,hi >= 0,lo <= state.pos[i],hi >= state.pos[i] else {message="J\(i+1): i limiti devono contenere HOME (0°) e la posizione attuale, entro −360° e +360°.";return}
   limits.append([lo,hi])
  }
  send("limits",["limits":limits])
 }
 func recordPose() {
  guard let pause=number(dwell,"la pausa"),pause >= 0,pause <= 60 else {if message.isEmpty {message="La pausa deve essere da 0 a 60 secondi."};return}
  send("record",["name":name.isEmpty ? "Posa \(state.sequence.count+1)" : name,"dwell":pause,"grip":poseGrip])
 }
 func refreshMultiPlan(){
  multiRevision+=1;multiRefresh?.cancel();multiPlan=nil
  guard multiMode else{return}
  let values=multiDrafts.map{Double($0.replacingOccurrences(of:",",with:"."))}
  guard values.allSatisfy({$0 != nil && $0!.isFinite && abs($0!)<=360}) else {multiPlan = .invalid(T("Inserisci sei angoli validi da −360° a +360°."));return}
  let revision=multiRevision
  let task=DispatchWorkItem{[weak self] in
   guard let self,self.multiMode,self.multiRevision==revision else{return}
   self.send("multi_preview",["deltas":values.map{$0!},"revision":revision])
  }
  multiRefresh=task;DispatchQueue.main.asyncAfter(deadline:.now()+0.15,execute:task)
 }
 func keyboardJog(_ sign:Double){if keyboardEnabled && !multiMode && canJog(keyboardAxis,sign){send("jog",["axis":keyboardAxis,"delta":sign*step])}}
 func canJog(_ axis:Int,_ sign:Double)->Bool {
  guard state.connected,state.identified,state.speed_confirmed,state.home,idle,!firmware.busy else {return false}
  if state.axes_available?[axis] == false || state.axes_enabled?[axis] == false || state.hardware_ok == false{return false}
  let target=state.pos[axis]+sign*step
  return state.limits[axis][0] <= target && target <= state.limits[axis][1]
 }
 func showFirmware() {
  guard let folder=Bundle.main.resourceURL?.appendingPathComponent("RegiaDemo") else{return}
  NSWorkspace.shared.selectFile(folder.appendingPathComponent("RegiaDemo.ino").path,inFileViewerRootedAtPath:folder.path)
 }
 func play(_ loop:Bool) {repeatPlay=loop;confirmPlay=true}
 func requestQuit() {
  if firmware.busy {message="Attendi la conclusione dell’operazione firmware prima di chiudere.";NSApp.reply(toApplicationShouldTerminate:false);return}
  if !state.connected || (idle && zero) {quit()} else {confirmQuit=true}
 }
 func quit() {
  timer?.invalidate()
  send("stop")
  let closingInput=input
  queue.async { [weak self] in
   try? closingInput?.close()
   Task { @MainActor [weak self] in
    self?.delegate?.allowQuit=true
    NSApp.reply(toApplicationShouldTerminate:true)
    NSApp.terminate(nil)
   }
  }
 }
 func finishCycleAndQuit() { returningToQuit=true;returnRequestAccepted=true;send("end_cycle") }
 func returnAndQuit() { returningToQuit=true;returnRequestAccepted=false;send("home") }
}
@MainActor final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
 weak var model: Regia?
 var allowQuit=false
 func applicationShouldTerminate(_ sender:NSApplication)->NSApplication.TerminateReply {
  if allowQuit{return .terminateNow};model?.requestQuit();return .terminateLater
 }
 func windowShouldClose(_ sender:NSWindow)->Bool {model?.requestQuit();return false}
 func applicationDidFinishLaunching(_ notification:Notification) {
  NSApp.setActivationPolicy(.regular); NSApp.activate(ignoringOtherApps:true)
  DispatchQueue.main.async { for w in NSApp.windows {w.delegate=self} }
 }
}
private struct PanelContentHeight:PreferenceKey {
 static var defaultValue:CGFloat=0
 static func reduce(value:inout CGFloat,nextValue:()->CGFloat){value=max(value,nextValue())}
}
struct Panel<Content:View>:View {
 @Environment(\.panelWidth) private var panelWidth
 let title:String
 let content:Content
 @AppStorage private var storedHeight:Double
 @State private var naturalHeight:CGFloat=1
 @State private var dragStart:CGFloat?
 @State private var hovering=false
 init(title:String,@ViewBuilder content:()->Content) {
  self.title=title;self.content=content()
  self._storedHeight=AppStorage(wrappedValue:0,"RobotConsole.PanelHeight."+title)
 }
 private var visibleHeight:CGFloat {storedHeight>0 ? min(CGFloat(storedHeight),max(1,naturalHeight)) : max(1,naturalHeight)}
 private func resize(_ height:CGFloat) {storedHeight=Double(min(1600,max(28,height)))}
 var body:some View {
  VStack(alignment:.leading,spacing:14) {
   HStack(spacing:10) {
    RoundedRectangle(cornerRadius:2).fill(RobotTheme.lime).frame(width:3,height:18)
    RText(title).font(.headline)
    Spacer()
    Button("Adatta"){storedHeight=0}.robotCaption().disabled(storedHeight<=0)
     .accessibilityLabel(T("Adatta altezza di "+title)).help("Ripristina l’altezza naturale del contenuto")
   }
   ScrollView(.vertical) {
    VStack(alignment:.leading,spacing:16){content}
     .frame(width:max(1,panelWidth-44),alignment:.leading)
     .fixedSize(horizontal:false,vertical:true)
     .background(GeometryReader{proxy in Color.clear.preference(key:PanelContentHeight.self,value:proxy.size.height)})
   }
   .frame(height:visibleHeight)
   .scrollIndicators(.visible)
   .scrollBounceBehavior(.basedOnSize)
   .onPreferenceChange(PanelContentHeight.self){height in if abs(height-naturalHeight)>0.5 {naturalHeight=height}}
   HStack(spacing:8) {
    Spacer()
    RoundedRectangle(cornerRadius:2).fill(RobotTheme.lime.opacity(hovering ? 0.85 : 0.28)).frame(width:44,height:3)
    Image(systemName:"arrow.up.and.down").font(.system(size:9,weight:.semibold)).foregroundStyle(hovering ? RobotTheme.lime : RobotTheme.secondary)
    Spacer()
   }
   .frame(maxWidth:.infinity).frame(height:16).contentShape(Rectangle())
   .onHover{inside in
    hovering=inside
    if inside {NSCursor.resizeUpDown.push()} else {NSCursor.pop()}
   }
   .gesture(DragGesture(minimumDistance:2,coordinateSpace:.global)
    .onChanged{value in
     if dragStart==nil {dragStart=visibleHeight}
     resize((dragStart ?? visibleHeight)+value.translation.height)
    }
    .onEnded{_ in dragStart=nil})
   .onTapGesture(count:2){storedHeight=0}
   .help("Trascina per cambiare solo l’altezza. Doppio clic per adattare al contenuto.")
   .accessibilityElement(children:.ignore)
   .accessibilityLabel(T("Ridimensiona "+title+" in verticale"))
   .accessibilityValue("\(Int(visibleHeight)) punti")
   .accessibilityAdjustableAction{direction in
    switch direction {
     case .increment:resize(visibleHeight+40)
     case .decrement:resize(visibleHeight-40)
     @unknown default:break
    }
   }
  }.padding(22).frame(maxWidth:.infinity,alignment:.leading)
   .background(LinearGradient(colors:[RobotTheme.graphite,RobotTheme.surface],startPoint:.topLeading,endPoint:.bottomTrailing),in:RoundedRectangle(cornerRadius:18))
   .overlay(RoundedRectangle(cornerRadius:18).stroke(RobotTheme.lime.opacity(0.18),lineWidth:1))
 }
}
struct FirmwarePanel:View {
 @ObservedObject var m:Regia
 var canWork:Bool {!m.state.connected && m.idle && !m.firmware.busy}
 var body:some View {
  Panel(title:"Firmware · Arduino Mega 2560") {
   DisclosureGroup("Carica il firmware direttamente dall’app",isExpanded:$m.firmwareExpanded) {
    VStack(alignment:.leading,spacing:10) {
     RText("Firmware incluso: Regia 4 · Mega 2560 + RAMPS 1.4. J2 usa il DM542 esterno; servo su D11.").robotCaption().foregroundStyle(RobotTheme.secondary)
     RText(m.firmware.status).foregroundStyle(RobotTheme.accentText)
     if m.firmware.busy {ProgressView().controlSize(.small)}
     if m.state.connected {RText("Prima premi Scollega controllo. Per il caricamento prepara la Mega con sola USB e senza alimentazione dei motori.").robotCaption().foregroundStyle(.orange)}
     if m.firmware.available {
      HStack {
       Button("Aggiorna porte"){m.firmwareAction("scan")}.disabled(!canWork)
       Picker("Scheda USB",selection:$m.firmwarePort) {
        RText("Seleziona una porta").tag("")
        ForEach(m.firmware.boards){board in RText(board.name+" · "+board.port).tag(board.port)}
       }.disabled(!canWork)
      }
      HStack {
       Button("Verifica compilazione"){m.firmwareAction("compile")}.disabled(!canWork)
       Button("Carica sulla Mega"){m.confirmUpload=true}
        .buttonStyle(RobotButtonStyle(prominent:true))
        .disabled(!canWork || !m.firmware.boards.contains(where:{$0.port==m.firmwarePort && $0.compatible}))
       Button("Prepara dipendenze…"){m.confirmToolSetup=true}.disabled(!canWork)
       if m.firmware.busy && m.firmware.phase != "uploading" {Button("Annulla operazione"){m.send("firmware_cancel")}}
      }
      RText("L’editor Arduino non viene aperto. Aggiorna le porte, scegli la Mega e conferma il caricamento. Al termine il controllo resta scollegato.").robotCaption().foregroundStyle(RobotTheme.secondary)
      RText("Strumento: "+m.firmware.tool).robotCaption(small:true).foregroundStyle(RobotTheme.secondary).textSelection(.enabled)
     } else {
      RText("Serve Arduino CLI con il core Arduino AVR e AccelStepper. Puoi installare la CLI senza Arduino IDE.").robotCaption()
      Link("Installa Arduino CLI dal sito ufficiale",destination:URL(string:"https://docs.arduino.cc/arduino-cli/installation")!)
      Button("Ricontrolla strumenti"){m.firmwareAction("scan")}.disabled(!canWork)
     }
     if !m.firmware.error.isEmpty {RText(m.firmware.error).foregroundStyle(.orange).textSelection(.enabled)}
     DisclosureGroup("Log compilazione e caricamento") {
      ScrollView {RText(m.firmware.logs.joined(separator:"\n")).robotCaption(small:true,mono:true).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}.frame(height:180)
     }
    }.padding(.top,8)
   }
  }
 }
}
struct CompanionPanel:View {
 @ObservedObject var m:Regia
 @StateObject var voice=VoiceCapture()
 var body:some View {
  Panel(title:"Assistente · memoria locale") {
   RText("Chat e voce consultano lo stato e il diario. Per muovere il robot usa i controlli manuali.").robotCaption().foregroundStyle(RobotTheme.secondary)
   ScrollView {
    LazyVStack(alignment:.leading,spacing:12) {
     if m.chat.isEmpty {RText("Chiedi: Qual è lo stato? · Cosa è successo? · Quali pose ho salvato?").foregroundStyle(RobotTheme.secondary)}
     ForEach(m.chat){entry in
      VStack(alignment:.leading,spacing:4){
       RText(entry.kind=="user" ? "Tu" : "Assistente").font(.caption.bold()).foregroundStyle(RobotTheme.accentText)
       RText(entry.text).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)
      }.padding(10).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:10))
     }
    }
   }.frame(height:220)
   HStack {
    TextField("Scrivi una domanda o Ricorda: …",text:$m.chatDraft).onSubmit {m.ask()}
    Button(m.assistantBusy ? "Rispondo…" : "Invia"){voice.stop();m.ask()}.disabled(m.assistantBusy || m.chatDraft.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)
    Button(voice.listening ? "Ferma dettatura" : "Parla"){if voice.listening {voice.stop()} else {m.speech?.terminate();voice.start{m.chatDraft=$0}}}
    Button("Leggi risposta"){voice.stop();m.speak()}.disabled(m.chat.last(where:{$0.kind=="assistant"}) == nil)
    Button("Silenzio"){m.speech?.terminate()}
   }
   if !voice.message.isEmpty {RText(voice.message).robotCaption().foregroundStyle(RobotTheme.secondary)}
   Toggle("Conversazione libera · IA offline con Ollama",isOn:$m.useLLM)
    .onChange(of:m.useLLM){_,enabled in if enabled {m.send("ollama_start")}}
   VStack(alignment:.leading,spacing:10) {
    HStack {
     Circle().fill(m.ollama.running ? RobotTheme.lime : Color.gray).frame(width:8,height:8)
     RText(m.ollama.status).font(.subheadline.weight(.semibold)).foregroundStyle(RobotTheme.accentText)
     if m.ollama.busy {ProgressView().controlSize(.small)}
     Spacer()
     Button("Aggiorna"){m.send("ollama_refresh")}
     Button("Ferma IA e libera memoria"){m.useLLM=false;m.send("ollama_stop")}
      .disabled(!m.ollama.running || m.ollama.busy || m.assistantBusy)
      .help("Scarica il modello selezionato. Se il servizio è stato avviato da questa app, lo arresta.")
    }
    HStack {
     RText("Installazione: "+(m.ollama.installed ? "presente" : "non rilevata"))
     RText("Servizio: "+(m.ollama.running ? "avviato" : "spento"))
     if !m.ollama.version.isEmpty {RText("v"+m.ollama.version)}
    }.robotCaption().foregroundStyle(RobotTheme.secondary)
    if !m.ollama.models.isEmpty {
     HStack {
      Picker("Modello locale",selection:Binding(get:{m.ollama.models.contains(where:{$0.name==m.ollama.selected}) ? m.ollama.selected : ""},set:{m.send("ollama_select",["model":$0])})) {
       RText("Scegli un modello").tag("")
       ForEach(m.ollama.models){model in RText(model.name+" · "+String(format:"%.1f",Double(model.size)/1_000_000_000)+" GB su disco").tag(model.name)}
      }.disabled(m.ollama.busy || m.assistantBusy)
      Button("Avvia e carica modello"){m.send("ollama_start")}.disabled(m.ollama.busy || m.assistantBusy)
     }
    } else if m.ollama.installed {
     Button("Avvia Ollama e cerca modelli"){m.send("ollama_start")}.disabled(m.ollama.busy)
    }
    RText("Caricati in memoria: "+(m.ollama.loaded.isEmpty ? "nessuno" : m.ollama.loaded.joined(separator:", "))).robotCaption().textSelection(.enabled)
    if !m.ollama.error.isEmpty {RText(m.ollama.error).robotCaption().foregroundStyle(.orange).textSelection(.enabled)}
    if !m.ollama.installed {
     Link("Scarica Ollama dal sito ufficiale",destination:URL(string:"https://ollama.com/download/mac")!)
    } else if m.ollama.running && m.ollama.models.isEmpty {
     RText("Installa prima un modello locale in Ollama, poi premi Aggiorna. Il primo download richiede Internet; dopo puoi lavorare offline.").robotCaption().foregroundStyle(RobotTheme.secondary)
     Link("Modelli sul sito ufficiale",destination:URL(string:"https://ollama.com/library")!)
    }
    RText("All’invio di una domanda con IA attiva avvio Ollama e carico il modello scelto. Uso solo modelli già presenti sul Mac; nessun download automatico.").robotCaption().foregroundStyle(RobotTheme.secondary)
    RText("Ferma IA scarica il modello selezionato dalla memoria e disattiva la conversazione libera. Il modello resta su disco. Un servizio Ollama già aperto da altre app rimane avviato. Il comando è disponibile al termine della risposta o del caricamento.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
   }.padding(12).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:10))

   DisclosureGroup("Diario persistente · ultimi 30 eventi") {
    ForEach(m.diary.reversed()){entry in
     VStack(alignment:.leading){RText(entry.time+" · "+entry.source).robotCaption(small:true).foregroundStyle(RobotTheme.secondary);RText(entry.text).robotCaption().textSelection(.enabled)}
      .frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,3)
    }
    RText("Memoria conservata in Library/Application Support/DOC Regia/memoria.sqlite3. Le posizioni da impulsi non sono misure fisiche.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
   }
  }.onDisappear{voice.stop()}
 }
}
struct LimitsPanel:View {
 @Environment(\.panelWidth) private var panelWidth
 private var columns:Int {panelWidth-44 >= 1050 ? 6 : (panelWidth-44 >= 620 ? 3 : 2)}
 @ObservedObject var m:Regia
 var body:some View {
  Panel(title:"Limiti dei giunti") {
    VStack(alignment:.leading,spacing:12) {
     let layout=panelWidth>850 ? AnyLayout(HStackLayout(spacing:12)) : AnyLayout(VStackLayout(alignment:.leading,spacing:10))
     layout {
      HStack {Picker("Predefinito",selection:$m.limitPreset){ForEach(m.limitPresets,id:\.self){span in RText(span==0 ? "Bloccato · 0°" : "±\(span)°").tag(span)}}.frame(width:220);Button("Per tutti i giunti"){m.setPreset(m.limitPreset)}}
      HStack {Button("Riprendi ultimi"){m.restoreLimits()}.disabled(m.lastLimits[m.limitsMode]==nil);Button("Applica limiti"){m.applyLimits()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.state.connected || !m.idle)}
     }
     Grid(horizontalSpacing:10,verticalSpacing:10) {
      ForEach(0..<(6/columns),id:\.self){row in
       GridRow {
        ForEach(0..<columns,id:\.self){column in
         let i=row*columns+column
         VStack(alignment:.leading,spacing:7) {
          RText("J\(i+1)").font(.subheadline.weight(.semibold))
          TextField("Minimo",text:$m.minima[i]).accessibilityLabel("J\(i+1) minimo")
          TextField("Massimo",text:$m.maxima[i]).accessibilityLabel("J\(i+1) massimo")
          Menu("Predefinito"){ForEach(m.limitPresets,id:\.self){span in Button(span==0 ? "Blocca a 0°" : "±\(span)°"){m.setPreset(span,axis:i)}}}
           .lineLimit(1).minimumScaleFactor(0.85)
         }.padding(10).frame(maxWidth:.infinity,alignment:.leading)
          .background(RobotTheme.black,in:RoundedRectangle(cornerRadius:10))
        }
       }
      }
     }.frame(maxWidth:.infinity,alignment:.leading)
     RText("Scegli o modifica gli intervalli, poi premi Applica limiti. I predefiniti non sono finecorsa meccanici. Gli ultimi limiti restano separati per Anteprima e Robot USB.").robotCaption().foregroundStyle(RobotTheme.secondary)
    }
  }.disabled(m.firmware.busy)
 }
}
private struct JointGridHeight:PreferenceKey {static var defaultValue:CGFloat=560;static func reduce(value:inout CGFloat,nextValue:()->CGFloat){value=max(value,nextValue())}}
struct MotionPanel:View {
 @Environment(\.panelWidth) private var panelWidth
 var innerWidth:CGFloat{panelWidth-44}
 var jointLayout:AnyLayout {innerWidth>=850 ? AnyLayout(HStackLayout(alignment:.top,spacing:14)) : AnyLayout(VStackLayout(alignment:.leading,spacing:14))}
 @State private var gridHeight:CGFloat=560
 @ObservedObject var m:Regia
 let lime=RobotTheme.lime
 var body:some View {
  Panel(title:"Muovi e osserva") {
   VStack(alignment:.leading,spacing:8) {
    HStack {RText("Velocità comune").font(.subheadline.weight(.semibold));Spacer();RText("\(m.speedDraft,specifier:"%.1f")°/s").monospacedDigit().foregroundStyle(RobotTheme.accentText)}
    HStack {RText("1°/s").robotCaption();Slider(value:$m.speedDraft,in:1...m.state.max_speed,step:0.5).accessibilityLabel("Velocità giunti");RText("\(Int(m.state.max_speed))°/s").robotCaption()}
    HStack {Button("Applica a tutti"){m.send("set_speed",["speed":m.speedDraft])}.disabled(!m.state.connected || !m.state.identified || !m.idle);RText("Stesse velocità per comandi singoli, simultanei e pose").robotCaption().foregroundStyle(RobotTheme.secondary)}
   }.disabled(!m.idle)
   Divider()
   Picker("Comando dei giunti",selection:$m.multiMode){RText("Singolo").tag(false);RText("Simultaneo").tag(true)}.pickerStyle(.segmented).disabled(!m.idle)
   if !m.multiMode {
   ViewThatFits(in:.horizontal) {
    HStack {
        RText("Spostamento per clic").font(.subheadline.weight(.semibold))
        Picker("Tastiera",selection:$m.keyboardAxis){ForEach(m.controlAxes,id:\.self){RText("J\($0+1)").tag($0)}}.frame(width:130).help("Option + freccia sinistra/destra: sposta il giunto selezionato")
        RText("\(m.step,specifier:"%.2f")°").monospacedDigit().foregroundStyle(RobotTheme.accentText)
        Spacer()
        TextField("Gradi",text:$m.stepText).frame(width:75).accessibilityLabel("Angolo da scrivere").onSubmit{m.applyStep()}
        RText("°")
        Button("Imposta angolo"){m.applyStep()}
        Stepper("±1°",value:Binding(get:{m.step},set:{m.selectStep($0)}),in:1...360,step:1).fixedSize()
       }.fixedSize(horizontal:true,vertical:false)
    VStack(alignment:.leading,spacing:10) {
     HStack{RText("Spostamento per clic").font(.subheadline.weight(.semibold));Spacer();Picker("Tastiera",selection:$m.keyboardAxis){ForEach(m.controlAxes,id:\.self){RText("J\($0+1)").tag($0)}}.frame(width:130);RText("\(m.step,specifier:"%.2f")°").monospacedDigit()}
     HStack{TextField("Gradi",text:$m.stepText).frame(width:75).accessibilityLabel("Angolo da scrivere").onSubmit{m.applyStep()};RText("°");Button("Imposta angolo"){m.applyStep()};Spacer();Stepper("±1°",value:Binding(get:{m.step},set:{m.selectStep($0)}),in:1...360,step:1).fixedSize()}
    }
   }
   HStack {
    RText("1°").robotCaption()
    Slider(value:Binding(get:{m.step},set:{m.selectStep($0)}),in:1...360,step:1).accessibilityLabel("Spostamento in gradi")
    RText("360°").robotCaption()
   }
   LazyVGrid(columns:Array(repeating:GridItem(.flexible(),spacing:6),count:innerWidth<800 ? 8 : 15),spacing:6) {
    ForEach([1.0,2,5,10,15,20,30,45,60,90,120,150,180,270,360],id:\.self){amount in
     Button{m.selectStep(amount)}label:{RText("\(amount,specifier:"%.0f")°").lineLimit(1).minimumScaleFactor(0.8).frame(maxWidth:.infinity)}
      .buttonStyle(RobotButtonStyle(prominent:m.step==amount)).accessibilityLabel("Spostamento \(Int(amount)) gradi")
    }
   }
   }
   if m.state.max_speed<20 {RText("Per abilitare 20°/s sul robot, carica il firmware incluso dalla sezione Firmware. Quello attuale resta utilizzabile fino a 10°/s.").robotCaption().foregroundStyle(RobotTheme.secondary)}
   RText("Il passo è lo spostamento per clic; la velocità è in gradi al secondo. − e + restano disponibili solo entro i limiti applicati.").robotCaption().foregroundStyle(RobotTheme.secondary)
   RText("I movimenti simultanei rispettano le velocità massime dei giunti e possono rallentare per il budget impulsi totale. STOP su un giunto del gruppo ferma l’intero gruppo mantenendo la tenuta.").robotCaption().foregroundStyle(RobotTheme.secondary)
   Toggle("Canali aggiuntivi · J6 se non associato al modello",isOn:$m.showExtraJoints).robotCaption().toggleStyle(.checkbox).disabled(!m.idle)
   jointLayout {
   LazyVGrid(columns:Array(repeating:GridItem(.flexible(),spacing:10),count:innerWidth>1200 ? 3 : 2),spacing:10) {
    ForEach(m.controlAxes,id:\.self){i in JointControlCard(m:m,axis:i)}

   }
   .frame(maxWidth:.infinity)
   .background(GeometryReader{p in Color.clear.preference(key:JointGridHeight.self,value:p.size.height)})
   ArmMiniView(m:m).frame(maxWidth:.infinity).frame(height:innerWidth>=850 ? max(560,gridHeight) : 560)
   }
   if m.multiMode {MultiJointControls(m:m)}
   VoiceMotionControls(m:m)
   HStack(spacing:12) {
    RText("Pinza").font(.subheadline.weight(.semibold))
    Button("Apri pinza"){m.send("servo",["command":"apri"])}
    Button("Chiudi pinza"){m.send("servo",["command":"chiudi"])}
    RText(m.state.grip).robotCaption().foregroundStyle(RobotTheme.secondary)
    Spacer()
    RText(m.state.mode=="demo" ? "Posizioni virtuali" : "Posizioni stimate · senza encoder").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
   }.disabled(!m.state.home || !m.idle)

  }.disabled(m.firmware.busy)
   .onPreferenceChange(JointGridHeight.self){height in if abs(height-gridHeight)>1 {gridHeight=height}}
   .onChange(of:m.multiMode){_,_ in m.refreshMultiPlan()}
   .onChange(of:m.multiDrafts){_,_ in m.refreshMultiPlan()}
   .onChange(of:m.state.axis_speeds){_,_ in m.refreshMultiPlan()}
   .onChange(of:m.state.max_speed){_,_ in m.refreshMultiPlan()}
   .onChange(of:m.state.pos){_,_ in m.refreshMultiPlan()}
   .onChange(of:m.state.limits){_,_ in m.refreshMultiPlan()}
   .onChange(of:m.state.axes_enabled){_,_ in m.refreshMultiPlan()}
   .onChange(of:m.state.multi_axis){_,_ in m.refreshMultiPlan()}
   .onChange(of:m.state.home){_,_ in m.refreshMultiPlan()}
   .onChange(of:m.state.busy){_,_ in m.refreshMultiPlan()}
 }
}
struct MultiJointControls:View {
 @ObservedObject var m:Regia
 @State private var pending:MultiPlan?
 @State private var confirm=false
 var body:some View {
  VStack(alignment:.leading,spacing:10) {
   RText("Movimento simultaneo").font(.headline).foregroundStyle(RobotTheme.accentText)
   RText("Imposta lo spostamento nelle schede J1–J6 e regola la velocità con gli stessi controlli del movimento singolo. Zero lascia fermo il giunto.").robotCaption().foregroundStyle(RobotTheme.secondary)
   if let plan=m.multiPlan {
    if plan.valid {
     HStack {RText("Tempo previsto: \(plan.duration,specifier:"%.2f") s").monospacedDigit();Spacer();if plan.budget_limited {RText("Velocità ridotte dal budget impulsi").foregroundStyle(.orange)}}.robotCaption()
     RText("Per partire e arrivare insieme, ogni giunto rispetta il proprio massimo e può rallentare. Il picco previsto considera anche l’accelerazione.").robotCaption().foregroundStyle(RobotTheme.secondary)
    }else{RText(plan.error).robotCaption().foregroundStyle(RobotTheme.secondary)}
   }
   if !m.speedEdits.isEmpty {RText("Applica le velocità modificate con Invio o ✓ prima di muovere il gruppo.").robotCaption().foregroundStyle(.orange)}
   HStack {
    Button("Muovi insieme…"){pending=m.multiPlan;confirm=true}.buttonStyle(RobotButtonStyle(prominent:true))
     .disabled(!m.state.home || !m.idle || m.multiPlan?.valid != true || !m.speedEdits.isEmpty)
    Button("Azzera spostamenti"){m.multiDrafts=Array(repeating:"0",count:6)}.disabled(!m.idle)
   }
   RText("Registra posa conserva il gruppo simultaneo. Le vecchie pose mantengono il percorso originale. Nessun controllo collisioni su questi movimenti.").robotCaption().foregroundStyle(RobotTheme.secondary)
  }.padding(12).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:12))
   .alert("Esegui movimento simultaneo?",isPresented:$confirm){
    Button("Esegui"){if let plan=pending {m.send("multi_jog",["deltas":plan.deltas,"context":plan.context])}}
    Button("Annulla",role:.cancel){}
   }message:{
    if let plan=pending {
     Text(plan.axes.map{String(format:T("J%d %+.2f° · massimo %.2f°/s · picco previsto %.2f°/s"),$0+1,plan.deltas[$0],plan.requested[$0],plan.peaks[$0])}.joined(separator:"\n")+String(format:T("\nTempo previsto: %.2f s"),plan.duration))
    }
   }
 }
}
struct VoiceMotionControls:View {
 @ObservedObject var m:Regia
 @StateObject private var voice=VoiceCapture()
 @StateObject private var speaker=MotionSpeaker()
 @State private var continuous=true
 @State private var transcript=""
 @State private var heard=""
 @State private var stage=""
 @State private var session=UUID()
 @State private var silence:DispatchWorkItem?
 @State private var timeout:DispatchWorkItem?
 func cancel(){session=UUID();silence?.cancel();timeout?.cancel();voice.stop();speaker.stop();m.voiceCommand=nil;stage="";m.send("voice_cancel")}
 func listen(_ callback:@escaping(String)->Void){
  let current=session
  voice.start {text in
   guard current==session else{return}
   heard=text;silence?.cancel()
   let work=DispatchWorkItem {
    guard current==session else{return}
    voice.stop();callback(text)
   }
   silence=work;DispatchQueue.main.asyncAfter(deadline:.now()+1.5,execute:work)
  }
 }
 func beginCommand(){
  transcript="";heard="";stage="Ascolto comando"
  let current=session
  timeout?.cancel()
  let expiry=DispatchWorkItem{if current==session {cancel()}}
  timeout=expiry;DispatchQueue.main.asyncAfter(deadline:.now()+20,execute:expiry)
  listen {text in
   let normalized=text.lowercased().trimmingCharacters(in:.whitespacesAndNewlines)
   if ["annulla","cancel","no"].contains(normalized){cancel();return}
   transcript=text;prepare()
  }
 }
 func nextCommand(){
  guard stage=="Movimento vocale in corso",m.idle else{return}
  if continuous && m.state.home && m.state.error.isEmpty {beginCommand()}else{stage=""}
 }
 func prepare(){
  timeout?.cancel();voice.stop();silence?.cancel();let current=session;m.voiceCommand=nil
  m.send("voice_prepare",["text":transcript]) {ok in
   guard current==session else{return}
   guard ok,let command=m.voiceCommand,command.text==transcript else{stage="";return}
   stage="Riepilogo vocale";timeout?.cancel()
   let expiry=DispatchWorkItem {if current==session {cancel();m.message=T("Conferma vocale scaduta. Ripeti il comando.")}}
   timeout=expiry;DispatchQueue.main.asyncAfter(deadline:.now()+29,execute:expiry)
   speaker.speak(command.summary) {
    guard current==session else{return}
    // A fresh recognizer starts only after synthesis ends; the question cannot confirm itself.
    DispatchQueue.main.asyncAfter(deadline:.now()+0.5){
     guard current==session else{return};stage="Di’ sì confermo oppure annulla";heard=""
     listen {answer in
      guard current==session else{return}
      timeout?.cancel();m.voiceCommand=nil
      let normalized=answer.lowercased().trimmingCharacters(in:.whitespacesAndNewlines)
      stage="Movimento vocale in corso"
      m.send("voice_execute",["token":command.token,"confirmation":answer]){ok in
       guard current==session else{return}
       if !ok || ["annulla","cancel","no"].contains(normalized){stage=""}else{nextCommand()}
      }
     }
    }
   }
  }
 }
 var body:some View {
  DisclosureGroup("Comandi vocali del robot") {
   VStack(alignment:.leading,spacing:10) {
    RText("Di’: muovi J2 di 45 gradi; muovi J1 a 45 e J2 a 30; avvia posa 1. A indica la posizione assoluta, di uno spostamento relativo.").robotCaption()
    TextField("Comando da riconoscere",text:$transcript).disabled(!stage.isEmpty)
    HStack {
     Button("Parla al robot") {cancel();beginCommand()}
      .disabled(!m.state.home || !m.idle || !stage.isEmpty)
     Button("Leggi e chiedi conferma"){session=UUID();prepare()}.disabled(!m.state.home || !m.idle || !stage.isEmpty || transcript.isEmpty)
     Button("Annulla ascolto"){cancel()}
     Button("STOP"){cancel();m.send("stop")}.buttonStyle(RobotButtonStyle(danger:true)).disabled(!m.state.connected)
    }
    Toggle("Ascolta il prossimo comando a movimento concluso",isOn:$continuous)
    if !stage.isEmpty {RText(stage).foregroundStyle(RobotTheme.accentText)}
    if !heard.isEmpty {Text(heard).robotCaption()}
    if let command=m.voiceCommand {Text(command.summary).font(.callout)}
    if !voice.listening && !voice.message.isEmpty && stage=="Ascolto comando" {RText(voice.message).robotCaption().foregroundStyle(RobotTheme.secondary)}
    RText("Trascrizione locale, senza IA. Attendi il riepilogo e rispondi sì confermo. La conferma scade dopo 30 secondi; STOP resta disponibile anche da tastiera.").robotCaption().foregroundStyle(RobotTheme.secondary)
   }.padding(.top,8)
  }.onDisappear{cancel()}.onChange(of:m.state.busy){_,_ in nextCommand()}.onChange(of:m.state.home){_,home in if !home {cancel()}}
 }
}
struct JointControlCard:View {
 @ObservedObject var m:Regia
 let axis:Int
 @State private var speed=5.0
 @State private var speedText="5"
 @State private var sliding=false
 @State private var confirmRelease=false
 var enabled:Bool {m.state.axes_enabled?[axis] ?? true}
 var supported:Bool {m.state.mode=="demo" || m.state.axis_control==true}
 var canRelease:Bool {m.state.mode=="robot" && m.state.connected && m.state.drive_caps?[axis]==true && m.state.drive_state?[axis] != false}
 var status:String {
  if !m.state.connected {return "Driver non connesso"}
  if m.state.mode=="demo" {return enabled ? "Enable simulato" : "Escluso in anteprima"}
  if m.state.axes_available?[axis]==false {return "Driver esterno da configurare"}
  if !supported {return "ENABLE richiede firmware aggiornato"}
  if m.state.pending_off?.contains(axis)==true {return "Disattivazione in attesa…"}
  if m.state.drive_caps?[axis] != true {return "ENA non collegato · coppia possibile"}
  if let state=m.state.drive_state?[axis] {return state ? "Driver in tenuta" : "ENABLE disattivato"}
  return "Stato ENABLE da confermare"
 }
 // Reconcile explicitly: a successful apply can leave the text unchanged,
 // so onChange(speedText) alone cannot clear a previously dirty field.
 func reconcileSpeedEdit() {
  let applied=min(m.state.axis_speeds?[axis] ?? 5,m.state.max_speed)
  if let value=Double(speedText.replacingOccurrences(of:",",with:".")),value.isFinite,abs(value-applied)<0.005 {
   m.speedEdits.remove(axis)
  }else{m.speedEdits.insert(axis)}
 }
 func syncSpeed() {
  speed=min(m.state.axis_speeds?[axis] ?? 5,m.state.max_speed)
  // The controller retains hundredths; never round them to tenths in the UI.
  speedText=String(format:"%.2f",speed)
  reconcileSpeedEdit()
 }
 func applySpeed() {
  let submitted=speedText
  guard let value=Double(submitted.replacingOccurrences(of:",",with:".")),value.isFinite,value>=1,value<=m.state.max_speed else {m.message=T("Velocità da 1 al massimo indicato, in gradi/s.");return}
  speed=value
  m.send("set_axis_speed",["axis":axis,"speed":value]){ok in
   guard ok else{return}
   // Do not overwrite a newer edit made while the acknowledgement was pending.
   if speedText==submitted {syncSpeed()}else{reconcileSpeedEdit()}
  }
 }
 var body:some View {
  VStack(alignment:.leading,spacing:10) {
   HStack {
    Toggle("J\(axis+1)",isOn:Binding(get:{enabled},set:{value in
     if !value && canRelease {m.send("axis_stop",["axis":axis]);confirmRelease=true}
     else {m.send("joint_enable",["axis":axis,"enabled":value])}
    })).toggleStyle(.checkbox)
     .disabled((!m.idle && !enabled) || (m.state.connected && !supported))
     .help("Togli la spunta per escludere il giunto e disattivare ENABLE, se collegato. Dopo il rilascio conferma di nuovo HOME.")
    Spacer()
    RText(["X","Y · DM542","Z","E0","E1","EXT"][axis]).robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
   }
   RText("\(m.state.pos[axis],specifier:"%.2f")°").font(.system(size:23,weight:.semibold,design:.rounded)).monospacedDigit().foregroundStyle(RobotTheme.accentText)
   if m.multiMode {
    HStack {RText("Spostamento").robotCaption();Spacer();TextField("0",text:$m.multiDrafts[axis]).frame(width:72).accessibilityLabel(T("Simultaneo J")+String(axis+1));RText("°")}
     .disabled(!m.idle || !enabled || m.state.axes_available?[axis]==false)
    if let plan=m.multiPlan,plan.valid {
     RText("Picco previsto: \(plan.peaks[axis],specifier:"%.2f")°/s").robotCaption(small:true).monospacedDigit().foregroundStyle(RobotTheme.accentText)
    }
   }else{
   HStack(spacing:8) {
    Button{m.send("jog",["axis":axis,"delta": -m.step])}label:{RText("−").frame(maxWidth:.infinity)}.disabled(!m.canJog(axis,-1)).accessibilityLabel("J\(axis+1) meno")
    Button{m.send("jog",["axis":axis,"delta":m.step])}label:{RText("+").frame(maxWidth:.infinity)}.disabled(!m.canJog(axis,1)).accessibilityLabel("J\(axis+1) più")
   }
   }
   RText(m.multiMode ? "Velocità massima" : "Velocità").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
   HStack(spacing:4) {
    TextField("°/s",text:$speedText).frame(width:52).onSubmit{applySpeed()}.accessibilityLabel(T("Velocità J")+String(axis+1))
    RText("°/s").robotCaption()
    Spacer(minLength:0)
    Button{applySpeed()}label:{Image(systemName:"checkmark")}.help("Applica velocità giunto")
   }.disabled(!m.idle)
   Slider(value:Binding(get:{speed},set:{speed=$0;speedText=String(format:"%.1f",$0)}),in:1...m.state.max_speed,step:0.5,onEditingChanged:{editing in
    sliding=editing
    if !editing {applySpeed()}
   }).disabled(!m.idle).accessibilityLabel(T("Velocità J")+String(axis+1))
   Button{m.send("axis_stop",["axis":axis])}label:{RText("■ STOP J\(axis+1)").frame(maxWidth:.infinity)}.buttonStyle(RobotButtonStyle(danger:true)).disabled(!m.state.connected).help("Arresta questo giunto mantenendo la tenuta. La sequenza in corso viene interrotta se questo è il giunto attivo.")
   RText(status).robotCaption(small:true).foregroundStyle(m.state.drive_caps?[axis]==false && m.state.mode=="robot" ? .orange : RobotTheme.secondary).fixedSize(horizontal:false,vertical:true)
   RText(m.state.limits[axis][0] == m.state.limits[axis][1] ? "Giunto bloccato" : "\(m.state.limits[axis][0],specifier:"%.0f")° … \(m.state.limits[axis][1],specifier:"%.0f")°").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
  }.padding(12).frame(maxWidth:.infinity,alignment:.leading)
   .background(RobotTheme.black,in:RoundedRectangle(cornerRadius:12))
   .overlay(RoundedRectangle(cornerRadius:12).stroke(RobotTheme.lime.opacity((m.state.active_axis==axis || m.state.active_axes?.contains(axis)==true) ? 0.8 : 0.12)))
   .onAppear{syncSpeed()}
   .onChange(of:speedText){_,_ in reconcileSpeedEdit()}
   .onDisappear{m.speedEdits.remove(axis)}
   .onChange(of:m.state.axis_speeds?[axis]){_,_ in if !sliding {syncSpeed()}}
   .onChange(of:m.state.max_speed){_,_ in if !sliding {syncSpeed()}}
   .alert("Rilascia la tenuta del giunto?",isPresented:$confirmRelease){
    Button("Disabilita ENABLE",role:.destructive){m.send("joint_enable",["axis":axis,"enabled":false])}
    Button("Annulla",role:.cancel){}
   }message:{RText("Il movimento è stato fermato se il giunto era attivo. Disabilitare ENABLE toglie la corrente alle bobine: un asse sotto carico può cadere. Sostienilo prima di confermare. La sequenza verrà interrotta e HOME dovrà essere ristabilita.")}
 }
}
struct OperatorNotes:View {
 @AppStorage("RobotConsole.OperatorNotes") private var notes=""
 var body:some View {
  VStack(alignment:.leading,spacing:12) {
   Label{RText("Note operatore").font(.headline)}icon:{Image(systemName:"note.text")}.foregroundStyle(RobotTheme.accentText)
   RText("Appunti, misure e idee per la sessione.").robotCaption().foregroundStyle(RobotTheme.secondary)
   TextEditor(text:$notes).font(.system(size:13)).scrollContentBackground(.hidden).padding(8).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:10)).accessibilityLabel(T("Note operatore"))
   RText("Salvate automaticamente su questo Mac. Restano separate dai progetti esportati e dalla memoria dell’IA.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary).fixedSize(horizontal:false,vertical:true)
  }.padding(16).frame(maxWidth:.infinity,maxHeight:.infinity).background(RobotTheme.graphite)
 }
}
struct PoseEditRequest:Identifiable {
 let id=UUID()
 let index:Int
 let revision:Int
 let pose:Pose
}
struct PoseEditor:View {
 @ObservedObject var m:Regia
 let request:PoseEditRequest
 @Environment(\.dismiss) private var dismiss
 @State private var name:String
 @State private var angles:[String]
 @State private var dwell:String
 @State private var grip:String
 @State private var enabled:Bool
 @State private var error=""
 @State private var saving=false
 init(m:Regia,request:PoseEditRequest) {
  self.m=m;self.request=request
  _name=State(initialValue:request.pose.name)
  _angles=State(initialValue:request.pose.pos.map{String(format:"%.2f",$0)})
  _dwell=State(initialValue:String(format:"%g",request.pose.dwell))
  _grip=State(initialValue:request.pose.grip ?? "non comandata")
  _enabled=State(initialValue:request.pose.isEnabled)
 }
 func save() {
  error=""
  let cleanName=name.trimmingCharacters(in:.whitespacesAndNewlines)
  guard !cleanName.isEmpty,cleanName.count<=60 else {error="Scrivi un nome da 1 a 60 caratteri.";return}
  guard let seconds=Double(dwell.replacingOccurrences(of:",",with:".")),seconds.isFinite,(0...60).contains(seconds) else {error="Pausa da 0 a 60 secondi.";return}
  var values=[Double]()
  for (i,text) in angles.enumerated() {
   guard let v=Double(text.replacingOccurrences(of:",",with:".")),v.isFinite,(-360...360).contains(v) else {error="J\(i+1): inserisci un angolo da −360° a +360°.";return}
   values.append((v*100).rounded()/100)
  }
  saving=true
  m.send("pose_update",["index":request.index,"revision":request.revision,"name":cleanName,"pos":values,"dwell":seconds,"grip":grip,"enabled":enabled],completion:{success in
   saving=false
   if success {dismiss()} else {error=m.message.isEmpty ? "Salvataggio non riuscito." : m.message}
  })
 }
 var body:some View {
  VStack(alignment:.leading,spacing:18) {
   HStack {RText("Modifica posa").font(.title2.bold());Spacer();Toggle("Abilitata",isOn:$enabled).toggleStyle(.switch)}
   TextField("Nome posa",text:$name).accessibilityLabel("Nome della posa")
   RText("Angoli assoluti rispetto a HOME").font(.headline)
   HStack(spacing:12) {
    ForEach(0..<6,id:\.self) {i in
     VStack(alignment:.leading,spacing:6) {RText("J\(i+1)").foregroundStyle(RobotTheme.accentText);TextField("Gradi",text:$angles[i]).accessibilityLabel("Angolo posa J\(i+1)")}
    }
   }
   HStack {RText("Pausa");TextField("Secondi",text:$dwell).frame(width:90).accessibilityLabel("Pausa della posa");RText("secondi");Spacer();Picker("Pinza",selection:$grip) {RText("Apri").tag("apri");RText("Chiudi").tag("chiudi");RText("Mantieni").tag("non comandata")}.frame(width:210)}
   RText("Salvare modifica la sequenza. Gli angoli nuovi vengono raggiunti dal percorso originale, correggendo J1–J6 in quest’ordine. Verifica questi tratti prima di riprodurli sul robot; i limiti saranno ricontrollati all’avvio.").robotCaption().foregroundStyle(RobotTheme.secondary).fixedSize(horizontal:false,vertical:true)
   if !error.isEmpty {RText(error).foregroundStyle(RobotTheme.stop).font(.callout).fixedSize(horizontal:false,vertical:true)}
   HStack {Button("Annulla"){dismiss()}.disabled(saving);Spacer();Button(saving ? "Salvataggio…" : "Salva modifiche"){save()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(saving || !m.idle || m.firmware.busy)}
  }.padding(26).frame(width:680).background(RobotTheme.surface).foregroundStyle(RobotTheme.text).tint(RobotTheme.accentText).buttonStyle(RobotButtonStyle())
 }
}
struct SequencePanel:View {
 @ObservedObject var m:Regia
 @State private var editing:PoseEditRequest?
 var body:some View {
  Panel(title:"La tua sequenza") {
   HStack(spacing:12) {
    TextField("Nome posa",text:$m.name)
    RText("Pausa").robotCaption()
    TextField("Secondi",text:$m.dwell).frame(width:65)
    RText("s")
    Picker("Pinza",selection:$m.poseGrip) {
     RText("Ultimo comando").tag("auto");RText("Apri").tag("apri");RText("Chiudi").tag("chiudi");RText("Mantieni").tag("non comandata")
    }.frame(width:210)
    Button("＋ Registra posa"){m.recordPose()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.state.home || !m.idle)
   }
   RText(!m.state.home ? "Conferma HOME e applica i limiti per muovere il robot e registrare le pose." : "Muovi con − e +, poi registra la posa con tutti e sei i giunti e la richiesta della pinza.").robotCaption().foregroundStyle(RobotTheme.secondary)
   RText("La pinza viene comandata all’arrivo nella posa. Il riordino ripercorre i tratti insegnati, anche a ritroso; può passare da HOME. Mantieni non invia comandi alla pinza.").robotCaption().foregroundStyle(RobotTheme.secondary)
   RText("\(m.state.sequence.filter{$0.isEnabled}.count) di \(m.state.sequence.count) pose abilitate. Una posa esclusa salta pausa e pinza; il percorso verso altre pose può comunque attraversarla.").robotCaption().foregroundStyle(RobotTheme.secondary)
   Button("Annulla ultima modifica pose"){m.send("pose_undo",["revision":m.state.sequence_revision])}.disabled(!m.idle || !m.state.can_undo)
   if m.state.sequence.isEmpty {
    HStack {
     Image(systemName:"square.stack.3d.up").foregroundStyle(RobotTheme.accentText)
     RText("La sequenza è vuota. Registra la prima posa per iniziare.").foregroundStyle(RobotTheme.secondary)
    }.padding(.vertical,12)
   } else {
    VStack(spacing:0) {
     ForEach(Array(m.state.sequence.enumerated()),id:\.offset){i,p in
      VStack(alignment:.leading,spacing:8) {
       HStack(spacing:10) {
        Toggle("Abilita posa \(i+1)",isOn:Binding(get:{p.isEnabled},set:{m.send("pose_enable",["index":i,"enabled":$0,"revision":m.state.sequence_revision])})).labelsHidden().toggleStyle(.switch).disabled(!m.idle)
        RText("\(i+1)").font(.caption.bold()).foregroundStyle(RobotTheme.accentText)
        RText(p.name).font(.subheadline.weight(.semibold)).lineLimit(1)
        if !p.isEnabled {RText("Esclusa").robotCaption().foregroundStyle(RobotTheme.secondary)}
        if p.angles_edited == true {RText("Angoli modificati").robotCaption().foregroundStyle(RobotTheme.accentText)}
        Spacer()
        Button("Modifica"){editing=PoseEditRequest(index:i,revision:m.state.sequence_revision,pose:p)}.disabled(!m.idle)
        Picker("Pinza posa",selection:Binding(get:{p.grip ?? "non comandata"},set:{m.send("pose_grip",["index":i,"grip":$0,"revision":m.state.sequence_revision])})) {
         RText("Apri").tag("apri");RText("Chiudi").tag("chiudi");RText("Mantieni").tag("non comandata")
        }.labelsHidden().frame(width:110).disabled(!m.idle)
        Button {m.send("pose_move",["index":i,"target":i-1,"revision":m.state.sequence_revision])} label:{Image(systemName:"arrow.up")}.help("Sposta posa prima").disabled(i==0 || !m.idle)
        Button {m.send("pose_move",["index":i,"target":i+1,"revision":m.state.sequence_revision])} label:{Image(systemName:"arrow.down")}.help("Sposta posa dopo").disabled(i==m.state.sequence.count-1 || !m.idle)
        Button {m.send("pose_delete",["index":i,"revision":m.state.sequence_revision])} label:{Image(systemName:"trash")}.help("Elimina questa posa").disabled(!m.idle)
        RText("\(p.dwell,specifier:"%.1f") s").robotCaption().foregroundStyle(RobotTheme.secondary)
       }
       RText(p.pos.enumerated().map{"J\($0.offset+1) \(String(format:"%.2f",$0.element))°"}.joined(separator:" · ")).robotCaption().monospacedDigit().foregroundStyle(RobotTheme.secondary)
      }.padding(12).frame(maxWidth:.infinity,alignment:.leading)
       .background(i%2==0 ? RobotTheme.black : Color.clear,in:RoundedRectangle(cornerRadius:8))
     }
    }
   }
   HStack(spacing:10) {
    Button("▶ Una volta"){m.play(false)}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.state.home || !m.idle || !m.state.sequence.contains(where:{$0.isEnabled}))
    Button("↻ Ripeti"){m.play(true)}.disabled(!m.state.home || !m.idle || !m.state.sequence.contains(where:{$0.isEnabled}))
    Button(m.state.paused ? "Riprendi" : "Pausa"){m.send("pause")}.disabled(!m.state.playing)
    if m.state.playing {Button("Termina al prossimo HOME"){m.send("end_cycle")}}
    Spacer()
    Button("↶ HOME"){m.send("home")}.disabled(!m.state.home || !m.idle)
    Button("Svuota"){m.confirmClear=true}.disabled(!m.state.home || !m.idle)
   }
   RText("Ogni ciclo ripercorre i movimenti al contrario fino a HOME. La pinza mantiene l’ultima richiesta.").robotCaption().foregroundStyle(RobotTheme.secondary)
  }.disabled(m.firmware.busy)
  .sheet(item:$editing) {request in PoseEditor(m:m,request:request)}
 }
}
struct SessionSidebar:View {
 @ObservedObject var m:Regia
 @State private var follow=true
 var body:some View {
  VStack(alignment:.leading,spacing:12) {
   Label{RText("Attività del robot").font(.headline)}icon:{Image(systemName:"list.bullet.rectangle")}.foregroundStyle(RobotTheme.accentText)
   RText(m.connectionStatus).robotCaption().foregroundStyle(RobotTheme.secondary)
   Toggle("Segui ultimi eventi",isOn:$follow).robotCaption().toggleStyle(.checkbox)
   ScrollViewReader {proxy in
    ScrollView {
     LazyVStack(alignment:.leading,spacing:10) {
      if let events=m.state.robot_events,!events.isEmpty {
       ForEach(events){event in
        VStack(alignment:.leading,spacing:4) {
         HStack {
          Text(Date(timeIntervalSince1970:event.time).formatted(date:.omitted,time:.standard)).monospacedDigit()
          Spacer()
          RText(event.mode=="demo" ? "Anteprima" : "Robot USB")
         }.robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
         RText(event.text).robotCaption(small:true,mono:true).textSelection(.enabled).fixedSize(horizontal:false,vertical:true)
        }.padding(9).frame(maxWidth:.infinity,alignment:.leading).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:8)).id(event.id)
       }
      }else{RText("Il diario della sessione comparirà qui.").robotCaption().foregroundStyle(RobotTheme.secondary)}
     }.frame(maxWidth:.infinity,alignment:.leading)
    }.accessibilityLabel(T("Registro attività del robot"))
     .onChange(of:m.state.robot_events?.last?.id){_,id in if follow,let id {proxy.scrollTo(id,anchor:.bottom)}}
     .onChange(of:follow){_,enabled in if enabled,let id=m.state.robot_events?.last?.id {proxy.scrollTo(id,anchor:.bottom)}}
   }
   Divider()
   RText("Sessione e chiusura").font(.subheadline.weight(.semibold))
   Button("HOME e chiudi l’app"){m.requestQuit()}.frame(maxWidth:.infinity).disabled(m.firmware.busy)
   RText("Torna a HOME e verifica la posizione prima di uscire.").robotCaption(small:true).foregroundStyle(RobotTheme.secondary)
  }.padding(14).frame(maxWidth:.infinity,maxHeight:.infinity).background(RobotTheme.graphite)
 }
}

struct SidebarDivider:View {
 @Binding var width:Double
 let leading:Bool
 @State private var initial:Double?
 var body:some View {
  Rectangle().fill(RobotTheme.lime.opacity(0.16)).frame(width:5).contentShape(Rectangle())
   .onHover{inside in if inside {NSCursor.resizeLeftRight.push()}else{NSCursor.pop()}}
   .gesture(DragGesture(minimumDistance:1,coordinateSpace:.global)
    .onChanged{value in if initial==nil {initial=width};width=min(340,max(200,(initial ?? width)+Double(value.translation.width)*(leading ? 1 : -1)))}
    .onEnded{_ in initial=nil})
   .onTapGesture(count:2){width=220}
   .accessibilityElement(children:.ignore)
   .accessibilityLabel(T(leading ? "Larghezza attività del robot" : "Larghezza note operatore"))
   .accessibilityValue("\(Int(width))")
   .accessibilityAdjustableAction{direction in width=min(340,max(200,width+(direction == .increment ? 20 : -20)))}
   .help("Trascina per ridimensionare. Doppio clic per ripristinare la larghezza.")
 }
}

struct ConnectionPanel:View {
 @ObservedObject var m:Regia
 @Environment(\.panelWidth) private var width
 var body:some View {
  Panel(title:"Connessione e riferimento") {
   HStack {
    Picker("Modalità",selection:$m.mode){RText("Anteprima").tag("demo");RText("Robot USB").tag("robot")}.frame(maxWidth:.infinity)
    Picker("Porta",selection:$m.port){RText("Nessuna porta").tag("");ForEach(m.state.ports,id:\.self){RText($0).tag($0)}}.frame(maxWidth:.infinity)
   }
   HStack {
    Button(m.mode == "demo" ? "Avvia anteprima" : "Connetti Mega"){m.connect()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.idle || m.firmware.busy)
    if m.state.connected {Button("Scollega controllo"){m.send("disconnect")}.disabled(!m.idle || m.firmware.busy)}
    Button("Conferma HOME"){m.confirmHome=true}.disabled(!m.state.connected || !m.state.identified || !m.state.speed_confirmed || !m.idle || m.firmware.busy)
   }
   RText("HOME è la posizione fisica iniziale scelta da te. Gli angoli sono calcolati dagli impulsi, senza encoder.").robotCaption().foregroundStyle(RobotTheme.secondary)
   RText(m.state.guidance).font(.subheadline.weight(.medium)).foregroundStyle(RobotTheme.accentText).fixedSize(horizontal:false,vertical:true)
   if m.state.mode == "robot" && m.state.connected {
    RText(m.state.identified ? "Firmware riconosciuto. La USB alimenta la logica della Mega; non alimenta i motori. Per provare i movimenti servono anche le alimentazioni esterne dei driver." : "USB aperta non significa robot pronto. Con sola USB usa Anteprima: i motori non hanno alimentazione e le pose reali non sono verificabili.").robotCaption().foregroundStyle(RobotTheme.secondary).fixedSize(horizontal:false,vertical:true)
    if !m.state.identified {Button("Mostra firmware da caricare"){m.showFirmware()}}
   }
  }
 }
}

struct Dashboard:View {
 @ObservedObject var m:Regia
 @AppStorage("RobotConsole.Workspace") private var area="operator"
 @State private var showGuide=false
 @AppStorage("RobotConsole.ShowNotes") private var showNotes=true
 @AppStorage("RobotConsole.ShowSession") private var showSession=true
 @AppStorage("RobotConsole.SessionWidth") private var sessionWidth=220.0
 @AppStorage("RobotConsole.NotesWidth") private var notesWidth=220.0
 let lime=RobotTheme.lime
 var body:some View {
  VStack(spacing:0) {
   HStack {RText("ROBOT").bold();RText("CONSOLE").foregroundStyle(RobotTheme.accentText).bold();Spacer();Button{showSession.toggle()}label:{Label{RText("Eventi")}icon:{Image(systemName:"sidebar.left")}}.help("Mostra o nascondi attività del robot");Button{showNotes.toggle()}label:{Label{RText("Note")}icon:{Image(systemName:"sidebar.right")}}.help("Mostra o nascondi note operatore");Button("Guida"){showGuide=true};LanguagePicker();AppearancePicker();RText(m.state.mode=="demo" ? "ANTEPRIMA" : "ROBOT REALE").font(.caption.weight(.semibold)).foregroundStyle(RobotTheme.accentText).padding(.horizontal,12).padding(.vertical,7).background(lime.opacity(0.10),in:Capsule()).overlay(Capsule().stroke(lime.opacity(0.25)));Button("■ STOP"){m.send("stop")}.buttonStyle(RobotButtonStyle(danger:true)).keyboardShortcut(.escape,modifiers:[])}.padding(22).background(RobotTheme.black)
   Rectangle().fill(lime.opacity(0.28)).frame(height:1)
   Picker("Area di lavoro",selection:$area){RText("Operatore").tag("operator");RText("Studio 3D e programmi").tag("studio");RText("Diagnostica e ROS 2").tag("diagnostics");RText("Assistente").tag("assistant")}.pickerStyle(.segmented).padding(.horizontal,26).padding(.vertical,12).onChange(of:area,initial:true){_,a in m.keyboardEnabled=a=="operator"}
   if !m.message.isEmpty || !m.state.error.isEmpty {
    HStack{Image(systemName:"exclamationmark.circle");RText([m.message,m.state.error].filter{!$0.isEmpty}.joined(separator:" · ")).robotCaption().textSelection(.enabled).lineLimit(3);Spacer()}.foregroundStyle(.orange).padding(.horizontal,26).padding(.bottom,10)
   }
   HStack(spacing:0) {
   if showSession {SessionSidebar(m:m).frame(width:sessionWidth);SidebarDivider(width:$sessionWidth,leading:true)}
   GeometryReader {viewport in
   ScrollView(.vertical) {
    VStack(alignment:.leading,spacing:20) {
     HStack {VStack(alignment:.leading,spacing:8){RText("Insegna un gesto. Ripetilo.").font(.system(size:32,weight:.bold));RText("Controllo locale · sei canali articolari · una sequenza da presentare").foregroundStyle(RobotTheme.secondary)};Spacer();VStack(alignment:.trailing){RText(m.connectionStatus).foregroundStyle(RobotTheme.accentText);RText("\(m.state.cycle) cicli completati").robotCaption()}}
     if area == "operator" {
     ConnectionPanel(m:m)
     FirmwarePanel(m:m)
     FirmwareEditorPanel(m:m)
     StudioSetupPanel(m:m)
     LimitsPanel(m:m)
     MotionPanel(m:m)
     SequencePanel(m:m)
     }else if area == "studio" {
      Panel(title:"Braccio 3D · target virtuale") {ArmMiniView(m:m).frame(height:440)}
      StudioSetupPanel(m:m)
      ProgramPanel(m:m)
      SequencePanel(m:m)
     }else if area == "diagnostics" {
      TelemetryPanel(m:m)
      ROSPanel(m:m)
      CameraPanel()
     }else{
      CompanionPanel(m:m)
     }
    }.frame(width:max(1,viewport.size.width-32),alignment:.leading).environment(\.panelWidth,max(1,viewport.size.width-32)).padding(16)
   }
   }.frame(minWidth:540,maxWidth:.infinity)
   if showNotes {SidebarDivider(width:$notesWidth,leading:false);OperatorNotes().frame(width:notesWidth)}
   }
  }.background(RobotTheme.black).foregroundStyle(RobotTheme.text).tint(RobotTheme.accentText).buttonStyle(RobotButtonStyle()).frame(minWidth:1040,minHeight:720)
  .sheet(isPresented:$showGuide){StudioGuide()}
  .alert("Esegui il target visualizzato?",isPresented:$m.confirmStudioTarget){Button("Esegui target"){m.send("studio_execute",["confirmed":true])};Button("Annulla",role:.cancel){}}message:{RText("Il movimento viene eseguito dal controllore attuale, un giunto alla volta. Verifica il percorso, la calibrazione e i limiti. Le interferenze del modello non certificano la sicurezza fisica.")}
  .alert("Esegui programma?",isPresented:$m.confirmStudioProgram){Button("Esegui programma"){m.send("studio_run",["confirmed":true])};Button("Annulla",role:.cancel){}}message:{RText("Avvio dalla HOME nella modalità selezionata. Le attese sensore hanno un timeout e i giunti esclusi restano bloccati. Nessuna ripresa automatica dopo un errore.")}
  .alert("Carica firmware sulla Mega?",isPresented:$m.confirmUpload){
   Button("Carica firmware"){m.firmwareAction("upload")}
   Button("Annulla",role:.cancel){}
  }message:{RText("Scriverò il firmware salvato nel workspace su "+m.firmwarePort+". Conferma che è la Mega 2560. Il caricamento sostituisce il programma e riavvia la scheda: predisponi il braccio e togli l’alimentazione dei motori. Chiudi eventuali monitor seriali. Dopo dovrai riconnettere e ristabilire HOME.")}
  .alert("Prepara strumenti firmware",isPresented:$m.confirmToolSetup){
   Button("Scarica dipendenze"){m.firmwareAction("setup")}
   Button("Annulla",role:.cancel){}
  }message:{RText("Scarica tramite Arduino CLI il core Arduino AVR 1.8.8 e AccelStepper 1.64. Serve Internet. Non carica nulla sulla scheda.")}
  .alert("Connessione al robot reale",isPresented:$m.confirmConnect){Button("Connetti Mega"){m.connectNow()};Button("Annulla",role:.cancel){}}message:{RText("Questa azione apre la porta seriale selezionata. Procedi solo quando hai predisposto i collegamenti e vuoi controllare il robot reale.")}
  .alert("Conferma HOME",isPresented:$m.confirmHome){Button("Conferma"){m.send("home_set")};Button("Annulla",role:.cancel){}}message:{RText(m.state.mode == "demo" ? "Confermi lo zero virtuale? L’anteprima non apre la seriale e non controlla il robot." : "Il braccio è fisicamente nella posa iniziale? La conferma azzera gli angoli e abilita la tenuta dei motori. Sostieni il braccio durante la prima abilitazione.")}
  .alert("Riproduci la sequenza",isPresented:$m.confirmPlay){Button("Esegui"){m.send("play",["repeat":m.repeatPlay])};Button("Annulla",role:.cancel){}}message:{RText("Verifica che il percorso sia libero e le condizioni uguali alla prova.")}
  .alert("Svuota sequenza",isPresented:$m.confirmClear){Button("Svuota",role:.destructive){m.send("clear")};Button("Annulla",role:.cancel){}}message:{RText("Le pose salvate saranno cancellate.")}
  .alert("Chiudi Robot Console",isPresented:$m.confirmQuit){
   if m.idle && m.state.home {Button("Torna a HOME"){m.returnAndQuit()}}
   if m.state.playing {Button("Completa ciclo e HOME"){m.finishCycleAndQuit()}}
   Button("STOP ed esci",role:.destructive){m.quit()}
   Button("Resta nell’app",role:.cancel){NSApp.reply(toApplicationShouldTerminate:false)}
  }message:{RText("Il robot non risulta fermo a HOME. Il ritorno è disponibile solo da fermo con riferimento valido. STOP interrompe gli impulsi mantenendo la tenuta.")}
  .alert("Verifica HOME",isPresented:$m.verifyQuit){Button("HOME verificata: esci"){m.quit()};Button("Resta nell’app",role:.cancel){NSApp.reply(toApplicationShouldTerminate:false)}}message:{RText("Ritorno completato nel conteggio impulsi. Verifica visivamente la posizione del robot.")}
 }
}
@main struct RobotConsole:App {
 @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
 @StateObject var model=Regia()
 @AppStorage(AppAppearance.storageKey) private var appearance = AppAppearance.system
 @AppStorage(AppLanguage.storageKey) private var language = AppLanguage.italian
 @AppStorage("RobotConsole.ShowSession") private var showSession=true
 @AppStorage("RobotConsole.ShowNotes") private var showNotes=true
 var body:some Scene {
  Window("Robot Console",id:"main") {
   Dashboard(m:model)
    .preferredColorScheme(appearance.colorScheme)
    .environment(\.locale,language.locale)
    .onChange(of:appearance,initial:true){_,theme in NSApp.appearance=theme.appKitAppearance}
    .onAppear{model.delegate=delegate;delegate.model=model;for w in NSApp.windows {w.delegate=delegate}}
  }.defaultSize(width:1440,height:850)
  .commands {
   CommandGroup(after:.sidebar) {
    Toggle("Attività del robot",isOn:$showSession).keyboardShortcut("b",modifiers:.command)
    Toggle("Note operatore",isOn:$showNotes).keyboardShortcut("b",modifiers:[.command,.option])
   }
   CommandMenu("Robot") {
    Button("Giunto selezionato −"){model.keyboardJog(-1)}.keyboardShortcut(.leftArrow,modifiers:.option)
    Button("Giunto selezionato +"){model.keyboardJog(1)}.keyboardShortcut(.rightArrow,modifiers:.option)
   }
   CommandMenu(LocalizedStringKey(T("Aspetto"))) {
    Picker("Tema",selection:$appearance) {
     ForEach(AppAppearance.allCases){theme in RText(theme.title).tag(theme)}
    }
   }
  }
 }
}
