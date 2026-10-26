// SPDX-License-Identifier: GPL-3.0-only
// Minimal deterministic host stub: no USB, GPIO or real motor control.
#pragma once
class AccelStepper {
 long position=0,target=0;
 protected: bool _direction=true; virtual void step1(long) {}
 public:
 static constexpr int DRIVER=1;
 AccelStepper(int,int,int,int=0,int=0,bool=true) {}
 void setCurrentPosition(long p){position=target=p;}
 void move(long d){target=position+d;}
 long distanceToGo(){return target-position;}
 void run(){position=target;}
 void setMaxSpeed(float){}
 void setAcceleration(float){}
 void setMinPulseWidth(int){}
 void setPinsInverted(bool,bool,bool){}
};
