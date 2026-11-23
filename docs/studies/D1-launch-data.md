# D1: launch-labelled seismic records - the study, phase 1

Written by the parcel LCH on 2026-11-23, for round 1 ([the plan](../plans/R1-reference-model.md), row LCH). It answers one question from public sources: could seismic records, labelled by public rocket-launch times, carry an experiment beside [D0](D0-rough-design.md)'s stage E3? It ends with a list of downloads for Logan to approve.

**When this study was written nothing in it had been measured on a waveform, and no waveform, catalogue file, PDF or software package had been fetched.** What was read: public web pages, and the text answers of station-metadata services. Phase 2 has since run, on the download of section 8: [D1b](D1b-first-look.md) is a first look at real records of one launch. The rows of this study that it settles are restated here, each saying what it said before, and are listed in the section Changes after the first look. Whether a launch can be seen in a public record is no longer only BELIEVED for that one launch (D1b, rows Q1a to Q3b). How often one can be seen still is (the plan's row V2).

## The answer in brief

Each sentence points at the rows that carry it.

- **Vandenberg can carry the experiment's first look.** The Caltech network (code CI) has public stations 13.5, 16.5 and 32.6 km from the launch complex and outward to 350 km, each with three components at 100 samples a second (M1, M2, M4). Its data centre lists continuous records for one of them, CI.LCP, from 2003 to today (T5). The network itself reported one launch as detected, and named that station (L3a, L3d, L3e).
- **Only one source read here puts a launch on a public station, and it measures nothing.** The network's post names the station (L3d, L3e), which its metadata puts 32.6 km from the complex (section 3); it gives no amplitude, no lag and no second distance (L3a). The nearest other thing is a Sandia abstract that names a 2020 launch and ranges up to 400 km without saying where the launch was seen (A2). So the ladder is a thing to measure, not a thing known.
- **Florida and Texas are thin.** Outside one citizen network whose licence the owner has not accepted, the nearest public station found is 97.7 km from Cape Canaveral's pad and 152.6 km from Starbase (M10, M11). Florida's five stations within 350 km each have an infrasound channel beside the seismometer.
- **The catalogue is good enough for a window, and its documentation names no code for a scrub.** GCAT gives launch times in UTC to the second where available, defined as first motion, under CC-BY (L5a to L5d). Its column descriptions name no code for a scrubbed countdown; the nearest are a pad abort, kept only for crewed attempts, and Z, an entry that is not a launch (L5e). No catalogue file was opened, so what the lists hold is not known. One other site counts scrubs, inferred from its own schedule edits, with the records behind a paid interface (S1 to S3).
- **The label is a window, and it widens with distance:** 207 s long at 13.5 km, 539 s at 275 km, for sound (W7). On the speeds chosen here the ground path's window overlaps it near the pad and separates from it by 100 km. That is arithmetic on constants this study picked (W1 is a DECISION, W2 an ESTIMATE; W4), not a finding about the ground.
- **For D0's row D1:** three components and 100 samples a second are MEASURED from metadata (M2). Samples wider than 16 bits are now MEASURED: two of the 25 files fetched hold values that need 17 (M6). The converters' width is another question and is still BELIEVED (M6b): the metadata names sensors, not digitisers (M5), and the one gain a service gives fits 24 bits over 40 volts and three narrower converters equally (M9).
- **The proposed download** is 30 small requests to one data centre. Before anything was fetched their size was estimated, on believed inputs, at about 41 MB at most and half that typically, with one catalogue file of perhaps 23 MB; what came was 10.8 MB and 13.8 MB (E4 to E6, now MEASURED). With them go the catalogue's pad table, and either one 14.8 MB package with dependencies not yet sized (P1) or a short reader written here. It has since been fetched: what came, and its sizes, are in rows E1 to E6 and in D1b.

## Labels, and how this file is held

The labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. `verify/run.sh` refuses a register row without one.

- **READ** here means: the page was opened on 2026-11-23, and the words between straight double quotes are on it. Every quotation is at most 25 words and is listed in [quotes.tsv](d1/quotes.tsv). [check_quotes.py](d1/check_quotes.py) holds each one, letter for letter, against the saved copy of its page and against the row that uses it. The saved pages are not committed. A READ row's claim says how far the source reaches; a quotation is evidence for the words quoted and no more.
- **MEASURED** means a station service's text answer was read by [stations.py](d1/stations.py). Those answers are not committed either; [queries.tsv](d1/queries.tsv) lists every request, so they can be made again.
- **COMPUTED** rows cite a labelled line of [figures.py](d1/figures.py), or a table that stations.py prints.
- The station tables and the request table in this file are written by [splice.py](d1/splice.py) from those scripts' output. `splice.py --check` fails if a table here differs from what the scripts print.
- `<scratch>` is this parcel's scratch folder in the round's run folder, outside the repository: saved pages under `pages/`, station answers under `stations/`, availability answers under `availability/`, and `requests.log`, one request a line with its time.

Prose outside the registers is this parcel's reasoning. The gate does not check it.

## 1. The sources register

What each source says, and how far it reaches. Rows L1 to L7 are the plan's rows of the same number, now checked against the page.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| L1a | One Falcon 9 launch at Vandenberg was recorded by nine three-component seismometers, in a line that began about 7 km from the pad. Reach: the abstract only; one launch; a research deployment; nothing on where the recordings are kept | READ | https://arxiv.org/abs/2502.01982, the abstract, read 2026-11-23: "Nine passive three-component (3C) seismometers were deployed every 18.75 meters along a 45-degree line from the launch site" and "starting at the offset of about 7 km kilometers from the launch pad" | the paper's body, offered only as a PDF and not opened |
| L1b | A three-component recorder about 15 km away caught no discernible body-wave arrivals. Reach: body waves only; the abstract does not say whether this recorder was one of the nine or another, nor what else it caught | READ | https://arxiv.org/abs/2502.01982, the abstract, read 2026-11-23: "a 3C recorder placed approximately 15 km from the launch site did not capture any discernible body wave arrivals" | the paper's body |
| L1c | At 7 km that launch also drove surface waves, stronger than the body waves | READ | https://arxiv.org/abs/2502.01982, the abstract, read 2026-11-23: "Stronger Rayleigh waves were also recorded and inverted to give an S-velocity profile to a depth of 60 m." | the paper's body |
| L1d | The plan's row L1 adds that the paper cites earlier work finding a Falcon 9's airwaves detectable beyond 10 km. The abstract does not say this | BELIEVED | the search summary in [R1-search-2026-11-21.md](../plans/R1-search-2026-11-21.md); the abstract at https://arxiv.org/abs/2502.01982, read 2026-11-23, is silent on it | the paper's body |
| L2 | In one pad explosion, recorded by one broadband seismometer 1.4 km away, the seismic signal was mainly air-coupled Rayleigh waves of 5 to 23 Hz. Reach: an explosion during a static test, not a launch; one station; a conference abstract | READ | https://digitalcommons.usf.edu/geo_facpub/2182, the abstract, read 2026-11-23: "The seismic signal consists mainly of air-coupled Rayleigh waves with frequencies of 5-23 Hz." and "a broadband 3-component seismometer at the Astronaut Beach House, just 0.87 miles (1.4 km) from the launch pad" | the presentation; LCH-2's spectra |
| L3a | The Southern California network's operators reported detecting what was most likely a Falcon 9 launch from Vandenberg in September 2021. Reach: a news post, hedged in its own words; no distance and no amplitude | READ | https://tungsten2.gps.caltech.edu/?p=4154, the post's first paragraph, read 2026-11-23: "This week we detected what is most likely the energy translated to the ground by the thrusters of a Falcon 9 rocket during take-off." | LCH-2's look at the records of that hour |
| L3b | They say the signal differs from an earthquake's: no distinct phases, a different duration, and a different speed across the network. Reach: the post does not say what the speed was | READ | https://tungsten2.gps.caltech.edu/?p=4154, the post's third paragraph, read 2026-11-23: "it lacks distinct seismic phases, and differs in both the duration of the energy signal and the speed at which it reaches different sensors" | onset time against distance, measured by LCH-2 |
| L3c | That launch was at 8:56 pm local time on Monday 13 September. Reach: to the minute, in local time; the year 2021 is from the post's title and date | READ | https://tungsten2.gps.caltech.edu/?p=4154, the post's first paragraph, read 2026-11-23: "at 8:56 pm local time on Monday September 13th" | the catalogue's time for that launch |
| L3d | The post names one station on which the launch was visible, LCP, and says partner networks with equipment on the base recorded it too | READ | https://tungsten2.gps.caltech.edu/?p=4154, the post's second paragraph and then its first, read 2026-11-23: "our Live Seismograms Feed detected the launch, which is visible on the channel LCP near Santa Maria" and "a number of our partner seismic networks have equipment at the base itself" | the records |
| L3e | The network's teaching page on rocket launches gives that station as CI.LCP | READ | https://www.scsn.org/index.php/education-outreach-2/understanding-waveforms/rocket-launch/, the paragraph that begins Along with the static seismometer images, read 2026-11-23: "which is visible on the channel CI.LCP near Santa Maria" | the records |
| L4 | The Falcon 9 flew 46 times from Vandenberg in 2024 | MEASURED | the launch catalogue as fetched on 2026-11-23: the last line that `python docs/studies/d1/catalogue.py <data>` prints; D1b, row Q6f. Before the file was fetched this row was BELIEVED, from a search summary of a Space Force page that refused to be read (section 9) | a later release of the catalogue |
| L5a | GCAT is released under CC-BY, version 4.0 by its copyright notice, and may be used with a citation | READ | https://planet4589.org/space/gcat/index.html, the section Citing GCAT and the copyright notice, read 2026-11-23: "GCAT is released under the Creative Commons CC-BY licence." and "You are free to use the data in GCAT as long as you include a citation to it." and "Licence: CC-BY-4.0" | the page |
| L5b | Its launch lists give times in UTC to the nearest second where available. Reach: a statement about the whole database; one launch's precision is carried by its own entry (L5d) | READ | https://planet4589.org/space/gcat/web/launch/index.html, the Introduction, read 2026-11-23: "The database gives launch times in UTC to the nearest second where available." | the entries of the launches used |
| L5c | Its launch time is first motion, which can differ by a few seconds from sources that use ignition | READ | https://planet4589.org/space/gcat/web/launch/lcols.html, the entry Launch_Date, read 2026-11-23: "defined as first motion, so may differ by a few seconds from some sources which use rocket ignition" | a launch whose catalogue time differs from its webcast by more |
| L5d | A time's precision is carried by its written form: one second at best in this catalogue, wider when fields are left off or a question mark is added | READ | https://planet4589.org/space/gcat/web/intro/vague.html, read 2026-11-23: "In the General Catalog we only allow 1 second precision" and "We provide the ability to encode greater uncertainty by allowing rightmost fields to be omitted, and optionally a question mark symbol to be appended." | the entries of the launches used |
| L5e | The launch lists' column descriptions name no code for a scrubbed countdown. The codes nearest to one are a pad abort, ignition without a launch, kept only for human spaceflight attempts, and Z, an entry that is not a launch. Reach: the descriptions of the codes. No catalogue file was opened, so what the lists hold is not known | READ | https://planet4589.org/space/gcat/web/launch/lcols.html, the entry LaunchCode, read 2026-11-23: "A for pad abort (ignition but no launch, and no explosion; included only for human spaceflight launch attempts." and "Z means the entry is not a launch; for example launch tags used for satellites whose launch is unknown." | the launch list itself: an entry for a countdown that was called off |
| L5f | The launch lists held 76,034 entries on 2026-11-23, 7,001 of them orbital launches, by the catalogue's own count page | READ | https://planet4589.org/space/gcat/web/launch/count.html, read 2026-11-23: "O Orbital Launches 7001" and "Total 76034" | the file's own row count |
| L5g | Each launch carries a citation for the source of its launch time | READ | https://planet4589.org/space/gcat/web/launch/index.html, the Introduction, read 2026-11-23: "For each launch a citation (LTCite) is given for the existence of the launch and the source of the launch time." | the file |
| L6 | Sound in air at 20 degrees C travels at about 343 m/s. Reach: one temperature, still air, near the ground | READ | Wikipedia, the page Speed of sound, https://en.wikipedia.org/wiki/Speed_of_sound, the first paragraph, read 2026-11-23: "the speed of sound in air is about 343 m/s" | measured lags; a meteorological source |
| L7a | At Kennedy Space Center a temporary network's seismic and infrasound spectrograms showed a Doppler shift for every launch recorded, lower frequencies later. Reach: a conference abstract; no distance is given | READ | https://digitalcommons.usf.edu/geo_facpub/2184, the abstract, read 2026-11-23: "there is a clear Doppler shift in seismic and infrasound spectrograms from all launches, with lower frequencies occurring later in the recorded signal" | the presentation; LCH-2's spectrograms |
| L7b | That network's infrasound array recorded 8 launches and also 2 static tests, 1 aborted launch and 1 explosion, so engines at a pad make sound without a launch. Reach: the abstract says this of the infrasound array; it does not say the seismometer recorded them. From May 2016 the network was one station | READ | https://digitalcommons.usf.edu/geo_facpub/2184, the abstract, read 2026-11-23: "8 rocket launches have been recorded by the infrasound array, as well as 2 static tests, 1 aborted launch and 1 rocket explosion" and "In May 2016 the network was scaled back to a single station" | the presentation |
| A1 | Sound that reaches the ground can couple into it and travel on as a seismic wave, a ground-coupled airwave | READ | https://www.osti.gov/biblio/1891700, the abstract of a Sandia report of 2022, read 2026-11-23: "Ground-coupled airwaves are created from incident pressure waves traveling through the atmosphere that couple to the earth and transmit as a seismic wave" | the report |
| A2 | That report studied such signals from a 2020 rocket launch in Southern California among its sources, at ranges it gives as 50 to 100 km and up to 400 km. Reach: the abstract does not say at which range the launch was seen, on which stations, or whether the data are public; its stations paired an acoustic sensor with a seismometer | READ | https://www.osti.gov/biblio/1891700, the abstract, read 2026-11-23: "rocket motor fuel elimination events at the Utah Test and Training Range (UTTR) as well as a 2020 rocket launch in Southern California" and "from 50-100 km and up to 400 km" | the report, a PDF that was not opened |
| A3 | A study of the nuclear-test monitoring network's infrasound stations examined 7,637 infrasound signatures of 2009 to mid-2020, a period that included 1,001 launches, and examined only launches within 5,000 km of a station. Reach: a press release about the study; microbarometer arrays, not seismometers; it does not say how many of the 1,001 were within 5,000 km | READ | https://news.agu.org/press-release/scientists-identify-distinctive-deep-infrasound-rumbles-of-space-launches-audio/, read 2026-11-23: "They examined 7,637 infrasound signatures recorded at IMS stations from 2009 to mid-2020, a period that included 1,001 rocket launches." and "The team only examined rocket launches that occurred up to 5,000 kilometers from an IMS station" | the paper |
| A4 | It found signatures for up to 73 percent of what the page calls these rockets, 733 of them: by infrasound a launch is often, and not always, detectable far away. Reach: which launches the 73 percent is a share of is the page's wording, not checked against the paper; 733 is 73 percent of A3's 1,001 | READ | https://news.agu.org/press-release/scientists-identify-distinctive-deep-infrasound-rumbles-of-space-launches-audio/, read 2026-11-23: "The researchers found infrasonic signatures for up to 73% of these rockets, or 733." | the paper |
| A5 | After one refinery explosion a dense seismic network recorded three acoustic phases, at overall speeds of 332, 292 and 250 m/s. Reach: an explosion in Germany, one event, one day's atmosphere | READ | https://pmc.ncbi.nlm.nih.gov/articles/PMC6736795, the abstract (Sci Rep 2019, 9:13027), read 2026-11-23: "three separate acoustic phases with celerities of 332, 292, and 250 m/s" | the measured lags of launches |
| A6 | That sound was detectable on seismometers from 10 to 350 km away | READ | https://pmc.ncbi.nlm.nih.gov/articles/PMC6736795, the abstract, read 2026-11-23: "The infrasound signal is detectable on seismic stations within 10–350 km from the source" | LCH-2's ladder |
| A7 | How strongly a seismometer records sound depends on how it is installed | READ | https://pmc.ncbi.nlm.nih.gov/articles/PMC6736795, the abstract, read 2026-11-23: "Seismo-acoustic amplitudes are strongly affected by the type of seismic installation" | two stations at one distance giving the same strength |
| A8 | A Falcon 9's first stage burns for 162 seconds. Reach: an encyclopedia's figure for the vehicle version, not for any one flight | READ | Wikipedia, the page Falcon 9, https://en.wikipedia.org/wiki/Falcon_9, the infobox, First stage, read 2026-11-23: "Burn time FT: 162 seconds" | a flight's own timeline |
| A9 | Vandenberg's Space Launch Complex 4 holds a launch pad and, in the same complex, a pad where first stages land. Reach: the page gives no distance between the two in the part read | READ | Wikipedia, the page Vandenberg Space Launch Complex 4, https://en.wikipedia.org/wiki/Vandenberg_Space_Launch_Complex_4, the first paragraph, read 2026-11-23: "one for launch operations, and the other as Landing Zone 4 (LZ-4) for SpaceX landings" | the catalogue's pad table |
| C1 | Vandenberg's Space Launch Complex 4 is at 34.633 N, 120.613 W. Reach: one coordinate for the complex, to three decimals; the page does not say which pad it marks | READ | Wikipedia, the page Vandenberg Space Launch Complex 4, https://en.wikipedia.org/wiki/Vandenberg_Space_Launch_Complex_4, the Coordinates line, read 2026-11-23: "34.633°N 120.613°W" | the catalogue's pad table; a map |
| C2 | Cape Canaveral's Space Launch Complex 40 is at 28.5619 N, 80.5772 W | READ | Wikipedia, the page Cape Canaveral Space Launch Complex 40, https://en.wikipedia.org/wiki/Cape_Canaveral_Space_Launch_Complex_40, the Coordinates line, read 2026-11-23: "28.5619°N 80.5772°W" | the catalogue's pad table; a map |
| C3 | Kennedy Space Center's Launch Complex 39A is at 28.60833 N, 80.60444 W | READ | Wikipedia, the page Kennedy Space Center Launch Complex 39A, https://en.wikipedia.org/wiki/Kennedy_Space_Center_Launch_Complex_39A, the Coordinates line, read 2026-11-23: "28.60833°N 80.60444°W" | the catalogue's pad table; a map |
| C4 | Starbase, in Texas, is at 25.997 N, 97.157 W. Reach: the page's coordinate for the whole site; which structure it marks is not established | READ | Wikipedia, the page SpaceX Starbase, https://en.wikipedia.org/wiki/SpaceX_Starbase, the Coordinates line, read 2026-11-23: "25.997°N 97.157°W" | the catalogue's pad table; a map |
| K1 | A channel code's first letter gives its sampling band: H is 80 to under 250 samples a second and B is 10 to under 80, both for sensors whose response reaches periods of 10 s or longer | READ | https://docs.fdsn.org/projects/source-identifiers/en/v1.0/channel-codes.html, the Band Code table, read 2026-11-23: "H High Broadband >= 80 to < 250 >= 10 sec" and "B Broadband >= 10 to < 80 >= 10 sec" | the page |
| K2 | The second letter gives the instrument: H a high-gain seismometer, N an accelerometer, D a pressure sensor. After D, a third letter F means infrasound and O an outside gauge | READ | https://docs.fdsn.org/projects/source-identifiers/en/v1.0/channel-codes.html, the sections Seismometer and Pressure, read 2026-11-23: "H High Gain Seismometer L Low Gain Seismometer M Mass Position Seismometer N Accelerometer" and "Source Code D Subsource Code O Outside I Inside D Down hole F Infrasound" | the page |
| K3 | The miniSEED format carries samples as 16-bit or 32-bit integers, as floats, or as Steim-compressed integers. Reach: version 3 of the format; what one archive file uses is written in the file | READ | https://docs.fdsn.org/projects/miniseed3/en/latest/data-encodings.html, the code table, read 2026-11-23: "3 32-bit integer (two’s complement), little endian byte order" and "11 Steim-2 integer compression, big endian byte order" | the encoding field of a fetched record |
| T1 | The Caltech data centre (SCEDC) asks for a citation for data taken from it | READ | https://scedc.caltech.edu/about/citation.html, read 2026-11-23: "Please use the following citation to cite data downloaded from SCEDC: SCEDC (2013): Southern California Earthquake Center. Caltech.Dataset. doi: 10.7909/C3WD3xH1" | the page |
| T2 | SCEDC asks users to consider its cloud bucket first, and users of its web services to keep to three sessions at once. Its service front page carries no statement that use accepts terms | READ | https://service.scedc.caltech.edu/, the paragraph above the service table, read 2026-11-23: "please be limit your downloads to 3 concurrent sessions" and, just before it, "please consider first using our AWS Open Dataset" | the page |
| T3 | SCEDC says it has archived continuous waveforms of 80 samples a second and faster since 2008, and all continuous waveforms since 2010 | READ | https://scedc.caltech.edu/data/waveform.html, Digital Seismograms, read 2026-11-23: "Archival of continuous waveforms 80 sps and greater began in 2008 and by 2010, all continuous waveforms have been archived at the SCEDC." | T4; an availability listing |
| T4 | Another SCEDC page lists the 100-sample channels HH as archived Triggered and the 40-sample channels BH as Continuous. It disagrees with T3 | READ | https://scedc.caltech.edu/station/seed.html, the channel table, read 2026-11-23: "HH[ZNE] Triggered High Broadband (80 or 100 sps); Seismic data: High gain" and "BH[ZNE] Continuous Broadband (20 or 40 sps); Seismic data: High gain" | T5 |
| T5 | For station CI.LCP, SCEDC lists continuous records of HHZ at 100 samples a second from 2003 to the day of the study, and of BHZ at 40 from 2009. Reach: an extent, earliest to latest. It does not show gaps: the listing's own count of time spans reads NA | READ | https://service.scedc.caltech.edu/fdsnws/availability/1/extent?network=CI&station=LCP&asset=continuous, requested 2026-11-23 under the lead's third ruling: "CI LCP -- HHZ 100.00 2003/02/22 05:59:57.430000 2026/11/23 07:49:28.000000 NA NA OPEN" and "CI LCP -- BHZ 40.00 2009/01/01 00:59:58.500000 2026/11/23 07:47:22.000000 NA NA OPEN" | the first waveform request for that station and date |
| T6 | SCEDC's availability page says its listing of gap-free spans stops in 2020: April in the line quoted, August in another line of the same page. If so it cannot say whether a 2021 window has gaps | READ | https://service.scedc.caltech.edu/fdsnws/availability/1/, the list under the heading for the query method, read 2026-11-23: "/query continuous records (*H*, *N* and *L*) from Jan 01 2011 - April 28, 2020" | the service answering a query for a later date |
| T7 | SCEDC's waveform service returns miniSEED only, and answers a request only up to a stated number of samples | READ | https://service.scedc.caltech.edu/fdsnws/dataselect/1/, the parameter list and the section Valid request time windows, read 2026-11-23: "Only miniSEED is supported as of now." and "(timewindow * sr + 100) <= 400 * 1024 * 1024 / 4" | the service |
| T8 | SCEDC also publishes its continuous archive as day-long files in a public cloud bucket, with 100-sample broadband records from 2008 | READ | https://scedc.caltech.edu/data/cloud.html, read 2026-11-23: "AWS Bucket Name and Region: s3://scedc-pds; us-west-2" and "Continuous archive of 100 sps broadband begins in 2008." | the bucket's listing |
| T9 | SCEDC lists a second waveform service whose output formats include plain text | READ | https://service.scedc.caltech.edu/, the SCEDCWS table, the row webstp, read 2026-11-23: "continuous waveform time series triggered waveform time series miniSEED SAC ASCII text" | that service's own page, which was not opened |
| T10 | The Berkeley data centre (NCEDC) asks for acknowledgement. Its service front page, https://service.ncedc.org/, carries no statement that use accepts terms | READ | https://ncedc.org/, the first section, read 2026-11-23: "If you use data from the NCEDC, we ask that you acknowledge both the NCEDC and the organizations that contributed the data." | the pages |
| T11 | EarthScope's services are used under terms that a visit accepts | READ | https://service.earthscope.org/, read 2026-11-23: "These services may be used under EarthScope Terms of Service"; and https://www.earthscope.org/terms-of-service/, the first paragraph, read 2026-11-23: "By visiting (in any manner) the Website (“Visitor”) you accept these terms and conditions" | the pages |
| T12 | Raspberry Shake's data service is used under a licence that use accepts. The licence makes its archive free to hobbyists, teachers, researchers and institutes, and sends commercial users to negotiate | READ | https://data.raspberryshake.org/, read 2026-11-23: "By using this service, you automatically accept these license terms"; and https://raspberryshake.org/license/, the section on legacy and FDSN web services, read 2026-11-23: "Free for hobbyists, school teachers, researchers and geophysical institutes." | the pages |
| T13 | That licence forbids redistributing its waveform data from one's own server | READ | https://raspberryshake.org/license/, Redistribution of Legacy Data, read 2026-11-23: "It is strictly prohibited to redistribute Raspberry Shake waveform data obtained from https://data.raspberryshake.org/fdsnws/ via your own FDSN Web Service, data center or server" | the page |
| T14 | The Southern California network's public site asks permission for reproduction. This study takes short attributed quotations from it and nothing else | READ | https://www.scsn.org/index.php/education-outreach-2/understanding-waveforms/rocket-launch/, the footer, read 2026-11-23: "Permission required to reproduce any portion of this site." | the page |
| T15 | SCEDC's earthquake catalogue can be asked for as text | READ | https://service.scedc.caltech.edu/fdsnws/event/1/, the description, read 2026-11-23: "By default, results are returned in QuakeML format, but may also be requested in text format." | the service |
| S1 | One public site keeps a record of launch attempts since December 2017 and calls an attempt a scrub when it was called off within 30 minutes of its target time, or after it | READ | https://www.rocketlaunch.live/scrub-statistics, Methodology, read 2026-11-23: "classified as a scrub (called off within 30 minutes of the target time, or after it) or a postponement (called off earlier that day)" | the site's records |
| S2 | Its attempt records before July 2026 are inferred from the site's own edits to its schedule, not taken from announcements | READ | https://www.rocketlaunch.live/scrub-statistics, About this data, read 2026-11-23: "reconstructed from this site's own edit history of schedule changes rather than official announcements" | the site's records |
| S3 | Full access to that site's records is for paying members. Whether a scrubbed attempt's target time can be read without paying is not established | READ | https://www.rocketlaunch.live/api, Summary, read 2026-11-23: "Full access to the API is available to our Premium Members only." | a launch's own page on that site |
| S4 | By its count the Falcon 9 had 149 scrubbed attempts across 579 launches, and Vandenberg had 221 launches at 0.70 delays each. Reach: inferred counts (S2); the column names are the page's | READ | https://www.rocketlaunch.live/scrub-statistics, the tables by vehicle and by launch site, read 2026-11-23: "Falcon 9 579 149 190 0.59" and "Vandenberg SFB 221 6 1 18 33% 0.70" | the site's records |
| P1 | The obspy package's build for this desktop's Python is 14.8 MB, under the LGPL version 3. Reach: the one file; what else it needs installed was not on the part of the page read | READ | https://pypi.org/project/obspy/, the release files and the sidebar, read 2026-11-23: "obspy-1.5.2-cp312-cp312-win_amd64.whl 14.8 MB" and "GNU Lesser General Public License v3 (LGPLv3)" | the file's size when fetched; its declared requirements |

**What the lead asked to have confirmed** (the brief's four findings), against these rows:

1. *That a launch reaches a seismometer mostly as sound, lagging by about 2.9 s per km.* **Not confirmed for launches; plausible.** For it: an explosion at 1.4 km was mainly air-coupled (L2); sound couples into the ground (A1); one explosion's sound was on seismometers out to 350 km at 332, 292 and 250 m/s (A5, A6); the network says a launch's energy crosses it at a different speed from an earthquake's, without giving the speed (L3b). Against it as the whole story: at 7 km a launch drove body waves and stronger surface waves through the ground (L1a, L1c). And 2.9 s per km is the fast edge: A5's three speeds give 3.01, 3.42 and 4.00 s per km (W5). No source read here measures a launch's lag against distance. The first look does, for one launch: its onsets at four stations give 3.02 s per km (D1b, row Q3b, a measure chosen after looking).
2. *That Southern California has many public stations within a few hundred km of Vandenberg, served by a public data centre.* **Confirmed** (M1, T1 to T3), with the limit that none is within 10 km on 2026-11-23. On 2021-09-14 one was (M4b).
3. *That GCAT's times are precise enough to predict a window.* **Confirmed for the catalogue as documented** (L5b to L5d): the second, first motion, with each entry carrying its own precision. When this was written no catalogue file had been opened. Since then: this launch's entry is to the second (D1b, row Q6a), and 35 of 2024's 46 from the same pad are (D1b, row Q6f).
4. *That seismic records are three components and wider than 16 bits.* **Three components: confirmed** (M2). **Wider than 16 bits: confirmed for the samples** (M6: two fetched files need 17 bits). The converters' own width is not established (M6b, M9).

## 2. The launch sites

Four coordinates for three sites, in [sites.tsv](d1/sites.tsv), each from the row named. Kennedy's pad 39A and the Cape's pad 40 are a few km apart and share one set of station answers.

| site id | site | latitude | longitude | row |
|---|---|---|---|---|
| VSFB | Vandenberg, Space Launch Complex 4 | 34.633 | -120.613 | C1 |
| CCSFS | Cape Canaveral, Space Launch Complex 40 | 28.5619 | -80.5772 | C2 |
| KSC | Kennedy Space Center, Launch Complex 39A | 28.60833 | -80.60444 | C3 |
| STARBASE | Starbase, Boca Chica, Texas | 25.997 | -97.157 | C4 |

**Limits.** Each is one point for a complex. Vandenberg has other pads, some of them many km from this one (BELIEVED; no page read here lists them), so a distance below is to Complex 4 and to nothing else. The catalogue has a table of pads with coordinates (its file `lp.tsv`, named on the index page read for L5b; not opened). An experiment uses the pad of each launch, from that table.

## 3. Stations by distance

**How the tables are made.** stations.py reads the saved text answers of the station services, keeps channel epochs open on the date asked about, and computes each station's distance from the site as a geodesic on the WGS-84 ellipsoid. Its self-test (`python docs/studies/d1/stations.py --self-test`, 9 cases, printed `OK self-test: 9 cases` on 2026-11-23) checks the distance against two cases worked by hand and against a spherical formula, and checks that swapped arguments are caught. A coordinate is whatever the service returned. A station appears here when a service describes it; **a row is not evidence that any waveform exists.**

**One service is held back; a second was, until the owner ruled.** Each said, on a page read only after it had been queried, that using it accepts terms. Accepting terms is the owner's to do, so the lead held both (ledger, 2026-11-23, 07:17 and 07:20).

- *EarthScope* (T11). Six station requests had been made before its terms were read. On 2026-11-23 Logan allowed it (ledger, 07:59), and its rows are in the tables below from then on. The acknowledgement its terms ask for is in PROVENANCE.md.
- *Raspberry Shake*, network code AM (T12, T13). Three station requests had been made before its terms were read. It is still held: its answers stay in `<scratch>`, and stations.py leaves the network out by name and cannot be told to read it. What its answers show is given below in prose only, with rounded distances, as the lead ruled.

<!-- d1:stations:today:begin -->

### VSFB: Vandenberg Space Launch Complex 4 (SLC-4E launch pad, SLC-4W landing zone)

Site at 34.63300, -120.61300. Responses used: `scedc-vsfb-channel.txt` (12816 channel epochs open on 2026-11-23); `ncedc-vsfb-channel.txt` (6735 channel epochs open on 2026-11-23); `es-vsfb-channel.txt` (6049 channel epochs open on 2026-11-23). Responses held and not opened: `rs-vsfb-channel.txt`.

Stations with a seismic or pressure channel open on 2026-11-23: 2845.

| station | lat | lon | km | bearing from site | seismic channels @ samples/s | pressure channels @ samples/s | metadata served by |
|---|---|---|---|---|---|---|---|
| CI.GATR | 34.5527 | -120.5024 | 13.5 | 131 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | EarthScope, NCEDC, SCEDC |
| CE.26456 | 34.6383 | -120.4569 | 14.3 | 088 | HN[ENZ]@100, HN[ENZ]@200 | none | NCEDC, SCEDC |
| CI.LOC | 34.6907 | -120.4469 | 16.5 | 067 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | EarthScope, NCEDC, SCEDC |
| SB.VAFB2 | 34.8449 | -120.5831 | 23.7 | 007 | HH[ENZ]@200, HN[ENZ]@200 | none | EarthScope, SCEDC |
| SB.VAFB1 | 34.8579 | -120.5986 | 25.0 | 003 | HH[ENZ]@200, HN[ENZ]@200 | none | EarthScope, SCEDC |
| CE.26971 | 34.5189 | -120.3289 | 29.0 | 116 | HN[ENZ]@100, HN[ENZ]@200 | none | NCEDC, SCEDC |
| PG.PSD | 34.9022 | -120.6217 | 29.9 | 358 | EH[ENZ]@100, HN[ENZ]@100 | none | NCEDC, SCEDC |
| CE.26693 | 34.8643 | -120.4437 | 30.0 | 031 | HN[ENZ]@100, HN[ENZ]@200 | none | NCEDC, SCEDC |
| CI.LCP | 34.7355 | -120.2800 | 32.6 | 069 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | EarthScope, NCEDC, SCEDC |
| CE.26152 | 34.9188 | -120.4415 | 35.4 | 026 | HN[ENZ]@100, HN[ENZ]@200 | none | NCEDC, SCEDC |
| CI.BUE | 34.6130 | -120.1968 | 38.2 | 093 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | EarthScope, NCEDC, SCEDC |
| CI.SQC | 34.8665 | -120.2944 | 39.0 | 048 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | EarthScope, NCEDC, SCEDC |
| CE.26472 | 34.9501 | -120.4123 | 39.7 | 027 | HN[ENZ]@200 | none | NCEDC, SCEDC |
| CI.GFS | 34.4766 | -120.2144 | 40.5 | 115 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | EarthScope, SCEDC |
| CE.26334 | 34.9673 | -120.4261 | 40.8 | 025 | HN[ENZ]@100, HN[ENZ]@200 | none | NCEDC, SCEDC |
| CI.NJQ | 34.5341 | -120.1774 | 41.4 | 105 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | EarthScope, NCEDC, SCEDC |
| CI.RSI | 34.8519 | -120.2087 | 44.3 | 057 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | EarthScope, SCEDC |
| CI.SMW | 35.0111 | -120.4100 | 45.9 | 024 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | EarthScope, NCEDC, SCEDC |
| CI.SYN | 34.6072 | -120.0696 | 49.9 | 093 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | EarthScope, NCEDC, SCEDC |
| PG.NPD | 35.0863 | -120.4725 | 51.9 | 014 | EH[ENZ]@100, HN[ENZ]@100 | none | NCEDC, SCEDC |
| CI.MAN | 34.8937 | -120.0807 | 56.7 | 059 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | EarthScope, SCEDC |
| CE.36343 | 35.1440 | -120.6403 | 56.7 | 357 | HN[ENZ]@100, HN[ENZ]@200 | none | NCEDC, SCEDC |
| RE.BRBY2 | 34.5895 | -119.9865 | 57.7 | 095 | EN[12Z]@100, HN[12Z]@100 | none | EarthScope |
| RE.BRBY1 | 34.5866 | -119.9821 | 58.1 | 095 | EN[12Z]@100, HN[12Z]@100 | none | EarthScope |
| RE.BRBY | 34.5867 | -119.9812 | 58.2 | 095 | EN[12Z]@100, HN[12Z]@100 | none | EarthScope |
| CI.FIG | 34.7283 | -119.9880 | 58.2 | 079 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | EarthScope, NCEDC, SCEDC |
| RE.BRBY3 | 34.5824 | -119.9806 | 58.3 | 095 | EN[12Z]@100, HN[12Z]@100 | none | EarthScope |
| BK.PABC | 35.1588 | -120.6400 | 58.4 | 358 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | EarthScope, NCEDC, SCEDC |
| CI.SYP | 34.5277 | -119.9783 | 59.4 | 101 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | EarthScope, NCEDC, SCEDC |
| NC.PBIB | 35.1614 | -120.4752 | 60.0 | 012 | EH[Z]@100, HN[ENZ]@100, HN[ENZ]@200 | none | EarthScope, NCEDC, SCEDC |

| distance band, km | stations | of them with a pressure channel | networks |
|---|---|---|---|
| 0 to 10 | 0 | 0 | none |
| 10 to 25 | 5 | 0 | CE 1, CI 2, SB 2 |
| 25 to 50 | 14 | 0 | CE 5, CI 8, PG 1 |
| 50 to 100 | 65 | 1 | BK 3, CE 13, CI 21, CJ 1, NC 5, NP 2, PG 10, RE 4, SB 6 |
| 100 to 200 | 430 | 9 | BK 17, BP 1, CE 141, CI 74, CJ 98, GM 7, HZ 1, NC 44, NP 30, PB 9, PG 1, RE 2, WR 5 |
| 200 to 350 | 2331 | 8 | AZ 2, BK 26, CE 393, CI 194, CJ 1438, FA 10, GM 1, GS 2, LB 1, NC 110, NP 128, PB 8, RE 8, SB 1, WR 9 |

Stations within 350 km with a pressure channel: 18.

| station | km | pressure channels @ samples/s | seismic channels @ samples/s | metadata served by |
|---|---|---|---|---|
| SB.CPSLO | 74.4 | infrasound HD[F]@100, LD[F]@1 | BH[ENZ]@20, HH[ENZ]@100, HN[ENZ]@200 | EarthScope, NCEDC, SCEDC |
| PB.CHL1 | 123.1 | barometer LD[O]@1, RD[O]@0.00333 | none | SCEDC |
| PB.B901 | 124.8 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B079 | 125.7 | barometer LD[DO]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B900 | 129.4 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B072 | 135.1 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B078 | 135.9 | barometer LD[DO]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B075 | 144.1 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B076 | 146.0 | barometer LD[DO]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B073 | 146.3 | barometer LD[DO]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B065 | 246.8 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B067 | 251.8 | barometer LD[DO]@1, RD[O]@0.0005556, VD[D]@0.1 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B058 | 255.8 | barometer LD[DO]@1, RD[O]@0.0005556, VD[D]@0.1 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B066 | 262.2 | barometer LD[DO]@1, RD[O]@0.0005556, VD[D]@0.1 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B921 | 306.1 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B918 | 309.7 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B917 | 317.9 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |
| PB.B916 | 318.5 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | EarthScope, NCEDC, SCEDC |

The ladder: CI stations with HHE, HHN, HHZ out to 350 km. The first rung is the nearest; each next rung is the nearest station at least 1.5 times farther than the rung before. Windows are seconds after the catalogue's launch time.

| station | lat | lon | km | bearing from site | sound, earliest | sound, latest | ground, earliest | ground, latest |
|---|---|---|---|---|---|---|---|---|
| CI.GATR | 34.5527 | -120.5024 | 13.5 | 131 | 34 | 241 | -3 | 194 |
| CI.LCP | 34.7355 | -120.2800 | 32.6 | 069 | 89 | 321 | 0 | 207 |
| CI.SYN | 34.6072 | -120.0696 | 49.9 | 093 | 140 | 393 | 3 | 218 |
| CI.BCH | 35.1853 | -120.0851 | 78.0 | 038 | 221 | 510 | 7 | 237 |
| CI.CDM | 34.3685 | -119.3414 | 120.4 | 104 | 344 | 687 | 14 | 265 |
| CI.LAT | 34.0445 | -118.7764 | 181.2 | 111 | 520 | 940 | 23 | 306 |
| CI.SUN | 34.2102 | -117.6942 | 272.4 | 099 | 784 | 1320 | 37 | 367 |

### CCSFS: Cape Canaveral Space Launch Complex 40

Site at 28.56190, -80.57720. Responses used: `es-cape-channel.txt` (186 channel epochs open on 2026-11-23). Responses held and not opened: `rs-cape-channel.txt`.

Stations with a seismic or pressure channel open on 2026-11-23: 9.

| station | lat | lon | km | bearing from site | seismic channels @ samples/s | pressure channels @ samples/s | metadata served by |
|---|---|---|---|---|---|---|---|
| IU.DWPF | 28.1103 | -81.4327 | 97.7 | 239 | BH[12Z]@40, HH[12Z]@100, HN[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.060A | 27.0361 | -80.3618 | 170.4 | 173 | HH[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.656A | 29.3689 | -82.5348 | 210.7 | 296 | HH[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.456A | 30.7248 | -82.0223 | 277.6 | 330 | HH[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.061Z | 25.8657 | -80.9070 | 300.5 | 186 | HH[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.257A | 31.9746 | -81.0261 | 380.8 | 354 | HH[12Z]@100, HN[12Z]@200 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |

| distance band, km | stations | of them with a pressure channel | networks |
|---|---|---|---|
| 0 to 10 | 0 | 0 | none |
| 10 to 25 | 0 | 0 | none |
| 25 to 50 | 0 | 0 | none |
| 50 to 100 | 1 | 1 | IU 1 |
| 100 to 200 | 1 | 1 | N4 1 |
| 200 to 350 | 3 | 3 | N4 3 |

Stations within 350 km with a pressure channel: 5.

| station | km | pressure channels @ samples/s | seismic channels @ samples/s | metadata served by |
|---|---|---|---|---|
| IU.DWPF | 97.7 | infrasound BD[F]@40; barometer LD[O]@1 | BH[12Z]@40, HH[12Z]@100, HN[12Z]@100 | EarthScope |
| N4.060A | 170.4 | infrasound BD[F]@40; barometer LD[O]@1 | HH[12Z]@100 | EarthScope |
| N4.656A | 210.7 | infrasound BD[F]@40; barometer LD[O]@1 | HH[12Z]@100 | EarthScope |
| N4.456A | 277.6 | infrasound BD[F]@40; barometer LD[O]@1 | HH[12Z]@100 | EarthScope |
| N4.061Z | 300.5 | infrasound BD[F]@40; barometer LD[O]@1 | HH[12Z]@100 | EarthScope |

No ladder: no CI station with HHE, HHN, HHZ is listed within 350 km of this site.

### KSC: Kennedy Space Center Launch Complex 39A

Site at 28.60833, -80.60444. Responses used: `es-cape-channel.txt` (186 channel epochs open on 2026-11-23). Responses held and not opened: `rs-cape-channel.txt`.

Stations with a seismic or pressure channel open on 2026-11-23: 9.

| station | lat | lon | km | bearing from site | seismic channels @ samples/s | pressure channels @ samples/s | metadata served by |
|---|---|---|---|---|---|---|---|
| IU.DWPF | 28.1103 | -81.4327 | 98.2 | 236 | BH[12Z]@40, HH[12Z]@100, HN[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.060A | 27.0361 | -80.3618 | 175.9 | 172 | HH[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.656A | 29.3689 | -82.5348 | 206.1 | 295 | HH[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.456A | 30.7248 | -82.0223 | 271.8 | 330 | HH[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.061Z | 25.8657 | -80.9070 | 305.4 | 186 | HH[12Z]@100 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |
| N4.257A | 31.9746 | -81.0261 | 375.4 | 354 | HH[12Z]@100, HN[12Z]@200 | infrasound BD[F]@40; barometer LD[O]@1 | EarthScope |

| distance band, km | stations | of them with a pressure channel | networks |
|---|---|---|---|
| 0 to 10 | 0 | 0 | none |
| 10 to 25 | 0 | 0 | none |
| 25 to 50 | 0 | 0 | none |
| 50 to 100 | 1 | 1 | IU 1 |
| 100 to 200 | 1 | 1 | N4 1 |
| 200 to 350 | 3 | 3 | N4 3 |

Stations within 350 km with a pressure channel: 5.

| station | km | pressure channels @ samples/s | seismic channels @ samples/s | metadata served by |
|---|---|---|---|---|
| IU.DWPF | 98.2 | infrasound BD[F]@40; barometer LD[O]@1 | BH[12Z]@40, HH[12Z]@100, HN[12Z]@100 | EarthScope |
| N4.060A | 175.9 | infrasound BD[F]@40; barometer LD[O]@1 | HH[12Z]@100 | EarthScope |
| N4.656A | 206.1 | infrasound BD[F]@40; barometer LD[O]@1 | HH[12Z]@100 | EarthScope |
| N4.456A | 271.8 | infrasound BD[F]@40; barometer LD[O]@1 | HH[12Z]@100 | EarthScope |
| N4.061Z | 305.4 | infrasound BD[F]@40; barometer LD[O]@1 | HH[12Z]@100 | EarthScope |

No ladder: no CI station with HHE, HHN, HHZ is listed within 350 km of this site.

### STARBASE: SpaceX Starbase launch site, Boca Chica, Texas

Site at 25.99700, -97.15700. Responses used: `es-starbase-channel.txt` (307 channel epochs open on 2026-11-23). Responses held and not opened: `rs-starbase-channel.txt`.

Stations with a seismic or pressure channel open on 2026-11-23: 53.

| station | lat | lon | km | bearing from site | seismic channels @ samples/s | pressure channels @ samples/s | metadata served by |
|---|---|---|---|---|---|---|---|
| 4T.FMR3 | 26.5808 | -98.5414 | 152.6 | 295 | CH[12Z]@250, HH[ENZ]@200 | none | EarthScope |
| 4T.FMR1 | 26.6028 | -98.5675 | 156.0 | 296 | CH[12Z]@250 | none | EarthScope |
| 4T.FMR2 | 26.5733 | -98.5845 | 156.2 | 295 | CH[12Z]@250 | none | EarthScope |
| US.KVTX | 27.5459 | -97.8929 | 186.6 | 337 | HH[12Z]@100, HN[12Z]@200 | none | EarthScope |
| TX.HBVL | 27.0650 | -98.6696 | 191.6 | 309 | HH[12Z]@200 | none | EarthScope |
| TX.EF09 | 27.8873 | -98.6011 | 253.8 | 326 | CH[ENZ]@250 | none | EarthScope |

| distance band, km | stations | of them with a pressure channel | networks |
|---|---|---|---|
| 0 to 10 | 0 | 0 | none |
| 10 to 25 | 0 | 0 | none |
| 25 to 50 | 0 | 0 | none |
| 50 to 100 | 0 | 0 | none |
| 100 to 200 | 5 | 0 | 4T 3, TX 1, US 1 |
| 200 to 350 | 24 | 1 | 2T 18, N4 1, TX 5 |

Stations within 350 km with a pressure channel: 1.

| station | km | pressure channels @ samples/s | seismic channels @ samples/s | metadata served by |
|---|---|---|---|---|
| N4.735B | 323.2 | infrasound BD[F]@40; barometer LD[O]@1 | HH[12Z]@100 | EarthScope |

No ladder: no CI station with HHE, HHN, HHZ is listed within 350 km of this site.

Window parameters: sound 0.240 to 0.345 km/s; ground 1.5 to 6.5 km/s; a source lasting 180 s; 5 s either side for the catalogue's time.
Networks left out: SY (synthetic seismograms, not instruments); AM (held: its service says use accepts a licence, which is the owner's to accept).

<!-- d1:stations:today:end -->

**Florida and Texas.** Their tables above come from EarthScope's answers alone: no other allowed service was asked about those sites (M10, M11).

**The citizen network, in prose** (MEASURED from the held answers; no row is committed). Raspberry Shake's network has stations nearer the Texas and Florida pads than any other public network found: under 10 km from Starbase and from Cape Canaveral's pad, and tens of km for a few more in Florida. Its use needs the owner's own acceptance of its licence (T12), which also bars passing its waveform data on (T13). No station of it is used anywhere in this study's proposal.

**The data centres and their terms** (rows T1 to T13; [PROVENANCE.md](../../PROVENANCE.md) has them as read):

| data centre | serves | asks for | acceptance by use | rows |
|---|---|---|---|---|
| SCEDC, Caltech | the CI network's waveforms and metadata; metadata for neighbours | a citation; at most 3 sessions at once | none stated on the pages read | T1, T2, T3 |
| NCEDC, Berkeley | northern California networks | acknowledgement | none stated on the pages read | T10 |
| EarthScope | national and global networks | acknowledgement; no load beyond a person's | yes: a visit accepts its terms. The owner allowed it on 2026-11-23 | T11 |
| Raspberry Shake | its own citizen network, AM | a licence: free to hobbyists, teachers, researchers; no passing on of waveforms | yes: use accepts its licence. Still held | T12, T13 |

**The stations on the day of the one launch whose time is known.** The network's post (L3c) gives a launch on 2021-09-13 local time. The block below is the same computation for channel epochs open on 2021-09-14, from one more request to SCEDC.

<!-- d1:stations:2021:begin -->

### VSFB: Vandenberg Space Launch Complex 4 (SLC-4E launch pad, SLC-4W landing zone)

Site at 34.63300, -120.61300. Responses used: `scedc-vsfb-20210914-channel.txt` (7581 channel epochs open on 2021-09-14). Responses held and not opened: none.

Stations with a seismic or pressure channel open on 2021-09-14: 1483.

| station | lat | lon | km | bearing from site | seismic channels @ samples/s | pressure channels @ samples/s | metadata served by |
|---|---|---|---|---|---|---|---|
| NC.PTQ | 34.5819 | -120.5740 | 6.7 | 148 | EH[Z]@100 | none | SCEDC |
| CI.GATR | 34.5527 | -120.5024 | 13.5 | 131 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| CE.26456 | 34.6383 | -120.4569 | 14.3 | 088 | HN[ENZ]@200 | none | SCEDC |
| CI.LOC | 34.6907 | -120.4469 | 16.5 | 067 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | SCEDC |
| SB.VAFB2 | 34.8449 | -120.5831 | 23.7 | 007 | HH[ENZ]@200, HN[ENZ]@200 | none | SCEDC |
| SB.VAFB1 | 34.8579 | -120.5986 | 25.0 | 003 | HH[ENZ]@200, HN[ENZ]@200 | none | SCEDC |
| CE.26971 | 34.5189 | -120.3289 | 29.0 | 116 | HN[ENZ]@200 | none | SCEDC |
| NC.PML | 34.8947 | -120.6093 | 29.0 | 001 | EH[Z]@100 | none | SCEDC |
| PG.PSD | 34.9022 | -120.6217 | 29.9 | 358 | EH[ENZ]@100, HN[ENZ]@100 | none | SCEDC |
| CE.26693 | 34.8644 | -120.4437 | 30.0 | 031 | HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| CI.LCP | 34.7355 | -120.2800 | 32.6 | 069 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| CE.26152 | 34.9188 | -120.4415 | 35.4 | 026 | HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| CI.BUE | 34.6130 | -120.1968 | 38.2 | 093 | EH[Z]@100, HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| CI.SQC | 34.8665 | -120.2944 | 39.0 | 048 | EH[Z]@100, HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| CE.26472 | 34.9501 | -120.4123 | 39.7 | 027 | HN[ENZ]@200 | none | SCEDC |
| CI.GFS | 34.4766 | -120.2144 | 40.5 | 115 | EH[Z]@100, HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| CE.26334 | 34.9673 | -120.4261 | 40.8 | 025 | HN[ENZ]@200 | none | SCEDC |
| CI.NJQ | 34.5341 | -120.1774 | 41.4 | 105 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| CI.RSI | 34.8519 | -120.2087 | 44.3 | 057 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| CI.SMW | 35.0111 | -120.4100 | 45.9 | 024 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | SCEDC |
| CI.SYN | 34.6072 | -120.0696 | 49.9 | 093 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | SCEDC |
| PG.NPD | 35.0863 | -120.4725 | 51.9 | 014 | EH[ENZ]@100, HN[ENZ]@100 | none | SCEDC |
| CI.FIG | 34.7283 | -119.9880 | 58.2 | 079 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| BK.PABC | 35.1588 | -120.6400 | 58.4 | 358 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | none | SCEDC |
| CI.SYP | 34.5277 | -119.9783 | 59.4 | 101 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100, HN[ENZ]@200 | none | SCEDC |
| NC.PBIB | 35.1614 | -120.4752 | 60.0 | 012 | EH[Z]@100, HN[ENZ]@100 | none | SCEDC |

| distance band, km | stations | of them with a pressure channel | networks |
|---|---|---|---|
| 0 to 10 | 1 | 0 | NC 1 |
| 10 to 25 | 5 | 0 | CE 1, CI 2, SB 2 |
| 25 to 50 | 15 | 0 | CE 5, CI 8, NC 1, PG 1 |
| 50 to 100 | 49 | 0 | BK 3, CE 11, CI 16, CJ 1, NC 5, NP 2, PG 10, SB 1 |
| 100 to 200 | 306 | 9 | BK 13, CE 140, CI 69, CJ 2, NC 39, NP 29, PB 9, PG 3, WR 2 |
| 200 to 350 | 1107 | 9 | AZ 2, BK 18, CE 374, CI 181, CJ 282, GS 3, NC 107, NP 124, PB 8, WR 8 |

Stations within 350 km with a pressure channel: 18.

| station | km | pressure channels @ samples/s | seismic channels @ samples/s | metadata served by |
|---|---|---|---|---|
| PB.CHL1 | 123.1 | barometer LD[O]@1, RD[O]@0.00333 | none | SCEDC |
| PB.B901 | 124.8 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B079 | 125.7 | barometer LD[D]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B900 | 129.4 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B072 | 135.1 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B078 | 135.9 | barometer LD[DO]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B075 | 144.1 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B076 | 146.0 | barometer LD[DO]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B073 | 146.3 | barometer LD[D]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| CI.PASC | 229.0 | barometer VD[O]@1 | BH[ENZ]@40, HH[ENZ]@100, HN[ENZ]@100 | SCEDC |
| PB.B065 | 246.8 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B067 | 251.8 | barometer LD[DO]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B058 | 255.8 | barometer LD[DO]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B066 | 262.2 | barometer LD[DO]@1, RD[O]@0.0005556, VD[D]@0.1 | EH[12Z]@100 | SCEDC |
| PB.B921 | 306.1 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B918 | 309.7 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B917 | 317.9 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |
| PB.B916 | 318.5 | barometer LD[O]@1, RD[O]@0.0005556 | EH[12Z]@100 | SCEDC |

The ladder: CI stations with HHE, HHN, HHZ out to 350 km. The first rung is the nearest; each next rung is the nearest station at least 1.5 times farther than the rung before. Windows are seconds after the catalogue's launch time.

| station | lat | lon | km | bearing from site | sound, earliest | sound, latest | ground, earliest | ground, latest |
|---|---|---|---|---|---|---|---|---|
| CI.GATR | 34.5527 | -120.5024 | 13.5 | 131 | 34 | 241 | -3 | 194 |
| CI.LCP | 34.7355 | -120.2800 | 32.6 | 069 | 89 | 321 | 0 | 207 |
| CI.SYN | 34.6072 | -120.0696 | 49.9 | 093 | 140 | 393 | 3 | 218 |
| CI.MPP | 34.8885 | -119.8136 | 78.5 | 069 | 222 | 512 | 7 | 237 |
| CI.CDM | 34.3685 | -119.3414 | 120.4 | 104 | 344 | 687 | 14 | 265 |
| CI.HDH | 34.7753 | -118.6400 | 181.4 | 084 | 521 | 941 | 23 | 306 |
| CI.SRN | 33.8285 | -117.7894 | 275.0 | 108 | 792 | 1331 | 37 | 368 |

Window parameters: sound 0.240 to 0.345 km/s; ground 1.5 to 6.5 km/s; a source lasting 180 s; 5 s either side for the catalogue's time.
Networks left out: SY (synthetic seismograms, not instruments); AM (held: its service says use accepts a licence, which is the owner's to accept).

<!-- d1:stations:2021:end -->

What the station answers establish:

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| M1 | On 2026-11-23, within 350 km of Complex 4, the answers of SCEDC, NCEDC and EarthScope describe 2,845 stations with a seismic or pressure channel. 299 are the Caltech network's (CI). None is within 10 km on that date; on 2021-09-14 one was (M4b) | MEASURED | `python docs/studies/d1/stations.py --responses <scratch>/stations`, the band table of the first block above; the three requests are the rows marked used for VSFB and 2026-11-23 in [queries.tsv](d1/queries.tsv) | making the three requests again |
| M2 | The CI stations nearest Complex 4 each offer three components (E, N, Z) of a broadband seismometer at 100 samples a second (HH) and at 40 (BH), and of an accelerometer at 100 (HN) | MEASURED | the same command; the rows CI.GATR, CI.LOC and CI.LCP of the first table above | making the requests again |
| M3 | On 2026-11-23 those answers list 18 stations with a pressure channel within 350 km of Complex 4, none of them within 50 km. One is an infrasound channel: SB.CPSLO, 74.4 km away, at 100 samples a second, listed by EarthScope's answer only. The other 17 are barometers at 1 sample a second, from 123 km out | MEASURED | the same command; the band table and the pressure table of the first block above | making the requests again; whether any record of that infrasound channel is held was not asked |
| M4 | On 2021-09-14 the CI ladder from Complex 4 had 7 rungs, from 13.5 to 275 km, each with HHE, HHN and HHZ at 100 samples a second and an empty location code | MEASURED | `python docs/studies/d1/stations.py --responses <scratch>/stations --as-of 2021-09-14 --site VSFB`, the ladder table of the second block above; the location code is the third field of those stations' lines in the answer saved as `scedc-vsfb-20210914-channel.txt` | making the request again |
| M4b | On 2021-09-14 one station was nearer than the ladder's first rung: NC.PTQ, 6.7 km from Complex 4, with a single vertical short-period channel at 100 samples a second. It is not in the answers for 2026-11-23 | MEASURED | the same command as M4; the first row of the first table of the second block above | making the request again |
| M5 | The answers name each channel's sensor and its scale, not its digitiser: CI.LCP's HHZ is described as an STS-2 at 629,865,000 counts per m/s | MEASURED | the line for CI, LCP, HHZ in the answer saved as `scedc-vsfb-channel.txt`, fields 11, 12 and 14, read 2026-11-23 | making the request again |
| M6 | Samples in these records are wider than 16 bits. Of the 25 files fetched, two hold values outside a signed 16-bit range, down to -36,647 and up to 35,420, and need 17 bits. The files store each record's first and last sample as 32-bit integers | MEASURED | `python docs/studies/d1/mseed.py <data>/*.mseed`, the columns smallest, largest and bits a sample needs; D1b, row Q5c. Before any record was read this row was BELIEVED, and spoke of the digitisers, which is now row M6b | the files, by their hashes in [manifest.tsv](d1/manifest.tsv) |
| M6b | The converters at these stations are 24 bits wide or wider | BELIEVED | from memory; no answer and no record read states a width. M9's gain does not settle it: it fits 24 bits over 40 volts, and equally 22 over 10, 21 over 5 and 20 over 2.5 (line F24 of [figures.py](d1/figures.py)). M6 shows only that the samples use more than 16 | a document that states the converter's width or its full-scale voltage |
| M7 | The first availability request, with a channel wildcard and a two-hour window, returned a header line and no rows. Why is not established: the service may hold nothing there, or may not take that form of request | MEASURED | `https://service.scedc.caltech.edu/fdsnws/availability/1/extent?net=CI&cha=HH?&start=2021-09-14T03:00:00&end=2021-09-14T05:00:00&asset=continuous&format=text&nodata=404`, 2026-11-23: HTTP 200 and 99 bytes | the same question in the documented form, station by station |
| M8 | Six station requests went to EarthScope's service (three at station level that nothing reads, and the three in queries.tsv) and three to Raspberry Shake's, all before their terms were read. The owner has since allowed EarthScope; Raspberry Shake's answers are still held | MEASURED | `<scratch>/requests.log`, 07:10 to 07:12 on 2026-11-23; the rows of [queries.tsv](d1/queries.tsv); the ledger's lead.md at 07:59 for the ruling | the log |
| M9 | For the vertical 100-sample channel of each of eight stations, the seven rungs of the 2021 ladder and CI.LOC, the response-level answer gives the volts-to-counts stage a gain of 419,430 counts a volt, the same at all eight, and describes no data logger at any. A gain is not a width (M6b) | MEASURED | `python docs/studies/d1/digitisers.py <scratch>/stations/scedc-ladder-20210914-response.xml`; the answer is that of `https://service.scedc.caltech.edu/fdsnws/station/1/query?net=CI&sta=GATR,LOC,LCP,SYN,MPP,CDM,HDH,SRN&cha=HHZ&level=response&format=xml&startbefore=2021-09-14T00:00:00&endafter=2021-09-15T00:00:00`, 2026-11-23 | making the request again |
| M10 | On 2026-11-23 EarthScope's answer lists 5 stations within 350 km of Cape Canaveral's pad 40, none within 50 km. The nearest is IU.DWPF, 97.7 km away (98.2 km from Kennedy's pad 39A). Each of the five has an infrasound channel at 40 samples a second beside a 100-sample seismometer | MEASURED | `python docs/studies/d1/stations.py --responses <scratch>/stations`, the CCSFS and KSC tables of the first block above | making the request again; a service not asked |
| M11 | On 2026-11-23 EarthScope's answer lists no station within 100 km of Starbase, 5 between 152.6 and 191.6 km, and 24 between 200 and 350 km. One of those 29 has a pressure channel: N4.735B, 323.2 km away, with an infrasound channel | MEASURED | the same command; the STARBASE tables of the first block above | making the request again; a service not asked |

**Networks in the Vandenberg tables that are not the Caltech network.** The codes CE, CJ and NP are strong-motion networks (BELIEVED, from their channel sets: accelerometers only), and whether any of them is recorded continuously was not read. The proposal in section 8 uses CI alone.

## 4. The launch catalogue

**GCAT**, Jonathan McDowell's General Catalog of Artificial Space Objects (rows L5a to L5g).

- **Fields**, from the column descriptions page: a launch tag; the launch date as a Julian date and as a UTC calendar time; the vehicle type and variant; flight and mission names; the launch site and the pad; apogee and other orbit fields, several of them newly added and not yet filled; the launch agency; a launch code whose first letter is the category (O for orbital) and whose second is success or failure; and two citation fields, the first for the launch time's source (L5g).
- **Time precision.** UTC, to the second where available (L5b), defined as first motion (L5c). The written form of each time carries its own precision, and a trailing question mark widens it (L5d). So a launch list is filtered on the time's form before a window is built from it.
- **Terms.** CC-BY 4.0; cite it (L5a). The page gives a short citation to use; PROVENANCE.md carries it.
- **Size.** 76,034 entries, 7,001 orbital (L5f). The file's size was not read.
- **Scrubs.** The column descriptions name no code for a scrubbed countdown (L5e). They do name codes for a pad explosion, for a pad abort, kept only for crewed attempts, and Z, an entry that is not a launch. What the lists themselves hold was not read: no catalogue file was opened.

**Is there a public record of scrubbed countdowns?** Partly. One site, RocketLaunch.Live, says it holds every announced attempt since December 2017, and counts 149 scrubbed Falcon 9 attempts (S1, S4). Three limits: its older records are inferred from its own schedule edits (S2); full access is paid (S3); and whether a scrubbed attempt's target time is on an open page was not established. A scrub is the best control this data could have, a published time with nothing behind it, so this is worth Logan's look. It is not in the proposed download.

**Two things a catalogue may not flag, and the records might hold anyway** (L7b): a static test, engines fired with the rocket held down, and an aborted launch. An infrasound array beside one pad recorded both; its abstract does not say whether the seismometer did. Either would put sound at the pad at a time no launch list is known to carry.

## 5. Predicted arrival windows

**The model.** The catalogue's time T0 is first motion at the pad. A station d km away is reached by sound at d divided by the sound's overall speed, and by a wave through the ground at d divided by its speed. The source goes on radiating while the engines burn. A window is the earliest and the latest second, after T0, at which that station could show the signal.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| W1 | The sound window opens d / 0.345 - 5 seconds after T0 and closes d / 0.240 + 180 + 5 seconds after it, for d in km | DECISION | proposed here. The speeds bracket L6's 343 m/s and A5's three phases, 332 to 250 m/s; the constants are at the top of [stations.py](d1/stations.py) | a measured onset outside it |
| W2 | The ground window opens d / 6.5 - 5 seconds after T0 and closes d / 1.5 + 180 + 5 seconds after it | ESTIMATE | 6.5 and 1.5 km/s are round figures for a fast wave in the crust and a slow surface wave, from memory. The one figure read is a P velocity of more than 2.0 km/s at one site, in the abstract behind L1a | a measured onset outside it |
| W3 | The source is taken to radiate for 180 seconds from where the pad is. **The first look shows this is too short for the one launch it has**: power stayed above 3 times noise for 270 to 454 seconds at four stations and outlasted every window, by 62 to 248 s (D1b, row Q4a). The windows of this study are not yet re-drawn | ESTIMATE | A8's 162 seconds of first-stage burn, rounded up. The rocket climbs and moves downrange while it burns, so its later sound starts farther off and arrives later than this allows | more launches; D1b has one |
| W4 | In seconds per km the sound window's edges are 2.90 and 4.17, and the ground window's 0.15 and 0.67. These are the chosen speeds of W1 and W2 turned over, not measurements | COMPUTED | `python docs/studies/d1/figures.py`, line F3 | arithmetic |
| W5 | At 343 m/s sound takes 2.92 s per km: 20.4 s to 7 km, 43.7 s to 15 km, 291.5 s to 100 km. At A5's three speeds it takes 3.01, 3.42 and 4.00 s per km | COMPUTED | the same command, lines F1 and F2; it reproduces the plan's row L6 | arithmetic |
| W6 | The launch of L3c was at 03:55:50 UTC on 2021-09-14, which is 20:55:50 on 13 September at 7 hours behind UTC | MEASURED | the launch catalogue's entry 2021-082, as `python docs/studies/d1/catalogue.py <data>` prints it; D1b, row Q6a; the subtraction is line F22 of figures.py. Before the file was fetched this row was BELIEVED and said about 03:56, from Pacific Daylight Time remembered | a later release of the catalogue |
| W7 | On the 2021 ladder the sound window is 34 to 241 s at 13.5 km, 207 s long, and 792 to 1331 s at 275 km, 539 s long | COMPUTED | the ladder table of the second block in section 3; figures.py, line F15 | arithmetic on W1 |
| W8 | A first stage that flies back is a second source beside the pad, minutes after liftoff, on the flights that land there | BELIEVED | A9 says the landing pad is there. When a landing comes, and on which flights, was not read | a flight timeline; a second onset in the records |

The windows for every rung are the last table of each block in section 3. On the speeds chosen here the two windows overlap near the pad (at 13.5 km: sound 34 to 241 s, ground -3 to 194 s) and are apart by 100 km. That is arithmetic on W1, a DECISION, and W2, an ESTIMATE; it says nothing yet about the ground. If it holds, the time of arrival alone does not say, near the pad, which path the energy took, and what separates the paths is the slope of onset time against distance across the ladder: 2.9 to 4.2 s per km for sound, under 0.7 for the ground (W4). That slope is the first thing LCH-2 measures.

**What would widen a window.**

- *The catalogue's time.* A time given to the minute adds 60 s. A question mark adds seconds (L5d). First motion against ignition is a few seconds (L5c), which the 5 s either side is for.
- *The air.* The overall speed of sound over a long path depends on which layer of the atmosphere turned it back, and on wind and temperature that day (A5 saw three speeds from one event). The window takes the whole range; it does not predict the day.
- *The moving source* (W3). Sound from late in the burn starts tens of km away, so the true signal can outlast the window, more so at stations ahead of the rocket's track.
- *The returning stage* (W8), where there is one.
- *The pad.* A launch from another pad of the same base is at another distance (section 2).
- *The station's position.* A coordinate is as good as the service's.

## 6. The controls

**Everything in this section is a DECISION proposed here: a design, not a finding.** Nothing below has been run.

Words used. A *record* is one channel of one station over one window with its lead-in. A *launch window* is one of section 5's two windows for one launch at one station, and every result names which: the *sound window* or the *ground window*. A *control window* has the same length and the same offsets, hung on a time when no launch happened; section 7 says which times may be used. A *hit* is defined in section 7. The *ladder* is the stations of section 3's rule, all of them. *Band power*, *up*, *stretch* and *onset* are defined once, in section 8 under The measure and in section 7. The band that counts is 2 to 8 Hz unless a result says otherwise; the other three bands are reported beside it.

The first nine are the plan's, in its order. Each says how LCH-2 could run it on section 8's download, which holds one launch, and what the full form needs.

| control | the way to pass while showing nothing | what is compared with what | the control has failed if |
|---|---|---|---|
| 1. A launch time is not an arrival time | scoring any energy on launch day as a detection | the onset time at each rung, against distance, an onset being looked for from the opening of the ground window to the close of the sound window and nowhere else (section 8, The measure); and hits in the true window against hits in the same record's wrong windows: one of the same length that closes 60 s before T0, and one placed as if the station were at twice its distance | the onsets do not rise with distance at a slope inside one of W4's two ranges; or the wrong windows hit as often as the true one. With fewer than three onsets the slope cannot be taken, and that is reported as not run, not as passed |
| 2. A launch is not a signal in every record | calling every launch window at a far station a positive | at each rung on its own, in the 2 to 8 Hz band: the count of sound-window hits among its launch windows against the count among that station's control windows, by Fisher's exact test, one-sided, at the level 0.01 | a rung is used as a source of positive labels while that test does not reject at 0.01 |
| 3. Launch times are not random | a model that learns the hour, the weekday, the season or the base's own bustle | launch windows against control windows at the same station, the same time of day and the same weekday, in weeks with no launch within a day; and a model shown only the ten minutes before T0, which no signal can have reached | hits in those matched controls match hits in launch windows; or the model shown only the minutes before T0 tells launch days from control days better than chance |
| 4. There is no known optimum | quoting a detection fraction as if it were measured against a best possible detector | the adaptive detector against one frozen, plain detector (band energy against the station's own noise), on the same held-out launches, at an equal false-alarm fraction of control windows | any result is given as a share of an optimum; or the comparison is made at an equal threshold; or the plain detector's settings moved after records were scored |
| 5. It is not a pulse | a detector that fires on any short burst | hits on launch windows against hits on windows chosen because the earthquake catalogue puts a local earthquake in them | earthquake windows hit more often than clean control windows: the detector answers to energy, not to a launch |
| 6. Distance is not the only thing that sets strength | reading a ladder of strength as a ladder of distance | each station's median ratio over the sound window, which is strength over that station's own noise, against distance; and two stations at nearly one distance against each other (CI.GATR and CI.LOC, 13.5 and 16.5 km), launch by launch | over at least ten launches recorded at both: the mean of the absolute difference of the two stations' log10 medians is more than twice the larger of the two stations' standard deviations of log10 median from launch to launch; or the rank correlation of median against distance across the ladder is not below zero. With fewer than ten launches at both it is reported as not run |
| 7. Other things happen in the window | counting an earthquake, another launch or a returning stage as the launch | every result with and without the windows that a catalogue marks, the rule applied alike to launch windows and control windows | a result changes sign when marked windows are dropped; or the rule was applied to one kind of window only |
| 8. One launch is seen at many stations | a test set the model has already seen | a split by launch and by date, all of a launch's records on one side, against a split record by record made on purpose | any launch is on both sides, which is refused by name; or the record-by-record split does not score higher, which says the test cannot see a leak |
| 9. The sources are mostly the cases that worked | keeping the stations and launches that showed something | the stations and the launches named by a rule before any record is seen, every rung reported, against what a search for signals would have kept | a station or launch is dropped after its record was seen; or the one launch the network wrote up (L3a) is pooled with launches chosen by rule |

**Notes on each, and how far LCH-2 can take it.**

1. *Arrival time.* LCH-2 can run this whole on one launch: seven rungs give seven onsets. With one launch the wrong-window comparison is a description, not a rate.
2. *Signal in every record.* On the download LCH-2 has one launch window and two control windows a station. It can say what it sees at each rung and no more. The full form needs enough launches for a fraction: by line F12 of figures.py, 46 launch windows put a fraction near one half within 7.4 points (one standard error), 100 within 5.0.
3. *Not random.* Matched controls need the catalogue, to know which days had no launch. The download's two control days are the day before and the day after at the same hour; LCH-2 first checks, in the catalogue, that neither held a launch. A scrubbed attempt would be a better control than either and none is in hand (section 4). An aborted launch or a static test is the opposite case, sound with no launch (L7b, of an infrasound array), and belongs in control 14.
4. *No optimum.* This stage never calibrates the instrument. D0's stage E0 does that, on synthetic data. Section 7 fixes the false-alarm rule this control needs.
5. *Not a pulse.* The hit rule of section 7 asks for a crossing that lasts. D0's matched-filter configuration does not fit; the configuration that may is the filter bank as band filters, the rectifier, a long pooling stage and the head, as the plan says. MOD-B's pooling length should cover the shortest window here, 207 s (W7), which at 100 samples a second is 20,700 samples.
6. *Strength.* Besides noise, LCH-2 records for each rung the sensor named in the metadata, the bearing from the pad, and the hour. A7 is the warning: the installation matters. Wind and temperature that day are not in hand; no weather source was looked at.
7. *Other things.* The earthquake catalogue is SCEDC's (T15); a catalogue of distant large earthquakes was not looked for. Other launches come from GCAT. The returning stage (W8) is treated as part of the launch if the window covers it, and its sub-window is reported apart.
8. *Splitting.* The manifest of section 7 lists every launch's side; a checker refuses a launch on both. Holding out a station, to ask whether a detector carries over to ground it has never seen, is a second experiment and is reported apart.
9. *Selection.* The ladder rule is in stations.py: the nearest CI station with three 100-sample components, then at each step the nearest one at least 1.5 times farther. The rule was fixed on 2026-11-23, before any record was seen. Rungs with nothing in them are reported as such.

**Five the plan did not list.**

| control | the way to pass while showing nothing | what is compared with what | the control has failed if |
|---|---|---|---|
| 10. A window's length grows with distance | a far station scores more hits because its window is 2.6 times longer (W7) | false alarms counted per control window of the very same length at that station, and also per hour | rungs are compared on raw hit counts; or a station's control windows are shorter than its launch windows |
| 11. The clock and the calendar | a window an hour or a day off, from local time or a date read wrong (W6) | T0 from the catalogue in UTC against any other source of it; and the slope of control 1, which a wrong hour destroys | two sources of one T0 differ by more than a minute and the launch is used anyway |
| 12. The instrument changed | a step in strength that is a new sensor, not a new season | each record's counts scaled by the metadata epoch that covers its date; strength statistics split at every epoch change | raw counts from two epochs are pooled. CI.LCP's present epoch began on 2021-09-09, four days before the one launch in hand (M4's answer file) |
| 13. Not every launch is the same source | pooling vehicles, pads and flights with and without a returning stage | results by vehicle, by pad, and by whether a stage returned to the base | the first experiment mixes pads or vehicles without saying so |
| 14. Engines without a launch | a static test or an aborted launch in a control window (L7b: an infrasound array recorded both; whether a seismometer shows them is not known) | control windows checked against whatever record of such firings can be found; none has been | a control window's hit is kept or dropped by eye |

## 7. What counts as a hit, and what is fixed first

All of this section is DECISION, proposed here, except the three COMPUTED rows.

**The series the rule reads.** D0's detector gives one score for each input sample, and its scorer compares the score with a threshold. For a launch that is not enough: a launch is minutes long, and one crossing is what an earthquake's first arrival also gives. So the rule reads the score once a second. *The second's score* is the mean of the detector's scores over one whole second, and seconds are counted from T0: second k runs from T0 + k to T0 + k + 1. Until a detector exists, the same rule is applied to the ratio of band power to noise that section 8 defines, in place of the score. A result says which. T0 is the launch catalogue's time for the launch, and it must be written to the second and not marked uncertain (L5d); a launch timed more coarsely is left out of a scored experiment. A second whose frame was left out for a missing sample is neither up nor not up: it ends any stretch at once, and it is not counted among a window's seconds.

**A hit**, written so that two people score one record alike:

1. A second is *up* when its score is above the station's threshold. (For the ratio of section 8 the threshold is 3.)
2. A *stretch* begins on an up second and runs on until two seconds in a row are not up. One second that is not up, between two that are, does not end it.
3. A stretch *counts* when it holds at least the minimum number of up seconds. The minimum proposed is 10.
4. A window is a **hit** when a stretch that counts begins on a second k with floor(open) <= k < ceiling(close), where open and close are that window's edges in seconds after T0.
5. A window gives one hit or none. A result always says which window it is about: a *sound-window hit* or a *ground-window hit*. The two are scored apart. The headline claim is the sound window's, and the ground window's is given beside it. A stretch that begins where the two windows overlap is a hit in both, and is reported as such.
6. Each station has its own threshold, and each band its own.

**Which records may set a number.** The minimum of step 3, the band that counts, and anything else chosen by looking at records, is set from launches of the training period only. A record that helped set it is never scored. The first look scores nothing, and the launch it looks at is on the training side from then on.

**False alarms.** They are counted in control windows only.

- A control window hangs on a time T0' that is at least 24 hours from the T0 of every launch from that site in the catalogue, whichever side of the split that launch is on. It has the same edges after T0' as that station's launch window has after T0.
- Control windows are split by date exactly as launches are. Those of the training period set thresholds. Those of the test period are scored for false alarms. None does both.
- A station's false-alarm fraction is its hits in test-period control windows over the number of them. It is also given per hour of control record, so stations with different window lengths can be set side by side (control 10).
- A station's threshold is set from training-period control windows, to give a false-alarm fraction of 0.05 there. That figure is proposed, not derived: by H1 it needs 200 training control windows at a station before it rests on ten expected false alarms, and a smaller fraction needs more. After every change of weights it is set again, the same way. Models are compared at an equal false-alarm fraction, never at an equal threshold. This is D0's third comparison rule, carried over.
- A detection claim at a rung is that rung's count of hits among launch windows against its count among control windows, both given, with the test and the level of control 2.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| H1 | A false-alarm fraction below 10 divided by the number of control windows rests on fewer than ten expected false alarms and is an extrapolation: 0.05 needs 200 control windows at a station, 0.01 needs 1,000 | COMPUTED | `python docs/studies/d1/figures.py`, line F13; the counterpart of D0's row D10 | arithmetic |
| H2 | With n launch windows at a rung, a hit fraction near one half has a standard error of 0.158 for n = 10, 0.074 for 46, 0.050 for 100 | COMPUTED | the same command, line F12 | arithmetic |
| H3 | A year of Vandenberg launches on an 8-station ladder would be 110,400,000 samples of one component, 0.82 of one of D0's 256 MiB replay channels at 16 bits | ESTIMATE | arithmetic, `python docs/studies/d1/figures.py`, line F14, on 46 launches from L4, which is BELIEVED, and on the channel's size from D0's row H8 | the catalogue's count; the card's memory as built |

**What is fixed and hashed before any record is scored.** D0's first comparison rule fixes the injection set. This stage has no injections, so its counterpart is one manifest, written and hashed (SHA-256) and the hash committed before a record is scored:

1. **The launch list**: the catalogue file's own hash and the date it was fetched; the rule that picks launches from it (site, pad, vehicle, dates, and the form of the time, by L5d); and the launches that rule gives, each with its tag, its T0 and its pad.
2. **The stations**: network, station, location and channel codes; the coordinates used; the metadata epoch for each launch date; the hash of each station answer; the ladder rule and its constants.
3. **The windows**: the speeds, the source's duration and the margins (W1, W2, W3), and the commit of the code that turns them into times.
4. **The control windows**: the rule that makes them, its seed if it draws at random, and the list of times it gives.
5. **The exclusions**: each catalogue's hash, and the rule, the same for launch and control windows (control 7).
6. **The split**: which launch is on which side (control 8).
7. **The hit rule**: the band that counts, the minimum number of up seconds, and the false-alarm fraction thresholds are set to.
8. **The model version to be reported**, named before the run, as D0's fifth rule asks.

A run whose manifest does not hash to the committed value is refused. A hash recorded after a run is not a control; D0's table of gates says the same of its own.

**For LCH-2's first look, which scores nothing**, the lighter rule is that the things it will measure are fixed here, before it sees a record: section 8's list of measurements, the four bands it reports (0.5 to 2, 2 to 8, 8 to 20 and 20 to 45 Hz), and the ladder.

## 8. The proposed download

**This list was written for Logan to approve, item by item, with nothing fetched. He allowed downloads on 2026-11-23 and it has since been run as written: D1b, section 1, has what came.** The sizes in the items below are the estimates made beforehand; rows E1 to E6 give what was measured. The list is the smallest that shows a ladder: one launch, the one whose time has been read from a page (L3c), on the 2021 ladder (M4). It is also the one launch the network wrote up (L3a), so it is a selected case (control 9): it can show that a signal exists and how it falls off, and it cannot show how often.

**The order LCH-2 would work in.** Items 1 to 3 first, because they can change items 4 to 7: the catalogue's T0 replaces the page's minute, and the request times move with it. If the two disagree by more than a minute, LCH-2 stops and says so.

| item | what | from | size | why |
|---|---|---|---|---|
| 1 | availability listings, as text, for the other 7 stations: 7 requests of the documented form, `https://service.scedc.caltech.edu/fdsnws/availability/1/extent?network=CI&station=GATR&asset=continuous` and the same for LOC, SYN, MPP, CDM, HDH and SRN; LCP's is in hand (T5) | SCEDC | a few KB each; LCP's was 3,795 bytes | whether anything at all is listed for each station around September 2021 (T3 and T4 disagree). An extent gives the earliest and the latest time and cannot show a gap, so it does not settle whether the launch hour is whole. Only the fetched record does (measure 7) |
| 2 | the launch list, `https://planet4589.org/space/gcat/tsv/launch/launch.tsv` | GCAT | perhaps 23 MB, as estimated beforehand; E6 has what came | T0 to the second; whether the two control days held a launch; what the lists hold of scrubs and of code Z (L5e) |
| 3 | the pad table and the site table, `https://planet4589.org/space/gcat/tsv/tables/lp.tsv` and `https://planet4589.org/space/gcat/tsv/tables/sites.tsv` | GCAT | not read; small beside the launch list (BELIEVED) | the pad of each launch and its coordinates, which section 2 says an experiment needs |
| 4 | tier A below: 3 requests | SCEDC | about 4.1 MB at most, 2.1 MB typically, as estimated beforehand; E4 and E5 have what came | the core: three distances, 13.5, 32.6 and 49.9 km, one launch |
| 5 | tiers B, C and D below: 27 requests | SCEDC | with tier A, about 41.1 MB at most, 20.6 MB typically, as estimated beforehand; E5 has what came | B: the rest of the ladder, to 275 km, and a second station near the pad. C: the same hour on the day before and the day after. D: the two horizontal components at the three nearest rungs |
| 6 | the earthquake catalogue for the three windows, as text: `https://service.scedc.caltech.edu/fdsnws/event/1/query?starttime=2021-09-14T03:00:00&endtime=2021-09-14T05:00:00&format=text`, and the same hours on 2021-09-13 and 2021-09-15 | SCEDC | a few KB each (ESTIMATE; an hour or two of a regional catalogue) | control 7 |
| 7 | a reader for miniSEED: either the package obspy, 14.8 MB (P1) and whatever else it needs installed, which was not sized; or none, see below | PyPI, or nobody | 14.8 MB and more, or nothing | to turn the files into numbers |

**Why the data centre's web service and not its cloud bucket.** SCEDC asks users to consider its cloud bucket first (T2, T8). The bucket holds one file for each channel and day; this list needs 50 minutes of each. Thirty day-long files hold 28.8 times the samples (figures.py, line F17), and the bucket sits with a cloud provider whose terms were not read. Thirty small requests, made one after another, are inside the limit the service states (T2). If Logan prefers the bucket, the same channels and days are there by name (T8).

<!-- d1:download:begin -->

| request | tier | station | km | channel | window, UTC | the request as it would be made |
|---|---|---|---|---|---|---|
| A01 | A | CI.GATR | 13.5 | HHZ | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=GATR&loc=--&cha=HHZ&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| A02 | A | CI.LCP | 32.6 | HHZ | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=LCP&loc=--&cha=HHZ&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| A03 | A | CI.SYN | 49.9 | HHZ | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=SYN&loc=--&cha=HHZ&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| B04 | B | CI.LOC | 16.5 | HHZ | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=LOC&loc=--&cha=HHZ&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| B05 | B | CI.MPP | 78.5 | HHZ | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=MPP&loc=--&cha=HHZ&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| B06 | B | CI.CDM | 120.4 | HHZ | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=CDM&loc=--&cha=HHZ&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| B07 | B | CI.HDH | 181.4 | HHZ | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=HDH&loc=--&cha=HHZ&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| B08 | B | CI.SRN | 275.0 | HHZ | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=SRN&loc=--&cha=HHZ&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| C09 | C | CI.GATR | 13.5 | HHZ | 2021-09-13 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=GATR&loc=--&cha=HHZ&start=2021-09-13T03:40:00&end=2021-09-13T04:30:00&nodata=404` |
| C10 | C | CI.LOC | 16.5 | HHZ | 2021-09-13 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=LOC&loc=--&cha=HHZ&start=2021-09-13T03:40:00&end=2021-09-13T04:30:00&nodata=404` |
| C11 | C | CI.LCP | 32.6 | HHZ | 2021-09-13 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=LCP&loc=--&cha=HHZ&start=2021-09-13T03:40:00&end=2021-09-13T04:30:00&nodata=404` |
| C12 | C | CI.SYN | 49.9 | HHZ | 2021-09-13 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=SYN&loc=--&cha=HHZ&start=2021-09-13T03:40:00&end=2021-09-13T04:30:00&nodata=404` |
| C13 | C | CI.MPP | 78.5 | HHZ | 2021-09-13 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=MPP&loc=--&cha=HHZ&start=2021-09-13T03:40:00&end=2021-09-13T04:30:00&nodata=404` |
| C14 | C | CI.CDM | 120.4 | HHZ | 2021-09-13 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=CDM&loc=--&cha=HHZ&start=2021-09-13T03:40:00&end=2021-09-13T04:30:00&nodata=404` |
| C15 | C | CI.HDH | 181.4 | HHZ | 2021-09-13 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=HDH&loc=--&cha=HHZ&start=2021-09-13T03:40:00&end=2021-09-13T04:30:00&nodata=404` |
| C16 | C | CI.SRN | 275.0 | HHZ | 2021-09-13 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=SRN&loc=--&cha=HHZ&start=2021-09-13T03:40:00&end=2021-09-13T04:30:00&nodata=404` |
| C17 | C | CI.GATR | 13.5 | HHZ | 2021-09-15 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=GATR&loc=--&cha=HHZ&start=2021-09-15T03:40:00&end=2021-09-15T04:30:00&nodata=404` |
| C18 | C | CI.LOC | 16.5 | HHZ | 2021-09-15 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=LOC&loc=--&cha=HHZ&start=2021-09-15T03:40:00&end=2021-09-15T04:30:00&nodata=404` |
| C19 | C | CI.LCP | 32.6 | HHZ | 2021-09-15 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=LCP&loc=--&cha=HHZ&start=2021-09-15T03:40:00&end=2021-09-15T04:30:00&nodata=404` |
| C20 | C | CI.SYN | 49.9 | HHZ | 2021-09-15 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=SYN&loc=--&cha=HHZ&start=2021-09-15T03:40:00&end=2021-09-15T04:30:00&nodata=404` |
| C21 | C | CI.MPP | 78.5 | HHZ | 2021-09-15 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=MPP&loc=--&cha=HHZ&start=2021-09-15T03:40:00&end=2021-09-15T04:30:00&nodata=404` |
| C22 | C | CI.CDM | 120.4 | HHZ | 2021-09-15 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=CDM&loc=--&cha=HHZ&start=2021-09-15T03:40:00&end=2021-09-15T04:30:00&nodata=404` |
| C23 | C | CI.HDH | 181.4 | HHZ | 2021-09-15 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=HDH&loc=--&cha=HHZ&start=2021-09-15T03:40:00&end=2021-09-15T04:30:00&nodata=404` |
| C24 | C | CI.SRN | 275.0 | HHZ | 2021-09-15 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=SRN&loc=--&cha=HHZ&start=2021-09-15T03:40:00&end=2021-09-15T04:30:00&nodata=404` |
| D25 | D | CI.GATR | 13.5 | HHE | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=GATR&loc=--&cha=HHE&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| D26 | D | CI.GATR | 13.5 | HHN | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=GATR&loc=--&cha=HHN&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| D27 | D | CI.LCP | 32.6 | HHE | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=LCP&loc=--&cha=HHE&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| D28 | D | CI.LCP | 32.6 | HHN | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=LCP&loc=--&cha=HHN&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| D29 | D | CI.SYN | 49.9 | HHE | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=SYN&loc=--&cha=HHE&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |
| D30 | D | CI.SYN | 49.9 | HHN | 2021-09-14 03:40 to 04:30 | `https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=SYN&loc=--&cha=HHN&start=2021-09-14T03:40:00&end=2021-09-14T04:30:00&nodata=404` |

30 requests; each is 50 minutes of one channel at 100 samples a second.

<!-- d1:download:end -->

The window is 03:40 to 04:30 UTC: 16 minutes of noise before the launch as read (W6), then 34 minutes, which covers the last rung's window to 1331 s (W7) with the minute's doubt in the launch time.

**One nearer station is left off the list.** NC.PTQ was 6.7 km from the complex on that date, with one vertical channel (M4b). It belongs to the northern network, so its waveforms would come from NCEDC (BELIEVED), whose holdings for it were not checked. If Logan wants the nearest rung there is, it is one more availability request and one more waveform request, both to NCEDC.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| E1 | The fetched records are 4096 bytes long and Steim-1 encoded. This row first said 512-byte records holding 112 uncompressed 32-bit samples, from memory, and that was wrong for this archive | MEASURED | `python docs/studies/d1/mseed.py <data>/*.mseed`; D1b, row Q5a | the files |
| E2 | Steim-1 compression came to 1.09 to 2.18 bytes a sample in the 25 files fetched, 1.44 on average. This row first said about 2 for Steim-2, from memory | MEASURED | `python docs/studies/d1/figures.py`, line F19, from the sizes in [manifest.tsv](d1/manifest.tsv); D1b, row Q5e | other stations and other hours |
| E3 | An entry of the catalogue's launch list averages 182 bytes. This row first estimated 300, from a count of columns | MEASURED | figures.py, line F20, from the fetched file's size and its number of entries; D1b, row R1 | a later release of the catalogue |
| E4 | One request came to 300,001 samples and between 327,680 and 655,360 bytes, 0.33 to 0.66 MB. This row first estimated 0.69 MB typically and 1.37 MB at most | MEASURED | [manifest.tsv](d1/manifest.tsv); D1b, rows Q5a and Q5e | the manifest |
| E5 | Of the 30 waveform requests 25 were answered, with 10,788,864 bytes in all, 10.8 MB. The other 5, all of CI.GATR, were answered 404. This row first estimated 20.6 MB typically and 41.1 MB at most for the 30 | MEASURED | manifest.tsv; D1b, rows R1 and Q1b | the manifest |
| E6 | The full launch list is 13,818,818 bytes, 13.8 MB. This row first estimated 22.8 MB | MEASURED | manifest.tsv, the row gcat-launch.tsv | a later release of the catalogue |
| E7 | SCEDC's waveform service answers up to 12.1 days of a 100-sample channel in one request; each request here is 50 minutes | COMPUTED | the same command, line F11, from T7 | the service refusing a request |

**The tools to read it.**

- *obspy*: one file of 14.8 MB for this desktop's Python (P1), LGPL version 3. What it requires beyond numpy, which is installed, was not read; scipy and others are likely (BELIEVED), and each is its own download for Logan to approve.
- *No package*: a miniSEED record is a fixed header and a block of Steim-compressed differences. LCH-2 could write a reader of a couple of hundred lines against the format's public description (ESTIMATE: an hour, plus a check). Its check would be the format's own: each compressed block carries its first and last sample, so a decoder that drifts is caught at the end of every record (BELIEVED, from memory of the format).
- *Text instead of miniSEED*: SCEDC lists a second service that returns text (T9). Its page was not opened, so whether it serves this data, and how large the text is, is not established.

**The measure**, fixed here before any record is seen:

- *Band power.* A record is cut into frames of 4 seconds, 400 samples, one beginning every second; frame k is centred on T0 + k seconds. The frame's mean is taken off, a Hann window is applied, and the squared magnitude of its discrete Fourier transform is summed over the bins from a band's lower edge up to, and not including, its upper edge. The four bands are 0.5 to 2, 2 to 8, 8 to 20 and 20 to 45 Hz. A frame with a missing sample is left out, and counted.
- *Noise.* For each band, the median band power over the frames centred from 660 s to 60 s before T0.
- *Ratio.* Band power over that noise. A second is *up* when its ratio is above 3.
- *Onset.* The first second of the first stretch that counts (section 7, steps 2 and 3, with the minimum of 10) and that begins between the opening of the ground window and the close of the sound window. Where T0 is known only to the minute, the close is put 60 s later. A frame is 4 seconds long, so an onset is known to about 2 seconds and no better.
- *The band that counts* is 2 to 8 Hz. It was picked before any record was seen, and it is a guess: L2's explosion was 5 to 23 Hz at 1.4 km, and higher frequencies are expected to die away faster with distance (BELIEVED). All four bands are reported.
- *A control day* is treated exactly as the launch day, with the same clock time standing in for T0.

With it LCH-2 reports:

1. At each rung, for the vertical channel, in each band and each of the two windows, on the launch day and on both control days: the median ratio over the window, the number of up seconds in it, and its longest stretch.
2. The onset at each rung, if there is one, and how long its stretch lasts.
3. The slope of onset time against distance across the ladder, set against W4's two ranges: sound, ground, or neither.
4. Strength over noise at each rung, and the farthest rung where there is an onset at all.
5. The same on each control day's record, where any onset is a false one.
6. CI.GATR against CI.LOC (control 6).
7. For D0's row D1, from the files themselves: the encoding, the sample rate, the smallest and largest sample value and so the bits a sample needs, the record length, and any gaps.
8. Each file's size against E4.

It would report every rung, with or without a signal.

## 9. What could not be established, and what the brief or the plan got wrong

**Not established.**

- Whether a public record shows a launch, as a rate. For one launch the first look says yes at three distances by its rule and four by its numbers (D1b, rows Q2a, Q2b); how often is not established.
- Why CI.GATR has no record for the three days fetched, when its extent spans them (D1b, row Q1b). The other seven stations' records for those hours are whole (D1b, row Q5a), which settles what T3 and T4 disagree on for them and for no other time.
- The converters' width at any station (M6b, M9). That samples exceed 16 bits is settled (M6).
- The precision of launch times in GCAT beyond what was counted: this launch's is to the second, and 35 of 2024's 46 from the same pad are (D1b, rows Q6a, Q6f). The other 11 are coarser or marked uncertain, and were not looked at one by one.
- Whether a scrubbed attempt's target time can be read without paying (S3).
- When a first stage returns to the base and on which flights (W8); the dates of static tests and aborted launches (control 14).
- What obspy needs installed besides numpy, and the size of it.
- The weather on any launch day, and a source for it.
- Whether the strong-motion networks in the tables record continuously.
- Which structure the Starbase coordinate marks (C4), and where Vandenberg's other pads are.
- Whether any record is held for the one infrasound channel listed near Vandenberg (M3).
- The terms of SCEDC's cloud bucket (T8); that page was read for what the bucket holds, and the cloud provider's own terms were not looked at.

**Sources that could not be opened.**

- The plan's row L4: `https://www.vandenberg.spaceforce.mil/News/Article-Display/Article/4030895/vsfb-achieves-historic-milestone-with-51-launches-in-2024/` and a second address of the same release on `www.spaceforce.mil`, and a reprint on `www.spacedaily.com`: HTTP 403 each. L4 stays BELIEVED.
- The plan's row L7 at its given address, `https://ui.adsabs.harvard.edu/abs/2017AGUFM.S44A..01M`: an empty answer (HTTP 202) to two tools. The same abstract was read on its authors' university site (L7a, L7b).
- The paper behind L1 beyond its abstract, and the Sandia report behind A1 and A2 beyond its abstract: each is offered as a PDF, and a PDF is a download.
- `https://www.edhat.com/news/vandenberg-sfb-leads-study-on-ascent-sonic-booms-in-space-launches/`, from the plan's second search: HTTP 403.

**What the brief or the plan got wrong, or did not foresee.**

1. *The brief allowed queries to public station-metadata services as if none had terms.* Two of the four queried say that use accepts terms (T11, T12). Nine requests were made before those pages were read (M8). A brief that sends a parcel to a service should say: read its front page first.
2. *The plan's row L1 reports something its source's abstract does not say* (L1d): that earlier work found the airwaves detectable beyond 10 km. It may be in the paper's body. As it stands it is a search tool's sentence.
3. *The plan's row L5 names four kinds of launch in GCAT's lists* (orbital launches, failures, suborbital flights, pad explosions). The count page shows seven (L5f's source: orbital, uncataloged orbital, failed to orbit, suborbital, mesospheric, endoatmospheric, pad explosion). Nothing rests on it.
4. *The plan's row L6 is right as arithmetic and is the fast edge as physics* (W5). The lag to plan for is 2.9 to 4.2 s per km.
5. *The plan's caution 7 lists earthquakes, other launches and the base's activity.* The records may also hold a static test, an aborted launch (L7b, of an infrasound array) and a returning first stage (W8). Controls 13 and 14 are for those.
6. *Not foreseen, and nobody's error: Git Bash's curl fails on this desktop* with error 43 on several hosts; the Windows one works. It is in the ledger.
7. *The brief's third item asks for stations by distance at each site.* In this study's first version Florida and Texas were met only in prose, because every station answer for those two came from a held service. The owner allowed EarthScope on 2026-11-23 and their tables are now in section 3.
8. *The plan's row V2 says L3 gives no distance.* True of the post; but the post names its station (L3d, L3e), and that station is 32.6 km from the complex by its metadata (section 3). So one public report of a launch on a public station at a known distance exists, with the limit that the report is the network's own hedged post.

**Limits of this study.**

- It reads abstracts and web pages. Two of its strongest sources for the physics are about explosions, not launches (L2, A5).
- A READ row is held to its page by check_quotes.py; whether the quotation carries the claim beside it is a reader's judgement, and the verifier's.
- The windows rest on speeds chosen here (W1, W2). They are wide on purpose and are not a prediction.
- One launch, chosen because someone wrote it up, cannot say how often a launch is seen.
- The sizes in section 8's list were estimates on figures from memory, and two of those figures were wrong. They have since been measured (E1 to E6).

## Changes after the verifier's pass, 2026-11-23

A verifier, VLCH, held every READ row against its page. It found two wrong answers and eleven smaller things. Each is answered here; the rows named are as they now stand.

| finding | what was wrong | what was done |
|---|---|---|
| 1. Row A3 | it said the study examined 1,001 launches; the page says the period included 1,001 and that only launches within 5,000 km were examined | A3 restated to the page, with the second sentence quoted; A4's reach restated |
| 2. No scrubs | L5e, section 4 and the summary said the catalogue has no scrubs; what was read is that its column descriptions name no scrub code, and no file was opened | all three restated; code Z, an entry that is not a launch, is now named and quoted |
| 3. L1b | a tenth recorder was an inference | restated to the abstract's words; the row says what the abstract does not say |
| 4. L7b | the abstract speaks of the infrasound array, not the seismometer | the row, section 4, controls 3 and 14 and section 9 restated |
| 5. M1 | none within 10 km is true of one date | the row and the confirmation list now give the date, and point at M4b |
| 6. The windows' overlap | given as a finding; it is arithmetic on chosen constants | the summary, W4 and the paragraph under the table say so |
| 7. E4, E5, E6 | labelled COMPUTED on believed inputs; an upper bound stated without that mark | relabelled ESTIMATE, each naming its inputs' bases; the summary and the item table restated; H3 relabelled for the same reason. 64-bit floats are named as what would break the bound |
| 8. Controls 1 and 2 | no level, no band, no start for the onset search | control 2 has its test and level; the band that counts is named; control 1 says where an onset is looked for and what happens with fewer than three |
| 9. The hit rule | which window; no tolerance; a minimum tuned on a scored record; control windows on launch days | section 7 rewritten as six steps, with the rule for which records may set a number and the rule for control times |
| 10. The download list | the availability request cannot show a gap; the pad table was missing | item 1 says what an extent can and cannot settle; item 3 adds the pad and site tables |
| 11. The cloud bucket | the data centre recommends it first and the list did not say why it was not used | T2 quotes the recommendation; section 8 gives the reason and leaves the choice to Logan |
| 12. EarthScope's rows | held until the owner ruled | added by marking its three answers used in queries.tsv; M1, M3, M8 restated, M10 and M11 new; the Florida and Texas prose replaced by tables |
| 13. The digitiser width | BELIEVED | one response-level request made; M9 is new and M6 restated. The service gives a gain that fits 24 bits and states no width, so M6 stays BELIEVED until a record is read |

## Changes after the first look, 2026-11-23

Phase 2 fetched the download of section 8 and looked ([D1b](D1b-first-look.md)). These rows of this study are restated from it; each says in its own text what it said before.

| row | what changed |
|---|---|
| L4 | BELIEVED to MEASURED: the catalogue lists 46 |
| W6 | BELIEVED to MEASURED: 03:55:50 UTC, from the catalogue |
| W3 | still an ESTIMATE, now marked as too short for the one launch looked at |
| M6, M6b | split. That samples are wider than 16 bits is MEASURED. The converters' width is M6b, still BELIEVED |
| M9 | reworded: eight stations, and a gain is not a width |
| E1, E3 | were wrong: 4096-byte records, and 182 bytes an entry. Now MEASURED |
| E2, E4, E5, E6 | sizes measured in place of estimated |

And from the verifier's re-check of part A, which left eight smaller findings: section 7 now says what a frame with a missing sample does to a stretch, which T0 the rule uses and how precise it must be, and the false-alarm fraction proposed (0.05); control 6 has a number. D1b answers each of the eight in its last section.

## What this means for D0, for the lead to weigh

Nothing here changes D0; these are the points where the study touches it.

- **Row D1, the sample format.** Three components at 100 samples a second are what the nearest public stations offer (M2). The width is not known (M6); the format allows 32 bits (K3). Until LCH-2 reads a record, the plan's choice stands: width and channel count as parameters.
- **Stage E4 beside E3.** A launch record is small beside the replay store (H3), so capacity is not the constraint. The label is: a window hundreds of seconds wide (W7), true at a station only as often as that station shows the launch (control 2).
- **The detector's configuration.** A pooling stage long enough for 207 s at 100 samples a second (control 5's note).
- **The comparison rules.** D0's rules 2, 3 and 5 carry over as written; rule 1 becomes the manifest of section 7; rule 4's floor becomes H1.
