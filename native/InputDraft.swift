// SPDX-License-Identifier: GPL-3.0-only
import Foundation
/// Parsing never rewrites the editable string: empty, '-', '+' and '0,' remain drafts.
/// Validation happens on preview/apply; invalid text is never silently replaced by zero.
enum InputDraft {
 static func normalized(_ text:String)->String {
  text.trimmingCharacters(in:.whitespacesAndNewlines).replacingOccurrences(of:"−",with:"-").replacingOccurrences(of:",",with:".")
 }
 static func number(_ text:String)->Double? {
  guard let n=Double(normalized(text)),n.isFinite else{return nil};return n
 }
 static func integer(_ text:String,range:ClosedRange<Int>)->Int? {
  guard let n=Int(normalized(text)),range.contains(n) else{return nil};return n
 }
}
