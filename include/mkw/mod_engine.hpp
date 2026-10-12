#pragma once
#include <mkw/course_catalog.hpp>
#include <array>
#include <cstdint>
#include <cstring>
#include <string>
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
    char mapTexture[64]{};
    char mapOverview[64]{};
    float mapX0 = 0.f, mapZ0 = 0.f, mapX1 = 0.f, mapZ1 = 0.f;
    uint16_t mapWidth = 0, mapHeight = 0;
    uint16_t mapOverviewWidth = 0, mapOverviewHeight = 0;
    float mapUnitsPerPixel = 64.f;
    float mapStartLeft[2]{};
    float mapStartRight[2]{};
};

// Definition for a custom cup containing up to 4 tracks
struct ModCupDef {
    char name[64]{};
    char icon[32]{};
    uint16_t trackCount = 0;
    std::array<ModTrackDef, 4> tracks{};
};

// Verified physics constants from Retro Rewind (rr-pulsar: Race/200ccParams.hpp & Race/200cc.cpp)
namespace PulsarPhysics {
    inline constexpr float SpeedFactor = 5.0f / 3.0f;          // 1.6666667f speed factor in 200cc
    inline constexpr float CannonExit = 2.0f / 3.0f;           // Cannon exit speed ratio in 200cc
    inline constexpr float BrakeDriftDecel = -1.5f;            // Deceleration during brake drift
    inline constexpr float FastFallingBodyGravity = 0.39f;     // Body gravity multiplier when pulling stick back
    inline constexpr float FastFallingWheelGravity = 0.3f;     // Wheel gravity multiplier when pulling stick back
    inline constexpr float Weight200cc = 6.0f;                 // Kart weight in 200cc
    inline constexpr uint32_t AllItemsBitfield = 0x7FFFF;      // Bitmask for all 19 standard items
}

// Runtime settings configurable by Pulsar-3DS or manifest
struct ModSettings {
    bool enable200cc = false;
    bool brakeDrifting = true;
    bool hardAI = false;
    bool customItems = false;
    uint32_t customItemsBitfield = PulsarPhysics::AllItemsBitfield;
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

struct CourseChoice;

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

    float speedFactor() const { return is200ccEnabled() ? PulsarPhysics::SpeedFactor : 1.0f; }
    float cannonExitRatio() const { return is200ccEnabled() ? PulsarPhysics::CannonExit : 1.0f; }
    float brakeDriftDeceleration() const { return PulsarPhysics::BrakeDriftDecel; }
    uint32_t customItemsBitfield() const { return settings_.customItemsBitfield; }

    bool loadSettings(const char* path = "sdmc:/3ds/mkw-3ds/pulsar_settings.bin");
    bool saveSettings(const char* path = "sdmc:/3ds/mkw-3ds/pulsar_settings.bin");

    // Dynamic Course Catalog (Phase 2)
    unsigned cupCount() const;
    unsigned trackCount() const;
    const CourseChoice& courseChoice(unsigned index) const;
    const char* courseName(unsigned index) const;
    const char* cupName(unsigned cupIndex) const;
    uint8_t courseLaps(unsigned index) const;

    // Manifest management (loads pulsar_manifest.json)
    bool loadManifest(const char* manifestPath);
    const std::vector<ModCupDef>& cups() const { return cups_; }
    const ModTrackDef* findTrack(Kinoko::Course course) const;
    const ModTrackDef* findTrackByIndex(unsigned index) const;

    const char* activeTrackArchive() const { return activeTrackArchive_; }
    void setActiveTrackArchive(const char* archive) {
        if (archive) {
            std::strncpy(activeTrackArchive_, archive, sizeof(activeTrackArchive_) - 1);
            activeTrackArchive_[sizeof(activeTrackArchive_) - 1] = '\0';
        } else {
            activeTrackArchive_[0] = '\0';
        }
    }

    // Character Skins
    unsigned characterSkin(unsigned driverId) const;
    void setCharacterSkin(unsigned driverId, unsigned slot);
    void cycleCharacterSkin(unsigned driverId, int dir);
    unsigned characterSkinCount(unsigned driverId) const;
    const char* characterSkinName(unsigned driverId, unsigned slot) const;
    const char* characterSkinAuthor(unsigned driverId, unsigned slot) const;

    // Track Variations
    unsigned trackVariantCount(unsigned courseIndex) const;
    const char* trackVariantName(unsigned courseIndex, unsigned variantIndex) const;
    void setActiveTrackVariant(unsigned courseIndex, unsigned variantIndex);
    unsigned activeTrackVariant(unsigned courseIndex) const;
    const char* activeTrackVariantArchive(unsigned courseIndex) const;

private:
    ModEngine();
    ~ModEngine();

    bool initialized_ = false;
    bool modLoaded_ = false;
    ModSettings settings_{};
    char activeTrackArchive_[128]{};
    std::vector<IModHook*> hooks_;
    std::vector<ModCupDef> cups_;
    std::vector<std::string> stringStorage_;
    std::vector<CourseChoice> dynamicTracks_;
    std::array<unsigned, 26> characterSkins_{};
    std::array<std::vector<std::string>, 26> characterSkinNames_{};
    std::array<std::vector<std::string>, 26> characterSkinAuthors_{};
    std::array<unsigned, 256> activeTrackVariants_{};
};

inline ModEngine& modEngine() {
    return ModEngine::instance();
}

} // namespace mkw
