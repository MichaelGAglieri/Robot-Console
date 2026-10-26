// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import SwiftUI
import AppKit
@preconcurrency import AVFoundation
import Vision
import CoreImage
import UniformTypeIdentifiers

final class CameraFrameReader:NSObject,AVCaptureVideoDataOutputSampleBufferDelegate,@unchecked Sendable {
 let lock=NSLock();var frame:CVPixelBuffer?
 func captureOutput(_ output:AVCaptureOutput,didOutput sampleBuffer:CMSampleBuffer,from connection:AVCaptureConnection){lock.lock();frame=CMSampleBufferGetImageBuffer(sampleBuffer);lock.unlock()}
 func image()->CVPixelBuffer?{lock.lock();defer{lock.unlock()};return frame}
}
final class CameraPipeline:@unchecked Sendable {
 let session=AVCaptureSession();let frames=CameraFrameReader();let queue=DispatchQueue(label:"robotconsole.camera")
 func start(device:AVCaptureDevice,completion:@escaping @Sendable (String?)->Void){
  queue.async{[self] in
   do {
    let input=try AVCaptureDeviceInput(device:device)
    session.beginConfiguration();session.sessionPreset = .medium
    for old in session.inputs{session.removeInput(old)};for old in session.outputs{session.removeOutput(old)}
    guard session.canAddInput(input)else{session.commitConfiguration();completion("Ingresso video non disponibile.");return};session.addInput(input)
    let output=AVCaptureVideoDataOutput();output.alwaysDiscardsLateVideoFrames=true;output.setSampleBufferDelegate(frames,queue:queue)
    guard session.canAddOutput(output)else{session.commitConfiguration();completion("Uscita video non disponibile.");return};session.addOutput(output);session.commitConfiguration();session.startRunning();completion(nil)
   }catch{completion(error.localizedDescription)}
  }
 }
 func stop(){queue.async{[self] in session.stopRunning()}}
}
@MainActor final class CameraMonitor:ObservableObject {
 @Published var running=false;@Published var status="Telecamera spenta";@Published var codes="";@Published var devices:[AVCaptureDevice]=[];@Published var selected=""
 let pipeline=CameraPipeline();var session:AVCaptureSession{pipeline.session};private var generation=0
 func refresh(){devices=AVCaptureDevice.DiscoverySession(deviceTypes:[.builtInWideAngleCamera,.external],mediaType:.video,position:.unspecified).devices;if !devices.contains(where:{$0.uniqueID==selected}){selected=devices.first?.uniqueID ?? ""}}
 func start(){
  guard !running else{return};generation+=1;let token=generation;status="Richiesta accesso alla telecamera…"
  AVCaptureDevice.requestAccess(for:.video){granted in Task{@MainActor in
   guard token==self.generation else{return}
   if !granted{self.status="Accesso non consentito: abilita Telecamera nelle impostazioni Privacy di macOS.";return}
   self.refresh();guard let device=self.devices.first(where:{$0.uniqueID==self.selected})else{self.status="Nessuna telecamera disponibile.";return}
   self.running=true;self.status="Avvio video locale…"
   self.pipeline.start(device:device){error in Task{@MainActor in
    guard token==self.generation else{return}
    if let error{self.running=false;self.status=error}else{self.status="Video locale · "+device.localizedName}
   }}
  }}
 }
 func stop(){generation+=1;pipeline.stop();running=false;status="Telecamera spenta"}
 func detectCodes(){
  guard let image=pipeline.frames.image()else{status="Avvia prima la telecamera.";return}
  let request=VNDetectBarcodesRequest();request.symbologies=[.qr]
  do {try VNImageRequestHandler(cvPixelBuffer:image).perform([request]);codes=(request.results ?? []).compactMap{$0.payloadStringValue}.joined(separator:"\n");if codes.isEmpty{codes="Nessun codice QR rilevato."}}catch{codes=error.localizedDescription}
 }
 func saveFrame(){
  guard let buffer=pipeline.frames.image()else{return};let panel=NSSavePanel();panel.allowedContentTypes=[.png];panel.nameFieldStringValue="robot-camera.png"
  if panel.runModal() == .OK,let url=panel.url {let image=CIImage(cvPixelBuffer:buffer);let context=CIContext();do{try context.writePNGRepresentation(of:image,to:url,format:.RGBA8,colorSpace:CGColorSpaceCreateDeviceRGB());status="Fotogramma salvato."}catch{status=error.localizedDescription}}
 }
}
struct CameraPreview:NSViewRepresentable {
 let session:AVCaptureSession
 final class VideoView:NSView {
  let video=AVCaptureVideoPreviewLayer()
  override init(frame:NSRect){super.init(frame:frame);wantsLayer=true;layer=CALayer();video.videoGravity = .resizeAspect;layer?.addSublayer(video)}
  required init?(coder:NSCoder){fatalError()}
  override func layout(){super.layout();video.frame=bounds}
 }
 func makeNSView(context:Context)->VideoView{let view=VideoView(frame:.zero);view.video.session=session;return view}
 func updateNSView(_ view:VideoView,context:Context){view.video.session=session}
}
struct CameraPanel:View {
 @StateObject var camera=CameraMonitor();@State private var expanded=false
 var body:some View {
  Panel(title:"Visione · telecamera locale") {
   HStack{RText(camera.status).font(.caption).foregroundStyle(RobotTheme.secondary);Spacer();Button(camera.running ? "Ferma video" : "Avvia video"){camera.running ? camera.stop() : camera.start()}}
   DisclosureGroup("Video, fotogrammi e codici",isExpanded:$expanded){
    HStack{Picker("Telecamera",selection:$camera.selected){ForEach(camera.devices,id:\.uniqueID){RText($0.localizedName).tag($0.uniqueID)}}.disabled(camera.running);Button("Aggiorna dispositivi"){camera.refresh()};Button("Salva fotogramma…"){camera.saveFrame()}.disabled(!camera.running);Button("Rileva QR"){camera.detectCodes()}.disabled(!camera.running)}
    if camera.running{CameraPreview(session:camera.session).frame(height:260).background(.black,in:RoundedRectangle(cornerRadius:10))}
    if !camera.codes.isEmpty{RText(camera.codes).font(.caption.monospaced()).textSelection(.enabled)}
    RText("Video e riconoscimento QR sono locali. Il contenuto rilevato viene mostrato come dato e non esegue comandi. Calibrazione ottica, AprilTag e stima 3D degli oggetti richiedono ulteriori modelli e un adattatore di visione.").font(.caption).foregroundStyle(RobotTheme.secondary)
   }
  }.onAppear{camera.refresh()}.onDisappear{camera.stop()}
 }
}
