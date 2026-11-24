# P03: the card's platform, measured, and hardware emulation tried

Written by the lead on 2026-11-24, for round 3's wave 0 ([the plan](../plans/R3-first-light.md), "Wave 0, the lead's"). It turns D0's survey rows about the shell into measurements where the tool gives them, says where it does not, and records one trial of hardware emulation in `cft2204`. **Nothing of Undertone was built, and the card was not touched**: the platform was read with `platforminfo` on `amd-arc-box`, and the trial ran a throwaway kernel that is not part of the design.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. `<repos>` is the folder that holds this repository and its siblings; `<platforms>` is the folder that holds the U50's development platform on each machine. The box's address is in the sibling project's notes and not here. The commands' whole output is in the round's folder, which is not committed.

## 1. What `platforminfo` says of the shell

Read on 2026-11-24 at 09:44 on `amd-arc-box`, with Vitis 2022.2 from its own settings script, of `<platforms>/xilinx_u50_gen3x16_xdma_5_202210_1/xilinx_u50_gen3x16_xdma_5_202210_1.xpfm`.

- **The part and the shell** (row P1): `xcu50-fsvh2104-2-e`, the board `xilinx.com:au50:1.1`, the shell `gen3x16_xdma_5`, version 202210.1. Two SLRs a kernel may use, SLR0 and SLR1 (P3).
- **The resources a kernel may use** (P4): 705,520 LUTs, 1,411,040 flip-flops, 1,116 block RAMs and 4,920 DSP slices in all; SLR0 has 351,840 LUTs and 2,352 DSP slices, SLR1 353,680 and 2,568.
- **The clocks** (P5): three, 300 MHz (index 0, the default), 500 MHz (index 1) and 100 MHz (index 2).
- **The memory** (P6): HBM, 32 segments, every one in SLR0, each taking up to 32 masters, and one memory named `mem0`, of type `hbm` and size "8GB"; the tool gives no segment's size. PLRAM, four segments, two in each SLR. A host memory segment, in SLR1, for which a kernel's port must be named explicitly.

## 2. What it changes in D0 and the plan

- **D0's H6**, "8 GB in 32 pseudo-channels of 256 MB", SURVEY: the 32 and the "8GB" are MEASURED (P6); 256 MB a channel is not given by the tool, and is COMPUTED from them only if "8GB" is 8 x 2^30 bytes and the segments are equal (P7).
- **D0's H7**, SURVEY: MEASURED (P4), and its first set of figures was right: 4,920 DSP slices, 2,352 in SLR0 and 2,568 in SLR1. The other sources' 5,936 to 5,948 are the part's, not what the shell leaves a kernel.
- **D0's H8**: still COMPUTED; whether "8GB" is 2^33 bytes the tool does not say.
- **D0's H12**, all 32 pseudo-channels on SLR0, SURVEY: MEASURED (P6).
- **D0's H3**, Vitis 2022.2 on the box: MEASURED (P2).
- **The plan's L14** says "The part has 5,952"; what the shell leaves a kernel is 4,920 (P4). **L17**, SLR0 offers 2,352, SURVEY: MEASURED. The first build's 724 slices by arithmetic (L18) are under a third of SLR0's.

## 3. Hardware emulation, tried in `cft2204`

The plan asked whether D0's row H1 and the plan's L23 hold for this project before anything depends on them: that hardware emulation runs in `cft2204`, as the sibling project's does, and not on the box. Parcel KRNL's design then chose Vitis's user-managed control protocol and named four things nothing here had tried: that `package_xo` takes it from the kernel's XML, that hardware emulation runs such a kernel, that a host finds the buffer's memory bank, and that the Python binding reaches its registers. The trial asks all four of a kernel of the lead's own, written for nothing else: an AXI4-Lite slave of six words and an AXI4 master that writes one burst of four 32-bit words, declared `hwControlProtocol="user_managed"`, with one buffer argument on its master. Its files are in the round's folder.

- **`cft2204` can run it** (P8): Ubuntu 22.04.5, glibc 2.35, and its libm has no `.relr.dyn` section, which is what stops Vivado 2022.2's linker on the box (the sibling's finding); Vitis 2022.2, XRT 2.14.354 of the 2022.2 branch, the U50's platform with its `hw_emu` files, g++ 11.4.0.
- **Packaged** (P9): Vivado 2022.2 packaged the kernel, inferring both its AXI interfaces, and `package_xo` took the user-managed XML; exit 0.
- **Linked** (P10): `v++ -l -t hw_emu` for the U50's platform at a kernel clock of 100 MHz, the master on HBM[0]: exit 0, 5 minutes 48 seconds by `v++`'s own count. `emconfigutil`: exit 0.
- **The Python binding cannot reach the kernel's registers** (P11): `pyxrt` of XRT 2.14 has no `ip` class, and its `kernel` offers no register read or write. It opened the emulated device and loaded the image. The C++ API has both, `xrt::ip` in `include/experimental/xrt_ip.h` and `xrt::kernel`'s in `include/xrt/xrt_kernel.h`.
- **A C++ host ran it under emulation** (P12): through `xrt::ip` it read the kernel's magic word and wrote its four registers; it found the buffer's bank from the image, HBM[0], through the argument's memory list; the burst landed at the buffer's base plus 64, as written, and nothing beside it changed; 31 seconds from start to end.
- **Two things a host here must know.** Under emulation the first buffer in HBM[0] sat at device address 0x0, so a kernel that ignored its buffer's base would pass there (P12). And XRT reports the argument named `buffer` in the XML as `buffer_r` (P12), so a host matches an argument by its offset.
- **Two runs before it did not pass** (P13). One stopped at `[HW-EMU 27] $XILINX_VITIS variable is not SET`: emulation needs Vitis's environment as well as XRT's, as the sibling's runner says. The other printed none of the host's own lines, a protobuf error on `xclCopyBufferHost2Device_response` and "SIMULATION EXITED", exited 0, and left the simulator's log saying "Failed to connect to device process". The sibling's emulation script records the same: a run "lost in the emulator handoff", about one case in ten, which passed on rerun. The passing run set `EMCONFIG_PATH` and made the host's output unbuffered; whether either mattered is not known.

## 4. Limits

1. **The tool's word, not the card's.** `platforminfo` reads the platform files on the box. That the card in the box runs this shell is the sibling project's record and not measured here; the card was not touched, and `xbutil` was not run.
2. **What a kernel gets is not what a kernel can place.** P4 is what the shell leaves; what one build places, routes and closes at a clock is that build's report.
3. **One throwaway kernel, one burst, in emulation.** The trial shows the flow and the API; it says nothing of Undertone's kernel, of timing, or of the card. Emulation's memory and interconnect are approximate by its own words.
4. **The box's XRT was not read.** The trial is of XRT 2.14 in `cft2204`; the sibling's notes say the box has 2.19. What works there, and whether its Python binding has `ip`, is not known here.
5. **A run under emulation can be lost and exit 0** (P13). A host run there prints a PASS line, and its absence is a lost run, never a result.
6. **A slip in the trial.** Its first script cleared `/tmp/root` in `cft2204` whole before its run, as the sibling's runner does, and so removed whatever was there, which this project did not make. It is recorded in the round's ledger.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| P1 | The platform file read is the U50's development platform `xilinx_u50_gen3x16_xdma_5_202210_1`, shell `gen3x16_xdma_5` version 202210.1, part `xcu50-fsvh2104-2-e` | MEASURED | `platforminfo -p <platforms>/xilinx_u50_gen3x16_xdma_5_202210_1/xilinx_u50_gen3x16_xdma_5_202210_1.xpfm` on the box, 2026-11-24 09:44, its sections "Basic Platform Information" and "Hardware Platform (Shell) Information" | that command |
| P2 | `v++` on the box is v2022.2, SW Build 3671529 of 2022-10-13 | MEASURED | `v++ --version` on the box after its Vitis 2022.2 settings script, 2026-11-24 09:44 | that command |
| P3 | Two SLRs are valid for a kernel, SLR0 and SLR1 | MEASURED | P1's command, "Valid SLRs" | that command |
| P4 | A kernel may use 705,520 LUTs, 1,411,040 flip-flops, 1,116 block RAMs and 4,920 DSP slices; SLR0 351,840 LUTs and 2,352 DSP slices, SLR1 353,680 and 2,568 | MEASURED | P1's command, "Resource Availability" | that command; a build's utilisation report |
| P5 | The shell offers clocks of 300 MHz (index 0, the default), 500 MHz (index 1) and 100 MHz (index 2) | MEASURED | P1's command, "Clock Information" | that command |
| P6 | HBM is 32 segments, each in SLR0 and each taking up to 32 masters, and one memory `mem0` of type `hbm` and size "8GB"; no segment's size is given | MEASURED | P1's command, "Memory Information", and its `--json` form, the platform's "memories" | that command |
| P7 | A segment of HBM is 256 MB if "8GB" is 8 x 2^30 bytes and the segments are equal | COMPUTED | 8 x 2^30 / 32 = 2^28; neither condition is given by the tool | a build's memory map |
| P8 | `cft2204` is Ubuntu 22.04.5 with glibc 2.35, its libm has no `.relr.dyn` section, and it holds Vitis 2022.2, XRT 2.14.354 of branch 2022.2, the U50's platform with its `hw_emu` folder, and g++ 11.4.0 | MEASURED | a read-only probe in `cft2204`, 2026-11-24 09:48: `/etc/os-release`, `ldd --version`, `readelf -S` of libm counted for "relr" (0), `v++ --version`, `/opt/xilinx/xrt/version.json`, a listing of the platform's folder, `g++ --version` (10:08) | those commands |
| P9 | Vivado 2022.2 packaged the trial kernel, inferring `m_axi_gmem` and `s_axi_control` as aximm, and `package_xo` took its user-managed XML, exit 0 | MEASURED | the trial's packaging script in `cft2204`, 2026-11-24 09:56:30 to 09:56:57: its BUSIF lines and its exit | a rerun |
| P10 | `v++ -l -t hw_emu` for the U50's platform, `--kernel_frequency 100`, the master on HBM[0], linked the trial kernel, exit 0, in 5 minutes 48 seconds by its own count; `emconfigutil` exited 0 | MEASURED | the trial's link in `cft2204`, 2026-11-24 09:56:57 to 10:02:48: "INFO: [v++ 60-791] Total elapsed time: 0h 5m 48s" | a rerun |
| P11 | XRT 2.14's `pyxrt` has no `ip` class and its `kernel` has no register read or write; it opened the emulated device and loaded the image; the C++ headers declare `xrt::ip::read_register` and `write_register` and `xrt::kernel`'s | MEASURED | in `cft2204`, 2026-11-24 10:08 to 10:09: `dir(pyxrt)` and `dir(pyxrt.kernel)`; the first emulated run's "loaded emu.xclbin" before its script's own error; `grep` of `/opt/xilinx/xrt/include` | those commands |
| P12 | A C++ host under emulation read the kernel's magic 0x454D554B through `xrt::ip`, wrote its four registers, found the buffer's bank from the image as HBM[0] index 0 on the argument XRT reports as `buffer_r`, allocated it at device address 0x0, and read back the four words at base + 64 as written with the bytes beside them unchanged; 10:16:07 to 10:16:38, exit 0, "PASS" | MEASURED | the trial's fourth run in `cft2204`, 2026-11-24, with Vitis's and XRT's settings, `EMCONFIG_PATH` set, `XCL_EMULATION_MODE=hw_emu` | a rerun |
| P13 | Of the three emulated runs before it, one stopped at "$XILINX_VITIS variable is not SET", one printed none of the host's lines and a protobuf error and "SIMULATION EXITED" and exited 0, with the simulator's log ending "Failed to connect to device process" | MEASURED | the trial's second and third runs in `cft2204`, 2026-11-24 10:09:50 and 10:10:09 to 10:15:20 | a rerun |
| P14 | The sibling project's emulation script records runs "lost in the emulator handoff", python exiting 0 with no output, about one case in ten, each passing on a rerun | READ | `<repos>/cft-fp256/hw/emu_smoke.sh`, its comment in `run_one` | that file |
