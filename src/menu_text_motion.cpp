#include <mkw/menu_text_motion.hpp>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>

namespace mkw {
namespace {
struct Affine {float a=1,b=0,c=0,d=1,x=0,y=0;};
Affine multiply(const Affine& p,const Affine& q){
 return {p.a*q.a+p.b*q.c,p.a*q.b+p.b*q.d,p.c*q.a+p.d*q.c,p.c*q.b+p.d*q.d,
         p.a*q.x+p.b*q.y+p.x,p.c*q.x+p.d*q.y+p.y};
}
float value(std::initializer_list<UiTextClipFrame> clips,const char* node,const char* kind,unsigned target,float fallback,bool reference){
 for(const auto& entry:clips)if(entry.clip){
  const auto* clip=reference&&entry.referenceClip?entry.referenceClip:entry.clip;
  fallback=uiAnimationValue(*clip,node,kind,target,reference?entry.reference:entry.frame,fallback);
 }
 return fallback;
}
}
UiTextMotion uiTextMotion(const UiPaneInfo& pane,std::initializer_list<UiTextClipFrame> clips){
 UiTextMotion result;
 bool tracks=false;for(const auto& entry:clips)tracks|=entry.clip&&entry.clip->trackCount;
 if(!tracks)return result;
 char panel[64];std::snprintf(panel,sizeof panel,"%s",pane.panel);
 for(const char* suffix:{"_free","_select","_ok"}){
  const auto length=std::strlen(panel),end=std::strlen(suffix);
  if(length>=end&&!std::strcmp(panel+length-end,suffix)){panel[length-end]=0;break;}
 }
 std::array<const UiPaneNode*,32> chain{};unsigned count=0;
 const auto* node=uiFindPaneNode(panel,pane.name);
 while(node&&count<chain.size()){
  chain[count++]=node;
  if(!*node->parent)break;
  node=uiFindPaneNode(panel,node->parent);
 }
 if(!count||!node||*chain[count-1]->parent)return result;
 Affine poses[2];float alpha[2]={1,1};bool visible=true;
 for(unsigned mode=0;mode<2;++mode){
  const bool reference=mode==0;
  for(unsigned i=count;i-->0;){
   const auto& n=*chain[i];
   auto v=[&](unsigned target,float fallback){return value(clips,n.name,"RLPA",target,fallback,reference);};
   const float radians=v(5,n.rz)*.017453292519943295f,co=std::cos(radians),si=std::sin(radians);
   float sx=v(6,n.sx),sy=v(7,n.sy);
   if(n.flags&4)sx*=608.f/832.f;
   poses[mode]=multiply(poses[mode],{co*sx,-si*sy,si*sx,co*sy,v(0,n.x),v(1,n.y)});
   const float own=std::clamp(value(clips,n.name,"RLVC",16,n.alpha*255.f,reference),0.f,255.f)/255.f;
   // InfluencedAlpha controls propagation to children. A pane's own draw
   // always uses its alpha multiplied by the inherited ancestor alpha.
   // A non-propagating intermediary retains the inherited value for its
   // descendants; it does not erase the ancestors' fade.
   if(i==0||(n.flags&2))alpha[mode]*=own;
   if(!reference)visible&=value(clips,n.name,"RLVI",0,float(n.flags&1),false)>0;
  }
 }
 const auto& r=poses[0];const auto& p=poses[1];const float det=r.a*r.d-r.b*r.c;
 if(std::fabs(det)<1e-8f)return result;
 const Affine inverse{r.d/det,-r.b/det,-r.c/det,r.a/det,(r.b*r.y-r.d*r.x)/det,(r.c*r.x-r.a*r.y)/det};
 const auto delta=multiply(p,inverse);
 // UiQuad currently represents axis-aligned panes. Rotating text needs the
 // general corner submission path; leave that unsupported path unchanged.
 if(std::fabs(delta.b)>1e-5f||std::fabs(delta.c)>1e-5f)return result;
 const auto& leaf=*chain[0];
 const float localX=(1.f-float(leaf.origin%3))*leaf.w*.5f;
 const float localY=(float(leaf.origin/3)-1.f)*leaf.h*.5f;
 const float offsetX=pane.x+pane.w*.5f-(r.a*localX+r.b*localY+r.x);
 const float offsetY=-pane.y-pane.h*.5f-(r.c*localX+r.d*localY+r.y);
 result.sx=delta.a;result.sy=delta.d;
 result.tx=delta.x+offsetX*(1.f-delta.a);result.ty=delta.y+offsetY*(1.f-delta.d);
 result.absoluteAlpha=alpha[0]==0;
 result.alpha=alpha[0]>0?alpha[1]/alpha[0]:alpha[1];
 result.visible=visible;
 return result;
}
}
