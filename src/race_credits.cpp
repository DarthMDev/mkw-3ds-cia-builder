#include <mkw/race_credits.hpp>
#include <mkw/race_credit_assets.hpp>
#include <mkw/mod_engine.hpp>
#include <algorithm>
namespace mkw {
void RaceCredits::reset(){track_.reset();music_.reset();course_=start_=~0u;}
void RaceCredits::load(unsigned course){
 reset();course_=modEngine().resolvedCourseIndex(course);
 if(course_>=RaceCreditRows.size())return;
 const auto& row=RaceCreditRows[course_];
 if(row.track.path)track_.load(row.track.path);
 if(row.music.path)music_.load(row.music.path);
}
void RaceCredits::draw(Renderer& renderer,unsigned stage,unsigned raceTime,unsigned tick,bool finished){
 if(course_>=RaceCreditRows.size()||finished)return;
 if(start_==~0u)start_=tick;
 renderer.setScreenDepth(renderer.stereoLayer(stereo::HudLayer));
 const auto& row=RaceCreditRows[course_];const unsigned age=tick-start_;
 // Course and author: first four seconds of the preview, ending before countdown.
 if(stage==0&&age<240&&track_.ready){
  const float alpha=age<180?1.f:float(240-age)/60.f;
  renderer.drawScreenSprite(track_,12.f,224.f-row.track.h,row.track.w,row.track.h,row.track.u,row.track.v,alpha);
 }
 // RaceManager keeps the four-second countdown in its timer after GO.
 const unsigned musicAge=raceTime>=240?raceTime-240:0;
 // Music credit starts at GO and fades out after five seconds.
 if(stage==2&&musicAge<300&&music_.ready){
  const float alpha=musicAge<240?1.f:float(300-musicAge)/60.f;
  renderer.drawScreenSprite(music_,12.f,224.f-row.music.h,row.music.w,row.music.h,row.music.u,row.music.v,alpha);
 }
}
}
