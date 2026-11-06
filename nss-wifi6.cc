// NSS Milestone 2 - dense Wi-Fi 6 cell: contention only vs RTS/CTS vs OFDMA
// One AP, N stations, UDP traffic, results appended to a CSV by FlowMonitor.
// Copy into ns-3.49/scratch/ and build with: ./ns3 build nss-wifi6

#include "ns3/boolean.h"
#include "ns3/command-line.h"
#include "ns3/config.h"
#include "ns3/double.h"
#include "ns3/enum.h"
#include "ns3/flow-monitor-helper.h"
#include "ns3/he-phy.h"
#include "ns3/internet-stack-helper.h"
#include "ns3/ipv4-address-helper.h"
#include "ns3/ipv4-flow-classifier.h"
#include "ns3/log.h"
#include "ns3/mobility-helper.h"
#include "ns3/multi-model-spectrum-channel.h"
#include "ns3/neighbor-cache-helper.h"
#include "ns3/propagation-delay-model.h"
#include "ns3/propagation-loss-model.h"
#include "ns3/rng-seed-manager.h"
#include "ns3/spectrum-wifi-helper.h"
#include "ns3/ssid.h"
#include "ns3/string.h"
#include "ns3/udp-client-server-helper.h"
#include "ns3/uinteger.h"
#include "ns3/wifi-acknowledgment.h"
#include "ns3/wifi-net-device.h"
#include "ns3/wifi-mac-header.h"
#include "ns3/wifi-phy.h"
#include "ns3/wifi-psdu.h"
#include "ns3/wifi-static-setup-helper.h"
#include "ns3/wifi-tx-vector.h"

#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <sstream>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("NssWifi6");

// PPDU counters, filled from the PHY trace
static uint64_t g_totalPpdu = 0;
static uint64_t g_dlMuPpdu = 0;
static uint64_t g_ulMuPpdu = 0;

static void
OnPhyTx(WifiConstPsduMap psduMap, WifiTxVector txVector, double /*txPowerW*/)
{
    g_totalPpdu++;
    if (txVector.IsDlMu())
    {
        g_dlMuPpdu++;
    }
    else if (txVector.IsUlMu())
    {
        g_ulMuPpdu++;
    }
}

// Frame trace (only filled with --trace): one row per transmitted PPDU inside a time window
struct TraceRow
{
    int64_t startUs;
    uint32_t node; // 0 = AP, 1.. = stations
    std::string type;
    int64_t durUs;
    uint32_t bytes;
    uint32_t mpdus;
    uint32_t receivers;
    int mu; // 0 single user, 1 DL multi-user, 2 UL multi-user (trigger based)
    bool retry;
};

static std::vector<TraceRow> g_trace;
static double g_traceFrom = 0;
static double g_traceTo = 0;

static void
OnPhyTxTrace(std::string context, WifiConstPsduMap psduMap, WifiTxVector txVector, double /*w*/)
{
    double now = Simulator::Now().GetSeconds();
    if (now < g_traceFrom || now >= g_traceTo || psduMap.empty())
    {
        return;
    }
    const auto first = psduMap.begin()->second;
    TraceRow r;
    r.startUs = Simulator::Now().GetMicroSeconds();
    auto pos = context.find("/NodeList/");
    r.node = std::stoul(context.substr(pos + 10));
    r.type = first->GetHeader(0).GetTypeString();
    r.durUs = WifiPhy::CalculateTxDuration(psduMap, txVector, WIFI_PHY_BAND_5GHZ).GetMicroSeconds();
    r.bytes = 0;
    r.mpdus = 0;
    for (const auto& [id, psdu] : psduMap)
    {
        r.bytes += psdu->GetSize();
        r.mpdus += psdu->GetNMpdus();
    }
    r.receivers = psduMap.size();
    r.mu = txVector.IsDlMu() ? 1 : (txVector.IsUlMu() ? 2 : 0);
    r.retry = first->GetHeader(0).IsRetry();
    g_trace.push_back(r);
}

int
main(int argc, char* argv[])
{
    uint32_t nStations = 10;
    bool useRts = false;
    bool useOfdma = false;
    bool ulOfdma = true;          // UL OFDMA (trigger frames) when OFDMA is on
    std::string direction = "both"; // dl, ul or both
    std::string topology = "single"; // single or hidden
    double simTime = 10.0;        // seconds of traffic
    uint32_t payload = 512;       // UDP payload, bytes
    double perStaMbps = 1.0;      // offered load per station per direction
    uint32_t mcs = 5;
    uint32_t channelWidth = 20;
    uint32_t guardInterval = 1600; // ns, UL OFDMA needs >= 1600
    uint32_t seed = 1;
    uint32_t maxMuStas = 9;       // 9 x 26-tone RUs fit in 20 MHz
    double radius = 5.0;          // m, single cell: ring around the AP
    double hiddenOffset = 28.0;   // m, hidden: two groups at +-offset from the AP
    double accessReqMs = 0.0;     // MU scheduler channel-access request interval, ms (0 = off)
    bool perFlow = false;
    std::string csvFile = "";
    std::string traceFile = "";
    double traceFrom = 3.0;
    double traceTo = 3.2;
    std::string label = "";

    CommandLine cmd(__FILE__);
    cmd.AddValue("nStations", "Number of stations", nStations);
    cmd.AddValue("rts", "Enable RTS/CTS for every frame", useRts);
    cmd.AddValue("ofdma", "Enable DL/UL OFDMA (RR multi-user scheduler)", useOfdma);
    cmd.AddValue("ulOfdma", "UL OFDMA on top of DL when ofdma is on", ulOfdma);
    cmd.AddValue("direction", "dl, ul or both", direction);
    cmd.AddValue("topology", "single (ring around AP), hidden (two groups out of range of each other) or cluster (one group, control)", topology);
    cmd.AddValue("simTime", "Traffic duration in seconds", simTime);
    cmd.AddValue("payload", "UDP payload size in bytes", payload);
    cmd.AddValue("perStaMbps", "Offered load per station per direction, Mbit/s", perStaMbps);
    cmd.AddValue("mcs", "HE MCS index (0-11), fixed rate", mcs);
    cmd.AddValue("channelWidth", "Channel width in MHz", channelWidth);
    cmd.AddValue("guardInterval", "Guard interval in ns (800, 1600, 3200)", guardInterval);
    cmd.AddValue("seed", "RNG run number (replication)", seed);
    cmd.AddValue("maxMuStas", "Max stations served per OFDMA transmission", maxMuStas);
    cmd.AddValue("radius", "Ring radius around the AP, single topology (m)", radius);
    cmd.AddValue("hiddenOffset", "Group distance from the AP, hidden topology (m)", hiddenOffset);
    cmd.AddValue("accessReqMs", "OFDMA: AP asks for channel access every X ms so UL triggers can go out with no DL traffic (0 = off)", accessReqMs);
    cmd.AddValue("perFlow", "Print per-flow packets", perFlow);
    cmd.AddValue("trace", "Write every PPDU sent inside [traceFrom, traceTo) to this CSV", traceFile);
    cmd.AddValue("traceFrom", "Trace window start, seconds of simulated time", traceFrom);
    cmd.AddValue("traceTo", "Trace window end, seconds of simulated time", traceTo);
    cmd.AddValue("csv", "Append one result row to this CSV file", csvFile);
    cmd.AddValue("label", "Free-text tag copied into the CSV row", label);
    cmd.Parse(argc, argv);

    NS_ABORT_MSG_IF(direction != "dl" && direction != "ul" && direction != "both",
                    "direction must be dl, ul or both");
    NS_ABORT_MSG_IF(topology != "single" && topology != "hidden" && topology != "cluster",
                    "topology must be single, hidden or cluster");

    auto wallStart = std::chrono::steady_clock::now();

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(seed);

    // RTS/CTS on every frame
    if (useRts)
    {
        Config::SetDefault("ns3::WifiRemoteStationManager::RtsCtsThreshold", StringValue("0"));
        Config::SetDefault("ns3::WifiDefaultProtectionManager::EnableMuRts", BooleanValue(true));
    }
    Config::SetDefault("ns3::WifiDefaultAckManager::DlMuAckSequenceType",
                       EnumValue(WifiAcknowledgment::DL_MU_BAR_BA_SEQUENCE));

    NodeContainer apNode;
    apNode.Create(1);
    NodeContainer staNodes;
    staNodes.Create(nStations);

    // PHY / channel: same spectrum PHY for every config so only the MAC differs
    auto spectrumChannel = CreateObject<MultiModelSpectrumChannel>();
    spectrumChannel->AddPropagationLossModel(CreateObject<LogDistancePropagationLossModel>());
    spectrumChannel->SetPropagationDelayModel(CreateObject<ConstantSpeedPropagationDelayModel>());

    SpectrumWifiPhyHelper phy;
    phy.SetChannel(spectrumChannel);
    std::ostringstream chan;
    chan << "{0, " << channelWidth << ", BAND_5GHZ, 0}";
    phy.Set("ChannelSettings", StringValue(chan.str()));

    std::ostringstream dataMode;
    dataMode << "HeMcs" << mcs;
    double refMbps = HePhy::GetNonHtReferenceRate(mcs) / 1e6;
    std::ostringstream ctrlMode;
    ctrlMode << "OfdmRate" << refMbps << "Mbps";

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211ax);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",
                                 StringValue(dataMode.str()),
                                 "ControlMode",
                                 StringValue(ctrlMode.str()));
    wifi.ConfigHeOptions("GuardInterval", TimeValue(NanoSeconds(guardInterval)));

    Ssid ssid("nss-wifi6");
    WifiMacHelper mac;
    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer staDevs = wifi.Install(phy, mac, staNodes);

    if (useOfdma)
    {
        mac.SetMultiUserScheduler("ns3::RrMultiUserScheduler",
                                  "EnableUlOfdma",
                                  BooleanValue(ulOfdma),
                                  "EnableBsrp",
                                  BooleanValue(ulOfdma),
                                  "NStations",
                                  UintegerValue(maxMuStas),
                                  "AccessReqInterval",
                                  TimeValue(MilliSeconds(accessReqMs)));
    }
    mac.SetType("ns3::ApWifiMac",
                "Ssid",
                SsidValue(ssid),
                "EnableBeaconJitter",
                BooleanValue(false),
                "BeaconGeneration",
                BooleanValue(false));
    NetDeviceContainer apDev = wifi.Install(phy, mac, apNode);

    int64_t stream = 100;
    stream += WifiHelper::AssignStreams(apDev, stream);
    stream += WifiHelper::AssignStreams(staDevs, stream);

    // positions
    MobilityHelper mob;
    auto pos = CreateObject<ListPositionAllocator>();
    pos->Add(Vector(0, 0, 0)); // AP
    for (uint32_t i = 0; i < nStations; i++)
    {
        if (topology == "single")
        {
            double a = 2 * M_PI * i / nStations;
            pos->Add(Vector(radius * std::cos(a), radius * std::sin(a), 0));
        }
        else if (topology == "cluster")
        {
            // control for hidden: same distance from the AP, all on one side, so they hear each other
            double y = (static_cast<int>(i % 7) - 3) * 0.5;
            pos->Add(Vector(hiddenOffset, y, 0));
        }
        else
        {
            // two groups on opposite sides of the AP, spread a little in y
            double side = (i % 2 == 0) ? 1.0 : -1.0;
            double y = (static_cast<int>((i / 2) % 7) - 3) * 0.5;
            pos->Add(Vector(side * hiddenOffset, y, 0));
        }
    }
    mob.SetPositionAllocator(pos);
    mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mob.Install(apNode);
    mob.Install(staNodes);

    // static association + block ack, so 60 stations do not fight over association
    auto apWifiDev = DynamicCast<WifiNetDevice>(apDev.Get(0));
    WifiStaticSetupHelper::SetStaticAssociation(apWifiDev, staDevs);
    WifiStaticSetupHelper::SetStaticBlockAck(apWifiDev, staDevs, {0});

    InternetStackHelper stack;
    stack.Install(apNode);
    stack.Install(staNodes);
    Ipv4AddressHelper addr;
    addr.SetBase("10.1.0.0", "255.255.0.0");
    Ipv4InterfaceContainer staIf = addr.Assign(staDevs);
    Ipv4InterfaceContainer apIf = addr.Assign(apDev);
    NeighborCacheHelper nb;
    nb.PopulateNeighborCache();

    // traffic
    const double interval = payload * 8.0 / (perStaMbps * 1e6); // s between packets
    const double appStart = 1.0;
    const double appStop = appStart + simTime;
    const uint16_t dlPort = 9;
    const uint16_t ulPort = 10;

    if (direction == "dl" || direction == "both")
    {
        UdpServerHelper srv(dlPort);
        ApplicationContainer sa = srv.Install(staNodes);
        sa.Start(Seconds(0));
        sa.Stop(Seconds(appStop + 1));
        for (uint32_t i = 0; i < nStations; i++)
        {
            UdpClientHelper cli(staIf.GetAddress(i), dlPort);
            cli.SetAttribute("MaxPackets", UintegerValue(4294967295U));
            cli.SetAttribute("Interval", TimeValue(Seconds(interval)));
            cli.SetAttribute("PacketSize", UintegerValue(payload));
            ApplicationContainer ca = cli.Install(apNode.Get(0));
            ca.Start(Seconds(appStart + 0.001 * i)); // tiny stagger, avoids lock-step
            ca.Stop(Seconds(appStop));
        }
    }
    if (direction == "ul" || direction == "both")
    {
        UdpServerHelper srv(ulPort);
        ApplicationContainer sa = srv.Install(apNode);
        sa.Start(Seconds(0));
        sa.Stop(Seconds(appStop + 1));
        for (uint32_t i = 0; i < nStations; i++)
        {
            UdpClientHelper cli(apIf.GetAddress(0), ulPort);
            cli.SetAttribute("MaxPackets", UintegerValue(4294967295U));
            cli.SetAttribute("Interval", TimeValue(Seconds(interval)));
            cli.SetAttribute("PacketSize", UintegerValue(payload));
            ApplicationContainer ca = cli.Install(staNodes.Get(i));
            ca.Start(Seconds(appStart + 0.001 * i));
            ca.Stop(Seconds(appStop));
        }
    }

    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Phys/*/PhyTxPsduBegin",
        MakeCallback(&OnPhyTx));

    if (!traceFile.empty())
    {
        g_traceFrom = traceFrom;
        g_traceTo = traceTo;
        Config::Connect("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Phys/*/PhyTxPsduBegin",
                        MakeCallback(&OnPhyTxTrace));
    }

    FlowMonitorHelper fmh;
    Ptr<FlowMonitor> fm = fmh.InstallAll();

    Simulator::Stop(Seconds(appStop + 1.5)); // drain queues
    Simulator::Run();
    fm->CheckForLostPackets();

    auto classifier = DynamicCast<Ipv4FlowClassifier>(fmh.GetClassifier());
    struct Agg
    {
        uint64_t tx{0};
        uint64_t rx{0};
        double delaySum{0};
    };
    Agg dl;
    Agg ul;
    std::vector<double> staMbps; // per flow goodput, for fairness
    for (const auto& [id, st] : fm->GetFlowStats())
    {
        auto t = classifier->FindFlow(id);
        Agg* a = nullptr;
        if (t.destinationPort == dlPort)
        {
            a = &dl;
        }
        else if (t.destinationPort == ulPort)
        {
            a = &ul;
        }
        if (!a)
        {
            continue;
        }
        a->tx += st.txPackets;
        a->rx += st.rxPackets;
        a->delaySum += st.delaySum.GetSeconds();
        if (perFlow)
        {
            std::cout << "  flow " << t.sourceAddress << " -> " << t.destinationAddress << ":"
                      << t.destinationPort << " tx " << st.txPackets << " rx " << st.rxPackets
                      << std::endl;
        }
        staMbps.push_back(st.rxPackets * payload * 8.0 / simTime / 1e6);
    }
    Simulator::Destroy();

    if (!traceFile.empty())
    {
        std::ofstream tr(traceFile);
        tr << "startUs,node,type,durUs,bytes,mpdus,receivers,mu,retry\n";
        for (const auto& r : g_trace)
        {
            tr << r.startUs << ',' << r.node << ',' << r.type << ',' << r.durUs << ',' << r.bytes
               << ',' << r.mpdus << ',' << r.receivers << ',' << r.mu << ',' << (r.retry ? 1 : 0)
               << '\n';
        }
    }

    auto gp = [&](const Agg& a) { return a.rx * payload * 8.0 / simTime / 1e6; };
    auto dly = [&](const Agg& a) { return a.rx ? a.delaySum / a.rx * 1000.0 : 0.0; };

    uint64_t totTx = dl.tx + ul.tx;
    uint64_t totRx = dl.rx + ul.rx;
    double totDelay = (dl.delaySum + ul.delaySum);
    double goodput = gp(dl) + gp(ul);
    double meanDelay = totRx ? totDelay / totRx * 1000.0 : 0.0;
    double loss = totTx ? 100.0 * (totTx - totRx) / totTx : 0.0;
    double offered = nStations * perStaMbps * ((direction == "both") ? 2 : 1);

    // Jain fairness over per-flow goodput
    double s1 = 0;
    double s2 = 0;
    for (double x : staMbps)
    {
        s1 += x;
        s2 += x * x;
    }
    double jain = (s2 > 0) ? (s1 * s1) / (staMbps.size() * s2) : 0.0;

    double muShare = g_totalPpdu ? 100.0 * (g_dlMuPpdu + g_ulMuPpdu) / g_totalPpdu : 0.0;
    double wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();

    const std::string header =
        "label,topology,direction,nStations,rts,ofdma,ulOfdma,accessReqMs,mcs,width,payload,perStaMbps,"
        "simTime,seed,offeredMbps,goodputMbps,dlMbps,ulMbps,meanDelayMs,dlDelayMs,ulDelayMs,"
        "lossPct,jain,txPkts,rxPkts,ppdus,dlMuPpdus,ulMuPpdus,muPct,wallSec";

    std::ostringstream row;
    row << std::fixed << std::setprecision(4) << label << ',' << topology << ',' << direction << ','
        << nStations << ',' << useRts << ',' << useOfdma << ',' << (useOfdma && ulOfdma) << ',' << accessReqMs << ','
        << mcs << ',' << channelWidth << ',' << payload << ',' << perStaMbps << ',' << simTime << ','
        << seed << ',' << offered << ',' << goodput << ',' << gp(dl) << ',' << gp(ul) << ','
        << meanDelay << ',' << dly(dl) << ',' << dly(ul) << ',' << loss << ',' << jain << ','
        << totTx << ',' << totRx << ',' << g_totalPpdu << ',' << g_dlMuPpdu << ',' << g_ulMuPpdu
        << ',' << muShare << ',' << wall;

    if (!csvFile.empty())
    {
        bool fresh = false;
        {
            std::ifstream probe(csvFile);
            fresh = !probe.good() || probe.peek() == std::ifstream::traits_type::eof();
        }
        std::ofstream out(csvFile, std::ios::app);
        if (fresh)
        {
            out << header << '\n';
        }
        out << row.str() << '\n';
    }

    std::cout << "N=" << nStations << " rts=" << useRts << " ofdma=" << useOfdma
              << " dir=" << direction << " topo=" << topology << " seed=" << seed << "\n"
              << "  offered " << offered << " Mbps | goodput " << goodput << " Mbps (DL "
              << gp(dl) << ", UL " << gp(ul) << ")\n"
              << "  mean delay " << meanDelay << " ms | loss " << loss << " % | Jain " << jain
              << "\n"
              << "  PPDUs " << g_totalPpdu << " (DL-MU " << g_dlMuPpdu << ", UL-MU " << g_ulMuPpdu
              << ", " << muShare << " % multi-user) | wall " << wall << " s" << std::endl;
    return 0;
}
