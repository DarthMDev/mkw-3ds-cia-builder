#pragma once
#include <mkw/course_bloom.hpp>
#include <algorithm>
namespace mkw {
// Original EGG threshold constant, byte-truncated like PostEffect::ColorScale.
inline uint32_t bloomThresholdColor(const CourseBloom& b){
 const float scale=(16.f+219.f*b.threshold)/255.f;
 uint32_t out=0;
 for(unsigned shift:{24u,16u,8u,0u})out|=uint32_t(std::clamp(float((b.thresholdColor>>shift)&255)*scale,0.f,255.f))<<shift;
 if(b.flags&16)out&=0xffffff00u;
 return out;
}
inline float bloomTapIntensity(const CourseBloom& b,unsigned band,unsigned stage=0){
 const float value=b.intensity[band]*(stage?.5f:1.f);
 return float(unsigned(std::clamp(value,0.f,1.f)*255.f))/255.f;
}
// LCD adaptation requested after hardware testing: reduce the bloom veil
// without changing scene lighting, authored blur radii or near texture detail.
// Remove only part of a yellow tint's excess over blue; do not brighten blue
// to neutralize it (that would wash the image out further). Red-only and cool
// course tints keep their hue. Original PBLM data remains unchanged.
inline uint32_t bloomDisplayTint(const CourseBloom& b){
 constexpr float gain=.85f,warmReduction=.15f;
 float rgb[3]={float(b.tint>>24),float((b.tint>>16)&255),float((b.tint>>8)&255)};
 if(rgb[0]>rgb[2]&&rgb[1]>rgb[2])
  for(unsigned i=0;i<2;++i)rgb[i]-=(rgb[i]-rgb[2])*warmReduction;
 uint32_t out=b.tint&255;
 for(unsigned i=0;i<3;++i)out|=uint32_t(rgb[i]*gain)<<(24-i*8);
 return out;
}
// PostEffectBlur's uniformly spaced ring, with angle zero at the first tap.
inline constexpr float BloomRing[16][2]={
 {0,1},{.3826834324f,.9238795325f},{.7071067812f,.7071067812f},{.9238795325f,.3826834324f},
 {1,0},{.9238795325f,-.3826834324f},{.7071067812f,-.7071067812f},{.3826834324f,-.9238795325f},
 {0,-1},{-.3826834324f,-.9238795325f},{-.7071067812f,-.7071067812f},{-.9238795325f,-.3826834324f},
 {-1,0},{-.9238795325f,.3826834324f},{-.7071067812f,.7071067812f},{-.3826834324f,.9238795325f}};
inline constexpr unsigned BloomFullQuads=4+8+8+16+2;
inline constexpr unsigned BloomReducedQuads=4+4+4+8+2;
}
