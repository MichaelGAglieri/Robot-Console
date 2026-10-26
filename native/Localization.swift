// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import Foundation

enum AppLanguage:String,CaseIterable,Identifiable {
 static let storageKey="RobotConsole.Language"
 case italian="it",english="en"
 var id:String{rawValue}
 var title:String{self == .italian ? "Italiano" : "English"}
 var locale:Locale{Locale(identifier:rawValue)}
 static var current:AppLanguage{AppLanguage(rawValue:UserDefaults.standard.string(forKey:storageKey) ?? "it") ?? .italian}
}
private enum Translations {
 static let english:[String:String]={guard let p=Bundle.main.url(forResource:"English",withExtension:"json"),let data=try? Data(contentsOf:p),let dict=try? JSONDecoder().decode([String:String].self,from:data) else{return [:]};return dict}()
 static let token=try! NSRegularExpression(pattern:#"%(?:\d+\$)?(?:@|lld|ld|d|g|(?:\.\d+)?f)|%%"#)
 static let patterns:[(NSRegularExpression,String)]=english.keys.sorted{$0.count>$1.count}.compactMap{key in
  let range=NSRange(key.startIndex...,in:key);let matches=token.matches(in:key,range:range)
  guard matches.contains(where:{(key as NSString).substring(with:$0.range) != "%%"}) else{return nil}
  var source="\\A";var last=0
  for match in matches {source+=NSRegularExpression.escapedPattern(for:(key as NSString).substring(with:NSRange(location:last,length:match.range.location-last)));source+=(key as NSString).substring(with:match.range)=="%%" ? "%" : "(.+?)";last=match.range.location+match.range.length}
  source+=NSRegularExpression.escapedPattern(for:(key as NSString).substring(from:last))+"\\z"
  guard let regex=try? NSRegularExpression(pattern:source) else{return nil};return (regex,english[key]!)
 }
 static func text(_ source:String)->String {
  guard AppLanguage.current == .english else{return source}
  if let exact=english[source]{return exact}
  for (regex,format) in patterns {
   guard let result=regex.firstMatch(in:source,range:NSRange(source.startIndex...,in:source)) else{continue}
   var answer="";var last=0;var group=1
   for match in token.matches(in:format,range:NSRange(format.startIndex...,in:format)) {
    answer+=(format as NSString).substring(with:NSRange(location:last,length:match.range.location-last))
    if (format as NSString).substring(with:match.range)=="%%"{answer+="%"}else if group<result.numberOfRanges{let captured=(source as NSString).substring(with:result.range(at:group));answer+=english[captured] ?? captured;group+=1}
    last=match.range.location+match.range.length
   }
   answer+=(format as NSString).substring(from:last);return answer
  }
  return source
 }
}
func T(_ source:String)->String{Translations.text(source)}
// Literal keys use SwiftUI localization; runtime status uses the same bilingual catalog.
struct RText:View {
 @AppStorage(AppLanguage.storageKey) private var language=AppLanguage.italian
 private let key:LocalizedStringKey?;private let value:String?
 init(_ key:LocalizedStringKey){self.key=key;self.value=nil}
 init<S:StringProtocol>(_ value:S){self.key=nil;self.value=String(value)}
 @ViewBuilder var body:some View{let _=language;if let key{SwiftUI.Text(key)}else{SwiftUI.Text(verbatim:T(value ?? ""))}}
}

struct LanguagePicker:View {
 @AppStorage(AppLanguage.storageKey) private var language=AppLanguage.italian
 var body:some View{Picker("Lingua",selection:$language){ForEach(AppLanguage.allCases){RText($0.title).tag($0)}}.pickerStyle(.menu).frame(width:175).accessibilityLabel("Lingua dell’app")}
}
