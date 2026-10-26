// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import AppKit
struct ROSTopic:Decodable,Identifiable {let name:String;let age:Double;var id:String{name}}
struct ROSHealth:Decodable {let running:Bool;let status:String;let domain:Int;let project:String;let age:Double;let nodes:[String];let topics:[ROSTopic];let error:String;let visualization_topic:String;let frame_prefix:String}
struct OptionalTool:Decodable,Identifiable {let name:String;let available:Bool;let running:Bool;var id:String{name}}
struct ToolsState:Decodable {let project:String;let error:String;let tools:[OptionalTool]}
struct LocalAPIState:Decodable {let running:Bool;let url:String;let token:String;let scope:String}
struct ROSPanel:View {
 @ObservedObject var m:Regia
 @AppStorage("RobotConsole.ROSDomain") private var domain=42
 @State private var expanded=false
 func name(_ value:String)->String{["rviz":"RViz 2","gazebo":"Gazebo · scena di esempio","webots":"Webots · laboratorio","bag":"Registrazione rosbag" ][value] ?? value}
 var body:some View {
  Panel(title:"ROS 2 · connessione, strumenti e API") {
   HStack{RText(m.rosHealth?.status ?? "Disconnesso").font(.headline).foregroundStyle(RobotTheme.lime);Spacer();RText("Solo osservazione e visualizzazione").font(.caption).foregroundStyle(RobotTheme.secondary)}
   HStack{TextField("Progetto ROS/Pixi",text:$m.projectPath);Button("Scegli cartella…"){m.chooseProject();m.send("tool_check",["project":m.projectPath])};RText("Dominio");TextField("42",value:$domain,formatter:NumberFormatter()).frame(width:55);Button("Collega ROS 2"){m.send("ros_connect",["project":m.projectPath,"domain":domain]);m.send("tool_check",["project":m.projectPath])};Button("Scollega"){m.send("ros_disconnect")}}
   RText("Il collegamento pubblica /robot_console/joint_states, /robot_console/robot_description e TF con prefisso robot_console/. Il modello segue l’anteprima o gli angoli stimati, secondo la modalità scelta. Nessun comando motore viene ricevuto da ROS.").font(.caption).foregroundStyle(RobotTheme.secondary)
   if let h=m.rosHealth,h.running {
    HStack{RText("Heartbeat: \(h.age,specifier:"%.1f") s");RText("Nodi: "+h.nodes.joined(separator:", ")).lineLimit(2)}.font(.caption)
    ForEach(h.topics){topic in RText("\(topic.name) · \(topic.age,specifier:"%.1f") s dall’ultimo dato").font(.caption.monospaced())}
    if !h.error.isEmpty{RText(h.error).foregroundStyle(RobotTheme.stop)}
   }
   RText(m.rosEvent).font(.caption).lineLimit(3)
   DisclosureGroup("Strumenti opzionali e integrazioni",isExpanded:$expanded){
    VStack(alignment:.leading,spacing:10){
     Button("Rileva strumenti nel progetto"){m.send("tool_check",["project":m.projectPath])}
     if let tools=m.tools {ForEach(tools.tools){tool in HStack{RText(name(tool.name)).frame(minWidth:230,alignment:.leading);RText(tool.available ? (tool.running ? "Avviato dalla console" : "Disponibile") : "Non rilevato").font(.caption).foregroundStyle(RobotTheme.secondary);Spacer();Button("Avvia"){m.send("tool_start",["name":tool.name,"project":m.projectPath,"domain":domain])}.disabled(!tool.available || tool.running);Button("Ferma"){m.send("tool_stop",["name":tool.name])}.disabled(!tool.running)}}}
     RText("RViz apre il modello della console; Webots mantiene il laboratorio dimostrativo separato. Gazebo apre una scena di esempio: un modello fisico calibrato richiede masse, inerzie e controllori appropriati. Gli strumenti non sono scaricati automaticamente e i log restano locali.").font(.caption).foregroundStyle(RobotTheme.secondary)
     Divider()
     if let api=m.localAPI {
      HStack{RText("API locale · stato e sensori").bold();Spacer();Button(api.running ? "Ferma API" : "Avvia API locale"){m.send(api.running ? "api_stop" : "api_start")}}
      if api.running {
       RText(api.url).font(.caption.monospaced()).textSelection(.enabled)
       Button("Copia token di questa sessione"){NSPasteboard.general.clearContents();NSPasteboard.general.setString(api.token,forType:.string)}
      }
      RText("API autenticata solo su 127.0.0.1; stato in lettura e valori di sensori già definiti. Nessuna apertura USB, HOME o comando di movimento. Il token cambia a ogni avvio e non viene salvato nei progetti.").font(.caption).foregroundStyle(RobotTheme.secondary)
     }
    }.padding(.top,10)
   }
  }
 }
}
