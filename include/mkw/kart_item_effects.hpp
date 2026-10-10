#pragma once
#include "mkw/race_effects.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace mkw {
// One racer's KartEffect power-up and slipstream emitters (RMCU KartEffect,
// docs/POWERUPS_SOURCE.md, docs/VFX_RESEARCH.md "Slipstream"). Presentation only: it reads
// kart status and item events and tells a sink which effect instances to create, move,
// colour, fade and kill. The sink picks the S variants for other racers.
enum class KartFx : uint8_t {
    Star,          // 0x204 rk_star
    Killer,        // 0x208 rk_killer
    Killer1T,      // 0x20c rk_killer1T
    Thunder,       // 0x210 rk_thunder
    KaminariGumo,  // 0x214 rk_kaminariGumo
    BiriLightning, // 0x218 rk_thunderBiri
    BiriCloud,     // 0x21c rk_thunderBiri
    Kyodai,        // 0x22c rk_kyodai
    Pow,           // 0x230 rk_pow
    Pow1,          // 0x234 rk_pow1
    PowUp,         // 0x238 rk_powUp
    SlipStreamPre, // 0x1fc rk_slipStreamPre, drafting
    SlipStream,    // 0x200 rk_slipStream, the slipstream boost
    Count
};
inline constexpr unsigned KartFxCount=unsigned(KartFx::Count);
// Each effect's index in KartEffect's handle table at +0x1f0: (offset above - 0x1f0) / 4.
inline constexpr uint8_t KartFxTableIndex[KartFxCount]={5,6,7,8,9,10,11,15,16,17,18,3,4};
// 0x8069146c with argument 0, the kart effect LOD's kill, spares indices 5..12, 14..19, 27
// and 35: every power-up here and the item box hit; it kills the slipstream (3, 4).
constexpr bool keptByLodKill(unsigned tableIndex){
    return (tableIndex>=5&&tableIndex<=12)||(tableIndex>=14&&tableIndex<=19)||tableIndex==27||tableIndex==35;
}

// What KartEffect copies from the kart (0x8068fa0c) and the item events of this step.
struct KartFxInput {
    Vec3 position{},right{1,0,0},up{0,1,0},forward{0,0,1}; // +0x6d0 and the pose +0x6f4
    float scale=1;        // +0x72c getScale
    float initialY=0;     // +0x74 bsp().initialYPos
    float bulletOffset=0; // the Bullet model's centre along up (KartKiller matrix)
    // Status 63 Star, 79 Mega, 91 Bullet, 71 Shocked, 4 BeforeRespawn.
    bool star=false,mega=false,bullet=false,shocked=false,beforeRespawn=false;
    // KartAction: the current action, its frame and the POW dodge (+0xcc bit 1);
    // powPending is KartMove::calcPow's POW-target-in-window test (0x8057a844).
    int action=-1;uint32_t actionFrame=0;bool powDodged=false,powPending=false;
    // Item events: a Lightning bolt (fn_1_288374), the Thunder Cloud's strike (0x80579d88)
    // and a POW stomp wave on a target (stomps 1 and 2, 0x807d9b10).
    bool lightningBolt=false,cloudBolt=false,powWave=false;
    // Slipstream (0x806972c0): state bits 64 drafting and 65 boost (KartState +0xc bits 0
    // and 1; Kinoko KartMove::slipstreamCharging/Boost) and status 32 InAction (+0xb9).
    bool drafting=false,slipBoost=false,inAction=false;
    // The effect matrix +0xc4 (0x80690234) and scale (0x806aefd4): the velocity +0x6dc
    // (KartDynamics, Kart::Link::GetSpeed), getScale before it is made uniform, and +0x49:
    // action 14 or status 80 (Crushed).
    Vec3 velocity{},kartScale{1,1,1};
    bool pressed=false;
    // Effects::Player hits during this step's kart collision: a counted wall contact
    // (0x8069d1d8, countedWallContact) and a bush (0x806a221c) with the capped speed ratio.
    bool wallHit=false,bushHit=false;
    float speedRatio=0;
};

// EGG::Effect calls on one racer's slots.
class KartFxSink {
public:
    virtual ~KartFxSink()=default;
    virtual bool alive(KartFx fx) const=0;
    virtual void create(KartFx fx,const EffectFrame& frame)=0; // no-op while the instance runs
    virtual void setFrame(KartFx fx,const EffectFrame& frame)=0;
    virtual void followFade(KartFx fx)=0;
    virtual void kill(KartFx fx)=0;
    virtual void setColor(KartFx fx,const uint8_t rgba[4])=0; // +0x50, active managers only
};

class KartItemEffects {
public:
    // Timer resets of KartEffect init (0x8068a790): bolts idle at 690 and 540, POW at 1000.
    static constexpr int32_t BoltEnd=690,CloudEnd=540,PowIdle=1000,PowEnd=690;
    static constexpr int32_t BoltWindow=70,BoltRecent=64,CrackleDelay=71;
    static constexpr int PowAction=11;
    static constexpr uint32_t PowHitFrame=8; // .data 0x808b11fc
    // KartEffect +0x7b4..+0x7b7: frames since the last wall, object, kart-contact and bush
    // hit effect, counted to 100 by 0x80690234.
    enum Hit : uint8_t {WallHit,ObjectHit,KartHit,BushHit,HitCount};
    static constexpr int8_t HitFramesMax=100,HitGap=30,HitSettle=60;
    static constexpr int32_t SlipFadeFrames=10; // +0x8c runs 0..9, alpha 255 - 25 * frame
    static constexpr float PressScale=0.7f;     // +0xac4 (0x8068a804)

    void reset(unsigned index,bool local,bool ghost=false){
        *this={};index_=uint8_t(index);local_=local;ghost_=ghost;
    }
    // One KartEffect update (0x8068f8fc) after the kart and item updates of the step. lod is
    // this frame's kart effect LOD flag (+7, KartEffectLod), set before the update.
    void step(const KartFxInput& in,KartFxSink& sink,bool lod=false){
        // The state copy (0x8068fa0c) clears +9, which the updates below set while one of the
        // power-up effects is active (retail sets it too under LIVE_VIEW, +0x13b, never in a
        // race). It also marks BeforeRespawn's first frame (+0x98).
        keepAlive_=false;
        if(ghost_)return;
        const bool respawnStart=in.beforeRespawn&&!wasBeforeRespawn_;
        wasBeforeRespawn_=in.beforeRespawn;
        // During the kart collision, before this update: Effects::Player counts the wall
        // contacts (+0x7b0, 0x8069d1d8) and OnBushCollision (0x806a221c) restarts the bush
        // timer for the player's own kart.
        wallContacts_+=in.wallHit;
        if(local_&&in.bushHit&&hitFrames_[BushHit]>HitGap&&in.speedRatio>=0.5f)hitFrames_[BushHit]=0;
        // KartMove::calcPow (0x8057a844): the hit at action 11 frame 8 restarts +0x54 unless
        // dodged (0x806a6044); a pending POW keeps rk_powUp alive (0x806a5d40).
        if(in.action==PowAction&&in.actionFrame==PowHitFrame&&!in.powDodged&&!in.beforeRespawn)powHit_=0;
        if(in.powPending){
            powUp_=true;
            if(!in.beforeRespawn)sink.create(KartFx::PowUp,scaled(pose(in),in));
        }
        if(in.powWave&&!in.beforeRespawn)powWave_=0;  // 0x806a6080
        if(in.lightningBolt)lightning_=0;             // fn_1_288374
        if(in.cloudBolt)cloud_=0;                      // 0x80579d88
        if(in.mega&&!wasMega_)sink.create(KartFx::Kyodai,scaled(pose(in),in)); // 0x806a6720
        wasMega_=in.mega;
        // While the Bullet runs its update (0x80698c98) ends with its own wall hit and the
        // update returns: no LOD edge, no matrix, no slipstream, no reset of +0x7b0.
        if(bulletStep(in,sink)){wallHit(in);return;}
        normalStep(in,sink);
        // +7's rising edge (+8) kills every effect but the power-ups (0x8069146c, argument 0).
        if(lod&&!wasLod_)lodKill(sink);
        wasLod_=lod;
        if(lod)return;
        // 0x80690234 counts the hit timers and builds the effect matrix; 0x80691720 updates
        // the slipstream first and checks for a wall hit last; 0x80692868 clears +0x7b0.
        for(auto& f:hitFrames_)f=int8_t(std::min<int>(f+1,HitFramesMax));
        slipstream(in,respawnStart,sink);
        wallHit(in);
        wallContacts_=0;
    }
    // +9: an effect that keeps this racer's effect group calculated and drawn under the LOD
    // (KartEffectLod::calcs/draws): the Star, a bolt or crackle, or a live rk_pow, rk_pow1,
    // rk_powUp or rk_kyodai. The Bullet's own +9 (0x806a4aa4) is set before the state copy
    // clears it.
    bool keepAlive() const { return keepAlive_; }
    // The slipstream emitters' matrix (+0xc4, 0x80690234): the pose, or above speed 1 and
    // 60 frames after every hit effect, a frame along the velocity (0x806af81c). The
    // translation is the kart position.
    EffectFrame effectFrame(const KartFxInput& in) const {
        const float speed=length(in.velocity); // +0x6e8
        bool recent=false;
        for(auto f:hitFrames_)recent|=f<HitSettle;
        if(speed<=1.f||recent)return pose(in);
        const Vec3 v=in.velocity*(1.f/speed);
        // Z is the direction with |y| raised to 0.001; X is horizontal, to the right of Z.
        Vec3 z=v;
        if(std::fabs(z.y)<0.001f)z.y=0.001f;
        const Vec3 flat{v.x,0.f,v.z};
        if(length(flat)==0.f)return pose(in); // straight up or down: retail's X would be zero
        const Vec3 h=flat*(1.f/length(flat));
        Vec3 x=cross(h,z);
        if(z.y>0.f)x=-x;
        x=x*(1.f/length(x));
        return frame(in.position,x,cross(z,x),z);
    }
    // 0x806aefd4: whether the slipstream emitters get setScale (+0xb0) and the uniform
    // scale (+0x72c) they get.
    static bool effectScale(const KartFxInput& in,float& scale){
        if(in.pressed){scale=PressScale;return true;}
        const bool scaled=std::fabs(in.kartScale.y-1.f)>=0.05f;
        if(!scaled||std::fabs(in.kartScale.x-1.f)>=0.05f)scale=in.kartScale.x;
        else scale=in.kartScale.y>=PressScale?in.kartScale.y:PressScale;
        return scaled;
    }
    int8_t hitFrames(Hit hit) const { return hitFrames_[hit]; }
    uint32_t wallContacts() const { return wallContacts_; }
    int32_t slipFade() const { return slipFade_; }
    int32_t lightningTimer() const { return lightning_; }
    int32_t cloudTimer() const { return cloud_; }
    int32_t powHitTimer() const { return powHit_; }
    int32_t powWaveTimer() const { return powWave_; }
private:
    // The wall hit (sparks and rumble; the end of 0x80691720 and 0x80699444 in the Bullet
    // update): a counted contact since +0x7b0 was last cleared, speed above 30 and 30 frames
    // since the last.
    void wallHit(const KartFxInput& in){
        if(!in.beforeRespawn&&wallContacts_>0&&length(in.velocity)>30.f&&hitFrames_[WallHit]>HitGap)hitFrames_[WallHit]=0;
    }
    void lodKill(KartFxSink& sink) const {
        for(unsigned index=0;index<0x2c;++index)
            for(unsigned fx=0;fx<KartFxCount;++fx)
                if(KartFxTableIndex[fx]==index&&!keptByLodKill(index)&&sink.alive(KartFx(fx)))sink.kill(KartFx(fx));
    }
    static EffectFrame frame(Vec3 origin,Vec3 x,Vec3 y,Vec3 z,float scale=1){
        EffectFrame f;f.origin=origin;f.x=x;f.y=y;f.z=z;f.scale=scale;return f;
    }
    // The pose matrix (+0x6f4), as Mega, rk_powUp and the POW frames use it.
    static EffectFrame pose(const KartFxInput& in){return frame(in.position,in.right,in.up,in.forward);}
    // EGG keeps setScale apart from setMtx, so a scaled instance stays scaled as it follows.
    static EffectFrame scaled(EffectFrame f,const KartFxInput& in){f.scale=in.scale;return f;}
    // Star and crackle: up, forward and right as the axes (0x806a464c, 0x806a5244).
    static EffectFrame body(const KartFxInput& in){return frame(in.position,in.up,in.forward,in.right,in.scale);}
    // A world-aligned frame at the kart: create, then only setTranslate (0x8069971c).
    static EffectFrame world(const KartFxInput& in){EffectFrame f;f.origin=in.position;return f;}
    // POW frames ride the kart's bottom: position - up * initialYPos (0x806a60a8).
    static EffectFrame bottom(const KartFxInput& in){
        auto f=pose(in);f.origin=in.position-in.up*in.initialY;f.scale=in.scale;return f;
    }
    // Bullet: forward, up and -right at the Bullet's height over the kart (0x806a4be8).
    EffectFrame bulletFrame(const KartFxInput& in) const {
        return frame(in.position+Vec3{0,bulletHeight_,0},in.forward,in.up,-in.right);
    }
    // A finished effect: the player's own kart lets it fade while following,
    // any other kart's is killed.
    void stop(KartFx fx,const EffectFrame& follow,KartFxSink& sink) const {
        if(!sink.alive(fx))return;
        if(!local_){sink.kill(fx);return;}
        sink.followFade(fx);sink.setFrame(fx,follow);
    }
    // 0x80698c98: returns true while the Bullet runs (the normal update is skipped).
    bool bulletStep(const KartFxInput& in,KartFxSink& sink){
        if(in.bullet){
            // The Bullet object creates rk_killer and sets its matrix (0x805b05e8 ->
            // 0x806a4aa4), which records the height over the kart.
            const Vec3 centre=in.position+in.up*in.bulletOffset;
            bulletHeight_=centre.y-in.position.y;
            const EffectFrame f=frame(centre,in.forward,in.up,-in.right);
            sink.create(KartFx::Killer,f);sink.setFrame(KartFx::Killer,f);
            bolts(in,sink);powHit(in,sink);powWave(in,sink);powUp(in,sink);
        }
        if(!in.bullet&&wasBullet_)sink.create(KartFx::Killer1T,scaled(bulletFrame(in),in));
        if(!in.bullet)stop(KartFx::Killer,bulletFrame(in),sink);
        if(sink.alive(KartFx::Killer1T))sink.setFrame(KartFx::Killer1T,scaled(bulletFrame(in),in));
        wasBullet_=in.bullet;
        return in.bullet;
    }
    // 0x80690884.
    void normalStep(const KartFxInput& in,KartFxSink& sink){
        if(in.star){sink.create(KartFx::Star,body(in));sink.setFrame(KartFx::Star,body(in));keepAlive_=true;}
        else stop(KartFx::Star,body(in),sink);
        bolts(in,sink);powHit(in,sink);powWave(in,sink);powUp(in,sink);
        if(sink.alive(KartFx::Kyodai)){sink.setFrame(KartFx::Kyodai,scaled(pose(in),in));keepAlive_=true;} // 0x806a6770
    }
    // 0x8069971c: Lightning (+0x4c) and Thunder Cloud (+0x50) bolts and the shocked crackle.
    void bolts(const KartFxInput& in,KartFxSink& sink){
        if(in.beforeRespawn)lightning_=cloud_=BoltEnd;
        const int32_t stagger=int32_t(index_%6)+1;
        const bool lightningRecent=lightning_<BoltRecent;
        if(lightningRecent)cloud_=CloudEnd;
        if(stagger<=lightning_&&lightning_<BoltWindow){sink.create(KartFx::Thunder,world(in));sink.setFrame(KartFx::Thunder,world(in));keepAlive_=true;}
        else if(sink.alive(KartFx::Thunder))sink.kill(KartFx::Thunder);
        const bool cloudRecent=cloud_<BoltRecent;
        if(cloudRecent)lightning_=BoltEnd;
        if(stagger<=cloud_&&cloud_<BoltWindow){sink.create(KartFx::KaminariGumo,world(in));sink.setFrame(KartFx::KaminariGumo,world(in));keepAlive_=true;}
        else stop(KartFx::KaminariGumo,world(in),sink);
        // The crackle follows a bolt while the kart stays shocked and the other bolt is over.
        const int32_t crackle=int32_t(index_)+CrackleDelay;
        if(in.shocked&&!lightningRecent&&cloud_==CloudEnd&&crackle<=lightning_&&lightning_<BoltEnd)crackleOn(KartFx::BiriLightning,in,sink);
        else stop(KartFx::BiriLightning,body(in),sink);
        lightning_=std::min(lightning_+1,BoltEnd);
        if(in.shocked&&!cloudRecent&&lightning_==BoltEnd&&crackle<=cloud_&&cloud_<CloudEnd)crackleOn(KartFx::BiriCloud,in,sink);
        else stop(KartFx::BiriCloud,body(in),sink);
        cloud_=std::min(cloud_+1,CloudEnd);
    }
    void crackleOn(KartFx fx,const KartFxInput& in,KartFxSink& sink){
        sink.create(fx,body(in));sink.setFrame(fx,body(in));keepAlive_=true; // 0x806a5244, 0x806a56c0
    }
    // 0x806a60a8: rk_pow bursts once, staggered by the racer index, at the kart's bottom.
    void powHit(const KartFxInput& in,KartFxSink& sink){
        const bool start=int32_t(index_%6)+1==powHit_;
        powHit_=std::min(powHit_+1,PowEnd);
        if(start)sink.create(KartFx::Pow,bottom(in));
        if(sink.alive(KartFx::Pow)){sink.setFrame(KartFx::Pow,bottom(in));keepAlive_=true;}
    }
    // 0x806a62fc: rk_pow1 bursts once at index + 1 after a stomp wave.
    void powWave(const KartFxInput& in,KartFxSink& sink){
        const bool start=int32_t(index_)+1==powWave_;
        powWave_=std::min(powWave_+1,PowEnd);
        if(start)sink.create(KartFx::Pow1,bottom(in));
        if(sink.alive(KartFx::Pow1)){sink.setFrame(KartFx::Pow1,bottom(in));keepAlive_=true;}
    }
    // rk_powUp follows while the POW is pending, then fades or is killed (0x80690884); +9
    // while it was alive this update.
    void powUp(const KartFxInput& in,KartFxSink& sink){
        keepAlive_|=sink.alive(KartFx::PowUp);
        if(powUp_){if(sink.alive(KartFx::PowUp))sink.setFrame(KartFx::PowUp,scaled(pose(in),in));}
        else stop(KartFx::PowUp,scaled(pose(in),in),sink);
        powUp_=false;
    }
    // 0x806972c0: rk_slipStreamPre while drafting, faded (on every kart) when drafting
    // stops; rk_slipStream through the boost, then ten frames fading out by setColor alpha
    // before the kill. InAction and BeforeRespawn hide both.
    void slipstream(const KartFxInput& in,bool respawnStart,KartFxSink& sink){
        const EffectFrame m=effectFrame(in);
        float scale=1;
        const bool scaled=effectScale(in,scale);
        // One EGG::Effect call sequence: create (+0xc), setMtx (+0x78), setColor (+0x50),
        // setScale (+0x70) when +0xb0, update (+0x80). Creating a new instance resets the
        // wrapper (+0x84), dropping an earlier setScale; a running instance keeps it.
        auto egg=[&](KartFx fx,bool create,const uint8_t* color){
            EggScale& s=eggScale_[fx==KartFx::SlipStream];
            if(create){if(!sink.alive(fx))s={};sink.create(fx,withScale(m,s));}
            if(color)sink.setColor(fx,color);
            if(scaled){s.set=true;s.value=scale;}
            sink.setFrame(fx,withScale(m,s));
        };
        if(in.drafting&&!in.inAction&&!in.beforeRespawn)egg(KartFx::SlipStreamPre,true,nullptr);
        else if(sink.alive(KartFx::SlipStreamPre)){sink.followFade(KartFx::SlipStreamPre);egg(KartFx::SlipStreamPre,false,nullptr);}
        const bool visible=in.slipBoost&&!in.inAction&&!in.beforeRespawn;
        if(visible)egg(KartFx::SlipStream,true,nullptr);
        if((!visible&&slipVisible_)||(respawnStart&&in.slipBoost))slipFade_=0;
        if(slipFade_!=-1){
            const uint8_t color[4]={255,255,255,uint8_t(255-25*slipFade_)};
            egg(KartFx::SlipStream,true,color);
            ++slipFade_;
        }
        if(slipFade_>=SlipFadeFrames){
            if(sink.alive(KartFx::SlipStream))sink.kill(KartFx::SlipStream);
            slipFade_=-1;
        }
        slipVisible_=visible;
    }
    struct EggScale { bool set=false; float value=1; };
    static EffectFrame withScale(EffectFrame f,const EggScale& s){f.scale=s.set?s.value:1.f;return f;}
    int32_t lightning_=BoltEnd,cloud_=CloudEnd,powHit_=PowIdle,powWave_=PowIdle;
    float bulletHeight_=0;
    uint8_t index_=0;
    bool local_=false,ghost_=false,wasBullet_=false,wasMega_=false,powUp_=false;
    // Retail resets only the wall and bush timers here: the object timer (+0x7b5, course
    // objects' hit callbacks) is not ported, and kart contact (+0x7b6, OnKartCollision)
    // reaches only the touched racer of a pair, never racer 0, which checks its pairs first.
    std::array<int8_t,HitCount> hitFrames_{};
    int32_t slipFade_=-1;          // +0x8c, -1 idle
    bool slipVisible_=false;       // +0x89
    bool wasBeforeRespawn_=false;  // +0x97
    bool wasLod_=false;            // +8, +7 at the last update outside a Bullet
    bool keepAlive_=false;         // +9
    uint32_t wallContacts_=0;      // +0x7b0
    std::array<EggScale,2> eggScale_{};
};

// KartItemEffects on RaceEffects: racer r owns KartFxCount slots from FirstSlot. The player's
// own kart uses the full emitters, every other racer the S variants (KartEffect 0x8068abbc).
// Racer r's instances live in effect group FirstGroup + r, as KartEffect's do (+0x134).
class KartFxSlots final : public KartFxSink {
public:
    static constexpr unsigned FirstSlot=32,MaxRacers=12,FirstGroup=2;
    static_assert(FirstSlot+MaxRacers*KartFxCount<=RaceEffects::SlotCount,"KartEffect slots");
    static_assert(FirstGroup+MaxRacers<=32,"one mask bit per group");
    static constexpr uint32_t groupBit(unsigned racer){return 1u<<(FirstGroup+racer);}
    void bind(RaceEffects& effects){
        static constexpr const char* names[KartFxCount][2]={
            {"rk_star","rk_starS"},{"rk_killer","rk_killerS"},{"rk_killer1T","rk_killer1TS"},
            {"rk_thunder","rk_thunderS"},{"rk_kaminariGumo","rk_kaminariGumoS"},
            {"rk_thunderBiri","rk_thunderBiri"},{"rk_thunderBiri","rk_thunderBiri"},
            {"rk_kyodai","rk_kyodaiS"},{"rk_pow","rk_powS"},{"rk_pow1","rk_pow1S"},{"rk_powUp","rk_powUp"},
            // 0x8068abbc: the boost's full emitter also goes to split-screen players
            // (+0x11, +0x13); with one screen both pick by the player's own kart (+0xf).
            {"rk_slipStreamPre","rk_slipStreamPreS"},{"rk_slipStream","rk_slipStreamS"}};
        effects_=&effects;
        for(unsigned i=0;i<KartFxCount;++i)for(unsigned j=0;j<2;++j)specs_[i][j]=effects.find(names[i][j]);
    }
    void select(unsigned racer,bool local){racer_=racer<MaxRacers?racer:0;local_=local;}
    bool alive(KartFx fx) const override { return effects_&&effects_->alive(slot(fx)); }
    void create(KartFx fx,const EffectFrame& frame) override {
        const int spec=specs_[unsigned(fx)][local_?0:1];
        if(effects_&&spec>=0)effects_->create(slot(fx),spec,frame,uint8_t(FirstGroup+racer_));
    }
    void setFrame(KartFx fx,const EffectFrame& frame) override { if(effects_)effects_->move(slot(fx),frame); }
    void followFade(KartFx fx) override { if(effects_)effects_->followFade(slot(fx)); }
    void kill(KartFx fx) override { if(effects_)effects_->kill(slot(fx)); }
    void setColor(KartFx fx,const uint8_t rgba[4]) override { if(effects_)effects_->setColor(slot(fx),rgba); }
private:
    unsigned slot(KartFx fx) const { return FirstSlot+racer_*KartFxCount+unsigned(fx); }
    RaceEffects* effects_=nullptr;
    int specs_[KartFxCount][2]{};
    unsigned racer_=0;
    bool local_=false;
};
}
