// Run in Chrome with a synthetic getUserMedia feed; never capture a real camera.
@TestOn('browser')
library;
import 'dart:async';
import 'dart:convert';
import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:stc_camera_preview/src/peer_link.dart';

class Backend implements FletBackend {
  final events=<Map<String,dynamic>>[];
  @override void triggerControlEvent(Control control,String name,[dynamic data]){events.add({'control':control.id,...Map<String,dynamic>.from(jsonDecode(data))});}
  @override dynamic noSuchMethod(Invocation invocation)=>super.noSuchMethod(invocation);
}
void main(){
  testWidgets('offline offer/reply connects and transfers a fragmented match without servers',(tester)async{
    final backend=Backend();
    final a=Control(id:1,type:'StcPeerLink',properties:{'bridge_id':'host'},backend:backend);
    final b=Control(id:2,type:'StcPeerLink',properties:{'bridge_id':'guest'},backend:backend);
    Future<void> render()=>tester.pumpWidget(Directionality(textDirection:TextDirection.ltr,child:Column(children:[StcPeerLinkControl(key:const ValueKey(1),control:a),StcPeerLinkControl(key:const ValueKey(2),control:b)])));
    var sequence=0;
    Future<Map<String,dynamic>> command(Control control,String op,Map<String,dynamic> args)async{
      final id='${++sequence}';control.properties['command']=jsonEncode({'id':id,'op':op,...args});await tester.runAsync(render);
      Map<String,dynamic>? reply;
      await tester.runAsync(()async{for(var i=0;i<160;i++){final found=backend.events.where((e)=>e['control']==control.id&&e['kind']=='reply'&&e['id']==id);if(found.isNotEmpty){reply=found.first;break;}await Future<void>.delayed(const Duration(milliseconds:100));}});
      expect(reply,isNotNull,reason:op+backend.events.toString());expect(reply!['error'],isNull);return Map<String,dynamic>.from(reply!['result']);
    }
    await render();
    final offer=await command(a,'offer',{'peer':'0123456789abcdef0123456789abcdef'});
    final answer=await command(b,'answer',{'code':offer['code']});
    await command(a,'accept',{'code':answer['code']});
    await tester.runAsync(()async{for(var i=0;i<100&&!backend.events.any((e)=>e['kind']=='open'&&e['control']==1);i++){await Future<void>.delayed(const Duration(milliseconds:100));}});
    expect(backend.events.where((e)=>e['kind']=='open').length,2);
    final text=jsonEncode({'events':List.generate(2000,(i)=>{'id':i,'stat':'Shot'})});
    await command(b,'send',{'peer':'0123456789abcdef0123456789abcdef','payload':text});
    await tester.runAsync(()async{for(var i=0;i<100&&!backend.events.any((e)=>e['kind']=='message');i++){await Future<void>.delayed(const Duration(milliseconds:100));}});
    expect(backend.events.firstWhere((e)=>e['kind']=='message')['payload'],text);
    const peer='0123456789abcdef0123456789abcdef';
    await command(a,'source',{'source':'self','viewers':[peer]});
    await command(b,'source',{'source':peer});
    await command(a,'camera',{'enabled':true,'lens':'front'});
    await tester.runAsync(()=>Future<void>.delayed(const Duration(seconds:3)));
    final video=await command(b,'diagnostics',{'peer':peer});
    expect((video['reports'] as List).any((r)=>r['type']=='inbound-rtp'&&(r['bytesReceived']??0)>0),isTrue,reason:video.toString());
    await command(a,'camera',{'enabled':false});
    await command(a,'close',{});await command(b,'close',{});await tester.pumpWidget(const SizedBox());
  },timeout:const Timeout(Duration(minutes:2)));
}

