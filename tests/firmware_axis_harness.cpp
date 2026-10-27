// SPDX-License-Identifier: GPL-3.0-only
// Compile the actual sketch against inert GPIO/serial stubs, then exercise commands.
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>
#include <utility>
#include <iostream>
using byte=uint8_t;
#define __AVR_ATmega2560__ 1
#define F_CPU 16000000UL
#define F(s) s
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define PB5 5
#define _BV(p) (1 << (p))
byte DDRB=0;
std::vector<std::pair<int,int>> writes;
void digitalWrite(byte p,int v){assert(p!=255);writes.push_back({p,v});}
void pinMode(byte,int){}
void delayMicroseconds(int){}
unsigned long fakeMillis=1;
unsigned long millis(){return fakeMillis;}
struct FakeSerial {
 std::ostringstream out;
 void begin(int){}
 int available(){return 0;}
 char read(){return 0;}
 template<class T>void print(T v){out<<v;}
 void print(byte v){out<<int(v);}
 template<class T>void print(T v,int){out<<v;}
 template<class T>void println(T v){print(v);out<<'\n';}
 template<class T>void println(T v,int){print(v);out<<'\n';}
 void println(){out<<'\n';}
} Serial;
const int SERVO_OPEN_US=1944,SERVO_CLOSED_US=1150;
void stopServoSignal(){}
void printServoStatus(){}
void requestServoPosition(int){}
// The runner embeds RegiaDemo.ino here, omitting only its AVR servo implementation.
#include "sketch.inc"
void cmd(const char* s){std::vector<char> line(s,s+strlen(s)+1);executeCommand(line.data());}
bool wrote(int pin,int level){for(auto w:writes)if(w.first==pin && w.second==level)return true;return false;}
int main(){
 setup();linked=true;writes.clear();
 cmd("mask 011111");cmd("arm");
 assert(!axisAllowed[0] && !enabled[0]);assert(!wrote(38,LOW));
 assert(wrote(62,LOW));assert(!wrote(56,LOW)); // RAMPS Y ENABLE never drives DM542.
 cmd("j1 10");assert(movingAxis==-1); // Excluded motor cannot auto-enable on a move.
 writes.clear();cmd("mask 111111");assert(!wrote(38,LOW));assert(!enabled[0]);
 cmd("arm");cmd("j1 10");assert(movingAxis==0 && motors[0]->distanceToGo()!=0);
 writes.clear();cmd("off 1");assert(movingAxis==-1);assert(motors[0]->distanceToGo()==0);
 assert(!axisAllowed[0] && !enabled[0]);assert(wrote(38,HIGH));assert(!wrote(62,HIGH));assert(enabled[2]);
 cmd("arm");assert(!enabled[0]); // HOME/ARM must not restore an excluded axis.
 cmd("j3 10");assert(movingAxis==2);writes.clear();cmd("off 2");
 assert(movingAxis==-1 && !axisAllowed[1]);assert(enabled[2]);assert(!wrote(56,HIGH));
 // Excluding J2 stops a sequence but does not pretend to remove its unmanaged current.
 assert(!managedEnable(1));assert(!managedEnable(5));assert(Serial.out.str().find("DRIVE_CAPS 101110")!=std::string::npos);
 writes.clear();bool old=axisAllowed[2];cmd("mask 11111z");cmd("off 0");cmd("off 7");cmd("off 11");
 assert(axisAllowed[2]==old && writes.empty()); // Validate entire command before GPIO writes.
 for(auto w:writes)assert(w.first!=255);
 // New group is validated atomically, starts multiple targets and restores single-axis acceleration.
 cmd("mask 111111");cmd("multi 10 20 -20 10 0 5 0 5 0 5 0 5");
 assert(multiMoving && movingMask==3);
 assert(motors[0]->distanceToGo()>0 && motors[1]->distanceToGo()<0);
 assert(std::abs(motors[0]->maxSpeed*2-motors[1]->maxSpeed)<1);
 assert(motors[0]->maxSpeed+motors[1]->maxSpeed<=2000.1f);
 assert(std::abs(motors[0]->acceleration*2-motors[1]->acceleration)<2);
 cmd("j3 10");assert(motors[2]->distanceToGo()==0); // Busy cannot append/start another move.
 holdStop();assert(!multiMoving && !movingMask);
 assert(!motors[0]->distanceToGo() && !motors[1]->distanceToGo());
 writes.clear();cmd("multi 10 5 20 5 0 5 0 5 0 5 1 5"); // Unconfigured J6: no partial start.
 assert(movingAxis==-1 && writes.empty());
 cmd("multi 10 5 20 0 0 5 0 5 0 5 0 5");assert(movingAxis==-1 && writes.empty());
 cmd("multi 10 5 20 5 0 5 0 5 0 5 0 5 extra");assert(movingAxis==-1 && writes.empty());
 cmd("mask 101111");writes.clear();cmd("multi 10 5 20 5 0 5 0 5 0 5 0 5");assert(movingAxis==-1 && writes.empty());
 cmd("mask 111111");cmd("multi 10 5 20 5 0 5 0 5 0 5 0 5");loop();
 assert(movingAxis==-1 && !multiMoving);assert(Serial.out.str().find("MULTI DONE:")!=std::string::npos);
 cmd("multi 10 5 20 5 0 5 0 5 0 5 0 5");fakeMillis=2000;loop();
 assert(!linked && movingAxis==-1 && !multiMoving && !motors[1]->distanceToGo());
 linked=true;cmd("j1 10");assert(motors[0]->acceleration==pulsesPerOutputRev[0]*OUTPUT_ACCELERATION/360.0f);
 std::cout<<"PASS: mask/ARM, disabled move, re-enable, active OFF, J2 isolation, invalid inputs\n";
}
