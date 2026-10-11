// Host tool for tools/optimize_menu_textures.py.
// Composes every menu page through the production composer (pages, modes,
// cursors, selections, ages, transitions and OK-glow pulses) and reports, per
// sprite, the largest on-screen size of its full UV extent in top-LCD pixels.
// Movie and vehicle-model quads are not textures and are skipped.
#include <mkw/menu_ui.hpp>
#include <mkw/menu_transition.hpp>
#include <mkw/menu_assets.hpp>
#include <mkw/mod_engine.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

namespace mkw {
unsigned courseCount() { return 32; }
unsigned cupCount() { return 8; }
const CourseChoice& course(unsigned index) { return Courses[index % 32]; }
const char* courseName(unsigned index) { return Courses[index % 32].name; }
const char* cupName(unsigned cupIndex) { return Courses[std::min(cupIndex * 4, 31u)].cup; }

ModEngine& ModEngine::instance() { static ModEngine e; return e; }
unsigned ModEngine::characterSkin(unsigned) const { return 0; }
void ModEngine::setCharacterSkin(unsigned, unsigned) {}
void ModEngine::cycleCharacterSkin(unsigned, int) {}
unsigned ModEngine::characterSkinCount(unsigned) const { return 0; }
const char* ModEngine::characterSkinName(unsigned, unsigned) const { return "Default"; }
void ModEngine::init() {}
bool ModEngine::loadSettings(const char*) { return true; }
bool ModEngine::saveSettings(const char*) { return true; }
bool ModEngine::loadManifest(const char*) { return false; }
Kinoko::Course ModEngine::onCourseResolve(int, int, Kinoko::Course id) { return id; }
const ModTrackDef* ModEngine::findTrack(Kinoko::Course) const { return nullptr; }
unsigned ModEngine::cupCount() const { return 8; }
unsigned ModEngine::trackCount() const { return 32; }
const CourseChoice& ModEngine::courseChoice(unsigned index) const { return Courses[index % 32]; }
const char* ModEngine::courseName(unsigned index) const { return index < 32 ? Courses[index].name : ""; }
const char* ModEngine::cupName(unsigned cupIndex) const { return cupIndex < 8 ? Courses[cupIndex * 4].cup : ""; }
ModEngine::ModEngine() = default;
ModEngine::~ModEngine() = default;
}

using namespace mkw;
static std::vector<float> maxW(std::size(UiSprites),0.f),maxH(std::size(UiSprites),0.f);
static void record(const std::vector<UiQuad>& quads){
 for(const auto& q:quads){
  if(q.movie!=~0u||q.vehicleIcon!=~0u||q.sprite>=std::size(UiSprites))continue;
  const float du=std::fabs(q.u1-q.u0),dv=std::fabs(q.v1-q.v0);
  if(du>1e-4f)maxW[q.sprite]=std::max(maxW[q.sprite],q.w/du);
  if(dv>1e-4f)maxH[q.sprite]=std::max(maxH[q.sprite],q.h/dv);
 }
}
int main(int argc,char** argv){
 if(argc<2){std::fprintf(stderr,"usage: %s output.json\n",argv[0]);return 2;}
 const UiPage pages[]={UiPage::Strap,UiPage::Intro,UiPage::Title,UiPage::License,UiPage::MainMenu,UiPage::Mode,UiPage::EngineClass,UiPage::VSMode,UiPage::BattleMode,UiPage::Character,UiPage::Vehicle,UiPage::Drift,UiPage::Cup,UiPage::Course,UiPage::BattleCup,UiPage::BattleStage,UiPage::Ghost,UiPage::Confirm,UiPage::Pause,UiPage::QuitConfirm,UiPage::Results,UiPage::Error};
 UiRaceView race{};race.count=12;for(unsigned i=0;i<12;++i){race.racers[i].driver=i;race.racers[i].rank=i+1;}
 std::vector<UiQuad> q;
 for(UiPage page:pages)for(unsigned mode=0;mode<4;++mode)for(unsigned variant=0;variant<24;++variant)for(int mixed=0;mixed<2;++mixed){
  if(mixed&&page!=UiPage::EngineClass&&page!=UiPage::Vehicle)continue;
  MenuState s;s.selection.mode=UiMode(mode);s.selection.driver=variant;s.selection.vehicle=variant%12;
  s.selection.course=(variant*4+mode)%32;s.selection.battleStage=variant%10;s.selection.mixedEngineTypes=mixed;
  s.selection.engineClass=UiEngineClass(variant%4);
  s.enter(page);
  for(unsigned cursor=0;cursor<s.count();++cursor){
   MenuState t=s;t.cursor=cursor;
   for(unsigned age:{0u,31u,61u,121u,181u,241u,361u,481u}){
    MenuState u=t;u.advance(age);
    composeMenu(u,race,q);record(q);
    u.unavailable=true;composeMenu(u,race,q);record(q);u.unavailable=false;
   }
   if(variant>1&&page!=UiPage::Character&&page!=UiPage::Vehicle)continue;
   for(int back=0;back<2;++back){
    MenuState logical=t;logical.advance(30);MenuTransition tr;UiInput key;key.accept=!back;key.back=back;
    tr.input(logical,key);
    for(unsigned frame=0;frame<120&&tr.active();++frame){composeMenu(tr.visual(logical),race,q,tr.view());record(q);tr.advance(logical,1);}
   }
  }
 }
 FILE* f=std::fopen(argv[1],"w");if(!f)return 1;
 std::fprintf(f,"{\n");bool first=true;
 for(unsigned i=0;i<std::size(UiSprites);++i){
  if(maxW[i]<=0&&maxH[i]<=0)continue;
  std::fprintf(f,"%s \"%s\": [%.4f, %.4f]",first?"":",\n",UiSprites[i].key,maxW[i],maxH[i]);first=false;
 }
 std::fprintf(f,"\n}\n");std::fclose(f);
 return 0;
}
