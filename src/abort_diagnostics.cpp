#include <cstdio>
#include <cstdint>
#include <3ds.h>
extern "C" [[noreturn]] void __real_abort();
extern "C" [[noreturn]] void __wrap_abort(){
    const auto caller=reinterpret_cast<std::uintptr_t>(__builtin_return_address(0));
    // Close immediately so the emulator keeps the breadcrumb after process exit.
    if(auto* file=std::fopen("sdmc:/3ds/mkw-3ds/boot.log","a")){
        std::fprintf(file,"FATAL abort caller=0x%08lx linear_free=%lu\n",static_cast<unsigned long>(caller),static_cast<unsigned long>(linearSpaceFree()));
        std::fclose(file);
    }
    __real_abort();
}

extern "C" [[noreturn]] void __real__ZSt17__throw_bad_allocv();
extern "C" [[noreturn]] void __wrap__ZSt17__throw_bad_allocv(){
    const auto caller=reinterpret_cast<std::uintptr_t>(__builtin_return_address(0));
    if(auto* file=std::fopen("sdmc:/3ds/mkw-3ds/boot.log","a")){
        std::fprintf(file,"FATAL C++ allocation failure caller=0x%08lx linear_free=%lu\n",static_cast<unsigned long>(caller),static_cast<unsigned long>(linearSpaceFree()));
        std::fclose(file);
    }
    __real__ZSt17__throw_bad_allocv();
}
