import 'dart:convert';
import 'package:flet/flet.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:stc_camera_preview/src/rtc_video.dart';
class Backend implements FletBackend {
  @override dynamic noSuchMethod(Invocation invocation)=>super.noSuchMethod(invocation);
}
class Probe extends Control {
  final events=<Map<String,dynamic>>[];
  Probe(String role,{String id=''}) : super(id:1,type:'StcRtcVideo',backend:Backend(),properties:{'role':role,'device_id':id});
  @override void triggerEvent(String name,[dynamic data]){events.add(jsonDecode(data));}
}
void main(){
  TestWidgetsFlutterBinding.ensureInitialized();
  final calls=<MethodCall>[];
  var fallback=false;
  var ids=['main','usb','capture'];
  setUp((){
    calls.clear();fallback=false;ids=['main','usb','capture'];
    final messenger=TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    for(final name in ['FlutterWebRTC.Event','FlutterWebRTC/Texture1']){
      messenger.setMockMethodCallHandler(MethodChannel(name),(_)async=>null);
    }
    messenger.setMockMethodCallHandler(const MethodChannel('FlutterWebRTC.Method'),(call)async{
      calls.add(call);
      if(call.method=='getSources')return {'sources':[for(final id in ids){'deviceId':id,'groupId':'','kind':'videoinput','label':'Camera $id'}]};
      if(call.method=='createVideoRenderer')return {'textureId':1};
      if(call.method=='getUserMedia'){
        final id=call.arguments['constraints']['video']['optional'][0]['sourceId'];
        return {'streamId':'stream','audioTracks':[],'videoTracks':[{'id':'track','kind':'video','label':'Camera','enabled':true,'settings':{'deviceId':fallback?'main':id}}]};
      }
      return null;
    });
  });
  Future<void> mount(WidgetTester tester,Probe control)async{
    await tester.pumpWidget(MaterialApp(home:StcRtcVideoControl(control:control)));
    for(var i=0;i<20;i++){await tester.pump(const Duration(milliseconds:10));}
    await tester.runAsync(()=>Future<void>.delayed(const Duration(milliseconds:50)));
    await tester.pump();
  }
  Future<void> close(WidgetTester tester)async{await tester.pumpWidget(const SizedBox());await tester.runAsync(()=>Future<void>.delayed(const Duration(milliseconds:50)));for(var i=0;i<20;i++){await tester.pump(const Duration(milliseconds:10));}}
  testWidgets('discovery, reordered devices, fallback and disconnection use exact identities',(tester)async{
   {
    final c=Probe('enumerate');await mount(tester,c);
    expect(c.events.single['devices'].map((d)=>d['id']),ids);
    expect(calls.where((c)=>c.method=='getUserMedia'),isEmpty);
    await close(tester);
   }
   calls.clear();
   {
    ids=['capture','main','usb'];final c=Probe('preview',id:'usb');await mount(tester,c);
    final capture=calls.singleWhere((c)=>c.method=='getUserMedia');
    expect(capture.arguments['constraints']['video']['optional'],[{'sourceId':'usb'}]);
    expect(c.events.last['status'],'Camera preview');await close(tester);
   }
   calls.clear();
   {
    fallback=true;final c=Probe('preview',id:'usb');await mount(tester,c);
    expect(c.events.last['error'],contains('selected camera could not be opened'));
    expect(calls.any((c)=>c.method=='trackDispose'),isTrue);
    expect(calls.where((c)=>c.method=='videoRendererSetSrcObject').every((c)=>c.arguments['streamId']==''),isTrue);
    await close(tester);
   }
   calls.clear();fallback=false;
   {
    ids=['main'];final c=Probe('preview',id:'usb');await mount(tester,c);
    expect(c.events.last['error'],contains('disconnected'));
    expect(calls.where((c)=>c.method=='getUserMedia'),isEmpty);await close(tester);
   }
  });
}
