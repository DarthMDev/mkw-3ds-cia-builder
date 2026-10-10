#pragma once
#include <algorithm>
#include <mkw/math.hpp>
namespace mkw {
// Retail USA StaticR: init 0x2cac54, follow 0x2cb188, face 0x2cc410.
// These are world-space heights, independent of kart bank and wheel scale.
struct ThunderCloudVisual {
    Vec3 position{},facing{0,0,1};
    float ramp=1.f,lateFollow=0.f,bounce=0.f,bounceVelocity=0.f;
    void spawn(Vec3 kart,Vec3 direction){
        *this={};position=kart+Vec3{0,600,0};facing=normalized(direction,{0,0,1});
    }
    void transfer(){ramp=lateFollow=0;bounceVelocity=10;}
    void step(Vec3 kart,Vec3 direction,unsigned age){
        ramp+=.005f;
        lateFollow=std::clamp(lateFollow+(age>520?.005f:-.005f),0.f,.4f);
        bounceVelocity=bounceVelocity*.93f-bounce*.02f;
        bounce+=bounceVelocity;
        const Vec3 target=kart+Vec3{0,365,0};
        const float horizontal=std::max(std::min(ramp,.4f),lateFollow);
        const float vertical=std::max(std::min(ramp,.3f),lateFollow);
        position.x+=(target.x-position.x)*horizontal;
        position.y+=(target.y-position.y)*vertical;
        position.z+=(target.z-position.z)*horizontal;
        facing=normalized(lerp(facing,direction,.3f),facing);
    }
    Vec3 modelPosition()const{return position+Vec3{0,bounce,0};}
};
}
