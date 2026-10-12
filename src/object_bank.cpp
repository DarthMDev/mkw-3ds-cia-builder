#include "mkw/object_bank.hpp"
#include <mkw/asset_pack.hpp>
#include <mkw/render_metrics.hpp>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
namespace mkw {
ClipSample sampleClip(unsigned frames,unsigned step,bool loop,float frame){
    if(frames<=1||!std::isfinite(frame))return {0,0,0};
    step=std::max(1u,step);
    const unsigned last=(frames-1+step-1)/step; // index of the final sample (frame frames-1)
    if(loop){frame=std::fmod(frame,float(frames));if(frame<0)frame+=float(frames);}
    else frame=std::clamp(frame,0.f,float(frames-1));
    const float lastFrame=float(frames-1);
    if(frame>=lastFrame){
        // The final interval of a loop blends the last sample back to frame 0.
        return loop?ClipSample{last,0,frame-lastFrame}:ClipSample{last,last,0};
    }
    const unsigned a=unsigned(frame)/step;
    const float fa=float(a*step),fb=std::min(float((a+1)*step),lastFrame);
    return {a,std::min(a+1,last),fb>fa?(frame-fa)/(fb-fa):0.f};
}
namespace {
uint32_t u32(const uint8_t* p){uint32_t v;std::memcpy(&v,p,4);return v;}
unsigned samples(unsigned frames,unsigned step){return frames<=1?1:(frames-1+step-1)/step+1;}
}
void ObjectBank::reset(){
    std::free(data_);data_=nullptr;vertices_=matrices_=shapes_=0;weighted_=false;
    source_=nullptr;ranges_=nullptr;bind_=nullptr;shared_={};sharedVertices_.reset();nodes_.clear();chr_.clear();pat_.clear();srt_.clear();clr_.clear();rigidParts_.clear();registerAlpha_.clear();
}
bool ObjectBank::load(const char* path){
    reset();
    size_t size=0;bool ok=false;
    if(const long packed=pack::size(path);packed>=0){
        size=size_t(packed);if(size<40||size>8*1024*1024)return false;
        data_=static_cast<uint8_t*>(std::malloc(size));if(!data_)return false;
        ok=pack::readInto(path,data_,size);
    }else{
        FILE* f=std::fopen(path,"rb");if(!f)return false;
        std::setvbuf(f,nullptr,_IONBF,0);
        std::fseek(f,0,SEEK_END);const long length=std::ftell(f);std::rewind(f);
        if(length<40||length>8*1024*1024){std::fclose(f);return false;}
        size=size_t(length);data_=static_cast<uint8_t*>(std::malloc(size));
        ok=data_&&std::fread(data_,1,size,f)==size;std::fclose(f);
    }
    if(!ok||std::memcmp(data_,"DOBJ",4)||u32(data_+4)!=1){reset();return false;}
    vertices_=u32(data_+8);matrices_=u32(data_+12);shapes_=u32(data_+16);
    const unsigned nodeCount=u32(data_+20),chrCount=u32(data_+24),patCount=u32(data_+28),srtCount=u32(data_+32),clrCount=u32(data_+36);
    if(!matrices_||matrices_>128||vertices_>65535||shapes_>256||nodeCount>256||chrCount>64||patCount>64||srtCount>64||clrCount>64){reset();return false;}
    size_t at=40;
    auto take=[&](size_t bytes)->const uint8_t*{if(bytes>size-std::min(at,size)||at>size)return nullptr;const uint8_t* p=data_+at;at+=bytes;return p;};
    source_=reinterpret_cast<const SourceVertex*>(take(size_t(vertices_)*sizeof(SourceVertex)));
    ranges_=reinterpret_cast<const Range*>(take(size_t(shapes_)*sizeof(Range)));
    bind_=reinterpret_cast<const float*>(take(size_t(matrices_)*48));
    if(!source_||!ranges_||!bind_){reset();return false;}
    for(unsigned i=0;i<vertices_;++i)if(source_[i].matrix>=matrices_){reset();return false;}
    for(unsigned i=0;i<shapes_;++i)if(vertices_&&(ranges_[i].first>vertices_||ranges_[i].count>vertices_-ranges_[i].first)){reset();return false;}
    nodes_.resize(nodeCount);
    for(auto& n:nodes_){
        const uint8_t* p=take(sizeof(Node));if(!p){reset();return false;}
        std::memcpy(&n,p,sizeof(Node));n.name[31]=0;
        if(n.parent>=int32_t(nodeCount)||n.slot>=int32_t(matrices_)){reset();return false;}
    }
    for(unsigned i=0;i<chrCount;++i){
        const uint8_t* p=take(48);if(!p){reset();return false;}
        Chr c{};std::memcpy(c.name,p,32);c.name[31]=0;c.frames=u32(p+32);c.loop=u32(p+36);c.step=u32(p+40);c.animatedCount=u32(p+44);
        if(!c.frames||c.frames>20000||!c.step||c.step>64||c.animatedCount>matrices_){reset();return false;}
        c.animated=reinterpret_cast<const uint32_t*>(take(size_t(c.animatedCount)*4));
        c.base=reinterpret_cast<const float*>(take(size_t(matrices_)*48));
        c.samples=reinterpret_cast<const float*>(take(size_t(samples(c.frames,c.step))*c.animatedCount*48));
        if(!c.animated||!c.base||!c.samples){reset();return false;}
        for(unsigned j=0;j<c.animatedCount;++j)if(c.animated[j]>=matrices_){reset();return false;}
        chr_.push_back(c);
    }
    for(unsigned i=0;i<patCount;++i){
        const uint8_t* p=take(40);if(!p){reset();return false;}
        Pat c{};std::memcpy(c.name,p,32);c.name[31]=0;c.frames=u32(p+32);c.loop=u32(p+36);
        if(!c.frames||c.frames>20000){reset();return false;}
        c.data=reinterpret_cast<const int32_t*>(take(size_t(c.frames)*shapes_*8));if(!c.data){reset();return false;}
        pat_.push_back(c);
    }
    for(unsigned i=0;i<srtCount;++i){
        const uint8_t* p=take(48);if(!p){reset();return false;}
        Srt c{};std::memcpy(c.name,p,32);c.name[31]=0;c.frames=u32(p+32);c.loop=u32(p+36);c.step=u32(p+40);c.count=u32(p+44);
        if(!c.frames||c.frames>20000||!c.step||c.step>64||c.count>shapes_){reset();return false;}
        c.shapes=reinterpret_cast<const uint32_t*>(take(size_t(c.count)*4));
        c.data=reinterpret_cast<const float*>(take(size_t(samples(c.frames,c.step))*c.count*48));
        if(!c.shapes||!c.data){reset();return false;}
        for(unsigned j=0;j<c.count;++j)if(c.shapes[j]>=shapes_){reset();return false;}
        srt_.push_back(c);
    }
    for(unsigned i=0;i<clrCount;++i){
        const uint8_t* p=take(44);if(!p){reset();return false;}
        Clr c{};std::memcpy(c.name,p,32);c.name[31]=0;c.frames=u32(p+32);c.loop=u32(p+36);c.count=u32(p+40);
        if(!c.frames||c.frames>20000||c.count>shapes_){reset();return false;}
        c.shapes=reinterpret_cast<const uint32_t*>(take(size_t(c.count)*4));
        c.flags=reinterpret_cast<const uint32_t*>(take(size_t(c.count)*4));
        c.data=reinterpret_cast<const uint32_t*>(take(size_t(c.frames)*c.count*12));
        if(!c.shapes||!c.flags||!c.data){reset();return false;}
        for(unsigned j=0;j<c.count;++j)if(c.shapes[j]>=shapes_){reset();return false;}
        clr_.push_back(c);
    }
    if(at<size){
        const auto* header=take(8);
        if(!header||std::memcmp(header,"MORF",4)||u32(header+4)>chr_.size()){reset();return false;}
        for(unsigned i=0;i<u32(header+4);++i){
            const auto* record=take(12);if(!record){reset();return false;}
            const unsigned clip=u32(record),count=u32(record+4),frames=u32(record+8);
            if(clip>=chr_.size()||frames!=chr_[clip].frames||count>vertices_){reset();return false;}
            const auto* indices=take(size_t(count)*4);
            const auto* deltas=take(size_t(count)*24);
            const auto* weights=take(size_t(frames)*4);
            if(!indices||!deltas||!weights){reset();return false;}
            for(unsigned j=0;j<count;++j)if(u32(indices+j*4)>=vertices_){reset();return false;}
        }
    }
    if(at!=size){reset();return false;}
    return true;
}
namespace {
template<class T> int findName(const std::vector<T>& list,const char* name){
    if(name)for(size_t i=0;i<list.size();++i)if(!std::strcmp(list[i].name,name))return int(i);
    return -1;
}
}
int ObjectBank::clip(const char* name) const {return findName(chr_,name);}
int ObjectBank::pattern(const char* name) const {return findName(pat_,name);}
int ObjectBank::scroll(const char* name) const {return findName(srt_,name);}
int ObjectBank::color(const char* name) const {return findName(clr_,name);}
int ObjectBank::node(const char* name) const {return findName(nodes_,name);}
void ObjectBank::pose(int clip,float frame,float* out) const {
    if(clip<0||unsigned(clip)>=chr_.size()){std::memcpy(out,bind_,size_t(matrices_)*48);return;}
    const auto& c=chr_[clip];
    std::memcpy(out,c.base,size_t(matrices_)*48);
    const auto s=sampleClip(c.frames,c.step,c.loop,frame);
    const float* a=c.samples+size_t(s.a)*c.animatedCount*12;
    const float* b=c.samples+size_t(s.b)*c.animatedCount*12;
    for(unsigned i=0;i<c.animatedCount;++i){
        float* m=out+c.animated[i]*12;const float* x=a+i*12;const float* y=b+i*12;
        for(unsigned k=0;k<12;++k)m[k]=x[k]+(y[k]-x[k])*s.t;
    }
}
bool ObjectBank::material(int pat,float patFrame,int srt,float srtFrame,int clr,float clrFrame,SubmeshOverride* out,unsigned count) const {
    // Submesh i is shape i: the cooker preserves vertices and starts one
    // submesh per shape.
    if(count!=shapes_)return false;
    bool any=false;
    for(unsigned i=0;i<count;++i){auto& o=out[i];o={};o.uv[0]=o.uv[4]=o.uv[6]=o.uv[10]=1;o.texture[0]=o.texture[1]=-1;o.tint[0]=o.tint[1]=o.tint[2]=o.tint[3]=1;}
    if(pat>=0&&unsigned(pat)<pat_.size()){
        const auto& c=pat_[pat];
        unsigned f=c.loop?unsigned(std::fmod(std::max(patFrame,0.f),float(c.frames))):unsigned(std::clamp(patFrame,0.f,float(c.frames-1)));
        if(f>=c.frames)f=c.frames-1;
        const int32_t* row=c.data+size_t(f)*shapes_*2;
        for(unsigned i=0;i<count;++i)if(row[i*2]>=0||row[i*2+1]>=0){out[i].texture[0]=row[i*2];out[i].texture[1]=row[i*2+1];out[i].flags|=SubmeshOverride::Texture;any=true;}
    }
    if(srt>=0&&unsigned(srt)<srt_.size()){
        const auto& c=srt_[srt];const auto s=sampleClip(c.frames,c.step,c.loop,srtFrame);
        const float* a=c.data+size_t(s.a)*c.count*12;const float* b=c.data+size_t(s.b)*c.count*12;
        for(unsigned j=0;j<c.count;++j){auto& o=out[c.shapes[j]];for(unsigned k=0;k<12;++k)o.uv[k]=a[j*12+k]+(b[j*12+k]-a[j*12+k])*s.t;o.flags|=SubmeshOverride::Uv;any=true;}
    }
    if(clr>=0&&unsigned(clr)<clr_.size()){
        const auto& c=clr_[clr];
        unsigned f=c.loop?unsigned(std::fmod(std::max(clrFrame,0.f),float(c.frames))):unsigned(std::clamp(clrFrame,0.f,float(c.frames-1)));
        if(f>=c.frames)f=c.frames-1;
        const uint32_t* row=c.data+size_t(f)*c.count*3;
        for(unsigned j=0;j<c.count;++j){
            auto& o=out[c.shapes[j]];const uint32_t flags=c.flags[j];
            if(flags&1){o.constant=row[j*3];o.flags|=SubmeshOverride::Constant;}
            if(flags&(2|4)){
                const uint32_t t=row[j*3+1];
                // Tint ratios were stored halved (255 is 2.0).
                for(unsigned k=0;k<4;++k)o.tint[k]=float((t>>(8*k))&255)*(2.f/255.f);
                if(!(flags&2))o.tint[0]=o.tint[1]=o.tint[2]=1;
                if(!(flags&4)&&!(flags&2))o.tint[3]=1;
                o.flags|=SubmeshOverride::Tint;
            }
            if((flags&4)&&c.shapes[j]<registerAlpha_.size()&&registerAlpha_[c.shapes[j]])o.flags|=SubmeshOverride::Alpha;
            if(flags&8){o.add=row[j*3+2];o.flags|=SubmeshOverride::Add;}
            any=true;
        }
    }
    return any;
}
void ObjectBank::markRegisterAlpha(const Model& model){
    registerAlpha_.assign(shapes_,0);
    if(model.submeshes.size()!=shapes_||!model.vertices||!model.indices)return;
    for(unsigned i=0;i<shapes_;++i){
        const auto& s=model.submeshes[i];
        // Source GX state (bit 31) with alpha mode 4: alpha is the vertex alpha alone.
        if(!(s.flags&(1u<<31))||((s.flags>>20)&7)!=4||!s.count||s.first+s.count>model.indexCount)continue;
        bool zero=true;
        for(unsigned k=s.first;k<s.first+s.count&&zero;++k){const unsigned v=model.indices[k];zero=v<model.vertexCount&&model.vertices[v].color[3]==0;}
        registerAlpha_[i]=zero;
    }
}
bool ObjectBank::makeRigid(Model& model){
    if(!ready()||rigid()||!vertices_||vertices_!=model.vertexCount)return false;
    for(const auto& s:model.submeshes)for(unsigned i=s.first;i+2<s.first+s.count;i+=3){
        const auto m=source_[model.indices[i]].matrix;
        if(source_[model.indices[i+1]].matrix!=m||source_[model.indices[i+2]].matrix!=m){weighted_=true;return false;}
    }
    std::vector<std::vector<RigidPart>> parts(model.submeshes.size());
    std::vector<std::array<uint16_t,3>> triangles;
    for(size_t n=0;n<model.submeshes.size();++n){
        const auto& s=model.submeshes[n];
        triangles.clear();
        for(unsigned i=s.first;i+2<s.first+s.count;i+=3)triangles.push_back({model.indices[i],model.indices[i+1],model.indices[i+2]});
        std::stable_sort(triangles.begin(),triangles.end(),[&](const auto& a,const auto& b){return source_[a[0]].matrix<source_[b[0]].matrix;});
        for(size_t k=0;k<triangles.size();++k){
            const unsigned at=s.first+unsigned(k)*3;std::memcpy(model.indices+at,triangles[k].data(),6);
            const unsigned matrix=source_[triangles[k][0]].matrix;
            if(parts[n].empty()||parts[n].back().matrix!=matrix)parts[n].push_back({at,0,matrix});
            parts[n].back().count+=3;
        }
    }
    for(unsigned i=0;i<vertices_;++i){
        const auto& v=source_[i];
        model.vertices[i].position={v.p[0],v.p[1],v.p[2]};model.vertices[i].normal={v.n[0],v.n[1],v.n[2]};
    }
    // Each part's bone-local bounds, for culling parts where they are drawn.
    for(auto& list:parts)for(auto& part:list){
        part.bounds.minimum=part.bounds.maximum=model.vertices[model.indices[part.first]].position;
        for(unsigned k=part.first;k<part.first+part.count;++k)part.bounds.include(model.vertices[model.indices[k]].position);
    }
    flushGpuData(model.vertices,model.vertexCount*sizeof(Vertex));
    flushGpuData(model.indices,model.indexCount*sizeof(uint16_t));
    rigidParts_=std::move(parts);
    return true;
}
bool ObjectBank::gpuSkin(Model& model) const {
    if(!vertices_||vertices_!=model.vertexCount||matrices_>Renderer::MaxSkinBones)return false;
    for(unsigned i=0;i<vertices_;++i){
        const auto& v=source_[i];
        model.vertices[i].position={v.p[0],v.p[1],v.p[2]};model.vertices[i].normal={float(v.matrix*3),0,0};
    }
    flushGpuData(model.vertices,vertices_*sizeof(Vertex));
    return true;
}
bool ObjectBank::shareSkinnedVertices(){
    if(!sharedVertices_)sharedVertices_=buildSkinRepresentatives(source_,vertices_);
    return bool(sharedVertices_);
}
void ObjectBank::skin(const float* palette,Model& model,bool normals) const {
    if(!vertices_||model.vertexCount!=vertices_)return;
    if(!normals&&shared_.ready()){
        auto& unique=sharedPositionScratch();
        for(unsigned u=0;u<shared_.first.size();++u){
            const auto& v=source_[shared_.first[u]];const float* m=palette+v.matrix*12;
            unique[u]={m[0]*v.p[0]+m[1]*v.p[1]+m[2]*v.p[2]+m[3],m[4]*v.p[0]+m[5]*v.p[1]+m[6]*v.p[2]+m[7],m[8]*v.p[0]+m[9]*v.p[1]+m[10]*v.p[2]+m[11]};
        }
        for(unsigned i=0;i<vertices_;++i)model.vertices[i].position=unique[shared_.of[i]];
        flushGpuData(model.vertices,vertices_*sizeof(Vertex));
        return;
    }
    const uint16_t* representative=normals?sharedVertices_.get():nullptr;
    for(unsigned i=0;i<vertices_;++i){
        if(representative&&representative[i]!=i){
            // The first matching source index is always earlier in this loop.
            // Copy only the transformed fields: UV/color seams stay intact.
            const auto& first=model.vertices[representative[i]];
            model.vertices[i].position=first.position;model.vertices[i].normal=first.normal;
            continue;
        }
        const auto& v=source_[i];const float* m=palette+v.matrix*12;
        model.vertices[i].position={m[0]*v.p[0]+m[1]*v.p[1]+m[2]*v.p[2]+m[3],m[4]*v.p[0]+m[5]*v.p[1]+m[6]*v.p[2]+m[7],m[8]*v.p[0]+m[9]*v.p[1]+m[10]*v.p[2]+m[11]};
        if(normals)model.vertices[i].normal=normalized(Vec3{m[0]*v.n[0]+m[1]*v.n[1]+m[2]*v.n[2],m[4]*v.n[0]+m[5]*v.n[1]+m[6]*v.n[2],m[8]*v.n[0]+m[9]*v.n[1]+m[10]*v.n[2]});
    }
    flushGpuData(model.vertices,vertices_*sizeof(Vertex));
}
bool ObjectBank::slotBounds(std::vector<Bounds>& out,std::vector<bool>& used) const {
    if(!vertices_)return false;
    out.assign(matrices_,{});used.assign(matrices_,false);
    for(unsigned i=0;i<vertices_;++i){
        const auto& v=source_[i];const Vec3 p{v.p[0],v.p[1],v.p[2]};
        if(!used[v.matrix]){out[v.matrix]={p,p};used[v.matrix]=true;}else out[v.matrix].include(p);
    }
    return true;
}
bool ObjectBank::animatedBounds(Bounds& out) const {
    std::vector<Bounds> slots;std::vector<bool> used;
    if(!slotBounds(slots,used))return false;
    bool first=true;
    auto include=[&](const float* palette){
        for(unsigned i=0;i<matrices_;++i)if(used[i]){
            const auto b=transformBounds(slots[i],palette+i*12);
            if(first){out=b;first=false;}else{out.include(b.minimum);out.include(b.maximum);}
        }
    };
    include(bind_);
    std::vector<float> palette(size_t(matrices_)*12);
    for(const auto& c:chr_){
        const unsigned n=samples(c.frames,c.step);
        std::memcpy(palette.data(),c.base,palette.size()*4);
        for(unsigned s=0;s<n;++s){
            for(unsigned i=0;i<c.animatedCount;++i)std::memcpy(&palette[c.animated[i]*12],c.samples+(size_t(s)*c.animatedCount+i)*12,48);
            include(palette.data());
        }
    }
    return !first;
}
}
