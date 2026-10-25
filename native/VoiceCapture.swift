// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import Foundation
import Speech
import AVFoundation
@MainActor final class VoiceCapture:ObservableObject {
 @Published var listening=false
 @Published var message=""
 private let engine=AVAudioEngine()
 private var request:SFSpeechAudioBufferRecognitionRequest?
 private var task:SFSpeechRecognitionTask?
 private var installed=false
 private var generation=0
 func stop() {
  generation+=1
  engine.stop()
  if installed {engine.inputNode.removeTap(onBus:0);installed=false}
  request?.endAudio();task?.cancel();task=nil;request=nil;listening=false
 }
 func start(_ receive:@escaping (String)->Void) {
  stop();let token=generation;message="Richiesta accesso al microfono…"
  SFSpeechRecognizer.requestAuthorization { status in
   AVCaptureDevice.requestAccess(for:.audio) { granted in
    Task { @MainActor in
     guard token == self.generation else{return}
     guard status == .authorized,granted else {self.message="Abilita Microfono e Riconoscimento vocale nelle impostazioni Privacy di macOS.";return}
     self.begin(receive)
    }
   }
  }
 }
 private func begin(_ receive:@escaping (String)->Void) {
  guard let recognizer=SFSpeechRecognizer(locale:Locale(identifier:"it-IT")),recognizer.isAvailable else {message="Riconoscimento italiano non disponibile. Puoi scrivere nella chat.";return}
  // Keep audio on this Mac; never silently fall back to remote recognition.
  guard recognizer.supportsOnDeviceRecognition else {message="Dettatura locale non disponibile su questo Mac. Usa il campo di testo.";return}
  let r=SFSpeechAudioBufferRecognitionRequest()
  r.requiresOnDeviceRecognition=true;r.shouldReportPartialResults=true;request=r
  let node=engine.inputNode,format=node.outputFormat(forBus:0)
  guard format.sampleRate>0,format.channelCount>0 else {message="Microfono non disponibile.";return}
  node.installTap(onBus:0,bufferSize:1024,format:format){buffer,_ in r.append(buffer)}
  installed=true
  let token=generation
  task=recognizer.recognitionTask(with:r){result,error in
   Task { @MainActor in
    guard token == self.generation else{return}
    if let result {receive(result.bestTranscription.formattedString)}
    if error != nil || result?.isFinal == true {self.stop()}
   }
  }
  do {try engine.start();listening=true;message="Ti ascolto. Ferma la dettatura e premi Invia."}
  catch {stop();message=error.localizedDescription}
 }
}
