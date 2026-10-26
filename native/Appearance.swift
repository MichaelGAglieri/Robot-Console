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
 // Dark green keeps lime accents readable on the light surfaces.
 static let lime = adaptive(light:rgb(0.20,0.36,0.035),dark:rgb(0.66,1.0,0.16))
 static let black = adaptive(light:rgb(0.94,0.96,0.925),dark:rgb(0.035,0.043,0.035))
 static let graphite = adaptive(light:rgb(0.995,1.0,0.985),dark:rgb(0.10,0.115,0.095))
 static let surface = adaptive(light:rgb(0.975,0.985,0.96),dark:rgb(0.065,0.077,0.060))
 static let text = adaptive(light:rgb(0.10,0.135,0.085),dark:rgb(0.94,0.96,0.91))
 static let secondary = adaptive(light:rgb(0.36,0.40,0.34),dark:rgb(0.65,0.69,0.62))
 static let stop = adaptive(light:rgb(0.75,0.14,0.10),dark:rgb(1.0,0.34,0.31))
 static let onStop = adaptive(light:.white,dark:rgb(0.035,0.043,0.035))
 // Filled lime buttons retain the robot's bright green in both appearances.
 static let buttonLime = Color(red:0.66,green:1.0,blue:0.16)
 static let ink = Color(red:0.035,green:0.043,blue:0.035)
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
