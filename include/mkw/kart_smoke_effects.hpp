#pragma once
#include "mkw/kart_start_effects.hpp"
#include "mkw/race_effects.hpp"
#include "mkw/kart_item_effects.hpp"
#include <array>
#include <algorithm>

namespace mkw {
// Smoke state belongs to the race, never to a static in the main loop.
struct KartSmokeState {
    KartStartEffects start;
    bool burnout=false;
};

// The remote KartEffect resources are already in RKRace; route the
// other racers to the original S roots instead of omitting them.
class RemoteKartSmoke {
public:
    static constexpr unsigned FirstSlot=KartFxSlots::FirstFreeSlot+8,MaxRacers=12,SlotsPerRacer=4;
    static_assert(FirstSlot+(MaxRacers-1)*SlotsPerRacer<=RaceEffects::SlotCount);
    bool bind(RaceEffects& effects){
        start_=effects.find("rk_startS");miss_=effects.find("rk_startMissS");
        return start_>=0&&miss_>=0;
    }
    void reset(){state_={};}
    void step(RaceEffects& effects,unsigned racer,const EffectFrame& pose,
              Vec3 rearLeft,Vec3 rearRight,unsigned timer,bool preview,
              bool countdown,bool accelerate,bool leftFloor,bool rightFloor,
              bool bike,bool burnout,bool hidden,uint32_t serial,
              int duration,bool lod){
        if(!racer||racer>=MaxRacers)return;
        auto& state=state_[racer];
        const unsigned slot=FirstSlot+(racer-1)*SlotsPerRacer;
        const uint8_t group=uint8_t(2+racer);
        // Source S startup table uses the rear-right point (80697078).
        // Keep the other startup slot reserved for independent wheel paths.
        const int wheels=state.start.step(timer,preview,countdown,accelerate,leftFloor,rightFloor,bike,serial,duration);
        auto frame=pose;frame.origin=rearRight;
        if(hidden||lod){effects.kill(slot);effects.kill(slot+1);}
        else if(wheels!=KartStartEffects::Hold){
            if(wheels&(bike?1:2))effects.create(slot,start_,frame,group);
            else effects.followFade(slot);
            effects.move(slot,frame);
        }
        // Finite burnout handles keep their own racer group and
        // follow the racer until all authored particles have expired.
        if(!preview&&!hidden&&!lod&&burnout&&!state.burnout){
            effects.kill(slot+2);effects.create(slot+2,miss_,pose,group);
        }
        state.burnout=burnout;
        if(hidden){effects.kill(slot+2);effects.kill(slot+3);}
        else effects.move(slot+2,pose);
        (void)rearLeft;
    }
private:
    int start_=-1,miss_=-1;
    std::array<KartSmokeState,MaxRacers> state_{};
};

// Original landing signals replace the arbitrary airborne frame thresholds.
// Large smoke is HardLanding (94), small kart smoke is a manual-drift hop.
// Bikes also emit a small puff when settling both wheels after a wheelie.
class KartLandingEffects {
public:
    static constexpr unsigned FirstSlot=RemoteKartSmoke::FirstSlot+(RemoteKartSmoke::MaxRacers-1)*RemoteKartSmoke::SlotsPerRacer;
    static_assert(FirstSlot+12*3<=RaceEffects::SlotCount);
    bool bind(RaceEffects& e){
        static constexpr const char* names[4][2]={{"rk_jumpSmoke","rk_jumpSmokeS"},{"rk_jumpSmokeMini","rk_jumpSmokeMiniS"},
            {"rk_jumpSmokeBikeL","rk_jumpSmokeBikeL_S"},{"rk_jumpSmokeBikeS","rk_jumpSmokeBikeS_S"}};
        for(unsigned i=0;i<4;++i)for(unsigned j=0;j<2;++j){spec_[i][j]=e.find(names[i][j]);if(spec_[i][j]<0)return false;}
        miniBike_=e.find("rk_jumpSmokeBikeLMini");return miniBike_>=0;
    }
    void reset(){wheelieFrames_={};}
    void step(RaceEffects& e,unsigned racer,bool local,const EffectFrame& pose,Vec3 rearMid,
              bool preview,bool hidden,bool lod,bool bike,bool groundStart,bool hard,
              bool manualDrift,bool jumpPad,bool water,bool wheelie,bool allWheels){
        if(racer>=12)return;
        const unsigned base=FirstSlot+racer*3;
        auto frame=pose;if(bike)frame.origin=rearMid;
        if(hidden){for(unsigned j=0;j<3;++j)e.kill(base+j);wheelieFrames_[racer]=0;return;}
        if(!preview&&!lod&&!jumpPad&&!water){
            if(hard){
                const int type=bike?(wheelie?2:3):0;
                e.create(base,spec_[type][local?0:1],frame,uint8_t(2+racer));
            }else if(groundStart&&manualDrift){
                const int spec=bike?(local?miniBike_:spec_[3][1]):spec_[1][local?0:1];
                e.create(base+1,spec,frame,uint8_t(2+racer));
            }else if(bike&&allWheels&&wheelieFrames_[racer]>5){
                e.create(base+2,local?miniBike_:spec_[3][1],frame,uint8_t(2+racer));wheelieFrames_[racer]=0;
            }
        }
        if(wheelie)wheelieFrames_[racer]=std::min(wheelieFrames_[racer]+1,200u);
        if(lod)for(unsigned j=0;j<3;++j)e.kill(base+j);
        else for(unsigned j=0;j<3;++j)e.move(base+j,frame);
    }
private:
    int spec_[4][2]{},miniBike_=-1;
    std::array<unsigned,12> wheelieFrames_{};
};
}
