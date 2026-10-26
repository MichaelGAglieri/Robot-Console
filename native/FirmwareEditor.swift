// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import AppKit
import UniformTypeIdentifiers
struct FirmwareAxis:Codable {var driver:String;var steps:Int;var microstep:Int;var reduction:Double;var invert:Bool;var active:Bool?;var step_pin:Int?;var dir_pin:Int?;var enable_pin:Int?}
struct FirmwareProfile:Codable {var schema:Int;var name:String;var board:String;var axes:[FirmwareAxis]}
struct FirmwareWorkspaceState:Decodable {let profile:FirmwareProfile;let identity:String;let `default`:FirmwareProfile;let max_speed:Double;let files:[String];let folder:String;let status:String;let error:String;let received_identity:String;let matches:Bool;let axis_control_source:Bool?}
struct FirmwareAxisDraft {
 var driver:String;var steps:String;var micro:String;var ratio:String;var invert:Bool;var active:Bool;var stepPin:String;var dirPin:String;var enablePin:String
 init(_ a:FirmwareAxis){driver=a.driver;steps=String(a.steps);micro=String(a.microstep);ratio=String(format:"%g",a.reduction);invert=a.invert;active=a.active ?? false;stepPin=String(a.step_pin ?? -1);dirPin=String(a.dir_pin ?? -1);enablePin=String(a.enable_pin ?? -1)}
 func value()throws->FirmwareAxis {
  guard let s=Int(steps),let m=Int(micro),let r=Double(ratio.replacingOccurrences(of:",",with:".")),r.isFinite else{throw NSError(domain:"Compila passi/giro, microstep e riduzione con numeri validi.",code:1)}
  return FirmwareAxis(driver:driver,steps:s,microstep:m,reduction:r,invert:invert,active:active,step_pin:Int(stepPin),dir_pin:Int(dirPin),enable_pin:Int(enablePin))
 }
}
struct FirmwareParameterRow:View {
 let index:Int;@Binding var a:FirmwareAxisDraft
 var body:some View {
  VStack(alignment:.leading){HStack {
   RText("J\(index+1)").bold().frame(width:25)
   Picker("Driver",selection:$a.driver){if index==1 || index==5{RText("DM542").tag("DM542")}else{RText("A4988").tag("A4988");RText("DRV8825").tag("DRV8825")}}.frame(width:155)
   TextField("Passi/giro",text:$a.steps).accessibilityLabel("Passi motore J\(index+1)")
   TextField("Microstep ×",text:$a.micro).accessibilityLabel("Microstepping J\(index+1)")
   TextField("Riduzione :1",text:$a.ratio).accessibilityLabel("Riduzione J\(index+1)")
   Toggle("Inverti",isOn:$a.invert)
   if let v=try? a.value(){RText("\(Double(v.steps)*Double(v.microstep)*v.reduction/360,specifier:"%.2f") imp/°").font(.caption.monospacedDigit()).frame(width:105)}
  }
  if index==5{HStack{Toggle("J6 fisico · driver esterno",isOn:$a.active);RText("STEP");TextField("Pin",text:$a.stepPin).frame(width:50);RText("DIR");TextField("Pin",text:$a.dirPin).frame(width:50);RText("ENA");TextField("−1",text:$a.enablePin).frame(width:50)}.font(.caption)
   RText("−1 = non collegato. Pin disponibili: 40, 42, 44, 57, 58, 59, 63–66; verificane l’uso sugli accessori. Per DM542 lascia ENA a −1. J6 resta disponibile in Anteprima anche senza driver.").font(.caption2).foregroundStyle(RobotTheme.secondary)}
  }
 }
}
struct FirmwareEditorPanel:View {
 @ObservedObject var m:Regia
 @State private var expanded=false;@State private var name="";@State private var axes:[FirmwareAxisDraft]=[];@State private var error="";@State private var confirmGenerate=false;@State private var confirmRestore=false;@State private var confirmUpgrade=false
 var editable:Bool{!m.state.connected && m.idle && !m.firmware.busy}
 func load(){if let p=m.firmwareWorkspace?.profile{name=p.name;axes=p.axes.map(FirmwareAxisDraft.init)}}
 func generate(){
  do{
   let p=FirmwareProfile(schema:1,name:name,board:"mega2560",axes:try axes.map{try $0.value()});let data=try JSONEncoder().encode(p);let object=try JSONSerialization.jsonObject(with:data)
   m.send("firmware_generate",["profile":object],completion:{ok in if ok{m.send("firmware_read",["name":"RegiaDemo.ino"])}})
  }catch{self.error=error.localizedDescription}
 }
 var body:some View {
  Panel(title:"Firmware · parametri ed editor") {
   if let workspace=m.firmwareWorkspace {
    RText("\(workspace.profile.name) · ID \(workspace.identity) · massimo calcolato \(workspace.max_speed,specifier:"%.1f")°/s").font(.caption.monospaced()).foregroundStyle(RobotTheme.lime)
    RText(workspace.status).font(.caption).foregroundStyle(RobotTheme.secondary)
    if workspace.axis_control_source != true {
     HStack{RText("Il sorgente salvato non include ancora il controllo ENABLE per giunto.").font(.caption).foregroundStyle(.orange);Button("Aggiorna comandi giunti…"){confirmUpgrade=true}.disabled(!editable)}
    }
    DisclosureGroup("Microstepping, riduttori e sorgenti",isExpanded:$expanded){
     VStack(alignment:.leading,spacing:12){
      TextField("Nome profilo",text:$name)
      HStack{RText("Asse / driver").frame(width:200,alignment:.leading);RText("Passi/giro");Spacer();RText("Microstep ×");Spacer();RText("Riduzione :1");Spacer()}.font(.caption).foregroundStyle(RobotTheme.secondary)
      ForEach(axes.indices,id:\.self){i in FirmwareParameterRow(index:i,a:$axes[i])}
      RText("Microstep 8 significa 1/8: jumper e DIP fisici devono corrispondere. La riduzione è giri motore / giro uscita, ad esempio 38,4. Corrente e alimentazione restano regolazioni hardware. Mega/RAMPS con DM542 su J2 e J6 esterno opzionale; nessuna sesta uscita motore è presente sulla RAMPS.").font(.caption).foregroundStyle(RobotTheme.secondary)
      HStack{Button("Genera e salva dai parametri…"){confirmGenerate=true}.buttonStyle(RobotButtonStyle(prominent:true));Button("Rileggi profilo"){load()};Button("Ripristina firmware originale…"){confirmRestore=true};Button("Esporta sorgenti…"){let p=NSSavePanel();p.allowedContentTypes=[.zip];p.nameFieldStringValue="firmware-robot.zip";if p.runModal() == .OK,let url=p.url{m.send("firmware_export",["path":url.path])}}}
      Divider()
      HStack{Picker("File",selection:$m.firmwareFile){ForEach(workspace.files,id:\.self){RText($0)}}.onChange(of:m.firmwareFile){_,file in m.send("firmware_read",["name":file])};Button("Rileggi file"){m.send("firmware_read",["name":m.firmwareFile])};Spacer();Button("Salva sorgente"){m.send("firmware_save",["name":m.firmwareFile,"text":m.firmwareText])}.buttonStyle(RobotButtonStyle(prominent:true))}
      TextEditor(text:$m.firmwareText).font(.system(size:12,design:.monospaced)).scrollContentBackground(.hidden).padding(8).background(RobotTheme.black,in:RoundedRectangle(cornerRadius:8)).frame(height:280)
      RText("Il salvataggio conserva una revisione precedente. Verifica compilazione e Carica sulla Mega usano questi file salvati. Modifiche libere possono rendere il firmware incompatibile: controlla watchdog, pin, limiti e identificazione. Nessuna scrittura sulla scheda avviene salvando.").font(.caption).foregroundStyle(RobotTheme.secondary)
      HStack{Button("Verifica compilazione"){m.firmwareAction("compile")};Button("Carica sulla Mega…"){m.confirmUpload=true}.disabled(m.firmwarePort.isEmpty || !m.firmware.available);Button("Apri cartella sorgenti"){NSWorkspace.shared.open(URL(fileURLWithPath:workspace.folder))}}
      if !workspace.error.isEmpty{RText(workspace.error).foregroundStyle(RobotTheme.stop)}
      if !error.isEmpty{RText(error).foregroundStyle(RobotTheme.stop)}
     }.padding(.top,10).disabled(!editable)
    }
   }
  }.onAppear{load();m.send("firmware_read",["name":m.firmwareFile])}
   .onChange(of:m.firmwareWorkspace?.identity){_,_ in load()}
   .alert("Generare il firmware dai parametri?",isPresented:$confirmGenerate){Button("Genera e salva"){generate()};Button("Annulla",role:.cancel){}}message:{RText("Salvo una revisione e aggiorno le costanti dei sei canali nel sorgente. La Mega non viene caricata. Conferma che i valori corrispondono ai driver e ai riduttori reali.")}
   .alert("Aggiornare i comandi dei giunti?",isPresented:$confirmUpgrade){Button("Aggiorna sorgente"){m.send("firmware_upgrade_axes",completion:{ok in if ok{load();m.send("firmware_read",["name":m.firmwareFile])}})};Button("Annulla",role:.cancel){}}message:{RText("Salvo una revisione, sostituisco il file RegiaDemo.ino con quello incluso e rigenero il tuo profilo, mantenendo microstep, riduzioni, versi e pin. Eventuali modifiche manuali al file restano nella revisione. La Mega non viene caricata.")}
   .alert("Ripristinare i sorgenti originali?",isPresented:$confirmRestore){Button("Ripristina"){m.send("firmware_restore",completion:{ok in if ok{load();m.send("firmware_read",["name":m.firmwareFile])}})};Button("Annulla",role:.cancel){}}message:{RText("La versione corrente resta nelle revisioni locali. Nessun caricamento sulla Mega.")}
 }
}
