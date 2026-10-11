#include <mkw/mod_engine.hpp>
#include <mkw/race_items.hpp>

#include <algorithm>
#include <cstdio>
#include <cstring>

namespace mkw {

ModEngine& ModEngine::instance() {
    static ModEngine s_instance;
    return s_instance;
}

ModEngine::ModEngine() = default;
ModEngine::~ModEngine() = default;

void ModEngine::init() {
    if (initialized_) {
        return;
    }
    initialized_ = true;

    // Check for Pulsar mod manifest in standard locations
    static constexpr const char* MANIFEST_CANDIDATES[] = {
        "sdmc:/3ds/mkw-3ds/pulsar_manifest.json",
        "pulsar_manifest.json",
        "romfs:/pulsar_manifest.json"
    };

    for (const char* path : MANIFEST_CANDIDATES) {
        if (loadManifest(path)) {
            break;
        }
    }
}

void ModEngine::shutdown() {
    hooks_.clear();
    cups_.clear();
    modLoaded_ = false;
    settings_ = ModSettings{};
    initialized_ = false;
}

void ModEngine::registerHook(IModHook* hook) {
    if (!hook) {
        return;
    }
    auto it = std::find(hooks_.begin(), hooks_.end(), hook);
    if (it == hooks_.end()) {
        hooks_.push_back(hook);
    }
}

void ModEngine::unregisterHook(IModHook* hook) {
    if (!hook) {
        return;
    }
    auto it = std::find(hooks_.begin(), hooks_.end(), hook);
    if (it != hooks_.end()) {
        hooks_.erase(it);
    }
}

void ModEngine::onPhysicsStep(float dt, unsigned step) {
    for (auto* hook : hooks_) {
        hook->onPhysicsStep(dt, step);
    }
}

void ModEngine::onKartMove(Kinoko::Kart::KartMove* move) {
    for (auto* hook : hooks_) {
        hook->onKartMove(move);
    }
}

Kinoko::Course ModEngine::onCourseResolve(int cupIndex, int trackIndex, Kinoko::Course fallback) {
    Kinoko::Course resolved = fallback;
    for (auto* hook : hooks_) {
        resolved = hook->onCourseResolve(cupIndex, trackIndex, resolved);
    }

    if (resolved == fallback && modLoaded_ && cupIndex >= 0 && trackIndex >= 0) {
        if (size_t(cupIndex) < cups_.size()) {
            const auto& cup = cups_[cupIndex];
            if (size_t(trackIndex) < cup.trackCount) {
                resolved = cup.tracks[trackIndex].courseId;
            }
        }
    }

    return resolved;
}

ItemKind ModEngine::onItemRoll(unsigned player, unsigned rank, ItemKind defaultItem) {
    ItemKind result = defaultItem;
    for (auto* hook : hooks_) {
        result = hook->onItemRoll(player, rank, result);
    }
    return result;
}

unsigned ModEngine::onAudioResolve(Kinoko::Course course, unsigned defaultStreamId) {
    unsigned streamId = defaultStreamId;
    for (auto* hook : hooks_) {
        streamId = hook->onAudioResolve(course, streamId);
    }

    if (streamId == defaultStreamId && modLoaded_) {
        if (const auto* track = findTrack(course)) {
            if (track->musicStreamId != 0) {
                streamId = track->musicStreamId;
            }
        }
    }

    return streamId;
}

const ModTrackDef* ModEngine::findTrack(Kinoko::Course course) const {
    for (const auto& cup : cups_) {
        for (size_t i = 0; i < cup.trackCount; ++i) {
            if (cup.tracks[i].courseId == course) {
                return &cup.tracks[i];
            }
        }
    }
    return nullptr;
}

// Lightweight manifest reader for pulsar_manifest.json
bool ModEngine::loadManifest(const char* manifestPath) {
    FILE* f = fopen(manifestPath, "rb");
    if (!f) {
        return false;
    }

    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (len <= 0 || len > 256 * 1024) { // 256 KiB safety limit
        fclose(f);
        return false;
    }

    std::vector<char> buffer(size_t(len) + 1, 0);
    size_t readBytes = fread(buffer.data(), 1, size_t(len), f);
    fclose(f);

    if (readBytes == 0) {
        return false;
    }

    const char* p = buffer.data();

    // Check for boolean settings
    if (strstr(p, "\"enable_200cc\": true") || strstr(p, "\"enable_200cc\":true")) {
        settings_.enable200cc = true;
    }
    if (strstr(p, "\"brake_drift\": true") || strstr(p, "\"brake_drift\":true")) {
        settings_.brakeDrifting = true;
    }
    if (strstr(p, "\"custom_items\": true") || strstr(p, "\"custom_items\":true")) {
        settings_.customItems = true;
    }

    modLoaded_ = true;
    return true;
}

} // namespace mkw
