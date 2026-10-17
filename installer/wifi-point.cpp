#include <windows.h>
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Security.Credentials.h>
#include <winrt/Windows.Devices.Enumeration.h>
#include <winrt/Windows.Devices.WiFiDirect.h>
#include <iostream>
#include <mutex>
#include <vector>
#include <thread>
#include <atomic>
using namespace winrt;
using namespace Windows::Devices::WiFiDirect;
std::mutex output;
void report(const char* message){std::lock_guard<std::mutex> lock(output);std::cout<<message<<std::endl;}
int main(int argc,char** argv){
 try{
  if(argc!=2)return 2;
  HANDLE parent=OpenProcess(SYNCHRONIZE,FALSE,std::stoul(argv[1]));if(!parent)return 2;
  init_apartment(apartment_type::multi_threaded);
  std::string ssid,password;std::getline(std::cin,ssid);std::getline(std::cin,password);
  if(ssid.size()>32||ssid.empty()||password.size()<8||password.size()>63)return 2;
  WiFiDirectAdvertisementPublisher publisher;
  auto advertisement=publisher.Advertisement();
  advertisement.IsAutonomousGroupOwnerEnabled(true);
  advertisement.LegacySettings().IsEnabled(true);
  advertisement.LegacySettings().Ssid(to_hstring(ssid));
  advertisement.LegacySettings().Passphrase().Password(to_hstring(password));
  std::atomic<bool> stop=false;
  publisher.StatusChanged([&stop](auto const&,auto const& args){
   if(args.Status()==WiFiDirectAdvertisementPublisherStatus::Started)report("READY");
   if(args.Status()==WiFiDirectAdvertisementPublisherStatus::Aborted){stop=true;report("ERROR: Windows could not create the Wi-Fi link. Check Wi-Fi is on, turn off other hotspots, and check adapter support.");}
   if(args.Status()==WiFiDirectAdvertisementPublisherStatus::Stopped)report("STOPPED");
  });
  std::mutex peers_lock;std::vector<WiFiDirectDevice> peers;
  WiFiDirectConnectionListener listener;
  listener.ConnectionRequested([&](auto const&,auto const& args){try{
   auto request=args.GetConnectionRequest();
   auto device=WiFiDirectDevice::FromIdAsync(request.DeviceInformation().Id()).get();
   if(device){std::lock_guard<std::mutex> lock(peers_lock);peers.push_back(device);}
   request.Close();
  }catch(...){report("ERROR: A device could not join the Wi-Fi link.");}});
  std::thread input([&]{std::string line;std::getline(std::cin,line);stop=true;});input.detach();
  publisher.Start();
  while(!stop&&WaitForSingleObject(parent,200)==WAIT_TIMEOUT){}
  publisher.Stop();CloseHandle(parent);
  // Process exit releases the network and any pending connection callbacks.
  ExitProcess(0);
 }catch(hresult_error const&){report("ERROR: Wi-Fi Direct is unavailable. Turn Wi-Fi on and check this adapter supports a direct access point.");return 1;}
 catch(...){report("ERROR: Could not create the Wi-Fi link.");return 1;}
}
