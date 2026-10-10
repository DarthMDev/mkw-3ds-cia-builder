#pragma once
#include <mkw/math.hpp>
#include <algorithm>
#include <array>
#include <cstdint>

namespace mkw {
// Recovered from the locally supplied RMCU StaticR.rel KartKiller routines.
// See docs/BULLET_BILL.md for addresses, constants and remaining integration gaps.
inline constexpr unsigned BulletDuration=480,BulletMinimumDuration=180,BulletEndDuration=70;
inline constexpr float BulletModelHeight=150.f,BulletUpSmoothing=.1f;
inline float bulletTurnRate(float previous,float yawRadians){
    const float target=.03f+std::fabs(yawRadians)*57.295780181884766f*.003f;
    return previous+.05f*(target-previous);
}
inline unsigned bulletTargetRank(unsigned rank,unsigned racers){
    constexpr std::array<unsigned,12> gains={1,1,1,1,2,2,3,3,4,4,5,5};
    const unsigned gain=gains[std::clamp(racers,1u,12u)-1];
    return rank>gain?rank-gain:1;
}
inline Vec3 bulletVisualPosition(Vec3 position,Vec3 smoothedUp,float initialYPos){
    // Retail .text a4f28..a4fa4: compensate the vehicle-specific BSP origin;
    // kart_killer's origin is its centre, not its bottom vertex.
    return position+smoothedUp*(BulletModelHeight-initialYPos);
}
}
