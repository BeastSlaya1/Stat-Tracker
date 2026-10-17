package za.co.stattracker.wifi;
import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.net.wifi.p2p.WifiP2pManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import java.util.HashMap;
import io.flutter.embedding.engine.plugins.FlutterPlugin;
import io.flutter.embedding.engine.plugins.activity.ActivityAware;
import io.flutter.embedding.engine.plugins.activity.ActivityPluginBinding;
import io.flutter.plugin.common.MethodChannel;
import io.flutter.plugin.common.PluginRegistry;

public class WifiPointPlugin implements FlutterPlugin,ActivityAware,PluginRegistry.RequestPermissionsResultListener {
 private MethodChannel bridge; private WifiP2pManager wifi; private WifiP2pManager.Channel channel;
 private Activity activity; private ActivityPluginBinding binding; private MethodChannel.Result pending;
 private boolean owns=false; private int generation=0; private final Handler handler=new Handler(Looper.getMainLooper());
 public void onAttachedToEngine(FlutterPluginBinding b){
  wifi=(WifiP2pManager)b.getApplicationContext().getSystemService(Context.WIFI_P2P_SERVICE);
  if(wifi!=null)channel=wifi.initialize(b.getApplicationContext(),Looper.getMainLooper(),()->{owns=false;fail("Wi-Fi service disconnected. Try again.");});
  bridge=new MethodChannel(b.getBinaryMessenger(),"stat_tracker/wifi_point");
  bridge.setMethodCallHandler((call,result)->{
   if(call.method.equals("stop")){stop();result.success(new HashMap<String,Object>());return;}
   if(!call.method.equals("start")){result.notImplemented();return;}
   if(pending!=null||owns){result.error("busy","A Wi-Fi link is already starting or active.",null);return;}
   if(activity==null||wifi==null||channel==null){result.error("unsupported","Wi-Fi Direct is unavailable on this device.",null);return;}
   pending=result;
   String permission=Build.VERSION.SDK_INT>=33?Manifest.permission.NEARBY_WIFI_DEVICES:Manifest.permission.ACCESS_FINE_LOCATION;
   if(activity.checkSelfPermission(permission)!=PackageManager.PERMISSION_GRANTED)activity.requestPermissions(new String[]{permission},4371);
   else start();
  });
 }
 private void fail(String text){if(pending!=null){pending.error("wifi",text,null);pending=null;}}
 @SuppressWarnings("MissingPermission") private void start(){
  if(pending==null||activity==null)return;
  final int attempt=++generation;
  try{wifi.requestGroupInfo(channel,existing->{
   if(attempt!=generation)return;
   if(existing!=null){fail("Another Wi-Fi Direct group is active. Disconnect it first.");return;}
   try{wifi.createGroup(channel,new WifiP2pManager.ActionListener(){
    public void onSuccess(){owns=true;if(attempt!=generation){stop();return;}readGroup(attempt,0);}
    public void onFailure(int reason){fail("Could not create Wi-Fi link ("+reason+"). Turn Wi-Fi on, enable Location if required, and close other hotspot apps.");}
   });}catch(SecurityException e){fail("Nearby Wi-Fi permission is required.");}
  });}catch(SecurityException e){fail("Nearby Wi-Fi permission or Location access is required.");}
  handler.postDelayed(()->{if(attempt==generation&&pending!=null){fail("Wi-Fi setup timed out. Try again.");stop();}},15000);
 }
 @SuppressWarnings("MissingPermission") private void readGroup(int attempt,int retry){
  if(attempt!=generation)return;
  try{wifi.requestGroupInfo(channel,group->{
   if(attempt!=generation)return;
   if(group==null||group.getPassphrase()==null){if(retry<20)handler.postDelayed(()->readGroup(attempt,retry+1),250);else{fail("Could not read Wi-Fi credentials.");stop();}return;}
   HashMap<String,Object> data=new HashMap<>();data.put("ssid",group.getNetworkName());data.put("password",group.getPassphrase());
   if(pending!=null){pending.success(data);pending=null;}
  });}catch(SecurityException e){fail("Wi-Fi permission was removed.");stop();}
 }
 private void stop(){generation++;fail("Wi-Fi setup cancelled.");if(owns&&wifi!=null&&channel!=null){owns=false;try{wifi.removeGroup(channel,null);}catch(Exception ignored){}}}
 public boolean onRequestPermissionsResult(int code,String[] permissions,int[] grants){if(code!=4371)return false;if(grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED)start();else fail("Nearby Wi-Fi permission was declined.");return true;}
 public void onAttachedToActivity(ActivityPluginBinding b){binding=b;activity=b.getActivity();b.addRequestPermissionsResultListener(this);}
 public void onDetachedFromActivityForConfigChanges(){if(binding!=null)binding.removeRequestPermissionsResultListener(this);binding=null;activity=null;}
 public void onReattachedToActivityForConfigChanges(ActivityPluginBinding b){onAttachedToActivity(b);}
 public void onDetachedFromActivity(){onDetachedFromActivityForConfigChanges();stop();}
 public void onDetachedFromEngine(FlutterPluginBinding b){stop();bridge.setMethodCallHandler(null);if(channel!=null&&Build.VERSION.SDK_INT>=27)channel.close();}
}
