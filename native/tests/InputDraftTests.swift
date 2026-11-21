// SPDX-License-Identifier: GPL-3.0-only
import Foundation
@main struct InputDraftTests {
 static func main(){
  for text in ["", "-", "+", ".", ",", "-.", "−,", "NaN", "inf", "1,2,3"]{precondition(InputDraft.number(text)==nil,"Invalid draft must not become zero: "+text)}
  let samples:[String:Double]=["0":0,"-20":-20,"−20,5":-20.5,"+45":45,"  -0,25  ":-0.25,"1e2":100,"0,":0]
  for (text,value) in samples{precondition(InputDraft.number(text)==value)}
  precondition(InputDraft.integer("",range:0...232)==nil)
  precondition(InputDraft.integer("42,5",range:0...232)==nil)
  precondition(InputDraft.integer("233",range:0...232)==nil)
  precondition(InputDraft.integer(" 42 ",range:0...232)==42)
  print("Input drafts: empty, signs, comma decimals, unicode minus, ranges and non-finite values: OK")
 }
}
