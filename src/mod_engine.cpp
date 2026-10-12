#include <mkw/mod_engine.hpp>
#include <mkw/course_catalog.hpp>
#include <mkw/race_items.hpp>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace mkw {

namespace {

// Lightweight helper functions to parse JSON strings and numbers
const char* skipWhitespace(const char* p) {
    while (*p && (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')) {
        ++p;
    }
    return p;
}

const char* findKey(const char* p, const char* key, const char* end) {
    size_t keyLen = std::strlen(key);
    while (p < end && *p) {
        if (*p == '"' && strncmp(p + 1, key, keyLen) == 0 && p[1 + keyLen] == '"') {
            const char* colon = p + 2 + keyLen;
            colon = skipWhitespace(colon);
            if (*colon == ':') {
                return skipWhitespace(colon + 1);
            }
        }
        ++p;
    }
    return nullptr;
}

bool parseString(const char* val, char* out, size_t maxLen) {
    if (!val || *val != '"') {
        return false;
    }
    ++val;
    size_t i = 0;
    while (*val && *val != '"' && i + 1 < maxLen) {
        if (*val == '\\' && val[1]) {
            ++val;
        }
        out[i++] = *val++;
    }
    out[i] = '\0';
    return true;
}

int parseInt(const char* val) {
    if (!val) {
        return 0;
    }
    return std::atoi(val);
}

} // namespace

ModEngine& ModEngine::instance() {
    static ModEngine s_instance;
    return s_instance;
}

ModEngine::ModEngine() = default;
ModEngine::~ModEngine() = default;

struct CharacterSkinTableEntry {
    const char* names[8];
};

static const CharacterSkinTableEntry RETRO_SKIN_TABLE[24] = {
    {{"Mario (Fire)", "Mario (Builder)", "Snowman", "Mario (SM64)", "Mario (SNES)", "Mario (Happi)", nullptr}},
    {{"Baby Peach (Cherub)", "Pikachu", "Lemmy", "Kirby", nullptr}},
    {{"Waluigi (Athletic)", "Waluigi (Vampire)", "Wiggler", "Waluigi (Mariachi)", "Captain Falcon", nullptr}},
    {{"Dark Bowser", "Bowser (Santa)", "Chargin' Chuck", "Boom Boom", "Bowser (Fury)", "Meowser", nullptr}},
    {{"Baby Daisy (Touring)", "Rocky Wrench", "Connie", "Talking Flower", "Baby Daisy (Raincoat)", nullptr}},
    {{"Dry Bones (Dark)", "Dry Bones (Gold)", "Goomba", "Peepa", nullptr}},
    {{"Baby Wario", "Baby Mario (Koala)", "Coin Coffer", "Shy Guy", "Paper Mario", "Cheep Cheep", nullptr}},
    {{"Luigi (Ice)", "Luigi (Vacation)", "Monty Mole", "Sonic", "Don-Chan", nullptr}},
    {{"Captain Toad", "Toad (Builder)", "Swoop", "Toadsworth", "Tuxie", "Toad (Pit Crew)", nullptr}},
    {{"DK (Yeti)", "DK (Gladiator)", "Kritter", "Pokey", "King K. Rool", "Pianta", nullptr}},
    {{"Yoshi (Black)", "Yoshi (Kangaroo)", "Piranha Plant", "Yoshi (Light-Blue)", nullptr}},
    {{"Wario (Cowboy)", "Wario (Hiker)", "King Bob-omb", "Wario (Metal)", "Morton", "Snooza Koopa", nullptr}},
    {{"Baby Waluigi", "Professor E. Gadd", "Spike", "Fuzzy", "Virus Trio", nullptr}},
    {{"Toadette (Summer)", "Toadette (Soft Server)", "Blooper", "Para-Biddybud", nullptr}},
    {{"Koopa Paratroopa", "Lakitu", "Koopa (Freerunning)", "Koopa (Sailor)", "Sidestepper", nullptr}},
    {{"Daisy (Black/Teal)", "Daisy (Farmer)", "Daisy (Swimwear)", "Ludwig", "Bill Board", "Daisy (Yukata)", nullptr}},
    {{"Peach (Ice)", "Peach (Explorer)", "Peach (Halloween)", "Peach (Touring)", "Shantae", nullptr}},
    {{"Birdo (White)", "Mega Man", "Dolphin", "Shadow", nullptr}},
    {{"Diddy Kong (All-Star)", "Dixie Kong", "The Chimp", "Iggy", "Fox McCloud", nullptr}},
    {{"King Boo (Dark Moon)", "Gooper Blooper", "Goku", "King Boo (Aristocrat)", nullptr}},
    {{"Bowser Jr. (Pirate)", "Hammer Bro", "Kamek", "Bowser Jr. (Wonder)", "Nabbit", "Ant Trooper", nullptr}},
    {{"Dry Bowser (Dark)", "Lubba", "Petey Piranha", "Plessie", nullptr}},
    {{"Zapple Kong", "Chain Chomp", "Funky Kong (Link)", "Funky Kong (Dripped Up)", "R.O.B.", "Jaxi", "Donkey Kong Jr.", nullptr}},
    {{"Rosalina (Aurora)", "Rosalina (Touring)", "Pauline", "Rosalina (Crystal Blue)", "Honey Queen", "Rosalina (Pro Racer)", nullptr}}
};

void ModEngine::init() {
    if (initialized_) {
        return;
    }
    initialized_ = true;

    for (size_t d = 0; d < 24; ++d) {
        characterSkinNames_[d].clear();
        for (size_t s = 0; s < 8 && RETRO_SKIN_TABLE[d].names[s]; ++s) {
            characterSkinNames_[d].push_back(RETRO_SKIN_TABLE[d].names[s]);
        }
        characterSkins_[d] = 0;
    }

    loadSettings();

    // Check for Pulsar mod manifest in standard locations
    static constexpr const char* MANIFEST_CANDIDATES[] = {
        "sdmc:/3ds/mkw-3ds/pulsar_manifest.json",
        "romfs:/pulsar_manifest.json",
        "pulsar_manifest.json"
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
    dynamicTracks_.clear();
    stringStorage_.clear();
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

    // Custom items distribution filter (verified from Retro Rewind: Race/CustomItems.cpp)
    if (settings_.customItems && result != ItemKind::None) {
        const uint32_t bitfield = settings_.customItemsBitfield ? settings_.customItemsBitfield : PulsarPhysics::AllItemsBitfield;
        const unsigned itemIdx = static_cast<unsigned>(result);
        if (itemIdx < 19 && !(bitfield & (1u << itemIdx))) {
            // Item disabled by rule: fallback to standard Mushroom if allowed, otherwise first allowed item
            if (bitfield & (1u << static_cast<unsigned>(ItemKind::Mushroom))) {
                result = ItemKind::Mushroom;
            } else {
                for (unsigned i = 0; i < 19; ++i) {
                    if (bitfield & (1u << i)) {
                        result = static_cast<ItemKind>(i);
                        break;
                    }
                }
            }
        }
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

unsigned ModEngine::cupCount() const {
    if (modLoaded_ && !cups_.empty()) {
        return cups_.size();
    }
    return 8;
}

unsigned ModEngine::trackCount() const {
    if (modLoaded_ && !dynamicTracks_.empty()) {
        return dynamicTracks_.size();
    }
    return CourseCount;
}

const CourseChoice& ModEngine::courseChoice(unsigned index) const {
    if (modLoaded_ && !dynamicTracks_.empty() && index < dynamicTracks_.size()) {
        return dynamicTracks_[index];
    }
    if (index < CourseCount) {
        return Courses[index];
    }
    return Courses[0];
}

const char* ModEngine::courseName(unsigned index) const {
    return courseChoice(index).name;
}

const char* ModEngine::cupName(unsigned cupIndex) const {
    if (modLoaded_ && cupIndex < cups_.size()) {
        if (cups_[cupIndex].name[0] != '\0') {
            return cups_[cupIndex].name;
        }
    }
    static constexpr const char* VANILLA_CUPS[] = {
        "Mushroom Cup", "Flower Cup", "Star Cup", "Special Cup",
        "Shell Cup", "Banana Cup", "Leaf Cup", "Lightning Cup"
    };
    if (cupIndex < 8) {
        return VANILLA_CUPS[cupIndex];
    }
    return "Custom Cup";
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
    const char* bufferEnd = p + readBytes;

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

    // Parse custom cups array
    const char* cupsStart = findKey(p, "cups", bufferEnd);
    if (cupsStart && *cupsStart == '[') {
        const char* cur = cupsStart + 1;
        while (cur < bufferEnd && *cur && *cur != ']') {
            cur = skipWhitespace(cur);
            if (*cur == '{') {
                const char* cupObjStart = cur;
                // Find matching closing brace for this cup
                int depth = 1;
                const char* cupObjEnd = cupObjStart + 1;
                while (cupObjEnd < bufferEnd && depth > 0) {
                    if (*cupObjEnd == '{') ++depth;
                    else if (*cupObjEnd == '}') --depth;
                    ++cupObjEnd;
                }

                ModCupDef cupDef{};
                const char* cupNameVal = findKey(cupObjStart, "name", cupObjEnd);
                if (cupNameVal) {
                    parseString(cupNameVal, cupDef.name, sizeof(cupDef.name));
                }
                const char* cupIconVal = findKey(cupObjStart, "icon", cupObjEnd);
                if (cupIconVal) {
                    parseString(cupIconVal, cupDef.icon, sizeof(cupDef.icon));
                }

                // Parse tracks inside this cup
                const char* tracksStart = findKey(cupObjStart, "tracks", cupObjEnd);
                if (tracksStart && *tracksStart == '[') {
                    const char* tCur = tracksStart + 1;
                    while (tCur < cupObjEnd && *tCur && *tCur != ']' && cupDef.trackCount < 4) {
                        tCur = skipWhitespace(tCur);
                        if (*tCur == '{') {
                            int tDepth = 1;
                            const char* trackObjStart = tCur;
                            const char* trackObjEnd = trackObjStart + 1;
                            while (trackObjEnd < cupObjEnd && tDepth > 0) {
                                if (*trackObjEnd == '{') ++tDepth;
                                else if (*trackObjEnd == '}') --tDepth;
                                ++trackObjEnd;
                            }

                            ModTrackDef trackDef{};
                            const char* tName = findKey(trackObjStart, "name", trackObjEnd);
                            if (tName) parseString(tName, trackDef.name, sizeof(trackDef.name));

                            const char* tId = findKey(trackObjStart, "course_id", trackObjEnd);
                            if (tId) trackDef.courseId = static_cast<Kinoko::Course>(parseInt(tId));

                            const char* tArch = findKey(trackObjStart, "archive", trackObjEnd);
                            if (tArch) parseString(tArch, trackDef.archive, sizeof(trackDef.archive));

                            const char* tLaps = findKey(trackObjStart, "laps", trackObjEnd);
                            trackDef.lapCount = tLaps ? static_cast<uint8_t>(parseInt(tLaps)) : 3;

                            const char* tMusic = findKey(trackObjStart, "music_stream_id", trackObjEnd);
                            trackDef.musicStreamId = tMusic ? static_cast<uint16_t>(parseInt(tMusic)) : 0;

                            const char* tModels = findKey(trackObjStart, "models", trackObjEnd);
                            if (tModels) parseString(tModels, trackDef.models, sizeof(trackDef.models));

                            const char* tSky = findKey(trackObjStart, "sky", trackObjEnd);
                            if (tSky) parseString(tSky, trackDef.sky, sizeof(trackDef.sky));

                            cupDef.tracks[cupDef.trackCount++] = trackDef;

                            // Add CourseChoice entry for dynamic catalog
                            stringStorage_.push_back(trackDef.name);
                            const char* storedName = stringStorage_.back().c_str();

                            stringStorage_.push_back(trackDef.archive);
                            const char* storedArchive = stringStorage_.back().c_str();

                            stringStorage_.push_back(trackDef.models);
                            const char* storedModels = stringStorage_.back().c_str();

                            stringStorage_.push_back(trackDef.sky);
                            const char* storedSky = stringStorage_.back().c_str();

                            stringStorage_.push_back(cupDef.name);
                            const char* storedCup = stringStorage_.back().c_str();

                            CourseChoice choice{
                                storedName,
                                trackDef.courseId,
                                storedArchive,
                                storedModels,
                                storedSky,
                                storedCup,
                                true, // supported
                                true  // cpuCompletionVerified
                            };
                            dynamicTracks_.push_back(choice);

                            tCur = trackObjEnd;
                        } else {
                            ++tCur;
                        }
                    }
                }

                cups_.push_back(cupDef);
                cur = cupObjEnd;
            } else {
                ++cur;
            }
        }
    }

    modLoaded_ = true;
    return true;
}

struct SavedSettingsBinary {
    uint32_t magic = 0x54544553; // 'SETT'
    uint32_t version = 1;
    uint8_t enable200cc = 0;
    uint8_t brakeDrifting = 1;
    uint8_t hardAI = 0;
    uint8_t customItems = 0;
    uint32_t customItemsBitfield = PulsarPhysics::AllItemsBitfield;
    uint8_t defaultEngineClass = 2;
    uint8_t reserved[19]{};
};

bool ModEngine::loadSettings(const char* path) {
    if (!path) return false;
    FILE* f = fopen(path, "rb");
    if (!f) return false;

    SavedSettingsBinary bin{};
    size_t readCount = fread(&bin, 1, sizeof(bin), f);
    fclose(f);

    if (readCount < sizeof(uint32_t) * 2 || bin.magic != 0x54544553) {
        return false;
    }

    settings_.enable200cc = bin.enable200cc != 0;
    settings_.brakeDrifting = bin.brakeDrifting != 0;
    settings_.hardAI = bin.hardAI != 0;
    settings_.customItems = bin.customItems != 0;
    settings_.customItemsBitfield = bin.customItemsBitfield ? bin.customItemsBitfield : PulsarPhysics::AllItemsBitfield;
    settings_.defaultEngineClass = bin.defaultEngineClass;
    return true;
}

bool ModEngine::saveSettings(const char* path) {
    if (!path) return false;
    char tempPath[128];
    std::snprintf(tempPath, sizeof(tempPath), "%s.tmp", path);

    FILE* f = fopen(tempPath, "wb");
    if (!f) return false;

    SavedSettingsBinary bin{};
    bin.magic = 0x54544553;
    bin.version = 1;
    bin.enable200cc = settings_.enable200cc ? 1 : 0;
    bin.brakeDrifting = settings_.brakeDrifting ? 1 : 0;
    bin.hardAI = settings_.hardAI ? 1 : 0;
    bin.customItems = settings_.customItems ? 1 : 0;
    bin.customItemsBitfield = settings_.customItemsBitfield;
    bin.defaultEngineClass = settings_.defaultEngineClass;

    size_t written = fwrite(&bin, 1, sizeof(bin), f);
    fclose(f);

    if (written != sizeof(bin)) {
        remove(tempPath);
        return false;
    }

    remove(path);
    return rename(tempPath, path) == 0;
}

// Global dynamic catalog accessors (course_catalog.hpp)
unsigned courseCount() {
    return modEngine().trackCount();
}

unsigned cupCount() {
    return modEngine().cupCount();
}

const CourseChoice& course(unsigned index) {
    return modEngine().courseChoice(index);
}

const char* courseName(unsigned index) {
    return modEngine().courseName(index);
}

const char* cupName(unsigned cupIndex) {
    return modEngine().cupName(cupIndex);
}

uint8_t ModEngine::courseLaps(unsigned index) const {
    if (modLoaded_ && !cups_.empty()) {
        unsigned cupIdx = index / 4;
        unsigned trackIdx = index % 4;
        if (cupIdx < cups_.size() && trackIdx < cups_[cupIdx].trackCount) {
            uint8_t l = cups_[cupIdx].tracks[trackIdx].lapCount;
            if (l > 0) return l;
        }
    }
    return 3;
}

unsigned courseLaps(unsigned index) {
    return modEngine().courseLaps(index);
}

unsigned ModEngine::characterSkin(unsigned driverId) const {
    if (driverId < 26) return characterSkins_[driverId];
    return 0;
}

void ModEngine::setCharacterSkin(unsigned driverId, unsigned slot) {
    if (driverId < 26) characterSkins_[driverId] = slot;
}

void ModEngine::cycleCharacterSkin(unsigned driverId, int dir) {
    if (driverId >= 26) return;
    unsigned maxSkins = characterSkinCount(driverId);
    if (maxSkins == 0) return;
    int cur = int(characterSkins_[driverId]);
    cur += dir;
    if (cur < 0) cur = int(maxSkins);
    else if (unsigned(cur) > maxSkins) cur = 0;
    characterSkins_[driverId] = unsigned(cur);
}

unsigned ModEngine::characterSkinCount(unsigned driverId) const {
    if (driverId < 26) return characterSkinNames_[driverId].size();
    return 0;
}

const char* ModEngine::characterSkinName(unsigned driverId, unsigned slot) const {
    if (slot == 0) return "Default";
    if (driverId < 26 && slot <= characterSkinNames_[driverId].size()) {
        return characterSkinNames_[driverId][slot - 1].c_str();
    }
    return "Default";
}

} // namespace mkw

extern "C" const char* getActiveTrackArchive() {
    return mkw::modEngine().activeTrackArchive();
}

