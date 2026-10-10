#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <algorithm>
namespace mkw {
// Original ItemSlot.bin: count, then [rank count, item count, item-major bytes].
// Copy the selected 12-racer tables so no race-heap/archive pointer escapes reset.
class ItemOdds {
public:
    bool load(const void* bytes,std::size_t size,unsigned localTable,unsigned cpuTable){
        tables_={};ready_=false;
        if(!bytes||size<1)return false;
        const auto* data=static_cast<const uint8_t*>(bytes);std::size_t offset=1;unsigned found=0;
        for(unsigned table=0;table<data[0];++table){
            if(size-offset<2)return false;
            const unsigned ranks=data[offset++],items=data[offset++];
            if(!ranks||!items||std::size_t(ranks)*items>size-offset)return false;
            for(unsigned role=0;role<2;++role)if(table==(role?cpuTable:localTable)){
                if(ranks!=12||items!=19)return false;
                for(unsigned item=0;item<19;++item)for(unsigned rank=0;rank<12;++rank)
                    tables_[role][rank][item]=data[offset+item*ranks+rank];
                ++found;
            }
            offset+=std::size_t(ranks)*items;
        }
        ready_=found==2&&offset==size;return ready_;
    }
    bool ready() const{return ready_;}
    const std::array<uint8_t,19>& weights(bool cpu,unsigned rank)const{return tables_[cpu?1:0][std::clamp(rank,1u,12u)-1];}
private:
    std::array<std::array<std::array<uint8_t,19>,12>,2> tables_{};
    bool ready_=false;
};
}
