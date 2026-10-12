#pragma once
namespace mkw::display {
// Native top LCD. Menus previously mapped to a letterboxed 400x225 canvas;
// all presentation now uses the full 5:3 frame requested for this build.
inline constexpr float Width=400.f,Height=240.f,Aspect=Width/Height;
inline constexpr float MenuScaleX=Width/608.f,MenuScaleY=Height/456.f;
static_assert(Width*3==Height*5);
}
