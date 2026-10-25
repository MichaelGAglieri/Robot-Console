// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
#pragma once
// PWM ripreso dal test Test_pinza_apri_chiudi; chiusura estesa di 100 us su richiesta.
// Mega 2560 16 MHz, D11/OC1A, 50 Hz. Nessun movimento comandato all'avvio.
#include <Arduino.h>
#include <util/atomic.h>

// Apertura originale; chiusura regolata da 1250 a 1150 us per aumentare la corsa.
const uint16_t SERVO_OPEN_US = 1944;
const uint16_t SERVO_CLOSED_US = 1150;
static_assert(SERVO_OPEN_US > 0 && SERVO_OPEN_US < 20000, "Impulso apertura non valido.");
static_assert(SERVO_CLOSED_US > 0 && SERVO_CLOSED_US < 20000, "Impulso chiusura non valido.");

const uint16_t SERVO_TOP_TICKS = 39999;
bool servoActive = false;

void stopServoSignal() {
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    TCCR1B = 0;              // ferma il timer
    TCCR1A = 0;              // scollega OC1A dal pin
    TIMSK1 = 0;             // nessun interrupt Timer1
    PORTB &= ~_BV(PB5);     // D11 LOW
  }
  servoActive = false;
}

void sendServoPulse(uint16_t microseconds) {
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    if (!servoActive) {
      TCCR1B = 0;
      TCCR1A = 0;
      TIMSK1 = 0;
      TCCR1C = 0;
      PORTB &= ~_BV(PB5);
      // In modo normale questi registri sono caricati subito.
      ICR1 = SERVO_TOP_TICKS;
      OCR1A = microseconds * 2U;
      TCNT1 = SERVO_TOP_TICKS;    // primo tick: BOTTOM e inizio impulso completo
      TIFR1 = _BV(ICF1) | _BV(OCF1C) | _BV(OCF1B) | _BV(OCF1A) | _BV(TOV1);
      // Fast PWM modo 14, TOP=ICR1; OC1A non invertente.
      TCCR1A = _BV(COM1A1) | _BV(WGM11);
      // 16 MHz / 8 = 2 MHz: tick 0,5 us; 40000 tick = 20 ms.
      TCCR1B = _BV(WGM13) | _BV(WGM12) | _BV(CS11);
      servoActive = true;
    } else {
      // Aggiornamento double-buffered a BOTTOM, senza riavviare il periodo.
      OCR1A = microseconds * 2U;
    }
  }
  Serial.print(F("Timer1: impulso richiesto = "));
  Serial.print(microseconds);
  Serial.println(F(" us; periodo nominale 20000 us. Nessun feedback fisico."));
}

uint16_t servoLastPulse = 0;

void printServoStatus() {
  Serial.print(F("Pinza D11: "));
  Serial.print(servoActive ? F("ON") : F("OFF"));
  if (!servoLastPulse) {
    Serial.println(F("; nessun comando di movimento dall'avvio."));
    return;
  }
  Serial.print(servoLastPulse == SERVO_OPEN_US ? F("; ultima richiesta: APERTURA") : F("; ultima richiesta: CHIUSURA"));
  Serial.print(F("; impulso = "));
  Serial.print(servoLastPulse);
  Serial.println(F(" us; posizione reale NON misurata."));
}

void requestServoPosition(uint16_t pulse) {
  if (!servoActive || servoLastPulse != pulse) sendServoPulse(pulse);
  else Serial.println(F("Stessa destinazione gia' comandata: segnale invariato."));
  servoLastPulse = pulse;
  printServoStatus();
}
