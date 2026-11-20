// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import AppKit

enum AppAppearance:String,CaseIterable,Identifiable {
 static let storageKey = "RobotConsole.Appearance"
 case system,light,dark
 var id:String {rawValue}
 var title:String {
  switch self {
   case .system:return "Sistema"
   case .light:return "Chiara"
   case .dark:return "Scura"
  }
 }
 var colorScheme:ColorScheme? {
  switch self {
   case .system:return nil
   case .light:return .light
   case .dark:return .dark
  }
 }
 var appKitAppearance:NSAppearance? {
  switch self {
   case .system:return nil
   case .light:return NSAppearance(named:.aqua)
   case .dark:return NSAppearance(named:.darkAqua)
  }
 }
}

enum RobotTheme {
 private static func adaptive(light:NSColor,dark:NSColor)->Color {
  Color(nsColor:NSColor(name:nil){appearance in
   appearance.bestMatch(from:[.aqua,.darkAqua]) == .darkAqua ? dark : light
  })
 }
 private static func rgb(_ red:CGFloat,_ green:CGFloat,_ blue:CGFloat)->NSColor {
  NSColor(srgbRed:red,green:green,blue:blue,alpha:1)
 }
 private static func hex(_ value:UInt32)->NSColor {
  rgb(CGFloat((value>>16)&0xFF)/255,CGFloat((value>>8)&0xFF)/255,CGFloat(value&0xFF)/255)
 }
 // Industrial palette: neutral cool greys, white cards, the DOC lime as brand accent only.
 // Light-mode text colours keep at least 4.8:1 contrast on every background below.
 static let lime = Color(nsColor:hex(0xA3EA2F))
 static let accentText = adaptive(light:hex(0x2B760C),dark:hex(0xA6F43C))
 static let canvas = adaptive(light:hex(0xE8ECF0),dark:hex(0x0B0E10))
 // Inset wells inside cards (lists, editors, joint tiles).
 static let black = adaptive(light:hex(0xF2F4F7),dark:hex(0x12161A))
 // Sidebars and secondary fills.
 static let graphite = adaptive(light:hex(0xF6F7F9),dark:hex(0x1C2227))
 static let surface = adaptive(light:hex(0xFFFFFF),dark:hex(0x171C20))
 static let border = adaptive(light:hex(0xCDD4DC),dark:hex(0x2C343B))
 static let text = adaptive(light:hex(0x11161B),dark:hex(0xE7EBEE))
 static let secondary = adaptive(light:hex(0x4F5A66),dark:hex(0x9AA4AE))
 static let stop = adaptive(light:hex(0xC62828),dark:hex(0xFF5A52))
 static let onStop = adaptive(light:.white,dark:hex(0x0B0E10))
 static let warning = adaptive(light:hex(0xA15C00),dark:hex(0xFFB020))
 // Filled lime buttons retain the robot's bright green in both appearances.
 static let buttonLime = Color(nsColor:hex(0xA3EA2F))
 static let ink = Color(nsColor:hex(0x0B0F0B))
 // Header bar is dark in both appearances, like a machine control panel.
 static let header = Color(nsColor:hex(0x14191E))
 static let headerText = Color(nsColor:hex(0xEEF2F5))
 static let headerSecondary = Color(nsColor:hex(0x9AA5B0))
 static let headerControl = Color(nsColor:hex(0x232A31))
 static let amber = Color(nsColor:hex(0xFFB020))
 // Selected segments carry white text: a deep green keeps it legible in both appearances.
 static let control = Color(nsColor:hex(0x2B760C))
}

struct AppearancePicker:View {
 @AppStorage(AppAppearance.storageKey) private var appearance = AppAppearance.system
 var body:some View {
  Picker("Tema",selection:$appearance) {
   ForEach(AppAppearance.allCases){theme in RText(theme.title).tag(theme)}
  }
  .pickerStyle(.menu)
  .frame(width:172)
  .accessibilityLabel("Tema dell’app")
  .help("Chiara, Scura oppure Sistema per seguire automaticamente l’aspetto di macOS")
 }
}

// The central viewport supplies a finite width to every panel, even inside scrolling.
private struct PanelWidthKey:EnvironmentKey {static let defaultValue:CGFloat=1000}
extension EnvironmentValues {var panelWidth:CGFloat {get{self[PanelWidthKey.self]}set{self[PanelWidthKey.self]=newValue}}}
private struct ReadableCaption:ViewModifier {
 @Environment(\.colorScheme) var scheme
 var small:Bool;var mono:Bool
 func body(content:Content)->some View {
  content.font(.system(size:scheme == .light ? (small ? 12 : 13) : (small ? 11 : 12),weight:scheme == .light ? .medium : .regular,design:mono ? .monospaced : .default))
 }
}
extension View {func robotCaption(small:Bool=false,mono:Bool=false)->some View {modifier(ReadableCaption(small:small,mono:mono))}}
