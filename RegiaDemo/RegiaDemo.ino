// SPDX-License-Identifier: GPL-3.0-only
// Copyright (c) 2026 Michael Giuseppe Aglieri
/* TEST 5 STEPPER + PINZA EBG-30 - Mega 2560 + RAMPS 1.4 + A4988 / DM542.
   j1=X A4988, j2=Y segnali per DM542 esterno, j3=Z, j4=E0, j5=E1.
   j1 180 / j2 -180 / j5 +2.5: relativi all'USCITA del riduttore.
   -360..360 gradi PER COMANDO, massimo due decimali. Nessuna coda.
   115200 baud, Nuova riga. x=STOP impulsi/rilascio A4988, p=stato, h=aiuto.
   Nessun movimento comandato all'avvio. DM542 con ENA non gestito puo' restare in coppia.
   Nessun homing, finecorsa, feedback o limite cumulativo del giunto.
   Pinza: apri=1944 us, chiudi=1150 us, D11/Timer1; OFF all'avvio.
   x interrompe anche il segnale servo, senza toglierne l'alimentazione.
*/
#include <AccelStepper.h>
#include <math.h>
#include <string.h>
#if !defined(__AVR_ATmega2560__) || F_CPU != 16000000UL
#error "Seleziona Arduino Mega 2560 a 16 MHz, processore ATmega2560."
#endif
#include "PinzaTimer1.h"

const byte AXES = 6;
// J6 uses a separate external driver. No pin is driven until configured explicitly.
const bool J6_CONFIGURED = false;
const byte J6_STEP_PIN = 255;
const byte J6_DIR_PIN = 255;
const byte J6_ENABLE_PIN = 255; // 255: ENA unmanaged, holding torque may remain.
const bool J6_DM542 = true;
const byte STEP_PINS[AXES] = {54, 60, 46, 26, 36, J6_STEP_PIN};
const byte DIR_PINS[AXES] = {55, 61, 48, 28, 34, J6_DIR_PIN};
const byte ENABLE_PINS[AXES] = {38, 56, 62, 24, 30, J6_ENABLE_PIN}; // Solo A4988: LOW=ON
const char * const SLOT[AXES] = {"X", "Y", "Z", "E0", "E1", "EXT"};

// CONFIGURAZIONE: ordine j1, j2, j3, j4, j5.
// Impulsi per giro MOTORE: A4988 200 passi x 1/8 = 1600.
// J2 DollaTek DM542: ON 1,3,7,8; OFF 2,4,5,6, dichiarati dall'utente.
// Tabella di riferimento: SW5/6 OFF, SW7/8 ON = 1600 impulsi/giro.
const uint16_t PULSES_PER_MOTOR_REV[AXES] = {1600, 1600, 1600, 1600, 1600, 1600};
const float REDUCTION[AXES] = {38.4f, 38.4f, 38.4f, 38.4f, 38.4f, 38.4f};
const bool INVERT_DIRECTION[AXES] = {false, false, false, false, false, false};
const byte DM542_AXIS = 1; // j2; STEP D60, DIR D61; ENA esterno non gestito.
// false: PUL+ riceve STEP, PUL- a GND (segnale attivo HIGH).
// true: PUL+ a +5 V, PUL- riceve STEP (segnale attivo LOW).
// Cablaggio confermato: PUL-/DIR- a GND Y, PUL+ STEP Y, DIR+ DIR Y; ENA libero.
const bool DM542_INVERT_STEP = false;
// Regolabile dall'app con speed 1.00 ... speed 20.00, solo da fermo.
// Non cambia la corrente impostata fisicamente sui driver.
float MAX_OUTPUT_SPEED = 5.0f;      // gradi uscita / secondo
const float OUTPUT_ACCELERATION = 20.0f; // gradi uscita / secondo^2

// AccelStepper standard non attende esplicitamente 5 us fra DIR e STEP.
// J2: DIR stabile per 10 us, impulso attivo 10 us, inattivo 10 us.
// ENA scollegato: non si dichiara mai che il DM542 sia stato disabilitato.
class DM542Stepper : public AccelStepper {
 public:
  DM542Stepper() : AccelStepper(AccelStepper::DRIVER, 60, 61) {}
 protected:
  void step1(long step) override {
    (void)step;
    digitalWrite(DIR_PINS[DM542_AXIS],
                 (_direction != INVERT_DIRECTION[DM542_AXIS]) ? HIGH : LOW);
    delayMicroseconds(10);
    digitalWrite(STEP_PINS[DM542_AXIS], DM542_INVERT_STEP ? LOW : HIGH);
    delayMicroseconds(10);
    digitalWrite(STEP_PINS[DM542_AXIS], DM542_INVERT_STEP ? HIGH : LOW);
    delayMicroseconds(10);
  }
};

AccelStepper motorX(AccelStepper::DRIVER, 54, 55);
DM542Stepper motorY;
AccelStepper motorZ(AccelStepper::DRIVER, 46, 48);
AccelStepper motorE0(AccelStepper::DRIVER, 26, 28);
AccelStepper motorE1(AccelStepper::DRIVER, 36, 34);
class ExternalJ6Stepper : public AccelStepper {
 public:
  ExternalJ6Stepper() : AccelStepper(AccelStepper::DRIVER,J6_STEP_PIN,J6_DIR_PIN,0,0,false) {}
 protected:
  void step1(long step) override {
    (void)step;
    digitalWrite(J6_DIR_PIN,(_direction != INVERT_DIRECTION[5]) ? HIGH : LOW);
    delayMicroseconds(10);digitalWrite(J6_STEP_PIN,HIGH);
    delayMicroseconds(10);digitalWrite(J6_STEP_PIN,LOW);delayMicroseconds(10);
  }
};
ExternalJ6Stepper motorJ6;
AccelStepper * const motors[AXES] = {&motorX, &motorY, &motorZ, &motorE0, &motorE1, &motorJ6};
long pulsesPerOutputRev[AXES];
bool enabled[AXES] = {false, false, false, false, false, false};
// Command permission is separate from electrical ENABLE. ARM respects this mask.
bool axisAllowed[AXES] = {true, true, true, true, true, true};
bool managedEnable(byte i) {
  return i!=DM542_AXIS && (i!=5 || (J6_CONFIGURED && !J6_DM542)) && ENABLE_PINS[i]!=255;
}
void printDrives() {
  Serial.print(F("DRIVES "));
  for(byte i=0;i<AXES;++i) Serial.print(managedEnable(i) ? (enabled[i] ? '1' : '0') : '?');
  Serial.println();
}
void printAxisFeatures() {
  Serial.println(F("FEATURES AXIS_ENABLE"));
  Serial.print(F("DRIVE_CAPS "));
  for(byte i=0;i<AXES;++i) Serial.print(managedEnable(i) ? '1' : '0');
  Serial.println(); printDrives();
}
int8_t movingAxis = -1;
char commandBuffer[40];
byte commandLength = 0;
bool discardLine = false;
unsigned long lastHeartbeat = 0;
bool linked = false;
void holdStop() {
  for(byte i=0;i<AXES;++i) motors[i]->setCurrentPosition(0);
  movingAxis=-1;
  commandLength=0; discardLine=false;
  // Mantiene ENABLE e PWM servo: stop impulsi, nessun rilascio del carico.
  Serial.println(F("HALTED"));
}

void printAxis(byte i) {
  Serial.print(F("j")); Serial.print(i+1);
  Serial.print(F("=")); Serial.print(SLOT[i]);
}
void stopAll() {
  stopServoSignal();
  for (byte i=0; i<AXES; ++i) {
    if(i==5 && !J6_CONFIGURED) continue;
    if(ENABLE_PINS[i]!=255) digitalWrite(ENABLE_PINS[i], HIGH);
    // Azzera velocita' e obiettivo software, senza definire uno zero fisico.
    motors[i]->setCurrentPosition(0);
    digitalWrite(STEP_PINS[i], (i==DM542_AXIS && DM542_INVERT_STEP) ? HIGH : LOW);
    enabled[i] = false;
  }
  movingAxis = -1;
  Serial.println(F("STOP: stepper fermi, A4988 OFF, segnale servo OFF. DM542: ENA non gestito, coppia possibile."));
}
void printStatus() {
  Serial.print(F("SPEED "));Serial.println(MAX_OUTPUT_SPEED,2);
  if (movingAxis >= 0) {
    printAxis(movingAxis);
    Serial.print(F(" IN MOTO; impulsi residui = "));
    Serial.println(motors[movingAxis]->distanceToGo());
    return;
  }
  for (byte i=0; i<AXES; ++i) {
    printAxis(i);
    if (i==DM542_AXIS) Serial.print(F(" DM542; ENA non gestito, coppia possibile"));
    else Serial.print(enabled[i] ? F(" A4988 ON") : F(" A4988 OFF"));
    Serial.print(F("; impulsi/giro uscita = "));
    Serial.println(pulsesPerOutputRev[i]);
  }
  printServoStatus();
}
void printHelp() {
  if (movingAxis >= 0) { printStatus(); return; }
  Serial.println(F("\nTEST 5 STEPPER + PINZA - J2 DM542; altri A4988"));
  Serial.println(F("j1=X; j2=DM542 STEP60 DIR61; j3=Z; j4=E0; j5=E1."));
  Serial.println(F("j1 180 oppure j2 -180: gradi relativi all'uscita riduttore."));
  Serial.println(F("Da -360 a +360 per comando; massimo due decimali, punto decimale."));
  Serial.println(F("Un comando e Invio, 115200 baud, Nuova riga. Un asse alla volta."));
  Serial.println(F("apri=1944 us; chiudi=1150 us; servo D11/Timer1, OFF all'avvio."));
  Serial.println(F("Durante un moto stepper, apri/chiudi sono rifiutati. Nessuna coda."));
  Serial.println(F("Attendi DONE. x=STOP/A4988 OFF/segnale servo OFF; p=stato; h=aiuto."));
  Serial.println(F("DM542: ENA non gestito, anche dopo x. Nessun homing/finecorsa/limite cumulativo."));
  Serial.print(F("Velocita' max uscita = ")); Serial.print(MAX_OUTPUT_SPEED);
  Serial.print(F(" gradi/s; accelerazione = ")); Serial.print(OUTPUT_ACCELERATION);
  Serial.println(F(" gradi/s^2. Avvio senza movimento."));
  printStatus();
}
bool isSpace(char c) { return c==' ' || c=='\t'; }

// Centesimi di grado: formato rigoroso, niente NaN, esponenti o overflow.
bool parseAngle(const char *text, int32_t &value) {
  bool negative = false;
  if (*text=='+' || *text=='-') negative = *text++=='-';
  if (*text<'0' || *text>'9') return false;
  int whole=0, fraction=0;
  while (*text>='0' && *text<='9') {
    whole = whole*10 + (*text++-'0');
    if (whole>360) return false;
  }
  if (*text=='.') {
    ++text;
    byte digits=0;
    while (*text>='0' && *text<='9') {
      if (digits==2) return false;
      fraction = fraction*10 + (*text++-'0');
      ++digits;
    }
    if (!digits) return false;
    if (digits==1) fraction*=10;
  }
  if (*text) return false;
  value = (int32_t)whole*100 + fraction;
  if (value>36000) return false;
  if (negative) value=-value;
  return true;
}
long angleToPulses(byte axis, int32_t centidegrees) {
  int64_t n = (int64_t)centidegrees*pulsesPerOutputRev[axis];
  n += n>=0 ? 18000 : -18000; // arrotondamento simmetrico
  return (long)(n/36000);
}
void moveAxis(byte axis, int32_t centidegrees) {
  if (movingAxis>=0) {
    Serial.println(F("Occupato: comando scartato. Attendi oppure x."));
    return;
  }
  if(!axisAllowed[axis]) {Serial.println(F("ERROR AXIS DISABLED"));return;}
  const long pulses=angleToPulses(axis, centidegrees);
  if (!pulses) {
    Serial.println(F("Spostamento nullo dopo arrotondamento: nessun impulso."));
    return;
  }
  // Conteggio locale del movimento: evita overflow dopo molti comandi.
  motors[axis]->setCurrentPosition(0);
  // Lo slot Y A4988 resta disabilitato: J2 usa il DM542 esterno.
  if (managedEnable(axis)) {
    digitalWrite(ENABLE_PINS[axis], LOW);
    enabled[axis]=true;
  }
  delayMicroseconds(5);
  motors[axis]->move(pulses);
  movingAxis=axis;
  printAxis(axis);
  Serial.print(F(" ACK; gradi uscita relativi = "));
  Serial.print(centidegrees/100.0f, 2);
  Serial.print(F("; impulsi richiesti = ")); Serial.println(pulses);
}
void executeCommand(char *text) {
  while (isSpace(*text)) ++text;
  int n=strlen(text);
  while (n && isSpace(text[n-1])) text[--n]=0;
  if (!n) return;
  if (!strcmp(text,"hello")) { Serial.println(F("DOC REGIA 4")); Serial.print(F("CAPS ")); Serial.println(J6_CONFIGURED ? 6 : 5); printAxisFeatures(); return; }
  if (!linked) { Serial.println(F("ERROR HEARTBEAT")); return; }
  // Atomic per-axis exclusion: cancel the current trajectory before releasing torque.
  // Other drivers keep their holding state; J2/DM542 ENA is never claimed controlled.
  if (!strncmp(text,"off ",4)) {
    if(strlen(text)!=5 || text[4]<'1' || text[4]>'6') {Serial.println(F("ERROR AXIS"));return;}
    byte axis=text[4]-'1';
    if(movingAxis>=0) holdStop();
    axisAllowed[axis]=false;
    if(managedEnable(axis)) {digitalWrite(ENABLE_PINS[axis],HIGH);enabled[axis]=false;}
    printDrives();Serial.print(F("AXIS_OFF "));Serial.println(axis+1);return;
  }
  if (!strncmp(text,"mask ",5)) {
    if(movingAxis>=0) {Serial.println(F("ERROR BUSY"));return;}
    if(strlen(text)!=5+AXES) {Serial.println(F("ERROR MASK"));return;}
    for(byte i=0;i<AXES;++i) if(text[5+i]!='0' && text[5+i]!='1') {Serial.println(F("ERROR MASK"));return;}
    for(byte i=0;i<AXES;++i) {
      axisAllowed[i]=text[5+i]=='1';
      // Including an axis never energizes it: the operator must confirm HOME/ARM.
      if(!axisAllowed[i] && managedEnable(i)) {digitalWrite(ENABLE_PINS[i],HIGH);enabled[i]=false;}
    }
    printDrives();return;
  }
  if (!strncmp(text,"speed ",6)) {
    if (movingAxis>=0) {Serial.println(F("ERROR BUSY"));return;}
    int32_t value;
    if (!parseAngle(text+6,value) || value<100 || value>2000) {
      Serial.println(F("ERROR SPEED 1..20"));return;
    }
    MAX_OUTPUT_SPEED=value/100.0f;
    for(byte i=0;i<AXES;++i) motors[i]->setMaxSpeed(pulsesPerOutputRev[i]*MAX_OUTPUT_SPEED/360.0f);
    Serial.print(F("SPEED "));Serial.println(MAX_OUTPUT_SPEED,2);
    return;
  }
  if (!strcmp(text,"arm")) {
    if(movingAxis>=0) { Serial.println(F("ERROR BUSY")); return; }
    for(byte i=0;i<AXES;++i) if(managedEnable(i)) {
      digitalWrite(ENABLE_PINS[i],axisAllowed[i] ? LOW : HIGH);enabled[i]=axisAllowed[i];
    }
    printDrives();Serial.println(F("ARMED"));return;
  }
  if (!strcmp(text,"p")) { printStatus(); return; }
  if (!strcmp(text,"h") || !strcmp(text,"?")) { printHelp(); return; }
  if (!strcmp(text,"apri") || !strcmp(text,"chiudi")) {
    if (movingAxis>=0) {
      Serial.println(F("Occupato: pinza non comandata. Attendi DONE oppure x."));
      return;
    }
    requestServoPosition(!strcmp(text,"apri") ? SERVO_OPEN_US : SERVO_CLOSED_US);
    return;
  }
  if (n<4 || text[0]!='j' || text[1]<'1' || text[1]>'6' || !isSpace(text[2])) {
    Serial.println(F("Formato: j1 180 ... j6 -180; apri; chiudi; h=aiuto."));
    return;
  }
  const byte axis=text[1]-'1';
  if(axis==5 && !J6_CONFIGURED){Serial.println(F("ERROR J6 NOT CONFIGURED"));return;}
  const char *angle=text+2;
  while (isSpace(*angle)) ++angle;
  int32_t degrees;
  if (!parseAngle(angle,degrees)) {
    Serial.println(F("Angolo rifiutato: -360..360, massimo due decimali."));
    return;
  }
  moveAxis(axis,degrees);
}
void readSerialCommand() {
  if (!Serial.available()) return;
  char c=Serial.read();
  if(c=='~') {lastHeartbeat=millis();linked=true;return;}
  if(c=='!') {holdStop();while(Serial.available()) Serial.read();return;}
  if (c>='A' && c<='Z') c+='a'-'A';
  if (c=='x') {
    commandLength=0; discardLine=false;
    stopAll();
    while (Serial.available()) Serial.read();
    return;
  }
  if (c=='\r' || c=='\n') {
    if (!discardLine && commandLength) {
      commandBuffer[commandLength]=0;
      executeCommand(commandBuffer);
    }
    commandLength=0; discardLine=false;
    return;
  }
  if (discardLine) return;
  if (commandLength>=sizeof(commandBuffer)-1) {
    commandLength=0; discardLine=true;
    Serial.println(F("Riga troppo lunga: scartata senza movimento."));
    return;
  }
  commandBuffer[commandLength++]=c;
}
void setup() {
  for (byte i=0; i<AXES; ++i) {
    pulsesPerOutputRev[i]=lroundf(PULSES_PER_MOTOR_REV[i]*REDUCTION[i]);
    if(i==5 && !J6_CONFIGURED) continue;
    if(ENABLE_PINS[i]!=255){digitalWrite(ENABLE_PINS[i],HIGH); pinMode(ENABLE_PINS[i],OUTPUT);}
    digitalWrite(STEP_PINS[i], (i==DM542_AXIS && DM542_INVERT_STEP) ? HIGH : LOW);
    digitalWrite(DIR_PINS[i],LOW);
    pinMode(STEP_PINS[i],OUTPUT); pinMode(DIR_PINS[i],OUTPUT);
    pulsesPerOutputRev[i]=lroundf(PULSES_PER_MOTOR_REV[i]*REDUCTION[i]);
    motors[i]->setPinsInverted(INVERT_DIRECTION[i],false,false);
    motors[i]->setMaxSpeed(pulsesPerOutputRev[i]*MAX_OUTPUT_SPEED/360.0f);
    motors[i]->setAcceleration(pulsesPerOutputRev[i]*OUTPUT_ACCELERATION/360.0f);
    motors[i]->setMinPulseWidth(3);
    motors[i]->setCurrentPosition(0);
  }
  stopServoSignal();
  DDRB |= _BV(PB5); // D11 uscita, LOW finche' non arriva apri/chiudi.
  const byte offPins[]={4,5,6,8,9,10};
  for (byte i=0; i<sizeof(offPins); ++i) {
    digitalWrite(offPins[i],LOW); pinMode(offPins[i],OUTPUT);
  }
  Serial.begin(115200);
  Serial.println(F("DOC REGIA 4")); Serial.print(F("CAPS ")); Serial.println(J6_CONFIGURED ? 6 : 5); printAxisFeatures();
  printHelp();
}
void loop() {
  readSerialCommand();
  if(linked && millis()-lastHeartbeat>1500) {
    linked=false; holdStop(); Serial.println(F("ERROR WATCHDOG"));
  }
  if (movingAxis<0) return;
  const byte axis=movingAxis;
  motors[axis]->run();
  if (!motors[axis]->distanceToGo()) {
    movingAxis=-1;
    printAxis(axis);
    Serial.print(F(" DONE: impulsi completati. "));
    if (axis==DM542_AXIS) Serial.print(F("DM542 ENA non gestito. "));
    else Serial.print(F("A4988 ON. "));
    Serial.println(F("Nessun feedback fisico."));
  }
}
