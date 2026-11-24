// The C++ shim under host/backend_xrt.py: one XRT call for each of its functions, behind a C ABI.
//
// Parcel HOST, round 3. XRT 2.14 reaches a user-managed kernel's registers only from C++ (xrt::ip): its
// Python binding has no `ip` (the lead, cft2204, 2026-11-24). Python calls these functions through ctypes.
//
// BUILD, by whoever runs it, on the machine with XRT (the lead: cft2204 for hardware emulation, the box for
// the card), with XRT's settings sourced so that XILINX_XRT is set:
//
//     g++ -std=c++17 -O2 -Wall -shared -fPIC host/xrt_shim.cpp -I"$XILINX_XRT/include" -L"$XILINX_XRT/lib" -lxrt_coreutil -o <a folder outside the tree>/libundertone_xrt.so
//
// and hand its path to host.backend_xrt.Backend (shim_path=...) or set UNDERTONE_XRT_SHIM. The .so is not
// committed. IT HAS NEVER BEEN COMPILED AGAINST XRT by its author: the desktop it was written on has no XRT. Its
// author checked its C++ alone, with g++ -std=c++17 -Wall -Wextra -fsyntax-only against stub headers of its own
// that declare what it believes XRT has (which caught a most vexing parse); that says nothing of XRT. Its calls
// are the ones the lead's C++ trial under hw_emu made on XRT 2.14 (lead.md, 2026-11-24 10:17): xrt::device,
// load_xclbin, xrt::xclbin's kernel arguments and get_mems()[0].get_index(), experimental xrt::ip with
// read_register and write_register, xrt::bo with sync, read and write.
//
// Every function returns 0, or not 0 with a message in `err`: an XRT exception is caught here and handed to
// Python, which raises OSError. Nothing is retried and nothing is checked but what XRT throws.

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <memory>
#include <string>
#include <vector>

#include <xrt/xrt_bo.h>
#include <xrt/xrt_device.h>

// xrt::ip and xrt::xclbin: wherever this XRT keeps them. 2.14 has them under include/experimental/ (the lead's
// trial); a later XRT may move them. The first header found is taken.
#if __has_include(<xrt/xrt_ip.h>)
#  include <xrt/xrt_ip.h>
#elif __has_include(<xrt/experimental/xrt_ip.h>)
#  include <xrt/experimental/xrt_ip.h>
#elif __has_include(<experimental/xrt_ip.h>)
#  include <experimental/xrt_ip.h>
#else
#  error "no xrt_ip.h under XRT's include folder: this shim needs xrt::ip"
#endif
#if __has_include(<xrt/xrt_xclbin.h>)
#  include <xrt/xrt_xclbin.h>
#elif __has_include(<xrt/experimental/xrt_xclbin.h>)
#  include <xrt/experimental/xrt_xclbin.h>
#elif __has_include(<experimental/xrt_xclbin.h>)
#  include <experimental/xrt_xclbin.h>
#else
#  error "no xrt_xclbin.h under XRT's include folder: this shim needs xrt::xclbin to find the memory group"
#endif

namespace {

struct Shim {
    xrt::device device;
    xrt::uuid uuid;
    std::unique_ptr<xrt::ip> ip;
    int group = -1;
};

struct Buf {
    xrt::bo bo;
};

int say(char *err, std::size_t errlen, const std::string &what) {
    if (err != nullptr && errlen > 0) std::snprintf(err, errlen, "%s", what.c_str());
    return 1;
}

int caught(char *err, std::size_t errlen, const char *call) {
    try {
        throw;
    } catch (const std::exception &e) {
        return say(err, errlen, std::string(call) + ": " + e.what());
    } catch (...) {
        return say(err, errlen, std::string(call) + ": an exception that is not a std::exception");
    }
}

// The kernel's name: a compute unit's name is "kernel:{instance}" or the kernel's own.
std::string kernel_of(const std::string &cu) {
    auto colon = cu.find(':');
    return colon == std::string::npos ? cu : cu.substr(0, colon);
}

}  // namespace

extern "C" {

// Open the device, load the image, find the buffer's memory group from the image (the kernel's argument at
// `buffer_offset`, by offset, never by name) unless `group` is 0 or more, and open the compute unit's registers.
int ut_open(const char *xclbin, unsigned device, const char *cu, std::uint32_t buffer_offset, int group,
            void **out, int *group_used, char *err, std::size_t errlen) {
    try {
        auto shim = std::make_unique<Shim>();
        shim->device = xrt::device(device);
        shim->uuid = shim->device.load_xclbin(std::string(xclbin));
        if (group < 0) {
            xrt::xclbin image{std::string(xclbin)};
            const std::string name = kernel_of(cu);
            bool found_kernel = false;
            for (auto &kernel : image.get_kernels()) {
                if (kernel.get_name() != name) continue;
                found_kernel = true;
                for (auto &arg : kernel.get_args()) {
                    if (arg.get_offset() != buffer_offset) continue;
                    auto mems = arg.get_mems();
                    if (mems.empty())
                        return say(err, errlen, "ut_open: the argument at offset " + std::to_string(buffer_offset) +
                                                " has no memory in the image");
                    group = static_cast<int>(mems[0].get_index());
                }
            }
            if (!found_kernel) return say(err, errlen, "ut_open: the image has no kernel named " + name);
            if (group < 0)
                return say(err, errlen, "ut_open: kernel " + name + " has no argument at offset " +
                                        std::to_string(buffer_offset));
        }
        shim->group = group;
        shim->ip = std::make_unique<xrt::ip>(shim->device, shim->uuid, std::string(cu));
        *group_used = group;
        *out = shim.release();
        return 0;
    } catch (...) {
        return caught(err, errlen, "ut_open");
    }
}

void ut_close(void *h) {
    delete static_cast<Shim *>(h);
}

int ut_read(void *h, std::uint32_t offset, std::uint32_t *word, char *err, std::size_t errlen) {
    try {
        *word = static_cast<Shim *>(h)->ip->read_register(offset);
        return 0;
    } catch (...) {
        return caught(err, errlen, "ut_read");
    }
}

int ut_write(void *h, std::uint32_t offset, std::uint32_t word, char *err, std::size_t errlen) {
    try {
        static_cast<Shim *>(h)->ip->write_register(offset, word);
        return 0;
    } catch (...) {
        return caught(err, errlen, "ut_write");
    }
}

// One write after another, in order. A failure stops the loop there, and says how far it got.
int ut_write_many(void *h, const std::uint32_t *offsets, const std::uint32_t *words, std::size_t n, char *err,
                  std::size_t errlen) {
    std::size_t i = 0;
    try {
        auto &ip = *static_cast<Shim *>(h)->ip;
        for (; i < n; ++i) ip.write_register(offsets[i], words[i]);
        return 0;
    } catch (...) {
        caught(err, errlen, "ut_write_many");
        return say(err, errlen, std::string(err) + " (at write " + std::to_string(i) + " of " + std::to_string(n) + ")");
    }
}

int ut_alloc(void *h, std::uint64_t size, void **bo, std::uint64_t *address, char *err, std::size_t errlen) {
    try {
        auto *shim = static_cast<Shim *>(h);
        auto buf = std::make_unique<Buf>();
        buf->bo = xrt::bo(shim->device, static_cast<std::size_t>(size), xrt::bo::flags::normal,
                          static_cast<xrt::memory_group>(shim->group));
        *address = buf->bo.address();
        *bo = buf.release();
        return 0;
    } catch (...) {
        return caught(err, errlen, "ut_alloc");
    }
}

// Into the host's copy of the buffer only; ut_bo_sync_to sends it to the device.
int ut_bo_write(void *h, void *bo, std::uint64_t at, const char *src, std::uint64_t n, char *err, std::size_t errlen) {
    (void)h;
    try {
        static_cast<Buf *>(bo)->bo.write(src, static_cast<std::size_t>(n), static_cast<std::size_t>(at));
        return 0;
    } catch (...) {
        return caught(err, errlen, "ut_bo_write");
    }
}

int ut_bo_sync_to(void *h, void *bo, std::uint64_t at, std::uint64_t n, char *err, std::size_t errlen) {
    (void)h;
    try {
        static_cast<Buf *>(bo)->bo.sync(XCL_BO_SYNC_BO_TO_DEVICE, static_cast<std::size_t>(n), static_cast<std::size_t>(at));
        return 0;
    } catch (...) {
        return caught(err, errlen, "ut_bo_sync_to");
    }
}

int ut_bo_sync_from(void *h, void *bo, std::uint64_t at, std::uint64_t n, char *err, std::size_t errlen) {
    (void)h;
    try {
        static_cast<Buf *>(bo)->bo.sync(XCL_BO_SYNC_BO_FROM_DEVICE, static_cast<std::size_t>(n), static_cast<std::size_t>(at));
        return 0;
    } catch (...) {
        return caught(err, errlen, "ut_bo_sync_from");
    }
}

// From the host's copy of the buffer only; ut_bo_sync_from brings the device's bytes into it first.
int ut_bo_read(void *h, void *bo, std::uint64_t at, char *dst, std::uint64_t n, char *err, std::size_t errlen) {
    (void)h;
    try {
        static_cast<Buf *>(bo)->bo.read(dst, static_cast<std::size_t>(n), static_cast<std::size_t>(at));
        return 0;
    } catch (...) {
        return caught(err, errlen, "ut_bo_read");
    }
}

int ut_free(void *h, void *bo, char *err, std::size_t errlen) {
    (void)h;
    try {
        delete static_cast<Buf *>(bo);
        return 0;
    } catch (...) {
        return caught(err, errlen, "ut_free");
    }
}

}  // extern "C"
