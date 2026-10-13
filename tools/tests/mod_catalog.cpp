#include <mkw/mod_engine.hpp>
#include <cassert>
#include <cstdio>
#include <cstring>

int main(int argc, char** argv) {
    assert(argc == 2);
    auto& engine = mkw::modEngine();
    assert(engine.loadManifest(argv[1]));
    unsigned index = 0;
    for (const auto& cup : engine.cups()) {
        for (unsigned i = 0; i < cup.trackCount; ++i, ++index) {
            const auto& expected = cup.tracks[i];
            const auto& actual = engine.courseChoice(index);
            assert(!std::strcmp(actual.name, expected.name));
            assert(!std::strcmp(actual.archive, expected.archive));
            assert(!std::strcmp(actual.models, expected.models));
            assert(!std::strcmp(actual.sky, expected.sky));
            assert(!std::strcmp(actual.cup, cup.name));
            assert(actual.id == expected.courseId);
        }
    }
    assert(index == engine.trackCount());
    unsigned variants = 0;
    for (unsigned i = 0; i < index; ++i) {
        for (unsigned v = 1; v < engine.trackVariantCount(i); ++v) {
            engine.setActiveTrackVariant(i, v);
            const unsigned resolved = engine.resolvedCourseIndex(i);
            assert(resolved != i);
            const auto& selected = mkw::course(i);
            assert(!std::strcmp(selected.archive, engine.activeTrackVariantArchive(i)));
            assert(!std::strcmp(selected.models, engine.courseChoice(resolved).models));
            assert(mkw::courseLaps(i) == engine.courseLaps(resolved));
            ++variants;
        }
        engine.setActiveTrackVariant(i, 0);
    }
    assert(variants == 10);
    std::printf("Validated %u variant archive/scenery/lap selections\n", variants);
    std::printf("Validated %u course names and asset paths\n", index);
}
