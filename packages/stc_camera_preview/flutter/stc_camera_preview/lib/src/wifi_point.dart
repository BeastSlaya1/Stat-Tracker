import 'dart:async';
import 'dart:convert';
import 'package:flutter/widgets.dart';
import 'package:flutter/services.dart';
import 'package:flet/flet.dart';
class StcWifiPointControl extends StatefulWidget {
 final Control control;
 const StcWifiPointControl({super.key,required this.control});
 @override State<StcWifiPointControl> createState()=>_WifiState();
}
class _WifiState extends State<StcWifiPointControl>{
 static const channel=MethodChannel('stat_tracker/wifi_point');String last='';
 @override void initState(){super.initState();configure();}
 @override void didUpdateWidget(covariant StcWifiPointControl oldWidget){super.didUpdateWidget(oldWidget);configure();}
 void configure(){final raw=widget.control.getString('command','')!;if(raw.isEmpty||raw==last)return;last=raw;run(raw);}
 Future<void> run(String raw)async{dynamic command;try{command=jsonDecode(raw);final result=await channel.invokeMethod(command['op'],{'ssid':command['ssid'],'password':command['password']});if(mounted)widget.control.triggerEvent('event',jsonEncode({'id':command['id'],'result':result}));}catch(e){if(mounted)widget.control.triggerEvent('event',jsonEncode({'id':command?['id'],'error':e is PlatformException?e.message:'Wi-Fi Direct is unavailable in this build.'}));}}
 @override void dispose(){unawaited(channel.invokeMethod('stop').catchError((_)=>null));super.dispose();}
 @override Widget build(BuildContext context)=>const SizedBox(width:1,height:1);
}
