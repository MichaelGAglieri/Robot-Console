// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import AppKit

enum RobotTheme {
 static let lime = Color(red:0.66,green:1.0,blue:0.16)
 static let black = Color(red:0.035,green:0.043,blue:0.035)
 static let graphite = Color(red:0.10,green:0.115,blue:0.095)
 static let surface = Color(red:0.065,green:0.077,blue:0.060)
 static let text = Color(red:0.94,green:0.96,blue:0.91)
 static let stop = Color(red:1.0,green:0.34,blue:0.31)
}
struct RobotButtonStyle: ButtonStyle {
 var prominent = false
 var danger = false
 @Environment(\.isEnabled) private var enabled
 func makeBody(configuration:Configuration)->some View {
  let accent = danger ? RobotTheme.stop : RobotTheme.lime
  return configuration.label
   .font(.system(size:13,weight:.semibold))
   .padding(.horizontal,14).padding(.vertical,9)
   .foregroundStyle((prominent || danger ? RobotTheme.black : RobotTheme.text).opacity(enabled ? 1 : 0.45))
   .background((prominent || danger ? accent : RobotTheme.graphite).opacity(enabled ? (configuration.isPressed ? 0.68 : 1) : 0.18),in:RoundedRectangle(cornerRadius:9))
   .overlay(RoundedRectangle(cornerRadius:9).stroke(accent.opacity(enabled ? (prominent || danger ? 0.9 : 0.40) : 0.10),lineWidth:1))
   .contentShape(RoundedRectangle(cornerRadius:9))
 }
}

struct Pose: Decodable { let name: String; let pos: [Double]; let dwell: Double; let grip: String?; let enabled: Bool?; let angles_edited: Bool?
 var isEnabled: Bool {enabled ?? true}
}
struct RobotState: Decodable {
 var mode: String; var connected: Bool; var home: Bool; var pos: [Double]
 var limits: [[Double]]; var trail: Int; var sequence: [Pose]; var events: [String]
 var busy: Bool; var playing: Bool; var paused: Bool; var error: String; var grip: String
 var cycle: Int; var ports: [String]
 var can_undo: Bool; var max_speed: Double; var sequence_revision: Int; var identified: Bool; var firmware: String; var speed: Double; var speed_confirmed: Bool; var guidance: String
 static let empty = RobotState(mode:"demo",connected:false,home:false,pos:Array(repeating:0,count:5),limits:Array(repeating:[0,0],count:5),trail:0,sequence:[],events:[],busy:false,playing:false,paused:false,error:"",grip:"non comandata",cycle:0,ports:[],can_undo:false,max_speed:20,sequence_revision:0,identified:false,firmware:"",speed:5,speed_confirmed:false,guidance:"1 · Avvia Anteprima per provare senza hardware.")
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
struct Reply: Decodable {
 let state:RobotState?;let error:String?;let ollama:OllamaState?;let firmware:FirmwareState?;let last_limits:[String:[[Double]]]?
 let chat:[MemoryEntry]?;let diary:[MemoryEntry]?
 let assistant_busy:Bool?;let ros_status:String?;let ros_event:String?
}
@MainActor final class Regia: ObservableObject {
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
 @Published var minima = Array(repeating:"0",count:5)
 @Published var maxima = Array(repeating:"0",count:5)
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
  var request=values;request["op"]=op
  guard let data=try? JSONSerialization.data(withJSONObject:request) else{completion?(false);return}
  queue.async { [weak self] in
   do {
    try input.write(contentsOf:data+Data([10]))
    var line=Data()
    while true { let byte=try output.read(upToCount:1) ?? Data();if byte.isEmpty { throw NSError(domain:"Controllo locale interrotto",code:1) };if byte[0]==10 {break};line.append(byte) }
    let reply=try JSONDecoder().decode(Reply.self,from:line)
    Task { @MainActor [weak self] in
     guard let self else{return}
     if let s=reply.state { self.state=s }
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
  guard let text=chat.last(where:{$0.kind=="assistant"})?.text else{return}
  let p=Process();p.executableURL=URL(fileURLWithPath:"/usr/bin/say");p.arguments=[text]
  try? p.run();speech=p
 }
 func chooseProject() {
  let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.allowsMultipleSelection=false
  if panel.runModal() == .OK,let url=panel.url {
   projectPath=url.path;UserDefaults.standard.set(projectPath,forKey:"rosProjectPath")
  }
 }
 func connect() { if mode == "robot" {confirmConnect=true} else {connectNow()} }
 func connectNow() { minima=Array(repeating:"0",count:5);speedDraft=5;maxima=minima;send("connect",["mode":mode,"port":port]) }
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
  for i in axis.map({[$0]}) ?? Array(0..<5) {minima[i]=String(-span);maxima[i]=String(span)}
 }
 var limitsMode:String {state.connected ? state.mode : mode}
 func restoreLimits() {
  guard let limits=lastLimits[limitsMode],limits.count==5 else{return}
  for i in 0..<5 {minima[i]=String(format:"%g",limits[i][0]);maxima[i]=String(format:"%g",limits[i][1])}
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
  for i in 0..<5 {
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
 func canJog(_ axis:Int,_ sign:Double)->Bool {
  guard state.connected,state.identified,state.speed_confirmed,state.home,idle,!firmware.busy else {return false}
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
 private var visibleHeight:CGFloat {storedHeight>0 ? CGFloat(storedHeight) : max(1,naturalHeight)}
 private func resize(_ height:CGFloat) {storedHeight=Double(min(1600,max(28,height)))}
 var body:some View {
  VStack(alignment:.leading,spacing:14) {
   HStack(spacing:10) {
    RoundedRectangle(cornerRadius:2).fill(RobotTheme.lime).frame(width:3,height:18)
    Text(title).font(.headline)
    Spacer()
    Button("Adatta"){storedHeight=0}.font(.caption).disabled(storedHeight<=0)
     .accessibilityLabel("Adatta altezza di "+title).help("Ripristina l’altezza naturale del contenuto")
   }
   ScrollView(.vertical) {
    VStack(alignment:.leading,spacing:16){content}
     .frame(maxWidth:.infinity,alignment:.leading)
     .background(GeometryReader{proxy in Color.clear.preference(key:PanelContentHeight.self,value:proxy.size.height)})
   }
   .frame(height:visibleHeight)
   .scrollIndicators(storedHeight>0 && visibleHeight<naturalHeight ? .visible : .hidden)
   .scrollBounceBehavior(.basedOnSize)
   .onPreferenceChange(PanelContentHeight.self){height in if abs(height-naturalHeight)>0.5 {naturalHeight=height}}
   HStack(spacing:8) {
    Spacer()
    RoundedRectangle(cornerRadius:2).fill(RobotTheme.lime.opacity(hovering ? 0.85 : 0.28)).frame(width:44,height:3)
    Image(systemName:"arrow.up.and.down").font(.system(size:9,weight:.semibold)).foregroundStyle(hovering ? RobotTheme.lime : Color.secondary)
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
   .accessibilityLabel("Ridimensiona "+title+" in verticale")
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
     Text("Firmware incluso: Regia 2 · Mega 2560 + RAMPS 1.4. J2 usa il DM542 esterno; servo su D11.").font(.caption).foregroundStyle(.secondary)
     Text(m.firmware.status).foregroundStyle(RobotTheme.lime)
     if m.firmware.busy {ProgressView().controlSize(.small)}
     if m.state.connected {Text("Prima premi Scollega controllo. Per il caricamento prepara la Mega con sola USB e senza alimentazione dei motori.").font(.caption).foregroundStyle(.orange)}
     if m.firmware.available {
      HStack {
       Button("Aggiorna porte"){m.firmwareAction("scan")}.disabled(!canWork)
       Picker("Scheda USB",selection:$m.firmwarePort) {
        Text("Seleziona una porta").tag("")
        ForEach(m.firmware.boards){board in Text(board.name+" · "+board.port).tag(board.port)}
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
      Text("L’editor Arduino non viene aperto. Aggiorna le porte, scegli la Mega e conferma il caricamento. Al termine il controllo resta scollegato.").font(.caption).foregroundStyle(.secondary)
      Text("Strumento: "+m.firmware.tool).font(.caption2).foregroundStyle(.secondary).textSelection(.enabled)
     } else {
      Text("Serve Arduino CLI con il core Arduino AVR e AccelStepper. Puoi installare la CLI senza Arduino IDE.").font(.caption)
      Link("Installa Arduino CLI dal sito ufficiale",destination:URL(string:"https://docs.arduino.cc/arduino-cli/installation")!)
      Button("Ricontrolla strumenti"){m.firmwareAction("scan")}.disabled(!canWork)
     }
     if !m.firmware.error.isEmpty {Text(m.firmware.error).foregroundStyle(.orange).textSelection(.enabled)}
     DisclosureGroup("Log compilazione e caricamento") {
      ScrollView {Text(m.firmware.logs.joined(separator:"\n")).font(.system(size:11,design:.monospaced)).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}.frame(height:180)
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
   Text("Chat e voce consultano lo stato e il diario. Per muovere il robot usa i controlli manuali.").font(.caption).foregroundStyle(.secondary)
   ScrollView {
    LazyVStack(alignment:.leading,spacing:12) {
     if m.chat.isEmpty {Text("Chiedi: Qual è lo stato? · Cosa è successo? · Quali pose ho salvato?").foregroundStyle(.secondary)}
     ForEach(m.chat){entry in
      VStack(alignment:.leading,spacing:4){
       Text(entry.kind=="user" ? "Tu" : "Assistente").font(.caption.bold()).foregroundStyle(RobotTheme.lime)
       Text(entry.text).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)
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
   if !voice.message.isEmpty {Text(voice.message).font(.caption).foregroundStyle(.secondary)}
   Toggle("Conversazione libera · IA offline con Ollama",isOn:$m.useLLM)
    .onChange(of:m.useLLM){_,enabled in if enabled {m.send("ollama_start")}}
   VStack(alignment:.leading,spacing:10) {
    HStack {
     Circle().fill(m.ollama.running ? RobotTheme.lime : Color.gray).frame(width:8,height:8)
     Text(m.ollama.status).font(.subheadline.weight(.semibold)).foregroundStyle(RobotTheme.lime)
     if m.ollama.busy {ProgressView().controlSize(.small)}
     Spacer()
     Button("Aggiorna"){m.send("ollama_refresh")}
     Button("Ferma IA e libera memoria"){m.useLLM=false;m.send("ollama_stop")}
      .disabled(!m.ollama.running || m.ollama.busy || m.assistantBusy)
      .help("Scarica il modello selezionato. Se il servizio è stato avviato da questa app, lo arresta.")
    }
    HStack {
     Text("Installazione: "+(m.ollama.installed ? "presente" : "non rilevata"))
     Text("Servizio: "+(m.ollama.running ? "avviato" : "spento"))
     if !m.ollama.version.isEmpty {Text("v"+m.ollama.version)}
    }.font(.caption).foregroundStyle(.secondary)
    if !m.ollama.models.isEmpty {
     HStack {
      Picker("Modello locale",selection:Binding(get:{m.ollama.models.contains(where:{$0.name==m.ollama.selected}) ? m.ollama.selected : ""},set:{m.send("ollama_select",["model":$0])})) {
       Text("Scegli un modello").tag("")
       ForEach(m.ollama.models){model in Text(model.name+" · "+String(format:"%.1f",Double(model.size)/1_000_000_000)+" GB su disco").tag(model.name)}
      }.disabled(m.ollama.busy || m.assistantBusy)
      Button("Avvia e carica modello"){m.send("ollama_start")}.disabled(m.ollama.busy || m.assistantBusy)
     }
    } else if m.ollama.installed {
     Button("Avvia Ollama e cerca modelli"){m.send("ollama_start")}.disabled(m.ollama.busy)
    }
    Text("Caricati in memoria: "+(m.ollama.loaded.isEmpty ? "nessuno" : m.ollama.loaded.joined(separator:", "))).font(.caption).textSelection(.enabled)
    if !m.ollama.error.isEmpty {Text(m.ollama.error).font(.caption).foregroundStyle(.orange).textSelection(.enabled)}
    if !m.ollama.installed {
     Link("Scarica Ollama dal sito ufficiale",destination:URL(string:"https://ollama.com/download/mac")!)
    } else if m.ollama.running && m.ollama.models.isEmpty {
     Text("Installa prima un modello locale in Ollama, poi premi Aggiorna. Il primo download richiede Internet; dopo puoi lavorare offline.").font(.caption).foregroundStyle(.secondary)
     Link("Modelli sul sito ufficiale",destination:URL(string:"https://ollama.com/library")!)
    }
    Text("All’invio di una domanda con IA attiva avvio Ollama e carico il modello scelto. Uso solo modelli già presenti sul Mac; nessun download automatico.").font(.caption).foregroundStyle(.secondary)
    Text("Ferma IA scarica il modello selezionato dalla memoria e disattiva la conversazione libera. Il modello resta su disco. Un servizio Ollama già aperto da altre app rimane avviato. Il comando è disponibile al termine della risposta o del caricamento.").font(.caption2).foregroundStyle(.secondary)
   }.padding(12).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:10))

   DisclosureGroup("ROS 2 · laboratorio") {
    Text("Osserva stato, esiti, risposte e missioni del laboratorio. Pubblica la telemetria Regia su /doc_regia/stato. Nessun comando di movimento passa da questo collegamento.").font(.caption)
    HStack {
     TextField("Cartella D.O.C.Mac (solo per ROS 2)",text:$m.projectPath)
     Button("Scegli cartella…"){m.chooseProject()}
     Button("Collega ROS 2"){m.send("ros_connect",["project":m.projectPath])}
     Button("Scollega"){m.send("ros_disconnect")}
    }
    Text(m.rosStatus).foregroundStyle(RobotTheme.lime)
    Text(m.rosEvent).font(.caption).lineLimit(4)
   }
   DisclosureGroup("Diario persistente · ultimi 30 eventi") {
    ForEach(m.diary.reversed()){entry in
     VStack(alignment:.leading){Text(entry.time+" · "+entry.source).font(.caption2).foregroundStyle(.secondary);Text(entry.text).font(.caption).textSelection(.enabled)}
      .frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,3)
    }
    Text("Memoria conservata in Library/Application Support/DOC Regia/memoria.sqlite3. Le posizioni da impulsi non sono misure fisiche.").font(.caption2).foregroundStyle(.secondary)
   }
  }.onDisappear{voice.stop()}
 }
}
struct LimitsPanel:View {
 @ObservedObject var m:Regia
 var body:some View {
  Panel(title:"Limiti dei giunti") {
    VStack(alignment:.leading,spacing:12) {
     HStack {
      Picker("Predefinito",selection:$m.limitPreset){ForEach(m.limitPresets,id:\.self){span in Text(span==0 ? "Bloccato · 0°" : "±\(span)°").tag(span)}}.frame(width:240)
      Button("Per tutti i giunti"){m.setPreset(m.limitPreset)}
      Spacer()
      Button("Riprendi ultimi"){m.restoreLimits()}.disabled(m.lastLimits[m.limitsMode]==nil)
      Button("Applica limiti"){m.applyLimits()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.state.connected || !m.idle)
     }
     LazyVGrid(columns:Array(repeating:GridItem(.flexible(),spacing:10),count:6),spacing:10) {
      ForEach(0..<5,id:\.self){i in
       VStack(alignment:.leading,spacing:8) {
        Text("J\(i+1)").font(.subheadline.weight(.semibold))
        TextField("Minimo",text:$m.minima[i]).accessibilityLabel("J\(i+1) minimo")
        TextField("Massimo",text:$m.maxima[i]).accessibilityLabel("J\(i+1) massimo")
        Menu("Predefinito"){ForEach(m.limitPresets,id:\.self){span in Button(span==0 ? "Blocca a 0°" : "±\(span)°"){m.setPreset(span,axis:i)}}}
       }.padding(12).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:10))
      }
      VStack(alignment:.leading,spacing:8) {
       Text("J6").font(.subheadline.weight(.semibold))
       TextField("Minimo",text:.constant("—")).accessibilityLabel("J6 minimo non disponibile")
       TextField("Massimo",text:.constant("—")).accessibilityLabel("J6 massimo non disponibile")
       Menu("Predefinito"){Text("Giunto non installato")}
      }.padding(12).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:10)).disabled(true)
     }
     Text("Scegli o modifica gli intervalli, poi premi Applica limiti. I predefiniti non sono finecorsa meccanici. Gli ultimi limiti restano separati per Anteprima e Robot USB.").font(.caption).foregroundStyle(.secondary)
    }.padding(.top,10)
  }.disabled(m.firmware.busy)
 }
}
struct MotionPanel:View {
 @ObservedObject var m:Regia
 let lime=RobotTheme.lime
 var body:some View {
  Panel(title:"Muovi e osserva") {
   HStack(spacing:14) {
    VStack(alignment:.leading,spacing:4) {
     Text("Velocità giunti").font(.subheadline.weight(.semibold))
     Text("\(m.speedDraft,specifier:"%.1f")°/s").monospacedDigit().foregroundStyle(lime)
    }.frame(width:120,alignment:.leading)
    Text("1°/s").font(.caption)
    Slider(value:$m.speedDraft,in:1...m.state.max_speed,step:0.5).accessibilityLabel("Velocità giunti")
    Text("\(Int(m.state.max_speed))°/s").font(.caption)
    Button("Applica velocità"){m.send("set_speed",["speed":m.speedDraft])}.disabled(!m.state.connected || !m.state.identified || !m.idle)
    Text(m.state.speed_confirmed ? "Applicata: \(String(format:"%.1f",m.state.speed))°/s" : "Da confermare").font(.caption).foregroundStyle(.secondary)
   }.disabled(!m.idle)
   Divider()
   HStack {
    Text("Spostamento per clic").font(.subheadline.weight(.semibold))
    Text("\(m.step,specifier:"%.2f")°").monospacedDigit().foregroundStyle(lime)
    Spacer()
    TextField("Gradi",text:$m.stepText).frame(width:75).accessibilityLabel("Angolo da scrivere").onSubmit{m.applyStep()}
    Text("°")
    Button("Imposta angolo"){m.applyStep()}
    Stepper("±1°",value:Binding(get:{m.step},set:{m.selectStep($0)}),in:1...360,step:1).fixedSize()
   }
   HStack {
    Text("1°").font(.caption)
    Slider(value:Binding(get:{m.step},set:{m.selectStep($0)}),in:1...360,step:1).accessibilityLabel("Spostamento in gradi")
    Text("360°").font(.caption)
   }
   LazyVGrid(columns:Array(repeating:GridItem(.flexible(),spacing:6),count:15),spacing:6) {
    ForEach([1.0,2,5,10,15,20,30,45,60,90,120,150,180,270,360],id:\.self){amount in
     Button{m.selectStep(amount)}label:{Text("\(amount,specifier:"%.0f")°").lineLimit(1).minimumScaleFactor(0.8).frame(maxWidth:.infinity)}
      .buttonStyle(RobotButtonStyle(prominent:m.step==amount)).accessibilityLabel("Spostamento \(Int(amount)) gradi")
    }
   }
   if m.state.max_speed<20 {Text("Per abilitare 20°/s sul robot, carica il firmware incluso dalla sezione Firmware. Quello attuale resta utilizzabile fino a 10°/s.").font(.caption).foregroundStyle(.secondary)}
   Text("Il passo è lo spostamento per clic; la velocità è in gradi al secondo. − e + restano disponibili solo entro i limiti applicati.").font(.caption).foregroundStyle(.secondary)
   LazyVGrid(columns:Array(repeating:GridItem(.flexible(),spacing:10),count:6),spacing:10) {
    ForEach(0..<5,id:\.self){i in
     VStack(alignment:.leading,spacing:10) {
      HStack {
       Text("J\(i+1)").font(.headline)
       Spacer()
       Text(["X","Y · DM542","Z","E0","E1"][i]).font(.caption2).foregroundStyle(.secondary)
      }
      Text("\(m.state.pos[i],specifier:"%.2f")°").font(.system(size:24,weight:.semibold,design:.rounded)).monospacedDigit().foregroundStyle(lime)
      HStack(spacing:8) {
       Button{m.send("jog",["axis":i,"delta": -m.step])}label:{Text("−").frame(maxWidth:.infinity)}
        .disabled(!m.canJog(i,-1)).accessibilityLabel("J\(i+1) meno")
       Button{m.send("jog",["axis":i,"delta":m.step])}label:{Text("+").frame(maxWidth:.infinity)}
        .disabled(!m.canJog(i,1)).accessibilityLabel("J\(i+1) più")
      }
      Text(m.state.limits[i][0] == m.state.limits[i][1] ? "Giunto bloccato" : "\(m.state.limits[i][0],specifier:"%.0f")° … \(m.state.limits[i][1],specifier:"%.0f")°")
       .font(.caption2).foregroundStyle(.secondary)
     }.padding(12).frame(maxWidth:.infinity,alignment:.leading)
      .background(RobotTheme.black,in:RoundedRectangle(cornerRadius:12))
      .overlay(RoundedRectangle(cornerRadius:12).stroke(lime.opacity(0.12)))
    }
    VStack(alignment:.leading,spacing:10) {
     HStack {
      Text("J6").font(.headline)
      Spacer()
      Text("Predisposto").font(.caption2).foregroundStyle(.secondary)
     }
     Text("—").font(.system(size:24,weight:.semibold,design:.rounded)).foregroundStyle(lime)
     HStack(spacing:8) {
      Button{}label:{Text("−").frame(maxWidth:.infinity)}.accessibilityLabel("J6 meno")
      Button{}label:{Text("+").frame(maxWidth:.infinity)}.accessibilityLabel("J6 più")
     }.disabled(true)
     Text("Non installato").font(.caption2).foregroundStyle(.secondary)
    }.padding(12).frame(maxWidth:.infinity,alignment:.leading)
     .background(RobotTheme.black,in:RoundedRectangle(cornerRadius:12))
     .overlay(RoundedRectangle(cornerRadius:12).stroke(lime.opacity(0.12)))
   }
   HStack(spacing:12) {
    Text("Pinza").font(.subheadline.weight(.semibold))
    Button("Apri pinza"){m.send("servo",["command":"apri"])}
    Button("Chiudi pinza"){m.send("servo",["command":"chiudi"])}
    Text(m.state.grip).font(.caption).foregroundStyle(.secondary)
    Spacer()
    Text(m.state.mode=="demo" ? "Posizioni virtuali" : "Posizioni stimate · senza encoder").font(.caption2).foregroundStyle(.secondary)
   }.disabled(!m.state.home || !m.idle)

  }.disabled(m.firmware.busy)
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
   HStack {Text("Modifica posa").font(.title2.bold());Spacer();Toggle("Abilitata",isOn:$enabled).toggleStyle(.switch)}
   TextField("Nome posa",text:$name).accessibilityLabel("Nome della posa")
   Text("Angoli assoluti rispetto a HOME").font(.headline)
   HStack(spacing:12) {
    ForEach(0..<5,id:\.self) {i in
     VStack(alignment:.leading,spacing:6) {Text("J\(i+1)").foregroundStyle(RobotTheme.lime);TextField("Gradi",text:$angles[i]).accessibilityLabel("Angolo posa J\(i+1)")}
    }
   }
   HStack {Text("Pausa");TextField("Secondi",text:$dwell).frame(width:90).accessibilityLabel("Pausa della posa");Text("secondi");Spacer();Picker("Pinza",selection:$grip) {Text("Apri").tag("apri");Text("Chiudi").tag("chiudi");Text("Mantieni").tag("non comandata")}.frame(width:210)}
   Text("Salvare modifica la sequenza. Gli angoli nuovi vengono raggiunti dal percorso originale, correggendo J1, J2, J3, J4 e J5 in quest’ordine. Verifica questi tratti prima di riprodurli sul robot; i limiti saranno ricontrollati all’avvio.").font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true)
   if !error.isEmpty {Text(error).foregroundStyle(RobotTheme.stop).font(.callout).fixedSize(horizontal:false,vertical:true)}
   HStack {Button("Annulla"){dismiss()}.disabled(saving);Spacer();Button(saving ? "Salvataggio…" : "Salva modifiche"){save()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(saving || !m.idle || m.firmware.busy)}
  }.padding(26).frame(width:680).background(RobotTheme.surface).foregroundStyle(RobotTheme.text).tint(RobotTheme.lime).buttonStyle(RobotButtonStyle()).preferredColorScheme(.dark)
 }
}
struct SequencePanel:View {
 @ObservedObject var m:Regia
 @State private var editing:PoseEditRequest?
 var body:some View {
  Panel(title:"La tua sequenza") {
   HStack(spacing:12) {
    TextField("Nome posa",text:$m.name)
    Text("Pausa").font(.caption)
    TextField("Secondi",text:$m.dwell).frame(width:65)
    Text("s")
    Picker("Pinza",selection:$m.poseGrip) {
     Text("Ultimo comando").tag("auto");Text("Apri").tag("apri");Text("Chiudi").tag("chiudi");Text("Mantieni").tag("non comandata")
    }.frame(width:210)
    Button("＋ Registra posa"){m.recordPose()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.state.home || !m.idle)
   }
   Text(!m.state.home ? "Conferma HOME e applica i limiti per muovere il robot e registrare le pose." : "Muovi con − e +, poi registra la posa con tutti e cinque i giunti e la richiesta della pinza.").font(.caption).foregroundStyle(.secondary)
   Text("La pinza viene comandata all’arrivo nella posa. Il riordino ripercorre i tratti insegnati, anche a ritroso; può passare da HOME. Mantieni non invia comandi alla pinza.").font(.caption).foregroundStyle(.secondary)
   Text("\(m.state.sequence.filter{$0.isEnabled}.count) di \(m.state.sequence.count) pose abilitate. Una posa esclusa salta pausa e pinza; il percorso verso altre pose può comunque attraversarla.").font(.caption).foregroundStyle(.secondary)
   Button("Annulla ultima modifica pose"){m.send("pose_undo",["revision":m.state.sequence_revision])}.disabled(!m.idle || !m.state.can_undo)
   if m.state.sequence.isEmpty {
    HStack {
     Image(systemName:"square.stack.3d.up").foregroundStyle(RobotTheme.lime)
     Text("La sequenza è vuota. Registra la prima posa per iniziare.").foregroundStyle(.secondary)
    }.padding(.vertical,12)
   } else {
    VStack(spacing:0) {
     ForEach(Array(m.state.sequence.enumerated()),id:\.offset){i,p in
      VStack(alignment:.leading,spacing:8) {
       HStack(spacing:10) {
        Toggle("Abilita posa \(i+1)",isOn:Binding(get:{p.isEnabled},set:{m.send("pose_enable",["index":i,"enabled":$0,"revision":m.state.sequence_revision])})).labelsHidden().toggleStyle(.switch).disabled(!m.idle)
        Text("\(i+1)").font(.caption.bold()).foregroundStyle(RobotTheme.lime)
        Text(p.name).font(.subheadline.weight(.semibold)).lineLimit(1)
        if !p.isEnabled {Text("Esclusa").font(.caption).foregroundStyle(.secondary)}
        if p.angles_edited == true {Text("Angoli modificati").font(.caption).foregroundStyle(RobotTheme.lime)}
        Spacer()
        Button("Modifica"){editing=PoseEditRequest(index:i,revision:m.state.sequence_revision,pose:p)}.disabled(!m.idle)
        Picker("Pinza posa",selection:Binding(get:{p.grip ?? "non comandata"},set:{m.send("pose_grip",["index":i,"grip":$0,"revision":m.state.sequence_revision])})) {
         Text("Apri").tag("apri");Text("Chiudi").tag("chiudi");Text("Mantieni").tag("non comandata")
        }.labelsHidden().frame(width:110).disabled(!m.idle)
        Button {m.send("pose_move",["index":i,"target":i-1,"revision":m.state.sequence_revision])} label:{Image(systemName:"arrow.up")}.help("Sposta posa prima").disabled(i==0 || !m.idle)
        Button {m.send("pose_move",["index":i,"target":i+1,"revision":m.state.sequence_revision])} label:{Image(systemName:"arrow.down")}.help("Sposta posa dopo").disabled(i==m.state.sequence.count-1 || !m.idle)
        Button {m.send("pose_delete",["index":i,"revision":m.state.sequence_revision])} label:{Image(systemName:"trash")}.help("Elimina questa posa").disabled(!m.idle)
        Text("\(p.dwell,specifier:"%.1f") s").font(.caption).foregroundStyle(.secondary)
       }
       Text(p.pos.enumerated().map{"J\($0.offset+1) \(String(format:"%.2f",$0.element))°"}.joined(separator:" · ")).font(.caption).monospacedDigit().foregroundStyle(.secondary)
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
   Text("Ogni ciclo ripercorre i movimenti al contrario fino a HOME. La pinza mantiene l’ultima richiesta.").font(.caption).foregroundStyle(.secondary)
  }.disabled(m.firmware.busy)
  .sheet(item:$editing) {request in PoseEditor(m:m,request:request)}
 }
}
struct SessionPanel:View {
 @ObservedObject var m:Regia
 var body:some View {
  Panel(title:"Sessione e chiusura") {
   HStack(alignment:.top,spacing:20) {
    VStack(alignment:.leading,spacing:6) {
     if m.state.events.isEmpty {Text("Il diario della sessione comparirà qui.").font(.caption).foregroundStyle(.secondary)}
     else {Text(m.state.events.suffix(5).joined(separator:"\n")).font(.system(size:11,design:.monospaced)).foregroundStyle(.secondary).textSelection(.enabled)}
    }.frame(maxWidth:.infinity,alignment:.leading)
    VStack(alignment:.trailing,spacing:8) {
     Button("HOME e chiudi l’app"){m.requestQuit()}
     Text("Torna a HOME e verifica la posizione prima di uscire.").font(.caption2).foregroundStyle(.secondary)
    }
   }
  }.disabled(m.firmware.busy)
 }
}

struct Dashboard:View {
 @ObservedObject var m:Regia
 let lime=RobotTheme.lime
 var body:some View {
  VStack(spacing:0) {
   HStack {Text("ROBOT").bold();Text("CONSOLE").foregroundStyle(lime).bold();Spacer();Text(m.state.mode=="demo" ? "ANTEPRIMA" : "ROBOT REALE").font(.caption.weight(.semibold)).foregroundStyle(lime).padding(.horizontal,12).padding(.vertical,7).background(lime.opacity(0.10),in:Capsule()).overlay(Capsule().stroke(lime.opacity(0.25)));Button("■ STOP"){m.send("stop")}.buttonStyle(RobotButtonStyle(danger:true)).keyboardShortcut(.escape,modifiers:[])}.padding(22).background(RobotTheme.black)
   Rectangle().fill(lime.opacity(0.28)).frame(height:1)
   ScrollView {
    VStack(alignment:.leading,spacing:20) {
     HStack {VStack(alignment:.leading,spacing:8){Text("Insegna un gesto. Ripetilo.").font(.system(size:32,weight:.bold));Text("Controllo locale · cinque giunti · una sequenza da presentare").foregroundStyle(.secondary)};Spacer();VStack(alignment:.trailing){Text(m.connectionStatus).foregroundStyle(lime);Text("\(m.state.cycle) cicli completati").font(.caption)}}
     Panel(title:"Connessione e riferimento") {
      HStack {Picker("Modalità",selection:$m.mode){Text("Anteprima").tag("demo");Text("Robot USB").tag("robot")}.frame(width:230);Picker("Porta",selection:$m.port){Text("Nessuna porta").tag("");ForEach(m.state.ports,id:\.self){Text($0).tag($0)}}.frame(width:250);Button(m.mode == "demo" ? "Avvia anteprima" : "Connetti Mega"){m.connect()}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.idle || m.firmware.busy);if m.state.connected {Button("Scollega controllo"){m.send("disconnect")}.disabled(!m.idle || m.firmware.busy)};Button("Conferma HOME"){m.confirmHome=true}.disabled(!m.state.connected || !m.state.identified || !m.state.speed_confirmed || !m.idle || m.firmware.busy)}
      Text("HOME è la posizione fisica iniziale scelta da te. Gli angoli sono calcolati dagli impulsi, senza encoder.").font(.caption).foregroundStyle(.secondary)
      Text(m.state.guidance).font(.subheadline.weight(.medium)).foregroundStyle(lime).fixedSize(horizontal:false,vertical:true)
      if m.state.mode == "robot" && m.state.connected {
       Text(m.state.identified ? "Firmware riconosciuto. La USB alimenta la logica della Mega; non alimenta i motori. Per provare i movimenti servono anche le alimentazioni esterne dei driver." : "USB aperta non significa robot pronto. Con sola USB usa Anteprima: i motori non hanno alimentazione e le pose reali non sono verificabili.").font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true)
       if !m.state.identified {Button("Mostra firmware da caricare"){m.showFirmware()}}
      }
      if !m.message.isEmpty {Text(m.message).foregroundStyle(.orange)}
      if !m.state.error.isEmpty {Text(m.state.error).foregroundStyle(.orange)}
     }
     FirmwarePanel(m:m)
     LimitsPanel(m:m)
     MotionPanel(m:m)
     SequencePanel(m:m)
     SessionPanel(m:m)
     CompanionPanel(m:m)
    }.padding(26)
   }
  }.background(RobotTheme.black).foregroundStyle(RobotTheme.text).tint(lime).buttonStyle(RobotButtonStyle()).preferredColorScheme(.dark).frame(minWidth:1040,minHeight:720)
  .alert("Carica firmware sulla Mega?",isPresented:$m.confirmUpload){
   Button("Carica firmware"){m.firmwareAction("upload")}
   Button("Annulla",role:.cancel){}
  }message:{Text("Scriverò Regia 2 su "+m.firmwarePort+". Conferma che è la Mega 2560. Il caricamento sostituisce il programma e riavvia la scheda: predisponi il braccio e togli l’alimentazione dei motori. Chiudi eventuali monitor seriali. Dopo dovrai riconnettere e ristabilire HOME.")}
  .alert("Prepara strumenti firmware",isPresented:$m.confirmToolSetup){
   Button("Scarica dipendenze"){m.firmwareAction("setup")}
   Button("Annulla",role:.cancel){}
  }message:{Text("Scarica tramite Arduino CLI il core Arduino AVR 1.8.8 e AccelStepper 1.64. Serve Internet. Non carica nulla sulla scheda.")}
  .alert("Connessione al robot reale",isPresented:$m.confirmConnect){Button("Connetti Mega"){m.connectNow()};Button("Annulla",role:.cancel){}}message:{Text("Questa azione apre la porta seriale selezionata. Procedi solo quando hai predisposto i collegamenti e vuoi controllare il robot reale.")}
  .alert("Conferma HOME",isPresented:$m.confirmHome){Button("Conferma"){m.send("home_set")};Button("Annulla",role:.cancel){}}message:{Text(m.state.mode == "demo" ? "Confermi lo zero virtuale? L’anteprima non apre la seriale e non controlla il robot." : "Il braccio è fisicamente nella posa iniziale? La conferma azzera gli angoli e abilita la tenuta dei motori. Sostieni il braccio durante la prima abilitazione.")}
  .alert("Riproduci la sequenza",isPresented:$m.confirmPlay){Button("Esegui"){m.send("play",["repeat":m.repeatPlay])};Button("Annulla",role:.cancel){}}message:{Text("Verifica che il percorso sia libero e le condizioni uguali alla prova.")}
  .alert("Svuota sequenza",isPresented:$m.confirmClear){Button("Svuota",role:.destructive){m.send("clear")};Button("Annulla",role:.cancel){}}message:{Text("Le pose salvate saranno cancellate.")}
  .alert("Chiudi Robot Console",isPresented:$m.confirmQuit){
   if m.idle && m.state.home {Button("Torna a HOME"){m.returnAndQuit()}}
   if m.state.playing {Button("Completa ciclo e HOME"){m.finishCycleAndQuit()}}
   Button("STOP ed esci",role:.destructive){m.quit()}
   Button("Resta nell’app",role:.cancel){NSApp.reply(toApplicationShouldTerminate:false)}
  }message:{Text("Il robot non risulta fermo a HOME. Il ritorno è disponibile solo da fermo con riferimento valido. STOP interrompe gli impulsi mantenendo la tenuta.")}
  .alert("Verifica HOME",isPresented:$m.verifyQuit){Button("HOME verificata: esci"){m.quit()};Button("Resta nell’app",role:.cancel){NSApp.reply(toApplicationShouldTerminate:false)}}message:{Text("Ritorno completato nel conteggio impulsi. Verifica visivamente la posizione del robot.")}
 }
}
@main struct RobotConsole:App {
 @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
 @StateObject var model=Regia()
 var body:some Scene {Window("Robot Console",id:"main"){Dashboard(m:model).onAppear{model.delegate=delegate;delegate.model=model;for w in NSApp.windows {w.delegate=delegate}}}.defaultSize(width:1180,height:850)}
}
