#pragma once

#include <Common.hh>
#include <array>
#include <cstdint>
#include <vector>

namespace Kinoko::Kart {
class KartMove;
class KartPhysics;
}

namespace mkw {

enum class ItemKind : uint8_t;

// Definition for a custom track in a Pulsar / Retro Rewind pack
struct ModTrackDef {
    char name[64]{};
    Kinoko::Course courseId = Kinoko::Course::Luigi_Circuit;
    char archive[64]{};
    char models[64]{};
    char sky[64]{};
    uint8_t lapCount = 3;
    uint16_t musicStreamId = 0;
};

// Definition for a custom cup containing up to 4 tracks
struct ModCupDef {
    char name[64]{};
    char icon[32]{};
    uint16_t trackCount = 0;
    std::array<ModTrackDef, 4> tracks{};
};

// Runtime settings configurable by Pulsar-3DS or manifest
struct ModSettings {
    bool enable200cc = false;
    bool brakeDrifting = false;
    bool customItems = false;
    uint8_t defaultEngineClass = 2; // 0=50cc, 1=100cc, 2=150cc, 3=200cc
};

// Interface for native mod hooks (Pulsar-3DS event callbacks)
class IModHook {
public:
    virtual ~IModHook() = default;

    // Called on each simulation step in the race loop
    virtual void onPhysicsStep(float dt, unsigned step) {}

    // Called on each KartMove::calc() step for a racer
    virtual void onKartMove(Kinoko::Kart::KartMove* move) {}

    // Called when resolving course ID for a given cup and track slot
    virtual Kinoko::Course onCourseResolve(int cupIndex, int trackIndex, Kinoko::Course fallback) {
        return fallback;
    }

    // Called when rolling/calculating an item during race roulette
    virtual ItemKind onItemRoll(unsigned player, unsigned rank, ItemKind defaultItem) {
        return defaultItem;
    }

    // Called when resolving audio / DSP stream for a course
    virtual unsigned onAudioResolve(Kinoko::Course course, unsigned defaultStreamId) {
        return defaultStreamId;
    }
};

// Central manager for Pulsar-3DS modular native modding
class ModEngine {
public:
    static ModEngine& instance();

    void init();
    void shutdown();

    void registerHook(IModHook* hook);
    void unregisterHook(IModHook* hook);

    // Core hook dispatchers (invokes registered hooks, falling back to vanilla behavior)
    void onPhysicsStep(float dt, unsigned step);
    void onKartMove(Kinoko::Kart::KartMove* move);
    Kinoko::Course onCourseResolve(int cupIndex, int trackIndex, Kinoko::Course fallback);
    ItemKind onItemRoll(unsigned player, unsigned rank, ItemKind defaultItem);
    unsigned onAudioResolve(Kinoko::Course course, unsigned defaultStreamId);

    // Mod status & settings
    bool isModLoaded() const { return modLoaded_; }
    const ModSettings& settings() const { return settings_; }
    void setSettings(const ModSettings& settings) { settings_ = settings; }

    bool is200ccEnabled() const { return settings_.enable200cc; }
    void set200ccEnabled(bool enabled) { settings_.enable200cc = enabled; }

    bool isBrakeDriftEnabled() const { return settings_.brakeDrifting; }
    void setBrakeDriftEnabled(bool enabled) { settings_.brakeDrifting = enabled; }

    // Manifest management (loads pulsar_manifest.json)
    bool loadManifest(const char* manifestPath);
    const std::vector<ModCupDef>& cups() const { return cups_; }
    const ModTrackDef* findTrack(Kinoko::Course course) const;

private:
    ModEngine();
    ~ModEngine();

    bool initialized_ = false;
    bool modLoaded_ = false;
    ModSettings settings_{};
    std::vector<IModHook*> hooks_;
    std::vector<ModCupDef> cups_;
};

inline ModEngine& modEngine() {
    return ModEngine::instance();
}

} // namespace mkw
