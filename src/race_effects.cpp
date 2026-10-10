#include "mkw/render_quality.hpp"
#include <mkw/race_effects.hpp>
#include <cstdio>
#include <cstring>
namespace mkw {
namespace {
using ef::be16;using ef::be32;using ef::bef;
Vec3 bevec(const uint8_t* p){return {bef(p),bef(p+4),bef(p+8)};}

// EmitterDesc and EmitterDrawSetting (MKW layout, docs/VFX_RESEARCH.md) from BREFF bytes.
void parseDesc(ef::EmitterDesc& d,const uint8_t* p){
    d.commonFlag=be32(p)|ef::EmitterDesc::Relocated;d.emitFlag=be32(p+4);
    d.emitLife=be16(p+8);d.ptclLife=be16(p+0xa);
    d.ptclLifeRandom=int8_t(p[0xc]);d.inheritChildPtclTranslate=int8_t(p[0xd]);d.emitIntervalRandom=int8_t(p[0xe]);d.emitRandom=int8_t(p[0xf]);
    d.emit=bef(p+0x10);d.emitStart=be16(p+0x14);d.emitPast=be16(p+0x16);d.emitInterval=be16(p+0x18);
    d.inheritPtclTranslate=int8_t(p[0x1a]);d.inheritChildEmitTranslate=int8_t(p[0x1b]);
    for(int i=0;i<6;++i)d.commonParam[i]=bef(p+0x1c+i*4);
    d.emitDiv=be16(p+0x34);d.velInitVelocityRandom=int8_t(p[0x36]);d.velMomentumRandom=int8_t(p[0x37]);
    d.velPowerRadiationDir=bef(p+0x38);d.velPowerYAxis=bef(p+0x3c);d.velPowerRandomDir=bef(p+0x40);d.velPowerNormalDir=bef(p+0x44);
    d.velDiffusionEmitterNormal=bef(p+0x48);d.velPowerSpecDir=bef(p+0x4c);d.velDiffusionSpecDir=bef(p+0x50);
    d.velSpecDir=bevec(p+0x54);d.scale=bevec(p+0x60);d.rotate=bevec(p+0x6c);d.translate=bevec(p+0x78);
    d.lodNear=p[0x84];d.lodFar=p[0x85];d.lodMinEmit=p[0x86];d.lodAlpha=p[0x87];d.randomSeed=be32(p+0x88);
    const uint8_t* s=p+0x94;ef::DrawSetting& w=d.draw;
    w.flags=be16(s);w.acmpComp0=s[2];w.acmpComp1=s[3];w.acmpOp=s[4];w.numTevs=s[5];w.flagClamp=s[6];w.indirectTargetStage=s[7];
    std::memcpy(w.tevTexture,s+0x8,4);std::memcpy(w.tevColor,s+0xc,16);std::memcpy(w.tevColorOp,s+0x1c,20);
    std::memcpy(w.tevAlpha,s+0x30,16);std::memcpy(w.tevAlphaOp,s+0x40,20);
    std::memcpy(w.kColorSel,s+0x54,4);std::memcpy(w.kAlphaSel,s+0x58,4);
    w.blendType=s[0x5c];w.blendSrc=s[0x5d];w.blendDst=s[0x5e];w.blendOp=s[0x5f];
    std::memcpy(w.colorInput,s+0x60,8);std::memcpy(w.alphaInput,s+0x68,8);
    w.zCompare=s[0x70];w.alphaFlickType=s[0x71];w.alphaFlickCycle=be16(s+0x72);w.alphaFlickRandom=s[0x74];w.alphaFlickAmplitude=s[0x75];
    w.lightingMode=s[0x76];w.lightingType=s[0x77];std::memcpy(w.lightingAmbient,s+0x78,4);std::memcpy(w.lightingDiffuse,s+0x7c,4);
    w.lightingRadius=bef(s+0x80);w.lightingPosition=bevec(s+0x84);
    for(int i=0;i<2;++i)for(int j=0;j<3;++j)w.indTexOffsetMtx[i][j]=bef(s+0x90+(i*3+j)*4);
    w.indTexScaleExp=int8_t(s[0xa8]);w.pivotX=int8_t(s[0xa9]);w.pivotY=int8_t(s[0xaa]);
    w.ptclType=s[0xac];w.typeOption=s[0xad];w.typeDir=s[0xae];w.typeAxis=s[0xaf];
    w.typeOption0=s[0xb0];w.typeOption1=s[0xb1];w.typeOption2=s[0xb2];w.zOffset=bef(s+0xb4);
}
void parsePtcl(ef::ParticleDesc& d,const uint8_t* p,const uint16_t tex[3]){
    std::memcpy(d.color,p,16);
    d.size[0]=bef(p+0x10);d.size[1]=bef(p+0x14);d.scale[0]=bef(p+0x18);d.scale[1]=bef(p+0x1c);
    for(int i=0;i<3;++i)d.rotate[i]=bef(p+0x20+i*4);
    for(int i=0;i<3;++i){
        d.textureScale[i][0]=bef(p+0x2c+i*8);d.textureScale[i][1]=bef(p+0x30+i*8);
        d.textureRotate[i]=bef(p+0x44+i*4);
        d.textureTranslate[i][0]=bef(p+0x50+i*8);d.textureTranslate[i][1]=bef(p+0x54+i*8);
        d.texture[i]=tex[i];
    }
    d.textureWrap=be16(p+0x74);d.textureReverse=p[0x76];d.acmpRef0=p[0x77];d.acmpRef1=p[0x78];
    for(int i=0;i<3;++i){d.rotateOffsetRandom[i]=p[0x79+i];d.rotateOffset[i]=bef(p+0x7c+i*4);}
}
ef::Mtx34 frameMtx(const EffectFrame& f){
    const Vec3 x=f.x*f.scale,y=f.y*f.scale,z=f.z*f.scale;
    return {{{x.x,y.x,z.x,f.origin.x},{x.y,y.y,z.y,f.origin.y},{x.z,y.z,z.z,f.origin.z}}};
}
}

RaceEffects::RaceEffects():system_(std::make_unique<ef::System>()){system_->reset();}
RaceEffects::~RaceEffects()=default;

bool RaceEffects::load(const char* path){
    ready=false;textures.clear();system_->resources.clear();blob_.clear();
    FILE* f=std::fopen(path,"rb");if(!f)return false;
    uint32_t h[5]{};
    bool ok=std::fread(h,1,sizeof h,f)==sizeof h&&!std::memcmp(h,"REFX",4)&&h[1]==3&&h[2]>0&&h[2]<=255&&h[3]<=96&&h[4]<=(1u<<20);
    struct Record { char name[32]; uint32_t desc,ptcl; uint16_t texture[3],ptclTracks,ptclInit,emitTracks,emitInit,ptclSize,pad[2]; uint32_t list; };
    static_assert(sizeof(Record)==64,"REFX record");
    std::vector<Record> records;
    if(ok){
        textures.resize(h[3]);records.resize(h[2]);blob_.resize(h[4]);
        for(auto& t:textures)ok&=std::fread(&t,1,40,f)==40;
        for(auto& r:records)ok&=std::fread(&r,1,64,f)==64;
        ok&=std::fread(blob_.data(),1,blob_.size(),f)==blob_.size()&&std::fgetc(f)==EOF;
    }
    std::fclose(f);
    auto& res=system_->resources;
    if(ok)res.resize(records.size());
    for(size_t i=0;ok&&i<records.size();++i){
        Record& r=records[i];r.name[31]=0;
        const size_t curves=size_t(r.ptclTracks)+r.emitTracks;
        ok&=r.desc+0x14c<=blob_.size()&&r.ptcl+0x88u<=blob_.size()&&r.ptclInit<=r.ptclTracks&&r.emitInit<=r.emitTracks&&
            (!curves||r.list+curves*4<=blob_.size());
        for(int k=0;k<3;++k)ok&=r.texture[k]==0xffff||r.texture[k]<textures.size();
        if(!ok)break;
        ef::EmitterResource& e=res[i];
        std::memcpy(e.name,r.name,32);e.index=uint16_t(i);
        parseDesc(e.desc,blob_.data()+r.desc);
        parsePtcl(e.ptcl,blob_.data()+r.ptcl,r.texture);
        for(size_t k=0;k<curves;++k){
            uint32_t at;std::memcpy(&at,blob_.data()+r.list+k*4,4);
            ok&=at+0x40<=blob_.size();
            if(!ok)break;
            (k<r.ptclTracks?e.ptclTracks:e.emitTracks).push_back(blob_.data()+at);
        }
        e.ptclInitTracks=r.ptclInit;e.emitInitTracks=r.emitInit;
    }
    for(auto& t:textures)t.name[31]=0;
    if(!ok){textures.clear();res.clear();blob_.clear();}
    reset();
    return ready=ok;
}
int RaceEffects::find(const char* name) const {
    const auto& res=system_->resources;
    for(size_t i=0;i<res.size();++i)if(!std::strcmp(res[i].name,name))return int(i);
    return -1;
}
void RaceEffects::reset(){system_->reset();slots_={};serial_=0;}
unsigned RaceEffects::liveParticles() const {return system_->liveParticles;}
void RaceEffects::setCamera(const float view[3][4]){std::memcpy(system_->cameraMtx.m,view,sizeof(float)*12);}
void RaceEffects::setCamera(Vec3 eye,Vec3 target,Vec3 up){
    const Vec3 look=normalized(eye-target,{0,0,1}),right=normalized(cross(up,look),{1,0,0}),camUp=cross(look,right);
    const float view[3][4]={{right.x,right.y,right.z,-dot(eye,right)},{camUp.x,camUp.y,camUp.z,-dot(eye,camUp)},
                            {look.x,look.y,look.z,-dot(eye,look)}};
    setCamera(view);
}

ef::Effect* RaceEffects::start(int spec,const EffectFrame& frame,uint8_t group){
    if(!ready||spec<0||size_t(spec)>=system_->resources.size())return nullptr;
    ef::Effect* e=system_->createEffect(system_->resources[size_t(spec)],0,group);
    if(!e)return nullptr;
    e->serial=++serial_;
    system_->setRootMtx(*e,frameMtx(frame));
    return e;
}
void RaceEffects::burst(int spec,const EffectFrame& frame){start(spec,frame);}
bool RaceEffects::alive(unsigned slot) const {
    return slot<SlotCount&&system_->alive(slots_[slot].effect,slots_[slot].serial);
}
void RaceEffects::create(unsigned slot,int spec,const EffectFrame& frame,uint8_t group){
    if(slot>=SlotCount||alive(slot))return;
    Slot& s=slots_[slot];
    s.effect=start(spec,frame,group);s.serial=s.effect?s.effect->serial:0;s.spec=spec;s.fading=false;
}
void RaceEffects::move(unsigned slot,const EffectFrame& frame){
    if(alive(slot))system_->setRootMtx(*slots_[slot].effect,frameMtx(frame));
}
void RaceEffects::followFade(unsigned slot){
    if(!alive(slot))return;
    system_->retireEmitters(*slots_[slot].effect);slots_[slot].fading=true;
}
void RaceEffects::setColor(unsigned slot,const uint8_t rgba[4]){
    if(alive(slot))system_->setColor(*slots_[slot].effect,rgba);
}
void RaceEffects::kill(unsigned slot){
    if(alive(slot))system_->retireEffect(*slots_[slot].effect);
    if(slot<SlotCount)slots_[slot]={};
}
void RaceEffects::attach(unsigned slot,int spec,const EffectFrame& frame,bool active){
    if(slot>=SlotCount)return;
    if(spec<0){kill(slot);return;}
    Slot& s=slots_[slot];
    if(active){
        // A fading instance or another emitter set hands the slot to a fresh one.
        if(alive(slot)&&(s.fading||s.spec!=spec)){followFade(slot);s={};}
        if(!alive(slot))create(slot,spec,frame);
    }else if(alive(slot)&&!s.fading)followFade(slot);
    move(slot,frame);
}
void RaceEffects::restart(unsigned slot,int spec,const EffectFrame& frame){
    kill(slot);create(slot,spec,frame);
}
void RaceEffects::setGroups(uint32_t calc,uint32_t draw){system_->calcGroups=calc;system_->drawGroups=draw;}
void RaceEffects::step(){if(ready)system_->calc();}
}
