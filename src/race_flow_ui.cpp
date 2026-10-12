#include <mkw/race_flow_ui.hpp>
#include <mkw/race_flow_draw.hpp>
#include <mkw/race_flow_layout.hpp>
#include <mkw/race_results.hpp>
#include <mkw/renderer.hpp>
#include <algorithm>
#include <array>
#include <cmath>
#include <type_traits>

namespace mkw {
namespace {
GPU_TEXTURE_WRAP_PARAM wrapMode(uint8_t gx){return gx==1?GPU_REPEAT:gx==2?GPU_MIRRORED_REPEAT:GPU_CLAMP_TO_EDGE;}
static_assert(sizeof(FlowQuad)==sizeof(Renderer::MaterialQuad)&&std::is_standard_layout_v<FlowQuad>&&std::is_standard_layout_v<Renderer::MaterialQuad>,
              "FlowQuad mirrors Renderer::MaterialQuad");
}

struct RaceFlowUi::Impl {
 Texture wipe;
 std::array<Texture,FlowResultTextures.size()> results;unsigned loaded=0;bool failed=false;
 FlowDrawer drawer;
 Renderer* renderer=nullptr;
 static void submit(const FlowBatch& batch,void* context){
  auto& m=*static_cast<Impl*>(context);
  Texture* t=batch.texture>=0&&unsigned(batch.texture)<m.results.size()?&m.results[batch.texture]:nullptr;
  if(batch.texture>=0&&(!t||!t->ready))return;
  // The sampler wrap is set where the quads are drawn (the render thread in races).
  m.renderer->drawScreenMaterialQuads(t,reinterpret_cast<const Renderer::MaterialQuad*>(batch.quads),batch.count,batch.color0,batch.color1,
                                     wrapMode(batch.wrapS),wrapMode(batch.wrapT));
 }
};

RaceFlowUi::RaceFlowUi():impl_(std::make_unique<Impl>()){}
RaceFlowUi::~RaceFlowUi()=default;

bool RaceFlowUi::load(){
 auto& m=*impl_;
 if(!m.wipe.ready){
  if(!m.wipe.load("textures/flow_wipe.t3x"))return false;
  C3D_TexSetWrap(&m.wipe.gpu,GPU_CLAMP_TO_EDGE,GPU_CLAMP_TO_EDGE); // sampler 0x1c04: clamp, clamp
 }
 return true;
}

void RaceFlowUi::unload(){impl_->wipe.reset();unloadResults();}

bool RaceFlowUi::loadResultsStep(){
 auto& m=*impl_;
 if(m.failed)return false;
 if(m.loaded<m.results.size()){
  if(!m.results[m.loaded].load(FlowResultTextures[m.loaded])){m.failed=true;return false;}
  ++m.loaded;
 }
 return m.loaded==m.results.size();
}
void RaceFlowUi::unloadResults(){
 auto& m=*impl_;for(auto& t:m.results)t.reset();
 m.loaded=0;m.failed=false;m.drawer.reset();
}
bool RaceFlowUi::resultsLoaded()const{return impl_->loaded==impl_->results.size();}
bool RaceFlowUi::resultsFailed()const{return impl_->failed;}
unsigned RaceFlowUi::resultsBytes()const{unsigned n=0;for(const auto& t:impl_->results)n+=t.bytes();return n;}

void RaceFlowUi::drawWipe(Renderer& renderer,float progress){
 auto& m=*impl_;
 if(progress<0||!m.wipe.ready)return;
 // AnimationGroup::PlayAnimationAtPercent: the frame is percent x the last frame.
 const float frame=std::clamp(progress,0.f,1.f)*float(FlowWipeTranslateT.size()-1);
 const unsigned i=std::min(unsigned(frame),unsigned(FlowWipeTranslateT.size()-2));
 const float t=FlowWipeTranslateT[i]+(FlowWipeTranslateT[i+1]-FlowWipeTranslateT[i])*(frame-float(i));
 // NW4R texture SRT about the centre: v' = scale (v - 0.5) + translate + 0.5.
 const float v0=(FlowWipeScaleT*-.5f+t+.5f)*FlowWipeTextureV,v1=(FlowWipeScaleT*.5f+t+.5f)*FlowWipeTextureV;
 // tex3ds stores rows bottom-up, so V runs opposite to the Wii's: unflipped,
 // the hold (translate 1) showed the scene and the wipe went black on either
 // side of it, a second time just after the respawn instead of over it.
 // The pane spans the whole 832x456 screen; colour register 0 is black.
 renderer.drawScreenSpriteRegion(m.wipe,0,0,400,240,0,FlowWipeTextureV-v0,1,FlowWipeTextureV-v1,1.f,0x000000ffu);
}

void RaceFlowUi::step(const RaceResultsFlow& flow){impl_->drawer.step(flow);}

void RaceFlowUi::drawResults(Renderer& renderer,const RaceResultsFlow& flow){
 auto& m=*impl_;
 if(!resultsLoaded())return;
 m.renderer=&renderer;
 m.drawer.draw(flow,&Impl::submit,&m);
}
}
