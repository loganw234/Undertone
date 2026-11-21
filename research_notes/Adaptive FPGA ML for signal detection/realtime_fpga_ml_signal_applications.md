# Real-time FPGA ML inference on signals and sensor streams: deployed and published systems (state as of November 2026)

Conventions used in these notes:

- Status tags: **[PRODUCTION]** = running in an operating experiment/facility; **[HARDWARE DEMO]** = measured on a real board or in a test stand; **[SYNTH/SIM]** = synthesis, place-and-route or RTL simulation only; **[PROPOSAL]** = study or position paper.
- "(search snippet)" means the figure came from a search-result summary of the linked source and the full text was not opened; treat as unverified.
- All latencies are as reported by the authors; measurement points differ (inference core only vs. end-to-end), so do not compare across rows without checking.

## 1. High-energy physics triggers and accelerator control: what runs, how fast, how big, how updated

### Takeaway
HEP is the one domain where FPGA ML is in routine production: CMS runs three hls4ml-built networks in the Run 3 Level-1 trigger (EMTF displaced-muon NN since June 2023, AXOL1TL and CICADA anomaly detectors since 2024) with 50-100 ns inference on Virtex-7, and ATLAS has an L1Topo anomaly-detection network (GELATO) fitting 25 ns. Every one of these models is static in the fabric; "updating" means offline retraining on newer zero-bias data, re-synthesis, and a firmware/menu release (AXOL1TL is at v5 after 2023-, 2024/25- and later-trained versions), and no published cadence or on-detector adaptation exists.

### Cited Findings

**CMS Level-1 (Run 3) - production**

- **AXOL1TL [PRODUCTION]**: variational autoencoder; only the encoder runs online; latent dimension 8; anomaly score = sum of squared latent means. Inputs: 10 jets, 4 e/gamma, 4 muons, MET (raw integer pT, eta, phi). Five thresholds (very tight ... very loose). Built with QKeras quantization-aware training + hls4ml for Xilinx Virtex-7. Trained on 2023 ZeroBias data at 13.6 TeV (pileup 62 with lumi-levelling). "Stable performance" reported for June 2024 data-taking; ~46% efficiency gain over the rest of L1 for H->4b exotic decays at 1 kHz (as extracted). System context: L1 output ~100 kHz inside a 4 us fixed latency; Global Trigger budget 50 ns at 40 MHz. - [CMS CR-2024/328, arXiv:2411.19506](https://arxiv.org/html/2411.19506v1)
- AXOL1TL firmware: 2 clock ticks at 40 MHz (50 ns), about 2.1% of LUTs and essentially no FF/DSP/BRAM in Vivado results (search snippet of conference slides; not confirmed in a paper). - [AXOL1TL EuCAIFCon slides](https://sioni.web.cern.ch/assets/eucaifcon/axol1tl_eucaifcon.pdf); [TWEPP 2023 talk](https://indico.cern.ch/event/1255624/contributions/5444028/attachments/2662416/4736599/TWEPP_Talk_Final_10_2_23.pdf); test-crate paper [arXiv:2312.10009](https://arxiv.org/pdf/2312.10009)
- AXOL1TL has been integrated in the Global Trigger since 2024, operates "within a fixed latency of 50 ns", and was updated in 2025 with an increased rate budget and a new self-supervised feature-extraction technique. - [FastML 2025 contribution (Giorgetti)](https://indico.cern.ch/event/1496673/contributions/6637931)
- AXOL1TL toolflow/version history: the 2024 deployment was trained with QKeras, converted with the hls4ml Vitis backend and synthesized with Vitis HLS, with a custom fully-inlined HLS wrapper to connect to the trigger's VHDL framework. A second variant trained a contrastive low-dimensional embedding first and a VAE on that embedding. A later, deeper model (v5) was trained with HGQ and deployed with da4ml + Vitis HLS. The algorithm has taken data in 2024, 2025 and 2026; ROC curves are shown for v4 and v5. - [Fast Machine Learning Foundation application page](https://fastmachinelearning.org/applications/anomaly-detection-for-new-physics-at-cms-level-1-trigger/); "AXOL1TL V4" label also appears in [AD4HEP 2025 slides](https://indico.nevis.columbia.edu/event/9/contributions/77/attachments/52/73/ad4hep_quinnan.pdf)
- AXOL1TL and CICADA together selected more than four billion collision events during 2024 data-taking. - [CMS ICHEP 2026 proceedings, arXiv:2609.31739](https://arxiv.org/abs/2609.31739)
- **CICADA [PRODUCTION]**: Calorimeter Image Convolutional Anomaly Detection Algorithm. Input: 18x14 calorimeter-region ET image (252 regions). A large convolutional-autoencoder teacher (~300k parameters) is distilled into a small student CNN that regresses the teacher's MSE anomaly score; the design constraint is roughly 1-10k parameters and an L1-compatible latency. Pipeline: QKeras QAT -> hls4ml -> Xilinx HLS, targeting the Virtex-7 calorimeter trigger processors; propagated to the uGT test crate over a 10 Gb/s link for parasitic running. Described in 2025 as one of the two AD algorithms online in the CMS trigger and "deployed at CMS Run 3 at 40 MHz". - [CICADA FastML 2024 slides](https://indico.cern.ch/event/1387540/contributions/6153609/attachments/2949396/5184001/cicada-fast-ml.pdf); [CICADA AD4HEP 2025 slides](https://indico.nevis.columbia.edu/event/9/contributions/79/attachments/53/77/CICADA-AD4HEP_KKennedy_06.16.2025.pdf); [APS April 2025 abstract](https://archive.aps.org/smt/2025/apr-c10/4); [arXiv:2411.19506](https://arxiv.org/html/2411.19506v1)
- CICADA resource/latency reference (third-party re-implementation, not the official firmware report): the QKeras student takes 16 clock cycles (~100 ns at 6.25 ns/cycle) with 159,447 LUTs, 50,368 FFs, 697 DSPs; a differentiable logic-gate-network replacement synthesizes on Virtex-7 at 3 cycles (~18.75 ns), 19,977 LUTs, 856 FFs, 0 DSPs and performs better at low trigger rates. Trained on public 2017 CMS Open Data (zero-bias inliers, ttbar outliers). **[SYNTH/SIM]** - [arXiv:2511.01908](https://arxiv.org/html/2511.01908v1)
- **CMS EMTF displaced-muon NN [PRODUCTION]**: two stitched dense networks (pT and d0), three dense layers each, 29 input features per track; hls4ml to Xilinx Virtex-7; latency 83 ns (runs in parallel with a ~100 ns BDT stage); LUT use went 74% -> 76% and DSP 2% -> 14% of the device; deployed 26 June 2023, used in triggers for 2024 data-taking. - [arXiv:2509.21062](https://arxiv.org/html/2509.21062v3)
- The hls4ml 2025 overview states three hls4ml-built algorithms have been deployed in the LHC trigger (muon pT/displacement MLP, AXOL1TL VAE, CICADA convolutional AE). - [hls4ml overview, arXiv:2512.01463](https://arxiv.org/html/2512.01463)

**ATLAS**

- **GELATO [PRODUCTION, commissioning-style rollout]**: ATLAS anomaly-detection trigger "now running" (2025) with a VAE-GAN-based L1 network on the L1Topo FPGAs plus a CPU autoencoder at HLT. L1 input: 44 features = (pT, eta, phi) of 15 objects (6 jets, 4 taus, 4 muons, MET), quantized to fit 25 ns inference. Two working points: T (physics, 500 Hz) and L (control, 1 kHz). The L1 rate was first only monitored, then enabled with ~1 Hz prescaled rate. Reported signal-efficiency gains 5-70% at L1. Sources disagree on details (44 vs 47 input features across talks). - [GELATO FastML 2025 slides](https://indico.cern.ch/event/1496673/contributions/6640029/attachments/3128131/5548711/GELATO_FastML_9_3_2025_Kenny.pdf); [ATLAS trigger slides Aug 2025](https://indico.cern.ch/event/1493037/contributions/6557276/attachments/3123666/5539629/sugizaki20250827.pdf); [APS April 2026 abstract](https://meetings-archive.aps.org/smt/2026/apr-h89/8/)
- **NomAD [HARDWARE DEMO / firmware tests]**: unsupervised VAE + BDT regression on low-level L1 muon features for anomalous dimuon events in L1Topo; sub-25 ns inference in firmware tests. Conference abstract only. - [APS April 2026 abstract](https://meetings-archive.aps.org/smt/2026/apr-h89/5/)
- ATLAS Global Event Processor (Run 4 upgrade): b-tagging DNN, VBF BDTs, MET-regression BDT and quark/gluon tagger evaluated; described as the first use of hls4ml and fwX in the ATLAS trigger; upgrade demonstration, not Run 3. **[SYNTH/SIM]** - [arXiv:2406.12875](https://arxiv.org/html/2406.12875v1)

**CMS Phase-2 (HL-LHC) and generic trigger-class models - not yet in data-taking**

- Multiclass DeepSets jet tagger (8 classes: light, gluon, b, c, tau+, tau-, electron, muon) with QAT: full jet reconstruction + tagger implemented on a Serenity ATCA blade with an AMD VU13P; total 1.011 us of which 234 ns is tagging (148 ns NN + 86 ns input preparation at 360 MHz), slightly above the 1 us correlator-layer-2 target. A July 2026 abstract quotes ~200 ns and O(1000) parameters. Phase-2 L1T plans >200 VU13P devices. 2025 slides state there is no tagging in current L1 data-taking. **[HARDWARE DEMO on prototype]** - [arXiv:2509.24371](https://arxiv.org/html/2509.24371v1); [FastML 2025 contribution](https://indico.cern.ch/event/1496673/contributions/6637937/); [2026 abstract](https://indico.cern.ch/event/1574970/contributions/7103176/)
- Autoencoders for 40 MHz unsupervised new-physics detection with hls4ml: anomaly detection "in as little as 80 ns" on a Virtex VU9P. **[SYNTH/SIM]** - [arXiv:2108.03986](https://ar5iv.labs.arxiv.org/html/2108.03986)
- Transformers with hls4ml on VU13P (Vivado HLS 2019.2): engine anomaly (3 blocks, 3,244 params) 1.9-3.8 us; b-tagging (3 blocks, 9,135 params) 2.1-5.9 us; LIGO GW (2 blocks, 3,394 params) 3.5-9.2 us depending on reuse factor. The abstract's "<2 us" holds only for the smallest model at reuse 1. **[SYNTH/SIM]** - [arXiv:2409.05207](https://arxiv.org/html/2409.05207)
- Jet-tagging MLP (16 features, 5 classes) with HGQ + distributed arithmetic on XCVU9P: 75.9% accuracy at 3 cycles / 12.1 ns with 2,891 LUTs, 0 DSPs; 76.9% at 5 cycles / 23.4 ns with 11,978 LUTs, 0 DSPs. On a small Artix XC7A35T the same models take 246-337 ns. **[SYNTH/SIM, post-P&R]** - [hls4ml overview, arXiv:2512.01463](https://arxiv.org/html/2512.01463)
- HLT-class models on datacenter cards: a 2.8M-parameter CNN and a 162k-parameter AE encoder for long-lived-particle triggers were run through Vitis-AI (DPU, 8-bit PTQ) on Alveo U50 and U250; CNN 3.7 ms / 950 fps on U50, 3.1 ms / 553 fps on U250; AE 2.6 ms / 1,497 fps on U50 - slower than a V100 GPU (1.0 ms / 9,930 fps for the CNN), with data loading suspected to dominate. **[HARDWARE DEMO]** - [arXiv:2307.05152, MLST 4 (2023) 045040](https://arxiv.org/html/2307.05152v2)

**Other experiments**

- **Belle II [PRODUCTION for the neural z-vertex trigger]**: the neural z-vertex track trigger ran actively in the L1 trigger in 2021 on four UT3 boards (Virtex-6 XC6VHX380T), one per CDC quadrant; overall L1 latency budget 5 us at 31.75 MHz throughput. - [Unger et al., operation in 2021](https://portal.fis.tum.de/en/publications/operation-of-the-neural-z-vertex-track-trigger-for-belle-ii-in-20/); [arXiv:1910.13679](https://arxiv.org/pdf/1910.13679)
- Belle II upgrades: (a) DNN first-level track trigger with a simplified self-attention block via HLS, 37% lower track-trigger rate and efficiency 96% -> 98% vs the existing neural trigger [arXiv:2510.02762](https://www.arxiv.org/abs/2510.02762); (b) tau trigger dense network with HGQ2 + hls4ml, 12 cycles (94 ns) with latency strategy, 9 cycles (71 ns) with da4ml, validated in RTL simulation and on the UT4 (Virtex UltraScale) board, deployment planned for the fall 2025 run [FastML 2025 slides](https://indico.cern.ch/event/1496673/contributions/6637927/attachments/3128250/5548971/FastML25.pdf); (c) GNN hit filter on XCVU160 in UT4 targeting ~1 us at 32 M events/s, offline validation 83% background-hit rejection at 95% signal-hit efficiency [arXiv:2511.04731](https://arxiv.org/abs/2511.04731v1). (a)-(c) are **[HARDWARE DEMO / pre-deployment]**.
- **DUNE [SYNTH/SIM]**: small two-layer 2D CNN for far-detector data selection tested for a Xilinx UltraScale+ via hls4ml with QAT. - [arXiv:2201.05638](https://ar5iv.labs.arxiv.org/html/2201.05638)
- **LHCb**: the FPGA RETINA demonstrator (eight PCIe FPGA cards, 27-day continuous run, 19.6 MHz event rate) is pattern-recognition, not a neural network; the 30 MHz software trigger and its NN ghost-killer run on GPUs; a GNN tracking pipeline has an FPGA implementation built only for a power/speed comparison with GPU. - [CHEP 2024 Retina slides](https://indico.cern.ch/event/1338689/contributions/6015410/attachments/2953452/5193313/CHEP_Retina_2024_v2.pdf); [arXiv:2508.07423](https://arxiv.org/abs/2508.07423v3); [arXiv:2502.02304](https://arxiv.org/pdf/2502.02304)
- **Cosmic-ray / neutrino radio self-trigger [SYNTH/SIM]**: fully-convolutional 1D CNN (~1.5e4 parameters, 50% pruned, ap_fixed<13,5>) on 128-sample traces sampled at 250 MHz; hls4ml + Vitis HLS 2023.2 at 200 MHz: Alveo U250 1.99 us (II 394 cycles, 17% DSP), Kintex UltraScale KU040 3.30 us (108% DSP), Zynq-7020 6.51 us (963% DSP, i.e. does not fit). Efficiency ~68% at FPR 1e-4 vs ~16.8% for an SNR threshold. No on-board test. - [arXiv:2502.21198](https://arxiv.org/html/2502.21198v3)
- Neutrino telescopes: an ICRC 2023 proceeding evaluates an FPGA ML trigger (hls4ml, P-ONE simulation) **[PROPOSAL]**. - [Capel & Spannfellner](https://inspirehep.net/files/d0ea4635aa796251f0b95094c6bdfa5b)
- NA62: a RICH event classifier was built with hls4ml + Vivado HLS for the online-processing upgrade (search snippet). - [arXiv:2202.03942](https://arxiv.org/pdf/2202.03942)

**Accelerator control (Fermilab)**

- **READS beam-loss de-blending [HARDWARE DEMO / operational demonstrator]**: ML model on an Altera Arria 10 SoC "central de-blending node" ingests streamed packets from remote DAQ nodes and attributes each beam-loss-monitor reading to Main Injector vs Recycler; inferences are streamed to ACNET for operators (aid to tuning, not closed-loop control). No measured latency found; the project quotes "millisecond scale" capability. - [IBIC 2023 TU3C02](https://accelconf.web.cern.ch/ibic2023/papers/tu3c02.pdf); [OSTI 2377381](https://www.osti.gov/biblio/2377381); [Fermilab READS page](https://artificialintelligence.fnal.gov/reads/)
- **Booster GMPS regulation [HARDWARE DEMO]**: DQN MLP agent (5 inputs, 3x128 hidden, 7 outputs, ~35k parameters, 20-bit fixed-point) on Intel Arria 10 SoC: 3.9 us latency against a 5 ms requirement for a 15 Hz loop; 53 DSPs, 238 BRAMs, 43.3k ALMs, 92.6k FFs. - [FastML Science Benchmarks, arXiv:2207.07958](https://ar5iv.labs.arxiv.org/html/2207.07958)

**How models are updated**

- AXOL1TL: first model trained on 2023 ZeroBias; updated model in 2025; v4 and v5 exist; newer model moved toolchain (QKeras/hls4ml -> HGQ/da4ml). All retraining is offline. - [arXiv:2411.19506](https://arxiv.org/html/2411.19506v1); [FastML 2025 contribution](https://indico.cern.ch/event/1496673/contributions/6637931); [FastML Foundation page](https://fastmachinelearning.org/applications/anomaly-detection-for-new-physics-at-cms-level-1-trigger/)
- A CHEP 2024 study for the CMS Phase-2 L1 trigger compares "baseline retraining and redeployment" against continual learning (replay or regularisation) as conditions change, with labels from offline analysis or L1 scouting (search snippet; PDF returned 403). - [EPJ Web Conf. CHEP 2024, 09037](https://www.epj-conferences.org/articles/epjconf/pdf/2024/05/epjconf_chep2024_09037.pdf)

### Inferences
- Typical production envelope in L1: inputs of ~50-250 quantized features, models of ~1k-10k parameters, 2-16 clock cycles, 25-100 ns, a few percent to tens of percent of a Virtex-7. HL-LHC prototypes on VU13P stretch to ~150-250 ns for set/attention models; transformers remain at 2-10 us and are not trigger-ready at L1.
- Toolflow has shifted during 2024-2026 from QKeras + hls4ml "latency" strategy to HGQ/HGQ2 + da4ml (distributed arithmetic, zero DSP) and to LUT/logic-gate networks; this is where the lowest-latency numbers now come from.
- The update path everywhere is retrain-offline -> resynthesize -> redeploy bitstream between fills/years. Nothing in HEP production changes weights at run time.

### Gaps
- No public document was found giving the AXOL1TL/CICADA retraining cadence, the official CICADA firmware latency/resources, or parameter counts for the production AXOL1TL versions (figures above for CICADA come from a third-party re-implementation).
- The AXOL1TL "2.1% LUT, 50 ns" figure is from slides via a search snippet; not confirmed against a CMS paper or detector performance note.
- COMET Phase-I (offline-trained MLP in an FPGA trigger with a 7.5 us decision budget) surfaced in a search snippet but the source document was not identified.
- No ML-on-FPGA production system was found for LHCb, DUNE, or any dark-matter experiment; nothing at all was found for dark-matter detectors.
- READS end-to-end latency and FPGA resource numbers were not found.

## 2. Gravitational-wave and astronomy: FPGA ML for GW detection/glitches, FRB/pulsar, RFI, SETI, telescope pipelines

### Takeaway
There is no production FPGA-ML system in gravitational-wave or radio astronomy as of late 2026: GW work is a handful of synthesis-level studies (LSTM/VAE autoencoders at 0.3-0.9 us on Alveo U250, a small hls4ml transformer at 3.5-9 us on VU13P), and operational ML in both fields (Aframe/AMPLFI in LVK, FETCH/frbid, Breakthrough Listen's Holoscan pipeline) runs on GPUs. Radio telescopes use large FPGA fleets, including Alveo U280/U55C cards, for classical channelization, correlation, RFI flagging and transient search, so the hardware is present but the ML-in-fabric layer is essentially unoccupied.

### Cited Findings

**Gravitational waves**

- LSTM autoencoder for GW anomaly detection (Que et al., ASAP 2021) **[SYNTH/SIM, RTL co-simulation]**: nominal model = 4 LSTM layers (32, 8, 8, 32 units) + TimeDistributed dense, 8 timesteps, 16-bit; on Xilinx Alveo U250 at 300 MHz: 0.867 us for the four-layer design with 9,021 DSPs (73%) and 463k LUTs (27%); single 32-unit layer 0.343 us with 2,221 DSPs; a small 2x9-unit model fits a Zynq 7045 at 100 MHz. CPU 39.7 ms and GPU 32.1 ms for comparison. Uses custom open-source HLS templates with per-layer reuse factors; II balancing cuts DSPs by up to 42%; 4.92-12.4x lower latency than prior FPGA LSTMs. Data are simulated signals (PyCBC, SEOBNRv4) in simulated noise. - [arXiv:2106.14089](https://ar5iv.labs.arxiv.org/html/2106.14089)
- Follow-up low-latency VAE for GW anomaly detection reports 61x speed-up over a prior FPGA autoencoder at equal accuracy (search snippet). - [Que et al., IEEE JETCAS 2024](https://www.doc.ic.ac.uk/~cg1710/pub/2024/jetcas24zq.pdf)
- hls4ml transformer on LIGO O3a data with injected BBH and sine-Gaussian signals: 2 blocks, hidden 32, 3,394 parameters, input 100x2, AUC 97.8%; VU13P; 3.53 us (reuse 1, II 212 cycles) to 9.18 us (reuse 4). **[SYNTH/SIM]** - [arXiv:2409.05207](https://arxiv.org/html/2409.05207)
- WaveNet-based CNN for binary-neutron-star early warning evaluated on CPU, GPU and FPGA for time, energy and cost; accuracy 66.81% -> 76.22% at 1% false-alarm probability on simulated O3-like data. Published MLST 6, 015072 (2025). FPGA device and latency not stated in the abstract. - [arXiv:2409.05068](https://arxiv.org/abs/2409.05068); [DOAJ record](https://doaj.org/article/b0395b60f7d0412aa896ce660970c3ed)
- DeepClean (LIGO noise subtraction, arXiv:2005.06534) and FACILE have hls4ml-derived FPGA implementations originally for Alveo U250 and benchmarked on Alveo U55C cards in the National Research Platform cluster; the repository page gives no latency numbers. **[HARDWARE DEMO]** - [fastmachinelearning/nrp_u55c_benchmark](https://www.github.com/fastmachinelearning/nrp_u55c_benchmark)
- Operational ML in LVK O4 is not FPGA-based as far as sources show: the Aframe neural search has detected 15 BBH events in real time since late August 2025 and AMPLFI distributes neural parameter estimates in low latency; no source ties these to FPGAs. - [APS April 2026 abstract](https://meetings-archive.aps.org/smt/2026/apr-d78/2/); background on GPU inference-as-a-service: [arXiv:2108.12430](https://arxiv.org/pdf/2108.12430)

**Radio astronomy, FRB/pulsar, RFI, SETI**

- Breakthrough Listen's in-path ML is GPU-based: at the Allen Telescope Array a modified ResNet-38 runs on NVIDIA Holoscan for end-to-end FRB detection on ~100 Gb/s beamformed spectrograms, without dedispersion or RFI-masking stages. - [The First Decade of Breakthrough Listen, arXiv:2610.07482](https://arxiv.org/pdf/2610.07482)
- hls4ml for radio transients (MPIfR; Men, Kazantsev, Karuppusamy, Kramer): CNN classifier for RFI / Crab giant pulses / FRBs motivated by MeerKAT and SKA data rates; evaluation and proof-of-concept only (tested on MNIST first). **[PROPOSAL / early demo]** - [PUNCH4NFDI TA5 WP2/4 report](https://indico.desy.de/event/48163/contributions/182688/attachments/95516/130717/TA5_WP2_4_report.pdf); [PUNCH workshop slides](https://indico.desy.de/event/39436/contributions/145805/attachments/82680/109026/PunchWorkshop_Yunpeng_Men.pdf)
- MeerKAT: a URSI 2023 paper proposes transient-RFI detection inside the digitiser (D-Engine) FPGA, with captured data to be used later to train a classifier; MeerTRAP's "frbid" ML classifier runs on candidates in software. - [URSI GASS 2023](https://www.ursi.org/proceedings/procGA23/papers/2661.pdf); [arXiv:2302.10107](https://arxiv.org/pdf/2302.10107)
- FPGA footprint in current/planned telescopes (classical DSP, not ML): ASKAP CRACO uses 20 Alveo U280 cards for RFI detection and transient search (~1.7 ms time resolution; the same paper's table says 1.728 ms); SKA-Low correlator/transient system uses 400 Alveo U55C cards (60 kW) and does RFI flagging in FPGA logic using under 50% of the logic; SKA-Low transient latency requirement is 100 us; MWA, LOFAR (1,664 Arria 10), SKA-Mid and ngVLA (Stratix 10 DX) are similarly FPGA-heavy. - [Pritchard, Dodson, Wicenec, arXiv:2601.07130](https://arxiv.org/html/2601.07130)
- Spiking-NN RFI detection is argued to be deployable in existing FPGA headroom at "zero capital cost", but existing SNN RFI results are software or the SynSense Xylo ASIC, and SNNs "lag in detection accuracy" behind larger ANNs on real LOFAR data. **[PROPOSAL]** - [arXiv:2601.07130](https://arxiv.org/html/2601.07130); related SNN pipeline on neuromorphic hardware [arXiv:2511.16060](https://arxiv.org/html/2511.16060v1)
- Non-neural real-time RFI on FPGA: adaptive filter for FAST with 4096 channels over 1 GHz, convergence 208.1 us (broadband) / 125.5 us (multi-carrier). - [arXiv:1805.06376](https://arxiv.org/pdf/1805.06376)
- Review of FPGA accelerators for SKA transient search: training on general-purpose systems, inference on accelerators; FPGAs favoured for reduced-precision inference. - [arXiv:2207.07054](https://arxiv.org/pdf/2207.07054)
- Real-time FRB candidate classifiers in operation (FETCH, ARTS, UTMOST random forest) are GPU/CPU. - [FETCH, arXiv:1902.06343](https://arxiv.org/pdf/1902.06343); [ARTS, arXiv:2205.12362](https://arxiv.org/pdf/2205.12362)
- hls4ml overview lists a CNN for self-triggering radio antennas (cosmic-ray detection) as demonstrated; see the air-shower entry in section 1 for numbers. - [arXiv:2512.01463](https://arxiv.org/html/2512.01463); [arXiv:2502.21198](https://arxiv.org/html/2502.21198v3)

### Inferences
- Radio telescopes already deliver channelized voltages/spectra as packet streams (BL's pipeline consumes ~100 Gb/s of beamformed spectrograms; CRACO and SKA-Low put Alveo U280/U55C cards directly in the data path), so a 100 GbE Alveo card is architecturally the native form factor here, unlike in RF/quantum work where RFSoC ADCs are required.
- GW strain is low-rate (kHz) so the "need" for sub-microsecond inference is weak; published FPGA numbers are ~1e4-1e5 times faster than the CPU/GPU baselines but the science case is driven by throughput/energy, not latency.
- The largest unoccupied niche in this group is ML-based RFI/transient classification in fabric on packetized telescope data.

### Gaps
- No FPGA-ML work was found for CHIME, DSA-110 or DSA-2000, nor any FPGA implementation of SETI technosignature search; searches returned only GPU pipelines.
- No "recurrent autoencoder via hls4ml for GW" paper was located; the GW recurrent/VAE autoencoder results use custom HLS templates.
- Martins et al. FPGA device, toolflow and timing were not extracted (abstract only).
- No measured-on-hardware GW FPGA result with timing was found; all GW latencies above are simulation/synthesis.
- CASPER-collaboration material on ML was not found.

## 3. RF and communications: modulation classification, spectrum sensing, fingerprinting, radar, jamming

### Takeaway
RF is the second most mature area after HEP but entirely at lab/prototype level: modulation classifiers on Zynq/RFSoC parts report ~8-30 us per classification at input rates of tens of MS/s (128 MHz ADC sampling before decimation in the Strathclyde RFSoC work), spectrum sensing ~0.6 ms, and RF fingerprinting ~0.2 ms. Radar and jamming applications have few FPGA NN implementations with measured latency, and one radar-warning-receiver study concluded FPGA LSTMs are not competitive with CFAR.

### Cited Findings

- Ternary-weight CNN for automatic modulation classification on Xilinx ZCU111 RFSoC (Tridgell et al., FPT 2019): classification latency ~8 us and operational throughput 488k classifications/s; an RTX 2080 Ti peaks around 30k classifications/s on the smaller models (search snippet; PDFs could not be parsed). **[HARDWARE DEMO]** - [FPT 2019 paper](https://sidmontu.github.io/pubs_pdfs/amc_fpt2019.pdf); [RAW 2020 extension](https://sidmontu.github.io/pubs_pdfs/amc_raw20.pdf)
- "RadioML Meets FINN" (Jentzsch et al., IEEE Micro 2022): FINN streaming-dataflow accelerators for RadioML modulation classification report >10x throughput and >100x lower latency than embedded GPUs at comparable accuracy and power, and 3.5x the throughput of alternative FPGA efforts; absolute figures not verified. - [IEEE Xplore](https://ieeexplore.ieee.org/document/9933377); [Paderborn record](https://ris.uni-paderborn.de/record/33990)
- FINN example zoo includes a RadioML 2018 VGG10 1D-CNN with 4-bit weights/activations, supported on ZCU104 only. - [Xilinx/finn-examples](https://github.com/Xilinx/finn-examples)
- Streaming CNN on AMD RFSoC (MacLellan, Crockett, Stewart, Strathclyde): modulation classification on RFSoC 2x2 in real time at 128 MHz sampling before decimation; thesis reports 29.6 us latency and 34k classifications/s; OJCS 2024 paper covers 16-, 8- and 4-bit models plus dataset generation and QAT. **[HARDWARE DEMO]** - [thesis](https://stax.strath.ac.uk/downloads/ng451j02r?locale=de); [NEWCAS 2023](https://strathprints.strath.ac.uk/86117/1/MacLellan_etal_NEWCAS2023_Streaming_Convolutional_Neural_Network_FPGA_architecture.pdf); [IEEE OJCS 2024](https://strathprints.strath.ac.uk/91541/7/MacLellan-etal-IEEE-OJCS-2024-RFSoC-modulation-classification-with-streaming-CNN.pdf)
- Embedded FNN on an FPGA SDR (Soltani et al. 2019): 1800-100-20-7 fully connected network, noise + six modulations; Zynq UltraScale+ XCZU9EG with AD9361 ("DeepRadio"); 24 us per 900-I/Q-sample decision; >37 MS/s without downsampling; 158,435 LUTs (57.8%), 210 DSPs (8.3%); ~28 uJ per decision; Jetson Xavier 3.6 ms and Nano 4.1 ms; accuracy ~94% vs 95% on GPU; 16-bit. **[HARDWARE DEMO]** - [arXiv:1910.05765](https://ar5iv.arxiv.org/html/1910.05765)
- DeepSense wideband spectrum sensing (Uvaydov, D'Oro, Restuccia, Melodia): CNN inside the transceiver baseband logic; precision 98%, recall 97%, latency as low as 0.61 ms (search snippet). **[HARDWARE DEMO]** - [NSF PAR copy](https://par.nsf.gov/servlets/purl/10293648)
- RF fingerprinting: photonics-inspired compact PRNN-CNN with 6.3k parameters classifying 30 identical ZigBee devices at 95.90% accuracy; PYNQ-Z1 via Vivado HLS dataflow; 219 us latency; FPGA accuracy drop 0.42%. **[HARDWARE DEMO]** - [arXiv:2106.13865](https://ar5iv.labs.arxiv.org/html/2106.13865)
- Sparsity-aware streaming SNN accelerator for AMC: 23.5 MS/s on RadioML 2016, about twice its baseline. - [arXiv:2601.02613](https://arxiv.org/html/2601.02613v1)
- ML-based wideband spectrum awareness on FPGA estimating angle of arrival, centre frequency, bandwidth and modulation (demonstration; search snippet). - [Lin et al., NSF PAR](https://par.nsf.gov/servlets/purl/10550215)
- Radar target detection: lightweight U-Net (HW-UNet) for sea-surface targets on a Xilinx KCU1500 board [Electronics 14(10):1944](https://www.mdpi.com/2079-9292/14/10/1944/htm); SAR target-detection accelerator [PMC11857116](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11857116/); a 2025 Chalmers thesis runs a NN binary detector on a CFAR feature plane on a device with programmable logic plus AI engines [Chalmers ODR](https://odr.chalmers.se/items/55100acc-7f4a-45d6-b106-bd0452046a8e/full). Latency figures were not extracted.
- Negative result: an FPGA LSTM for pulse detection in radar warning receivers "exhibits high latency, significant resource consumption, and requires prior training with knowledge of the noise environment" and is judged not a viable alternative to CFAR. - [journal record](https://www.ebsco.com/articles/technology/42757fd8-b4f9-5f4d-82a4-eb1ec68df25e/performance-evaluation-of-fpga-based-lstm-neural-networks-for-pulse-signal-detection-on-real-time-radar-warning-receivers)
- Anti-jamming: FPGA accelerator for a DQN making radar anti-jamming decisions, ~46x (single decision) and ~84x (continuous) faster than a CPU system (search snippet; Chinese-language paper). - [NUAA journal](https://sjcj.nuaa.edu.cn/sjcjycl/article/pdf/202305013)

### Inferences
- Reported RF latencies cluster in three bands: ~10 us (binarized/ternarized or tiny dense nets on RFSoC), ~20-30 us (streaming CNN / FNN), and 0.2-0.6 ms (HLS dataflow on small Zynq, wideband sensing). Nothing published reaches the tens-of-nanoseconds regime of HEP triggers because input windows are hundreds to thousands of I/Q samples.
- All RF demonstrations found are static models trained offline; the radar-warning study explicitly lists the need for prior knowledge of the noise environment as a weakness, which is an adaptation gap.
- RFSoC is the dominant platform; no RF ML example on an Alveo card was found.

### Gaps
- Absolute throughput/latency for the FINN RadioML VGG10 on RFSoC (IEEE Micro) could not be verified (paywalled; mirror unreachable).
- No FPGA jamming-recognition or RF-anomaly-detection paper with measured end-to-end latency was found; no low-SNR signal-detection FPGA paper with numbers was found.
- No DeepSig product or defence-lab (e.g. MILCOM/DySPAN) FPGA numbers were located in the searches run.
- Tridgell et al. resource usage and exact model were not extracted (PDF binary).

## 4. Other real-time signal domains: fusion, quantum, seismic, biomedical, event cameras/LiDAR, network traffic, finance

### Takeaway
Outside HEP, the systems closest to operational use are in fusion (a dense network on a KCU1500 installed in DIII-D's plasma control system with run-time-updatable weights; a CNN on a frame-grabber FPGA at HBT-EP at 17.6 us trigger-to-output), superconducting-qubit readout/decoding (32 ns readout on QICK/RFSoC; a real-time distance-3 surface-code experiment with a 124 ns NN decoder) and finance (audited STAC-ML LSTM inference at ~2-5 us p99). Network intrusion detection has the lowest published latencies (6-20 ns, sub-1k to ~27k LUTs) but almost all of it is synthesis/RTL simulation on replayed PCAP rather than live 100 GbE traffic.

### Cited Findings

**Fusion plasma**

- **DIII-D, SLAC Neural Network Library (SNL) [PRODUCTION-adjacent: installed in PCS]**: dense network on an AMD/Xilinx KCU1500 card installed in the real-time Plasma Control System nodes, receiving live Beam Emission Spectroscopy signals to forecast disruptive ELM conditions; output feeds a controller driving RMP coils. SNL supports on-the-fly updates of weights and biases without full FPGA resynthesis, and the authors suggest hot-swapping multiple classification tasks on one FPGA. Inference latency ~4.4 us (search snippet; not in the abstract; HTML unavailable). - [arXiv:2604.26042](https://arxiv.org/abs/2604.26042)
- **HBT-EP mode tracking [HARDWARE DEMO]**: CNN (3 Conv2D-MaxPool blocks + 2 dense; 12,910 parameters, 32x32 input, 7-bit QAT, 50% sparsity) via QKeras + hls4ml on a Euresys Coaxlink Octo frame grabber (Kintex UltraScale KU035) fed by a Phantom S710 camera; measured inference 7.7 us; trigger-to-output 17.6 us (3 us exposure + 5.3 us readout/buffering + 7.7 us inference + 1.6 us writeout); runs up to 120 kfps; model uses 36.7% LUT, 7.8% DSP, 9.3% BRAM on top of ~25% LUT for the CoaXPress firmware. Closed-loop control "not yet conducted". - [arXiv:2312.00128](https://arxiv.org/html/2312.00128v3)
- **DIII-D plasma-state predictor on Alveo U50 [SYNTH/SIM]**: recurrent probabilistic NN (GRU 64 + encoder 128 + residual-MLP decoder 128; ~175k parameters, reduced 94.9% from 3.45M; text and table disagree by 160 parameters), 53 inputs -> 27 outputs, ap_fixed<16,6> QAT; hls4ml (resource strategy, reuse factor 64, io_stream) -> Vitis HLS -> Vivado -> v++ 2022.1 on part xcu50-fsvh2104-2-e, platform xilinx_u50_gen3x16_xdma_5_202210; 104.7 MHz; latency 276 cycles = 2.64 us; II 122 cycles = 1.17 us (~8.6e5 inferences/s); post-route LUT 262,381/744,638 (35.2%), FF 280,955 (17.8%), DSP 3,868/5,948 (65.0%), BRAM 562/1,163 (48.3%), URAM 0/636. ~240x faster than CPU (608 us) and ~410x faster than A100 (1,085 us) at batch 1. Trained on 19,648 DIII-D shots at 20 ms cadence. The authors state "no physical Alveo U50 card was available to us for direct hardware testing". - [arXiv:2609.23141](https://arxiv.org/html/2609.23141)

**Quantum: readout and error-correction decoding**

- **QICK + hls4ml single-transmon readout [HARDWARE DEMO]**: 2-layer MLP with QAT on the RFSoC running QICK: 96% single-shot fidelity, 32 ns latency (32.25 ns in the journal version), <16% LUT utilization. An earlier version reported 92% fidelity (vs 84% for a matched filter) at 1.3 us readout time with <50 ns inference. - [arXiv:2501.14663](https://arxiv.org/html/2501.14663v1); [IEEE TQE 2025](https://tqe.ieee.org/2025/09/11/end-to-end-workflow-for-machine-learning-based-qubit-readout-with-qick-and-hls4ml/); [FastML 2024 abstract](https://indico.cern.ch/event/1387540/contributions/6153407); [OSTI 1974720](https://www.osti.gov/biblio/1974720)
- LUT-based neural networks for RFSoC readout discrimination with no DSP usage (details not extracted). - [arXiv:2512.07808](https://arxiv.org/pdf/2512.07808v1)
- **Real-time surface-code QEC with FPGA NN decoder [HARDWARE DEMO on a quantum processor]**: distance-3 on a superconducting processor; deterministic closed-loop latency 550 ns including 124 ns NN decoding, within a 1.25 us QEC cycle; logical performance comparable to offline decoding. FPGA part and network size not in the abstract. - [arXiv:2605.04892](https://arxiv.org/abs/2605.04892)
- Other FPGA neural decoders: GNN-based accelerator for distances up to 7 with <1 us latency [arXiv:2603.22149](https://arxiv.org/abs/2603.22149); programmable neural decoder 197 ns (L=5) and 1.136 us (L=7) [arXiv:2305.15767](https://ar5iv.labs.arxiv.org/html/2305.15767); feed-forward decoder NN measured at 87.6 ns on FPGA [arXiv:2411.18090](https://arxiv.org/pdf/2411.18090v2); accuracy-latency co-design up to d=9 [arXiv:2605.12046](https://arxiv.org/pdf/2605.12046). Mostly **[SYNTH/SIM]**.
- On-chip online learning for readout: see section 5 (KAN, 140 ns per full update).

**Seismic / earthquake early warning**

- Searches returned only software deep-learning EEW work (P-wave pickers, PGA predictors, network-level models); no FPGA neural-network implementation was found. - [universal EEW networks, PMC11488472](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11488472/)

**Biomedical**

- Spiking-NN seizure detection from raw EEG on FPGA: 0.5 us and 4.55 nJ per inference, 99.3% average accuracy (search snippet). - [IEEE TBioCAS 2025 preprint](https://iris.unica.it/retrieve/bd497415-9d97-4b96-8b09-3b7d00ebee37/Wearable_Epilepsy_Seizure_Detection_on_FPGA_With_Spiking_Neural_Networks.pdf)
- Compact 1D-CNN for spike detection and artifact removal: 95.05% accuracy at 5.6 mW on an FPGA board. - [arXiv:2504.14279](https://arxiv.org/pdf/2504.14279)
- FPGA spike assignment for high-density probes with 1 ms latency, using a model built offline in software. - [Janelia](https://janelia.org/publication/low-latency-extracellular-spike-assignment-for-high-density-electrodes-at-single-neuron)
- Closed-loop neuroscience needs stimulation within a few milliseconds of detected activity. - [PMC5421577](https://pmc.ncbi.nlm.nih.gov/articles/PMC5421577)
- hls4ml uses: 1D-CNN ECG arrhythmia classifier on a SoC at 1.655 W (no latency given); lymphocyte classification on a Euresys frame-grabber FPGA at 12x lower latency than GPUs. - [arXiv:2512.01463](https://arxiv.org/html/2512.01463)

**Event cameras and LiDAR**

- Graph convolutional network for event data on ZCU104 without external memory: 13.3 million events/s; latency 4.47 ms. - [arXiv:2406.07318](https://arxiv.org/pdf/2406.07318)
- Event-driven GNN accelerator on an edge FPGA: average 16 us per-event prediction latency at 6.86 W, 9.2x faster than software on an RTX A6000. - [TU Delft thesis](https://repository.tudelft.nl/record/uuid:5bc8cb13-4147-4ff3-875f-fc3fd515c975)
- LiDAR: ChipNet drivable-region CNN on XCKU115, 12.59 ms per scan [arXiv:1808.03506](https://arxiv.org/pdf/1808.03506); PointNet on ZCU104, 19.8 ms classification / 34.6 ms segmentation [arXiv:2006.00049](https://ar5iv.arxiv.org/html/2006.00049). Millisecond-scale, matched to 10 Hz scan rates.

**Network traffic anomaly / intrusion detection**

- **FSNIC [SYNTH/SIM]**: flow-based IDS for FPGA SmartNICs; P4 parser (Vitis Networking P4) + flow accumulator + LogicNets classifier (77-593-100-1, 1-bit inputs, 2-bit activations, fan-in 7, Brevitas QAT) on Alveo U280 (xcu280-fsvh2892-2L-e), Vitis/Vivado 2024.2; 6 ns inference; 846 LUTs, 252 FFs, 0 BRAM, 0 DSP; 500 M packets/s at 500 MHz out-of-context; accuracy 97.68% on UNSW-NB15 (vs 86.92% stateless) and 96.40% on CICIDS2017. Evaluated by RTL simulation on reconstructed PCAP; board-level validation and live traffic are future work. - [arXiv:2609.16363](https://arxiv.org/html/2609.16363)
- Prior FPGA IDS points from the same comparison table: Murovic & Trost 92.04% on UNSW-NB15, 19 ns, 26,879 LUTs; LogicNets NID-S 91.30%, 10.5 ns, 15,949 LUTs; Vreca et al. 82.10%, 91 ns, 11 M pps; Le Jeune et al. (with on-chip feature extraction) 6.68 us to 1.78 ms. - [arXiv:2609.16363](https://arxiv.org/html/2609.16363); see also [Farooq et al., SciTePress 2024](https://www.scitepress.org/Papers/2024/123678/123678.pdf)
- hls4ml ternary model detecting malicious executables in packets: 44 ns latency while maintaining 100 Gbps throughput (board not stated in the review). - [arXiv:2512.01463](https://arxiv.org/html/2512.01463)
- P4-programmable in-network NN/regression inference with fixed-point arithmetic on FPGA SmartNICs at the National Research Platform (search results associate this with 32 Alveo U55C cards); no latency numbers in the abstract. - [arXiv:2507.00428](https://arxiv.org/abs/2507.00428)
- Context: an Alveo U250 packet-processing design services ~98 Mpps on 100 GbE links (not ML). - [ACM doi 10.1145/3630047.3630191](https://unpaywall.org/10.1145%2F3630047.3630191); CMU's 100 Gbps open-source IDS uses an Intel Stratix 10 (not ML). - [CyLab](https://www.cylab.cmu.edu/news/2020/11/05-intrusion.html)

**Financial tick data**

- **STAC-ML Markets (Inference), audited [PRODUCTION-grade commercial stack]**: Myrtle.ai VOLLO on Intel Agilex (four BittWare IA-840f cards), Tacana suite: LSTM_A p99 5.07-5.08 us for 1-4 model instances (5.97 us with 8), LSTM_B p99 6.77-7.75 us; earlier Sumaco suite 24.0-24.1 us for LSTM_A. April 2026 audit on AMD Versal Premium: p99 under 2 us for LSTM_A (secondary sources). - [STAC report MRTL230426](https://stacresearch.com/node/47622); [STAC summit slides](https://stacresearch.com/system/files/resource/files/STAC-Summit-18-May-2023-STAC-ml.pdf); [April 2026 release](https://www.aap.com.au/aapreleases/cision20260429ae43196/)
- GPU comparison: NVIDIA reports 4.6-4.7 us STAC-ML LSTM latencies on GH200. - [NVIDIA blog](https://developer.nvidia.com/blog/?p=115102)
- FINN-GL (extended FINN with LSTM support): ConvLSTM for mid-price trend prediction (~141k parameters, W8A6) on FI-2010 limit-order-book data; ZCU104 (XCZU7EV) at 150 MHz; 4.3 ms at batch 1; ~49.6% LUT, 15.2% DSP. Notes that most LOB papers omit deployment latency although inter-event gaps can be nano- to microseconds. **[HARDWARE DEMO]** - [arXiv:2506.20810](https://arxiv.org/html/2506.20810v1)
- A 2026 METU thesis reports sub-microsecond XGBoost mid-price prediction on FPGA (search snippet). - [METU](https://open.metu.edu.tr/handle/11511/118428)

**Miscellaneous sensing (hls4ml review)**

- Microwave-sensing food-contaminant MLP: 27 us on AMD Kria K26; surface-texture C-RNN: 6.21 us; automotive semantic segmentation CNN on ZCU102: ~5 ms using <30% resources; typical HEP trigger constraint ~10 us. - [arXiv:2512.01463](https://arxiv.org/html/2512.01463)

### Inferences
- Latency by domain, as published: network IDS 6-100 ns; qubit readout 30-60 ns; QEC decoding 90 ns-1 us; fusion 2.6-18 us; finance 2-25 us (p99, end-to-end, audited); biomedical 0.5 us-1 ms; event cameras 16 us-4.5 ms; LiDAR 12-35 ms.
- Fusion and finance are the two non-HEP domains where a PCIe-attached datacenter-class FPGA card is the actual deployment form factor (KCU1500 in DIII-D PCS nodes; BittWare/Versal cards in trading servers).
- Network IDS is a crowded benchmark area (UNSW-NB15, CICIDS2017) with very small models; the open problems named by authors are board-level validation, live traffic and flow churn, not model latency.

### Gaps
- No FPGA NN for seismic/earthquake early warning was found.
- DIII-D SNL model size, resources and the 4.4 us latency could not be verified from full text.
- The QEC d=3 demonstration's FPGA part, model size and toolflow were not extracted.
- The SNN seizure figure (0.5 us) target hardware and measurement method were not checked.
- STAC 2026 Versal figures come from a press release, not the STAC report itself.
- No peer-reviewed 10-100 GbE ML IDS measured on live traffic on an Alveo card was found.

## 5. Online adaptation, on-device learning and frequent retraining: who does it, how, and where it is named as unmet

### Takeaway
Almost every system in this catalogue is a static, offline-trained model; the only fielded mechanism for changing a model without rebuilding the bitstream is run-time weight/bias loading (SLAC SNL at DIII-D). True in-fabric learning exists only as 2026 research prototypes - notably fixed-point online training of Kolmogorov-Arnold networks at 50-140 ns per forward+backward+update step on a VU13P - and several authors (HBT-EP, CMS trigger studies, the "Need for Ultrafast Training" position paper, the radar-warning LSTM study) explicitly identify adaptation to changing conditions as unsolved.

### Cited Findings

**Systems with some form of adaptation**

- Run-time weight reload: SNL at DIII-D supports "on-the-fly updates of the neural network weights and biases" without full FPGA resynthesis; authors propose hot-swapping tasks on one FPGA. Training itself remains offline. - [arXiv:2604.26042](https://arxiv.org/abs/2604.26042)
- In-fabric online learning (KAN): fixed-point online training exploiting B-spline locality (sparse updates). On AMD XCVU13P, 200 MHz target, Vitis HLS, post-route: one complete online update (forward + backward + in-place update) takes 50 ns for adaptive function approximation (430 LUT / 199 FF / 4 DSP), 140 ns for adaptive single-shot qubit readout (10,592 LUT / 3,858 FF / 84 DSP), 70 ns for non-stationary Acrobot control (7,666 LUT / 4,385 FF / 106 DSP); no BRAM. Under drift, KAN reaches 92.8% readout accuracy where fixed-point MLPs stay at ~50%. Claimed as the first model-free online learning at sub-microsecond latency; accepted at ICML 2026. **[SYNTH/SIM, post-route]** - [arXiv:2602.02056](https://arxiv.org/html/2602.02056)
- Prior on-FPGA training work listed there: EF-Train (Tang 2022), low-precision tensor training (Zhang 2021), compiler-based CNN training (Venkataramanaiah 2019), sparse training (Dey 2018), pipelined online backprop (Gadea 2000), equalizer with on-chip training (Liu 2023); gradient-free/decoupled approaches: Mehrabi 2024 (spiking), Sivak 2025 (learning decoupled from inference), Reuer 2023 (deep RL for quantum feedback). hls4ml and FINN are classed as inference-only. - [arXiv:2602.02056](https://arxiv.org/html/2602.02056)
- ONLAD: OS-ELM-based sequential on-device learning anomaly detector as an FPGA IP core on PYNQ-Z1; training 1.95-4.51x and prediction 2.29-4.73x faster than BP-NN software; 5.0-25.4x lower power than comparison systems; designed to follow concept drift. **[HARDWARE DEMO]** - [arXiv:1907.10147](https://ar5iv.labs.arxiv.org/html/1907.10147); companion drift detector [arXiv:2212.09637](https://arxiv.org/pdf/2212.09637)
- Online incremental learning on FPGA accelerators under concept drift without labelled data (ISQED 2023). - [ISQED 2023 session](https://isqed.org/English/Archives/2023/Technical_Sessions/73.html)
- Periodic offline retraining and redeployment: CMS AXOL1TL (2023-trained model, 2025 update, v4/v5) - see section 1. - [FastML Foundation page](https://fastmachinelearning.org/applications/anomaly-detection-for-new-physics-at-cms-level-1-trigger/)
- Adaptive control around a static model: "Towards a Self-Driving Trigger" dynamically reallocates resources and adjusts thresholds in real time for a menu including anomaly-detection triggers, demonstrated on simulated streams and public CMS data; the autoencoder is given the number of primary vertices as an input so it can learn pileup-dependent response. Hardware/FPGA not specified in the abstract. **[PROPOSAL / simulation]** - [arXiv:2601.08910](https://arxiv.org/abs/2601.08910)

**Explicit statements that adaptation is an unmet need**

- "nearly all existing accelerators assume static models trained offline", "relegating learning and adaptation to slower CPUs or GPUs"; "model updates must occur at the timescale of the underlying physics". Domains named: quantum error correction, cryogenic qubit calibration, plasma and fusion control, accelerator tuning, autonomous experiments. - [Hoang, "Position: The Need for Ultrafast Training", arXiv:2602.02005](https://arxiv.org/abs/2602.02005)
- "Ultrafast online learning is essential for high-frequency systems, such as controls for quantum computing and nuclear fusion"; host-accelerator training loops are too slow because "the system may have already shifted operating conditions". - [arXiv:2602.02056](https://arxiv.org/html/2602.02056)
- HBT-EP: machine and diagnostic upgrades changed plasma boundary conditions, so new training data must be collected and weights updated before control experiments; continuous monitoring, active learning, domain adaptation and RL are listed only as future directions. - [arXiv:2312.00128](https://arxiv.org/html/2312.00128v3)
- CMS: current trigger menus are "static, hand-tuned", while "instrumentation and environmental conditions evolve"; residual pileup dependence remains after calibration. - [arXiv:2601.08910](https://arxiv.org/abs/2601.08910)
- CMS Phase-2 L1 study treats model degradation under changing conditions as a design problem and compares retrain-and-redeploy with continual learning (search snippet). - [CHEP 2024, EPJ Web Conf.](https://www.epj-conferences.org/articles/epjconf/pdf/2024/05/epjconf_chep2024_09037.pdf)
- Radar warning receivers: the FPGA LSTM "requires prior training with knowledge of the noise environment". - [journal record](https://www.ebsco.com/articles/technology/42757fd8-b4f9-5f4d-82a4-eb1ec68df25e/performance-evaluation-of-fpga-based-lstm-neural-networks-for-pulse-signal-detection-on-real-time-radar-warning-receivers)
- Radio astronomy: RFI growth is driven by LEO satellites; "adaptive systems capable of detection previously unobserved transients are advantageous"; on-FPGA STDP learning is cited as existing technique but not applied to RFI. - [arXiv:2601.07130](https://arxiv.org/html/2601.07130)
- Air-shower radio trigger: trained and tested at a single high-RFI site; other sites, varying noise and retraining are not evaluated. - [arXiv:2502.21198](https://arxiv.org/html/2502.21198v3)
- QEC: the d=3 real-time decoder reports "robustness against varying error conditions" but describes no online adaptation. - [arXiv:2605.04892](https://arxiv.org/abs/2605.04892)
- hls4ml's 2025 overview contains no on-chip training or run-time adaptation feature; QAT is done before synthesis and listed future work is new front/back ends, transformers, AI-engine integration and distributed inference. - [arXiv:2512.01463](https://arxiv.org/html/2512.01463)

### Inferences
- Three tiers exist: (1) retrain offline and rebuild firmware (HEP, RF, IDS - the norm); (2) reload weights at run time into fixed architecture (SNL at DIII-D; also implicit in P4 designs that store weights in control-plane tables, per arXiv:2507.00428); (3) learn in fabric (KAN prototype, ONLAD/OS-ELM, small-scale). Tier 3 has no fielded example in any signal domain covered here.
- The domains where authors most concretely describe drift that breaks a static model are: fusion diagnostics after hardware changes, qubit readout/calibration drift, trigger anomaly detection under pileup/detector changes, and RFI/noise-environment change in radio/RF. Of these, anomaly detection on packetized detector or telescope data is the one that can be reproduced without an ADC.
- An adaptive anomaly detector for a streaming signal (autoencoder or OS-ELM/KAN-style learner) with in-fabric or tier-2 updates, evaluated under controlled drift on a public dataset, would sit in a gap none of the catalogued production systems fill.

### Gaps
- No documented case of in-fabric learning running on a live instrument was found.
- No RF (modulation/spectrum) or network-IDS FPGA design with online retraining and measured latency was found in the searches run.
- The CHEP 2024 continual-learning paper's quantitative results were not accessible (HTTP 403).
- Whether SNL's weight reload at DIII-D is actually exercised between shots (and how often) is not stated in the abstract.

## 6. Public datasets and prototyping on a 100 GbE / PCIe card without an ADC; existing Alveo examples

### Takeaway
Domains whose inputs are already digital records or packets - HEP trigger objects, network traffic, market data, telescope back-end streams, and replayed GW strain or recorded qubit/RF traces - can be prototyped on an ADC-less Alveo card, and most have public datasets. Published Alveo examples exist (U50: DIII-D plasma RNN, synthesis only, and a Vitis-AI DPU trigger demo; U250: GW LSTM autoencoder, air-shower CNN, FINN zoo, DeepClean/FACILE; U55C: NRP hls4ml benchmarks, hls4ml Coyote backend; U280: FSNIC, CRACO), but no published work was found that wires a low-latency hls4ml/FINN model to the 100 GbE port of an Alveo for streaming scientific data, and no measured-on-hardware low-latency result on a U50 was found.

### Cited Findings

**Public datasets (with the FPGA work that used them)**

- HEP jets: hls4ml LHC jet dataset (16 expert features or up to 100 particles/jet), Zenodo doi 10.5281/zenodo.3602254. - [FastML Science Benchmarks](https://ar5iv.labs.arxiv.org/html/2207.07958)
- HEP L1 anomaly detection: "LHC physics dataset for unsupervised New Physics detection at 40 MHz" (ADC2021 challenge; MET + 4 e/gamma + 4 muons + 10 jets as pT/eta/phi; 4M background-like training events; Zenodo; two record IDs appear in sources). - [arXiv:2107.02157](https://ar5iv.labs.arxiv.org/html/2107.02157); [Scientific Data 2022](https://www.nature.com/articles/s41597-022-01187-8.pdf)
- CMS Open Data 2017 zero-bias and ttbar events used to train CICADA-style teacher/student models. - [arXiv:2511.01908](https://arxiv.org/html/2511.01908v1)
- Accelerator control: BOOSTR Booster dataset (15 Hz, 54 devices). - [FastML Science Benchmarks](https://ar5iv.labs.arxiv.org/html/2207.07958)
- Qubit readout: ml-quantum-readout dataset, raw ADC traces from a ZCU216 as .npy, Zenodo record 14427490, code on GitHub. - [MLCommons Science benchmark entry](https://mlcommons-science.github.io/benchmark/md/benchmarks/single_qubit_readout_on_qick_system); [fastmachinelearning/ml-quantum-readout](https://github.com/fastmachinelearning/ml-quantum-readout)
- Gravitational waves: LIGO O3a data with injected BBH/sine-Gaussian signals (hls4ml transformer); simulated PyCBC signals in simulated noise (LSTM AE). - [arXiv:2409.05207](https://arxiv.org/html/2409.05207); [arXiv:2106.14089](https://ar5iv.labs.arxiv.org/html/2106.14089)
- RF: RadioML 2018 (FINN VGG10 example) and RadioML 2016 (SNN accelerator). - [finn-examples](https://github.com/Xilinx/finn-examples); [arXiv:2601.02613](https://arxiv.org/html/2601.02613v1)
- Network: UNSW-NB15 and CICIDS2017, replayed as PCAP traces. - [arXiv:2609.16363](https://arxiv.org/html/2609.16363)
- Finance: FI-2010 limit-order-book dataset. - [arXiv:2506.20810](https://arxiv.org/html/2506.20810v1)
- Generic time-series anomaly: FordA (UCR/UEA archive). - [arXiv:2409.05207](https://arxiv.org/html/2409.05207)
- TinyML: ToyADMOS (anomaly detection), Speech Commands, CIFAR-10. - [arXiv:2206.11791](https://ar5iv.labs.arxiv.org/html/2206.11791)
- Radio astronomy RFI: a real LOFAR RFI dataset is used in SNN RFI studies. - [arXiv:2601.07130](https://arxiv.org/html/2601.07130)

**Alveo-specific examples**

- **U50**: DIII-D recurrent probabilistic NN via hls4ml (2.64 us, 35% LUT, 65% DSP, 48% BRAM; synthesized and implemented, never run on a card). - [arXiv:2609.23141](https://arxiv.org/html/2609.23141). Vitis-AI DPU deployment of LLP-trigger CNN/AE on U50 (ms-scale, measured). - [arXiv:2307.05152](https://arxiv.org/html/2307.05152v2)
- **U250**: GW LSTM autoencoder at 300 MHz, 0.343-0.867 us (RTL co-simulation) [arXiv:2106.14089](https://ar5iv.labs.arxiv.org/html/2106.14089); air-shower 1D CNN 1.99 us (synthesis) [arXiv:2502.21198](https://arxiv.org/html/2502.21198v3); FINN examples for CIFAR-10 CNV, MNIST MLP, MobileNet-v1 and ResNet-50 [finn-examples](https://github.com/Xilinx/finn-examples); FACILE and DeepClean hls4ml designs originally built for U250 [nrp_u55c_benchmark](https://www.github.com/fastmachinelearning/nrp_u55c_benchmark); LLP CNN via Vitis-AI [arXiv:2307.05152](https://arxiv.org/html/2307.05152v2).
- **U55C**: NRP cluster hls4ml benchmarks (FACILE, DeepClean) [nrp_u55c_benchmark](https://www.github.com/fastmachinelearning/nrp_u55c_benchmark); hls4ml Coyote backend deploys models on PCIe-attached Alveo cards with default device u55c and support for u280 and u250 [hls4ml Coyote backend docs](https://fastmachinelearning.org/hls4ml/autodoc/hls4ml.backends.coyote.html); SKA-Low correlator uses 400 U55C (non-ML) [arXiv:2601.07130](https://arxiv.org/html/2601.07130).
- **U280**: FSNIC flow-based IDS (6 ns, 846 LUTs; synthesis + RTL simulation) [arXiv:2609.16363](https://arxiv.org/html/2609.16363); ASKAP CRACO's 20 U280 cards (non-ML) [arXiv:2601.07130](https://arxiv.org/html/2601.07130).
- hls4ml on Alveo generally: the "Vitis System Design Flow" back end targets datacenter Alveo cards, generating a Vitis kernel, host-transfer wrapper and multi-threaded host code; PCIe transfers overlapped with compute reach up to 96% of theoretical throughput; multi-kernel/multi-accelerator setups exceed 1.4 million inferences/s; the Coyote v2 shell is the other route. - [arXiv:2512.01463](https://arxiv.org/html/2512.01463)
- The original VitisAccelerator pull request was tested on a VCK5000 with Vitis 2022.2 and reported timing failures (WNS about -3 to -5 ns) on u55c and u250 at that time (search snippet; current status not checked). - [hls4ml PR #991](https://www.github.com/fastmachinelearning/hls4ml/pull/991)
- 100 GbE on Alveo: the Xilinx Vitis Network Example (VNx) provides a 100 Gbit/s UDP stack for Vitis kernels on Alveo cards. - [Xilinx/xup_vitis_network_example](https://www.github.com/Xilinx/xup_vitis_network_example)
- hls4ml networking precedent: ternary malicious-executable detector at 44 ns while sustaining 100 Gbps (board unspecified). - [arXiv:2512.01463](https://arxiv.org/html/2512.01463)

### Inferences
- Fit to an ADC-less U50 (inference, by data path): strong - network IDS (native packets, UNSW-NB15/CICIDS2017 PCAP replay), HEP-style anomaly detection (ADC2021 / CMS Open Data replayed as packets or over PCIe), market data (natively packets, but public tick data is limited to FI-2010-class sets), radio-astronomy back-end streams (telescopes emit UDP spectra/voltages; public RFI sets exist); moderate - GW strain replay (public LIGO data, low sample rate) and fusion (DIII-D deployment uses a PCIe card, but data availability is unclear); weak - RF modulation/fingerprinting and qubit readout, where the published value is tight ADC integration on RFSoC even though traces (RadioML, Zenodo 14427490) can be replayed.
- The U50 resource envelope reported after shell overhead (744,638 LUTs, 1,579,376 FFs, 5,948 DSPs, 1,163 BRAMs, 636 URAMs) is one to two orders of magnitude larger than any trigger-class or IDS model in this catalogue; a 175k-parameter GRU model consumed 65% of DSPs at reuse factor 64, which bounds how large a recurrent model can go.
- hls4ml documentation found does not list U50 as a Coyote or accelerator-backend board; the only U50 precedent uses plain hls4ml -> Vitis HLS -> v++ with the xilinx_u50_gen3x16_xdma platform, so some integration work is expected.
- An on-hardware, 100 GbE-fed, low-latency ML result on a U50 would itself be novel relative to the published record found.

### Gaps
- Whether the DIII-D shot database used in arXiv:2609.23141 is publicly accessible was not determined.
- No public packetized radio-telescope voltage/spectrum dataset specifically prepared for FPGA replay was identified.
- NRP U55C benchmark latency/throughput numbers and the data-delivery path were not on the repository landing page.
- Current status of hls4ml's VitisAccelerator timing closure on Alveo and any U50 support was not verified.
- The Open Cloud Testbed U280 + VNx multi-FPGA ML work (ResNet-50) appeared only in a search snippet and its source was not confirmed.

## 7. Benchmark suites and reference numbers

### Takeaway
Three benchmark families cover this space: FastML Science Benchmarks (jet classification 55 ns on VU9P; sensor-data compression 25 ns in a 65 nm ASIC; beam control 3.9 us on Arria 10), MLPerf Tiny (hls4ml/FINN open-division submissions at 17-45 us for anomaly detection and keyword spotting on Zynq-7020/Artix-7), and domain-specific de facto benchmarks (hls4ml jet tagging, UNSW-NB15 IDS, RadioML, STAC-ML Markets, the MLCommons Science QICK qubit-readout task). No benchmark in any of them measures adaptation or performance under drift.

### Cited Findings

**FastML Science Benchmarks** (Duarte, Tran, Hawks, Herwig, Muhizi, Prakash, Reddi; MLBench @ MLSys 2022; code at github.com/fastmachinelearning/fastml-science) - [arXiv:2207.07958](https://ar5iv.labs.arxiv.org/html/2207.07958)

| Task | Reference model | Constraint | Reference implementation |
|---|---|---|---|
| Jet classification (supervised) | 16-64-32-32-5 MLP, 6-bit QAT, ~4,389 params, 74.8% accuracy | latency <= 1 us, new input every 150 ns | 55 ns, 5 ns clock, II 1; Virtex UltraScale+ VU9P; 124 DSPs, 39,782 LUTs, 8,128 FFs |
| Irregular sensor data compression (unsupervised; CMS HGCal, 48 trigger cells) | CNN autoencoder, ~2,288 params, 6-bit weights; metric = energy mover's distance | 40 MHz, <= 100 ns, <= 4 mm2, < 100 mW | 25 ns, 60 mW (simulated), 65 nm LP-CMOS encoder ASIC |
| Accelerator beam control (RL; BOOSTR) | DQN MLP 5-128-128-128-7, ~35k params (LSTM surrogate ~1.5M) | 15 Hz loop, 5 ms | 3.9 us, 20-bit; Intel Arria 10 SoC; 53 DSPs, 238 BRAMs, 43.3k ALMs, 92.6k FFs |

**MLPerf Tiny v0.7, open-division FPGA submissions** (hls4ml + FINN co-design) - [arXiv:2206.11791](https://ar5iv.labs.arxiv.org/html/2206.11791)

| Task | Tool / model | Params | Quality | Pynq-Z2 (Zynq-7020) | Arty A7-100T |
|---|---|---|---|---|---|
| Anomaly detection (ToyADMOS) | hls4ml autoencoder, 6-12 bit | 22,285 | 0.83 AUC | 19 us, 30.1 uJ, 40,658 LUTs (76.4%), 205 DSPs (93.2%) | 45 us, 98.4 uJ, 51,429 LUTs (81.1%) |
| Keyword spotting (Speech Commands) | FINN MLP, 3-bit | 259,584 | 82.5% | 17 us, 30.9 uJ, 33,732 LUTs (63.4%) | 33 us, 53.7 uJ, 42,518 LUTs (67.1%) |
| Image classification (CIFAR-10) | FINN CNV-W1A1, 1-bit | 1,542,848 | 84.5% | 1.5 ms, 2,535 uJ | 1.5 ms, 3,419 uJ |
| Image classification (CIFAR-10) | hls4ml CNN, 8-12 bit | 58,115 | 83.5% | 27.3 ms, 44,330 uJ | 33.1 ms, 73,166 uJ |

- A 2026 preprint (ConvLUT) reports latency as low as 9 ns on MLPerf Tiny tasks with LUT-based convolutional architectures, compared against FINN baselines (search snippet). - [arXiv:2611.11507](https://arxiv.org/pdf/2611.11507)

**hls4ml jet-tagging reference numbers (2025 overview)** - [arXiv:2512.01463](https://arxiv.org/html/2512.01463)

- XCVU9P, 5 ns clock, HGQ + distributed arithmetic: 76.9% / 5 cycles (23.4 ns) / 11,978 LUTs / 0 DSP; 76.5% / 4 cycles (18.0 ns) / 6,067 LUTs; 75.9% / 3 cycles (12.1 ns) / 2,891 LUTs.
- XCVU9P at 1 GHz target (Fmax 713-756 MHz), DA: 27.8-39.3 ns at 21-28 cycles.
- XC7A35T (Artix-7): 246-337 ns; the most accurate latency-strategy model failed placement.
- Older QKeras baselines: 76.3% at 15 cycles (105 ns) and 76.1% at 10 cycles (50 ns); the extracted DSP/LUT columns for these rows looked transposed and should be checked against the paper.
- HGQ general claims: 50-95% LUT reduction, 50-100% DSP reduction, up to 80% latency reduction versus other compression methods.
- Other hls4ml benchmark sets: RNN benchmarks for top tagging, flavour tagging and QuickDraw [arXiv:2207.00559](https://arxiv.org/pdf/2207.00559); hls4ml vs SLAC SNL synthesis-strategy comparison [arXiv:2411.11678](https://arxiv.org/pdf/2411.11678); evaluation sets named in the overview include smart pixels, MNIST, SVHN and particle-based jet tagging.

**Domain benchmarks**

- MLCommons Science working group: "Single Qubit Readout on QICK System" (dated 2025-01-24), dataset Zenodo 14427490, metrics accuracy and latency, model "hls4ml quantized NN"; no runnable baseline linked. Reference result: 96% fidelity at 32 ns, <16% LUTs. - [MLCommons Science entry](https://mlcommons-science.github.io/benchmark/md/benchmarks/single_qubit_readout_on_qick_system); [arXiv:2501.14663](https://arxiv.org/html/2501.14663v1)
- STAC-ML Markets (Inference): audited LSTM inference; p99 5.07 us (Agilex, 2023), <2 us (Versal Premium, April 2026, secondary source). - [STAC](https://stacresearch.com/node/47622); [release](https://www.aap.com.au/aapreleases/cision20260429ae43196/)
- Network IDS de facto benchmark on UNSW-NB15: 82-98% accuracy, 6-91 ns, 846-26,879 LUTs across LogicNets-style designs. - [arXiv:2609.16363](https://arxiv.org/html/2609.16363)
- FINN example zoo: CIFAR-10 CNV and MNIST MLP (1/2-bit; Pynq-Z1, ZCU104, Ultra96, U250), MobileNet-v1 and ResNet-50 (U250), RadioML 2018 VGG10 (W4A4, ZCU104), Speech Commands MLP (W3A3, Pynq-Z1), UNSW-NB15 MLP (W2A2; Pynq-Z1, ZCU104, Ultra96), GTSRB, MaskedFace-Net. No accuracy numbers on the landing page. - [Xilinx/finn-examples](https://github.com/Xilinx/finn-examples)
- ADC2021 anomaly-detection challenge as the L1-trigger AD benchmark; reference hls4ml autoencoder result 80 ns on VU9P. - [arXiv:2107.02157](https://ar5iv.labs.arxiv.org/html/2107.02157); [arXiv:2108.03986](https://ar5iv.labs.arxiv.org/html/2108.03986)

### Inferences
- A prototype can be anchored to existing reference points: for a small autoencoder anomaly detector, ~80-100 ns on UltraScale+ (HEP) and ~19 us on Zynq-7020 (MLPerf Tiny) bracket the design space; for dense classifiers, 12-55 ns at 3k-40k LUTs.
- None of the suites includes a drift/adaptation track, a streaming-over-Ethernet delivery mode, or a datacenter-card platform, so results on an Alveo U50 with 100 GbE ingest would not have a like-for-like published comparator.

### Gaps
- Newer MLPerf Tiny rounds (after v0.7) with FPGA entries were not checked.
- FastML Science Benchmarks does not appear to have published updated reference numbers since 2022; whether the suite was extended (e.g. smart pixels, qubit readout) beyond the MLCommons Science entry was not confirmed.
- hls4ml example-models repository contents and any associated reference numbers were not inspected.
- No benchmark specific to radio-astronomy RFI or GW inference on FPGA was found.
