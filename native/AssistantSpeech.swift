// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
import Foundation

enum AssistantSpeech {
 static func spokenText(_ answer:String)->String {
  // Model attribution remains in the chat; only the leading metadata is silent.
  answer.replacingOccurrences(
   of:#"\A\s*\[(?:Ollama locale|Local Ollama)\s*·[^\]\r\n]*\]\s*"#,
   with:"",options:.regularExpression
  ).trimmingCharacters(in:.whitespacesAndNewlines)
 }
}
