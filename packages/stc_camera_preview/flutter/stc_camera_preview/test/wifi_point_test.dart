import 'dart:convert';
import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:stc_camera_preview/src/wifi_point.dart';
class Backend implements FletBackend {@override dynamic noSuchMethod(Invocation invocation)=>super.noSuchMethod(invocation);}
class Probe extends Control {
 final events=<Map<String,dynamic>>[];
 Probe():super(id:1,type:'StcWifiPoint',backend:Backend(),properties:{'command':jsonEncode({'id':'one','op':'start','ssid':'DIRECT-ST-Team','password':'stable-pass'})});
 @override void triggerEvent(String name,[dynamic data]){events.add(jsonDecode(data));}
}
void main(){
 TestWidgetsFlutterBinding.ensureInitialized();
 testWidgets('returns network details and stops on removal',(tester)async{
  final calls=<String>[];
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(const MethodChannel('stat_tracker/wifi_point'),(call)async{calls.add(call.method);if(call.method=='start')expect(call.arguments,{'ssid':'DIRECT-ST-Team','password':'stable-pass'});return {'ssid':'test-network','password':'test-only'};});
  final c=Probe();await tester.pumpWidget(StcWifiPointControl(control:c));await tester.pump();
  expect(c.events.single['id'],'one');expect(c.events.single['result']['ssid'],'test-network');
  await tester.pumpWidget(const SizedBox());await tester.pump();expect(calls,['start','stop']);
 });
 testWidgets('permission failures are returned to the requesting command',(tester)async{
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(const MethodChannel('stat_tracker/wifi_point'),(call)async{if(call.method=='start')throw PlatformException(code:'wifi',message:'Permission declined');return null;});
  final c=Probe();await tester.pumpWidget(StcWifiPointControl(control:c));await tester.pump();expect(c.events.single['error'],'Permission declined');
  await tester.pumpWidget(const SizedBox());await tester.pump();
 });
}
