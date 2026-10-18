// Elevated, process-bound local sharing. Dynamic WFP objects never persist.
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <initguid.h>
#include <fwpmu.h>
#include <iphlpapi.h>
#include <vector>
#include <string>
#include <cstdlib>

static bool local(UINT32 ip) {
    return (ip >> 24) == 10 || (ip >> 20) == 0xac1 ||
           (ip >> 16) == 0xc0a8 || (ip >> 16) == 0xa9fe;
}
int wmain(int argc, wchar_t** argv) {
    if (argc != 6) return 2;
    DWORD pid = wcstoul(argv[1], nullptr, 10);
    IN_ADDR address{};
    if (!pid || InetPtonW(AF_INET, argv[2], &address) != 1) return 2;
    UINT32 ip = ntohl(address.S_un.S_addr);
    if (!local(ip)) return 2;
    UINT32 port = wcstoul(argv[5], nullptr, 10);
    if (port < 1024 || port > 65535) return 2;
    HANDLE owner = OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!owner) return 3;
    wchar_t executable[32768]; DWORD length = 32768;
    if (!QueryFullProcessImageNameW(owner, 0, executable, &length)) return 3;
    HANDLE stop = OpenEventW(SYNCHRONIZE, FALSE, argv[3]);
    HANDLE ready = OpenEventW(EVENT_MODIFY_STATE, FALSE, argv[4]);
    if (!stop || !ready) return 4;
    // Resolve the selected address against a real, active adapter. Never accept
    // caller-provided subnets or an arbitrary executable/firewall scope.
    ULONG size = 16384; std::vector<BYTE> bytes(size);
    ULONG result = GetAdaptersAddresses(AF_INET, 0, nullptr,
        reinterpret_cast<IP_ADAPTER_ADDRESSES*>(bytes.data()), &size);
    if (result == ERROR_BUFFER_OVERFLOW) {
        bytes.resize(size); result = GetAdaptersAddresses(AF_INET, 0, nullptr,
            reinterpret_cast<IP_ADAPTER_ADDRESSES*>(bytes.data()), &size);
    }
    if (result != NO_ERROR) return 5;
    UINT64 luid = 0; ULONG prefix = 32;
    for (auto a = reinterpret_cast<IP_ADAPTER_ADDRESSES*>(bytes.data()); a; a = a->Next) {
        if (a->OperStatus != IfOperStatusUp) continue;
        for (auto u = a->FirstUnicastAddress; u; u = u->Next) {
            auto s = reinterpret_cast<sockaddr_in*>(u->Address.lpSockaddr);
            if (s && s->sin_family == AF_INET && s->sin_addr.S_un.S_addr == address.S_un.S_addr) {
                luid = a->Luid.Value; prefix = u->OnLinkPrefixLength;
            }
        }
    }
    if (!luid || prefix > 32 || prefix < 8) return 5;
    UINT32 mask = 0xffffffffu << (32 - prefix);
    UINT32 network = ip & mask;
    if (!local(network) || !local(network | ~mask)) return 5;
    HANDLE engine = nullptr;
    FWPM_SESSION0 session{}; session.flags = FWPM_SESSION_FLAG_DYNAMIC;
    session.displayData.name = const_cast<wchar_t*>(L"Stat Tracker temporary local sharing");
    if (FwpmEngineOpen0(nullptr, RPC_C_AUTHN_WINNT, nullptr, &session, &engine)) return 6;
    FWP_BYTE_BLOB* app = nullptr;
    DWORD error = FwpmGetAppIdFromFileName0(executable, &app);
    GUID key{}; UuidCreate(&key);
    FWPM_SUBLAYER0 layer{}; layer.subLayerKey = key; layer.weight = 0xffff;
    layer.displayData.name = session.displayData.name;
    if (!error) error = FwpmTransactionBegin0(engine, 0);
    if (!error) error = FwpmSubLayerAdd0(engine, &layer, nullptr);
    FWP_V4_ADDR_AND_MASK remote{network, mask};
    for (UINT8 protocol : {UINT8(IPPROTO_TCP), UINT8(IPPROTO_UDP)}) {
        if (error) break;
        FWPM_FILTER_CONDITION0 c[5]{};
        for (auto& condition : c) condition.matchType = FWP_MATCH_EQUAL;
        c[0].fieldKey = FWPM_CONDITION_ALE_APP_ID;
        c[0].conditionValue.type = FWP_BYTE_BLOB_TYPE; c[0].conditionValue.byteBlob = app;
        c[1].fieldKey = FWPM_CONDITION_IP_LOCAL_INTERFACE;
        c[1].conditionValue.type = FWP_UINT64; c[1].conditionValue.uint64 = &luid;
        c[2].fieldKey = FWPM_CONDITION_IP_REMOTE_ADDRESS;
        c[2].conditionValue.type = FWP_V4_ADDR_MASK; c[2].conditionValue.v4AddrMask = &remote;
        c[3].fieldKey = FWPM_CONDITION_IP_PROTOCOL;
        c[3].conditionValue.type = FWP_UINT8; c[3].conditionValue.uint8 = protocol;
        c[4].fieldKey = FWPM_CONDITION_IP_LOCAL_PORT;
        c[4].conditionValue.type = FWP_UINT16; c[4].conditionValue.uint16 = static_cast<UINT16>(port);
        FWPM_FILTER0 filter{};
        filter.displayData.name = session.displayData.name;
        filter.layerKey = FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V4;
        filter.subLayerKey = key; filter.action.type = FWP_ACTION_PERMIT;
        filter.flags = FWPM_FILTER_FLAG_CLEAR_ACTION_RIGHT;
        filter.weight.type = FWP_UINT8; filter.weight.uint8 = 15;
        filter.numFilterConditions = protocol == IPPROTO_TCP ? 5 : 4;
        filter.filterCondition = c;
        error = FwpmFilterAdd0(engine, &filter, nullptr, nullptr);
    }
    if (!error) error = FwpmTransactionCommit0(engine);
    else FwpmTransactionAbort0(engine);
    if (app) FwpmFreeMemory0(reinterpret_cast<void**>(&app));
    if (!error) {
        SetEvent(ready);
        HANDLE events[]{owner, stop}; WaitForMultipleObjects(2, events, FALSE, INFINITE);
    }
    FwpmEngineClose0(engine); // Also removed by Windows if this process crashes.
    CloseHandle(owner); CloseHandle(stop); CloseHandle(ready);
    return error ? 7 : 0;
}
