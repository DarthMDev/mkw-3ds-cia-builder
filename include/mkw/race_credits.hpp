#pragma once
#include <mkw/renderer.hpp>
namespace mkw {
class RaceCredits {
public:
 void load(unsigned course);
 void reset();
 void draw(Renderer& renderer,unsigned stage,unsigned raceTime,unsigned tick,bool finished);
private:
 Texture track_,music_;unsigned course_=~0u,start_=~0u;
};
}
