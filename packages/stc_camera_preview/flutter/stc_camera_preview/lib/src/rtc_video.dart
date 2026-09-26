import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:http/http.dart' as http;

class StcRtcVideoControl extends StatefulWidget {
  final Control control;
  const StcRtcVideoControl({super.key,required this.control});
  @override
  State<StcRtcVideoControl> createState()=>_VideoState();
}

class _Cancelled implements Exception {}
class _VideoState extends State<StcRtcVideoControl> {
  static Future<void> _operations=Future.value();
  RTCVideoRenderer? _renderer;
  RTCPeerConnection? _peer;
  MediaStream? _stream;
  Timer? _pollTimer,_heartbeat,_deadline;
  String _settings='',_base='',_token='',_room='',_role='',_status='Starting camera…',_lastEvent='';
  final String _device=List.generate(16,(_)=>Random.secure().nextInt(256).toRadixString(16).padLeft(2,'0')).join();
  int _generation=0,_approval=0;
  bool _answered=false,_failed=false,_firstFrame=false;

  @override
  void initState(){super.initState();_configure();}
  @override
  void didUpdateWidget(covariant StcRtcVideoControl oldWidget){
    super.didUpdateWidget(oldWidget);_configure();
    final approval=widget.control.getInt('approve_request',0)!;
    if(approval!=_approval){_approval=approval;if(_role=='send'&&_room.isNotEmpty)unawaited(_approve());}
  }
  void _configure(){
    final c=widget.control;
    final settings=['role','room_code','lens','token','server_url'].map((k)=>c.getString(k,'')).join('|');
    if(settings==_settings)return;
    _settings=settings;final run=++_generation;
    _operations=_operations.catchError((Object _){}).then((_)async{
      await _close();if(!mounted||run!=_generation)return;
      try{await _start(run);}on _Cancelled{await _close();}catch(_){
        if(mounted&&run==_generation)await _fail('Camera connection failed. Check camera permission, staff sign-in and your network.');
      }
    });
  }
  void _check(int run){if(!mounted||run!=_generation)throw _Cancelled();}
  Map<String,String> get _headers=>{'Content-Type':'application/json','Authorization':'Bearer $_token','X-Camera-Device':_device,if(!kIsWeb)'User-Agent':'StatTracker/4.0.5'};
  Future<Map<String,dynamic>> _api(String path,{String method='GET',Map<String,dynamic>? body})async{
    final request=http.Request(method,Uri.parse('$_base$path'))..headers.addAll(_headers);
    if(body!=null)request.body=jsonEncode(body);
    final client=http.Client();
    try{
      final response=await http.Response.fromStream(await client.send(request).timeout(const Duration(seconds:15))).timeout(const Duration(seconds:15));
      final data=jsonDecode(response.body) as Map<String,dynamic>;
      if(response.statusCode>=400)throw StateError(data['error']?.toString()??'Camera service unavailable.');
      return data;
    }finally{client.close();}
  }
  void _emit(String status,{String? receiver,bool approved=false,String? error}){
    if(!mounted)return;
    final event=jsonEncode({'status':status,'room_code':_room,'receiver_name':receiver,'approved':approved,'error':error});
    if(event==_lastEvent)return;
    _lastEvent=event;setState(()=>_status=status);widget.control.triggerEvent('state',event);
  }
  Future<void> _start(int run)async{
    final c=widget.control;
    _base=c.getString('server_url','')!.replaceFirst(RegExp(r'/$'),'');_token=c.getString('token','')!;
    _role=c.getString('role','preview')!;_answered=false;_failed=false;_firstFrame=false;
    _approval=c.getInt('approve_request',0)!;
    _emit('Starting camera…');
    _renderer=RTCVideoRenderer();await _renderer!.initialize();_check(run);
    void frameReady(){
      if(mounted&&run==_generation){_firstFrame=true;if(_role=='receive'){_deadline?.cancel();_emit('Live — receiving camera video');}}
    }
    _renderer!.onFirstFrameRendered=frameReady;
    // The web renderer reports video dimensions instead of the native first-frame event.
    _renderer!.onResize=(){
      if((_renderer?.videoWidth??0)>0&&(_renderer?.videoHeight??0)>0)frameReady();
    };
    if(_role!='receive'){
      final lens=c.getString('lens','back')!;
      final video=<String,dynamic>{'facingMode':lens=='front'?'user':'environment','width':1280,'height':720,'frameRate':20};
      final index=int.tryParse(lens);
      if(index!=null){
        final devices=(await navigator.mediaDevices.enumerateDevices()).where((d)=>d.kind=='videoinput').toList();_check(run);
        if(index>=0&&index<devices.length)video['deviceId']=devices[index].deviceId;
      }
      _stream=await navigator.mediaDevices.getUserMedia({'audio':false,'video':video});_check(run);
      _renderer!.srcObject=_stream;setState((){});
      if(_role=='preview'){_emit('Camera preview');return;}
    }
    if(_token.isEmpty)throw StateError('Sign in first.');
    _peer=await createPeerConnection({'iceServers':[{'urls':'stun:stun.cloudflare.com:3478'}],'sdpSemantics':'unified-plan'});_check(run);
    final peer=_peer!;
    peer.onTrack=(event){if(mounted&&run==_generation&&event.streams.isNotEmpty){_renderer!.srcObject=event.streams.first;setState((){});}};
    peer.onConnectionState=(state){
      if(!mounted||run!=_generation)return;
      if(state==RTCPeerConnectionState.RTCPeerConnectionStateConnected){
        _pollTimer?.cancel();
        if(_role=='send'){_deadline?.cancel();_emit('Live — sending camera video');}
        else if(_firstFrame){_deadline?.cancel();_emit('Live — receiving camera video');}
      }else if(state==RTCPeerConnectionState.RTCPeerConnectionStateFailed){
        unawaited(_fail('Video could not connect. Use the same Wi-Fi and scan again. This network may require a relay.'));
      }else if(state==RTCPeerConnectionState.RTCPeerConnectionStateDisconnected){_emit('Video interrupted — waiting to reconnect');}
    };
    if(_role=='send'){
      for(final track in _stream!.getTracks()){await peer.addTrack(track,_stream!);_check(run);}
      await peer.setLocalDescription(await peer.createOffer());await _gather(peer);_check(run);
      final description=await peer.getLocalDescription();_check(run);
      final response=await _api('/camera/devices',method:'POST',body:{'offer':{'type':description!.type,'sdp':description.sdp},'name':c.getString('device_label','Match camera'),'kind':c.getString('device_kind','Browser')});
      _room=response['code'] as String;_check(run);_emit('Ready — scan for cameras on the receiving device');
    }else{
      _room=c.getString('room_code','')!;
      await _api('/camera/devices/$_room/join',method:'POST',body:{});_check(run);_emit('Waiting for approval on the camera device');
    }
    _heartbeat=Timer.periodic(const Duration(seconds:15),(_)=>unawaited(_beat(run)));
    unawaited(_poll(run));
  }
  Future<void> _gather(RTCPeerConnection peer)async{
    if(peer.iceGatheringState==RTCIceGatheringState.RTCIceGatheringStateComplete)return;
    final done=Completer<void>();
    peer.onIceGatheringState=(state){if(state==RTCIceGatheringState.RTCIceGatheringStateComplete&&!done.isCompleted)done.complete();};
    if(peer.iceGatheringState==RTCIceGatheringState.RTCIceGatheringStateComplete)return;
    await done.future.timeout(const Duration(seconds:10),onTimeout:(){});
  }
  void _connectionDeadline(int run){
    if((_firstFrame&&_role=='receive')||(_role=='send'&&_peer?.connectionState==RTCPeerConnectionState.RTCPeerConnectionStateConnected))return;
    _deadline?.cancel();_deadline=Timer(const Duration(seconds:45),(){if(mounted&&run==_generation)unawaited(_fail('No video arrived. Use the same Wi-Fi, restart Camera Mode and scan again.'));});
  }
  Future<void> _approve()async{
    final run=_generation;
    try{await _api('/camera/devices/$_room/approve',method:'POST',body:{});if(run==_generation)_emit('Approved — connecting video',approved:true);}
    catch(_){if(run==_generation)await _fail('Approval failed. Restart Camera Mode and scan again.');}
  }
  Future<void> _poll(int run)async{
    try{
      final data=await _api('/camera/devices/$_room');_check(run);
      if(_role=='send'){
        if(!_answered){_emit(data['receiver_name']!=null?'A device wants to receive this camera':'Ready — scan for cameras on the receiving device',receiver:data['receiver_name'] as String?,approved:data['approved']==true);}
        if(data['answer']!=null&&!_answered){_answered=true;final answer=data['answer'];await _peer!.setRemoteDescription(RTCSessionDescription(answer['sdp'],answer['type']));_check(run);_connectionDeadline(run);}
      }else if(data['offer']!=null&&!_answered){
        _answered=true;final offer=data['offer'];final peer=_peer!;
        await peer.setRemoteDescription(RTCSessionDescription(offer['sdp'],offer['type']));_check(run);
        await peer.setLocalDescription(await peer.createAnswer());await _gather(peer);_check(run);
        final answer=await peer.getLocalDescription();_check(run);
        await _api('/camera/devices/$_room/answer',method:'POST',body:{'answer':{'type':answer!.type,'sdp':answer.sdp}});_check(run);
        _connectionDeadline(run);if(!_firstFrame)_emit('Connecting video…');
      }
      if(mounted&&run==_generation&&_peer?.connectionState!=RTCPeerConnectionState.RTCPeerConnectionStateConnected)_pollTimer=Timer(const Duration(seconds:2),()=>unawaited(_poll(run)));
    }on _Cancelled{/* A stopped camera must not update the new session. */}catch(_){if(mounted&&run==_generation)await _fail('Camera unavailable. Check staff sign-in and scan again.');}
  }
  Future<void> _beat(int run)async{
    try{await _api('/camera/devices/$_room/heartbeat',method:'POST',body:{});}
    catch(_){if(mounted&&run==_generation)await _fail('Camera connection ended. Check your internet connection and scan again.');}
  }
  Future<void> _fail(String message)async{
    if(_failed)return;_failed=true;++_generation;
    await _close();_emit(message,error:message);
  }
  Future<void> _close()async{
    _pollTimer?.cancel();_heartbeat?.cancel();_deadline?.cancel();
    final room=_room;_room='';
    final peer=_peer;_peer=null;
    final stream=_stream;_stream=null;
    final renderer=_renderer;_renderer=null;
    if(peer!=null){peer.onConnectionState=null;peer.onTrack=null;try{await peer.close();await peer.dispose();}catch(_){}}
    if(stream!=null){for(final track in stream.getTracks()){try{await track.stop();}catch(_){}}try{await stream.dispose();}catch(_){}}
    if(renderer!=null){renderer.srcObject=null;try{await renderer.dispose();}catch(_){}}
    if(room.isNotEmpty)unawaited(_api('/camera/devices/$room/close',method:'POST',body:{}).catchError((_)=> <String,dynamic>{}));
  }
  @override
  void dispose(){++_generation;_pollTimer?.cancel();_heartbeat?.cancel();_deadline?.cancel();_operations=_operations.catchError((Object _){}).then((_)=>_close());super.dispose();}
  @override
  Widget build(BuildContext context)=>LayoutControl(control:widget.control,child:_renderer?.srcObject!=null
      ? RTCVideoView(_renderer!,objectFit:RTCVideoViewObjectFit.RTCVideoViewObjectFitContain)
      : Center(child:Text(_status,textAlign:TextAlign.center,style:const TextStyle(color:Colors.white))));
}
