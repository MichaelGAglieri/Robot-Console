// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import AppKit

struct OutputReading:Decodable,Identifiable {let name:String;let kind:String;let value:Bool?;let simulated:Bool;let source:String;var id:String{name}}
struct AdapterReading:Decodable,Identifiable {let id:String;let name:String;let simulated:Bool;let alive:Bool;let age:Double}
struct OutputRequest:Decodable,Identifiable {let id:String;let name:String;let value:Bool;let status:String}
struct IOState:Decodable {let outputs:[OutputReading];let adapters:[AdapterReading];let requests:[OutputRequest]}

struct OutputIOPanel:View {
 @ObservedObject var m:Regia
 @State private var name=""
 var body:some View {
  VStack(alignment:.leading,spacing:8){
   Divider()
   HStack{RText("Uscite digitali e adattatori").bold();Spacer();TextField(T("Nome uscita"),text:$name).frame(width:170);Button("Definisci uscita"){m.send("studio_output_add",["name":name])}.disabled(!m.idle || name.trimmingCharacters(in:.whitespaces).isEmpty)}
   if let io=m.studio?.io {
    ForEach(io.outputs){o in HStack{Text(o.name).bold();Text(o.value.map{$0 ? "1" : "0"} ?? "—").monospacedDigit();RText(o.simulated ? "Simulata" : "Confermata dall’adattatore").robotCaption();RText(o.source).robotCaption().foregroundStyle(RobotTheme.secondary)}}
    ForEach(io.adapters){a in HStack{Text(a.name).bold();RText(a.simulated ? "Simulato" : "Dichiarato misurato");RText(a.alive ? "Heartbeat attivo" : "Heartbeat scaduto").foregroundStyle(a.alive ? RobotTheme.accentText : RobotTheme.warning)}.robotCaption()}
    ForEach(io.requests.suffix(5)){r in HStack{Text(r.name);Text(r.value ? "1" : "0");RText(r.status).robotCaption()}}
   }
   RText("Le uscite si comandano come istruzioni di programma. In Anteprima sono simulate; sul robot serve la conferma dell’adattatore entro il timeout. Nessuna uscita GPIO della Mega viene modificata.").robotCaption().foregroundStyle(RobotTheme.secondary)
  }
 }
}
struct LocalAPIPanel:View {
 @ObservedObject var m:Regia
 var body:some View {
  if let api=m.localAPI {
   VStack(alignment:.leading,spacing:10){
    Divider()
    HStack{RText("API Python · programmi e I/O").bold();Spacer();Button(api.running ? "Ferma API" : "Avvia API locale"){m.send(api.running ? "api_stop" : "api_start")}}
    if api.running {
     Text(api.url).robotCaption(mono:true).textSelection(.enabled)
     Button("Copia token di questa sessione"){NSPasteboard.general.clearContents();NSPasteboard.general.setString(api.token,forType:.string)}
     Toggle(isOn:Binding(get:{api.motion_enabled},set:{m.send("api_permissions",["enabled":$0,"demo_execution":api.demo_execution])})){RText("Consenti pianificazione dei programmi da API")}
     Toggle(isOn:Binding(get:{api.demo_execution},set:{m.send("api_permissions",["enabled":api.motion_enabled,"demo_execution":$0])})){RText("Consenti esecuzione da script in Anteprima")}.disabled(!api.motion_enabled)
     if let active=api.active{Text(String(format:T("Script in esecuzione: %@"),active.name)).robotCaption();Button("STOP script"){m.send("studio_cancel")}.buttonStyle(RobotButtonStyle(danger:true))}
    }
    RText("Permessi disattivati a ogni avvio API. Sul robot reale ogni esecuzione richiede conferma nell’app. Solo 127.0.0.1 e token di sessione; nessun comando USB, firmware, HOME o limiti. Script assente per 3 s: STOP, senza ripresa automatica.").robotCaption().foregroundStyle(RobotTheme.secondary)
   }
  }
 }
}
struct APIApprovalBanner:View {
 @ObservedObject var m:Regia
 var body:some View {
  if let request=m.localAPI?.pending {
   HStack(spacing:12){
    Image(systemName:"hand.raised.fill")
    VStack(alignment:.leading,spacing:3){
     RText("Richiesta Python · conferma sul robot reale").bold()
     Text(request.name)
     Text(String(format:T("Piano %@ · %.1f s stimati · %lld rami verificati"),String(request.plan_id.prefix(12)),request.duration,request.branches)).robotCaption()
     RText("Controlla il piano in Studio prima di approvare. La conferma vale solo per questa esecuzione.").robotCaption()
    }
    Spacer()
    Button("Rifiuta richiesta"){m.send("api_approve",["id":request.id,"confirmed":false])}
    Button("Approva ed esegui"){m.send("api_approve",["id":request.id,"confirmed":true])}.buttonStyle(RobotButtonStyle(prominent:true)).disabled(!m.idle || !m.speedEdits.isEmpty)
   }.padding(12).background(RobotTheme.warning.opacity(0.12)).overlay(Rectangle().stroke(RobotTheme.warning.opacity(0.4))).padding(.horizontal,16).padding(.top,8)
  }
 }
}
