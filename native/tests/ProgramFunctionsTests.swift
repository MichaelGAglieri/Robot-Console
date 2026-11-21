// SPDX-License-Identifier: GPL-3.0-only
// Compile with the actual ProgramCallFrame/MoveJStage DTOs, ProgramStructure and boundaries
// extracted from the native sources. See BUILD44_CONSEGNA.md for the invocation.
import Foundation
@main struct ProgramFunctionsTests {
 static func main()throws {
  let plain = #"{"kind":"movej","name":"old","block_index":1,"start_time":0,"end_time":1,"duration":1}"#
  let old=try JSONDecoder().decode(MoveJStage.self,from:Data(plain.utf8))
  precondition(old.call_path == nil,"Older plans must still decode")
  var stages:[MoveJStage]=[]
  for (i,call) in [4,5,5].enumerated(){
   let frame:[String:Any]=["function":"f","definition":0,"call_index":call,"iteration":"((), ())"]
   let json:[String:Any]=["kind":"movej","name":"f","block_index":1,"start_time":Double(i),"end_time":Double(i+1),"duration":1.0,"call_path":[frame]]
   stages.append(try JSONDecoder().decode(MoveJStage.self,from:JSONSerialization.data(withJSONObject:json)))
  }
  precondition(boundaries(MoveJPlan(stages:stages,duration:3)) == [0,1,3],"Distinct calls need preview boundaries, MoveL segments do not")
  let kinds=["function","loop","if","note","else","note","end","end","return","end","call"]
  let blocks=kinds.map{ProgramBlock(kind:$0)}
  precondition(ProgramStructure.markers(blocks,0)==[9],"Delete the complete function body")
  precondition(ProgramStructure.markers(blocks,2)==[4,6],"Nested Else belongs to its If")
  precondition(ProgramStructure.depths(blocks)==[0,1,2,3,2,3,2,1,1,0,0])
  print("Native function DTO compatibility, call boundaries and nested structure: OK")
 }
}
