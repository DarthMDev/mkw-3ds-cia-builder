#include <mkw/snd_engine.hpp>
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>
int main(int argc,char**argv){
    assert(argc>2);
    std::ifstream payload(argv[1],std::ios::binary|std::ios::ate);
    const auto size=static_cast<std::uint64_t>(payload.tellg());assert(size>0);
    for(int i=2;i<argc;++i){
        std::ifstream stream(argv[i],std::ios::binary);
        std::vector<mkw::snd::u8> bytes((std::istreambuf_iterator<char>(stream)),{});
        mkw::snd::Archive archive;assert(archive.load(std::move(bytes)));
        for(unsigned f=0;f<archive.fileCount();++f){
            const auto*file=archive.file(f);assert(std::uint64_t(file->mainOffset)+file->mainSize<=size);
            assert(std::uint64_t(file->waveOffset)+file->waveSize<=size);
            for(unsigned w=0;w<file->waveCount;++w){const auto*wave=archive.wave(f,w);assert(wave);assert(std::uint64_t(wave->offset)+wave->size<=file->waveSize);}
        }
        for(unsigned s=0;s<archive.soundCount();++s){const auto reach=archive.reach(s);for(unsigned w=0;w<reach.count;++w)if(!archive.wave(reach.file,reach.waves[w])){std::fprintf(stderr,"%s sound=%u file=%u wave=%u count=%u\n",argv[i],s,reach.file,reach.waves[w],archive.file(reach.file)?archive.file(reach.file)->waveCount:0);return 1;}}
    }
    std::printf("Validated %d skin sound archives and reachable wave bounds\n",argc-2);
}
