#pragma once
#include <memory>
#include <mkw/math.hpp>
namespace mkw {
class Renderer;
class RaceItems;
// Each opponent owns its deforming vertices. Textures remain shared by Model.
class RacerVisuals {
public:
    RacerVisuals();
    ~RacerVisuals();
    bool load();
    void reset();
    void resetAnimation();
    void step(unsigned tick);
    // Poses and culls every opponent for this frame, on the job worker where
    // possible. Call after Renderer::begin; race state must not change until draw.
    void prepare(const Renderer& renderer,const RaceItems& items,Vec3 viewer,unsigned tick);
    // Draws in racer order; prepares inline first when prepare() was not called.
    void draw(Renderer& renderer,const RaceItems& items,Vec3 viewer,unsigned tick);
    unsigned count() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
