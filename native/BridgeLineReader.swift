// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import Foundation
import Darwin
// Accessed only on Regia's serial request queue; never on the UI thread.
final class BridgeLineReader:@unchecked Sendable {
 private var buffer=Data()
 func read(_ output:FileHandle)throws->Data {
  while !buffer.contains(10) {
   var bytes=[UInt8](repeating:0,count:8192)
   let count=Darwin.read(output.fileDescriptor,&bytes,bytes.count)
   if count<0 && errno==EINTR{continue}
   if count<=0{throw NSError(domain:"Controllo locale interrotto",code:Int(errno))}
   buffer.append(contentsOf:bytes.prefix(count))
   if buffer.count>8_000_000{throw NSError(domain:"Risposta locale troppo grande",code:1)}
  }
  let end=buffer.firstIndex(of:10)!;let line=Data(buffer[..<end]);buffer.removeSubrange(...end);return line
 }
}
