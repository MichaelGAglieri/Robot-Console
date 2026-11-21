// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import AppKit
import UniformTypeIdentifiers

private struct ManualSection:Identifiable {
 let id:Int;let title:String;let content:String
 var searchable:String{title+"\n"+content}
}
private enum ManualDocument {
 static let documents:[String:String]=["it","en"].reduce(into:[:]){result,language in
  let filename=language=="en" ? "USER_GUIDE.en.md" : "USER_GUIDE.md"
  if let url=Bundle.main.resourceURL?.appendingPathComponent("docs/"+filename){result[language]=(try? String(contentsOf:url,encoding:.utf8)) ?? ""}
 }
 static func sections(_ text:String)->[ManualSection] {
  var result:[ManualSection]=[];var title="";var body:[String]=[]
  for line in text.components(separatedBy:.newlines) {
   if line.hasPrefix("## ") {
    if !title.isEmpty{result.append(ManualSection(id:result.count,title:title,content:body.joined(separator:"\n")))}
    title=String(line.dropFirst(3));body=[]
   }else if !title.isEmpty{body.append(line)}
  }
  if !title.isEmpty{result.append(ManualSection(id:result.count,title:title,content:body.joined(separator:"\n")))}
  return result
 }
}
private struct ManualParagraph:View {
 let source:String
 var heading:Bool{source.hasPrefix("### ")}
 var content:String{heading ? String(source.dropFirst(4)) : source}
 var rich:AttributedString{(try? AttributedString(markdown:content,options:.init(interpretedSyntax:.inlineOnlyPreservingWhitespace))) ?? AttributedString(content)}
 var body:some View{Text(rich).font(heading ? .system(size:18,weight:.semibold) : .system(size:15)).lineSpacing(5).foregroundStyle(heading ? RobotTheme.accentText : RobotTheme.text).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}
}
struct StudioGuide:View {
 @Environment(\.dismiss) private var dismiss
 @AppStorage(AppLanguage.storageKey) private var language=AppLanguage.italian
 @State private var query=""
 @State private var selection=0
 var source:String{ManualDocument.documents[language.rawValue] ?? ""}
 private var sections:[ManualSection]{ManualDocument.sections(source)}
 private var matches:[ManualSection]{let text=query.trimmingCharacters(in:.whitespacesAndNewlines);return text.isEmpty ? sections : sections.filter{$0.searchable.localizedStandardContains(text)}}
 private var current:ManualSection?{matches.first(where:{$0.id==selection}) ?? matches.first}
 func save(){
  let panel=NSSavePanel();panel.allowedContentTypes=[UTType(filenameExtension:"md") ?? .plainText];panel.nameFieldStringValue=language == .english ? "Robot-Console-User-Guide.en.md" : "Robot-Console-Guida.md"
  if panel.runModal() == .OK,let url=panel.url{do{try source.write(to:url,atomically:true,encoding:.utf8)}catch{NSAlert(error:error).runModal()}}
 }
 var body:some View {
  VStack(alignment:.leading,spacing:14) {
   HStack{VStack(alignment:.leading,spacing:4){RText("Guida completa Robot Console").font(.title2.bold());RText("Manuale offline · funzioni, procedure ed esempi").robotCaption().foregroundStyle(RobotTheme.secondary)};Spacer();Button{save()}label:{RText("Salva manuale…")};Button{dismiss()}label:{RText("Chiudi")}.keyboardShortcut(.cancelAction)}
   TextField(T("Cerca nella guida…"),text:$query).textFieldStyle(.roundedBorder).accessibilityLabel(T("Cerca nella guida"))
   Divider()
   HStack(alignment:.top,spacing:18) {
    ScrollView {
     VStack(alignment:.leading,spacing:5){ForEach(matches){section in Button{selection=section.id}label:{Text(section.title).font(.system(size:13,weight:current?.id==section.id ? .semibold : .regular)).multilineTextAlignment(.leading).frame(maxWidth:.infinity,alignment:.leading).padding(8).background(current?.id==section.id ? RobotTheme.lime.opacity(0.16) : .clear,in:RoundedRectangle(cornerRadius:7))}.buttonStyle(.plain)}}
    }.frame(width:235)
    Divider()
    if let item=current {
     ScrollViewReader{proxy in
      ScrollView {
       VStack(alignment:.leading,spacing:15){Text(item.title).font(.title2.bold()).id("top");ForEach(Array(item.content.components(separatedBy:"\n\n").filter{!$0.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty}.enumerated()),id:\.offset){_,paragraph in ManualParagraph(source:paragraph.trimmingCharacters(in:.whitespacesAndNewlines))}}
        .frame(maxWidth:.infinity,alignment:.leading).padding(.trailing,12).id(language.rawValue+String(item.id))
      }.onChange(of:item.id){_,_ in proxy.scrollTo("top",anchor:.top)}
     }.frame(maxWidth:.infinity)
    }else{RText("Nessun risultato. Prova un’altra parola.").foregroundStyle(RobotTheme.secondary).frame(maxWidth:.infinity)}
   }
   Divider()
   HStack {
    Button{if let item=current,let i=matches.firstIndex(where:{$0.id==item.id}),i>0{selection=matches[i-1].id}}label:{RText("Capitolo precedente")}.disabled(current?.id==matches.first?.id)
    Button{if let item=current,let i=matches.firstIndex(where:{$0.id==item.id}),i+1<matches.count{selection=matches[i+1].id}}label:{RText("Capitolo successivo")}.disabled(current?.id==matches.last?.id)
    Spacer();Text("\(matches.count) / \(sections.count)").font(.caption.monospacedDigit())
   }
  }.padding(24).frame(width:1000,height:700).background(RobotTheme.surface).foregroundStyle(RobotTheme.text).tint(RobotTheme.accentText).environment(\.locale,language.locale).buttonStyle(RobotButtonStyle())
 }
}
