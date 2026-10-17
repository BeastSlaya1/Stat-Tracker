import 'dart:async';
import 'dart:convert';
import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'video_quality.dart';

final _views=<String,ValueNotifier<MediaStream?>>{};
ValueNotifier<MediaStream?> _view(String id)=>_views.putIfAbsent(id,()=>ValueNotifier(null));

class StcPeerLinkControl extends StatefulWidget {
  final Control control;
  const StcPeerLinkControl({super.key,required this.control});
  @override State<StcPeerLinkControl> createState()=>_LinkState();
}
class _LinkState extends State<StcPeerLinkControl> {
  final _peers=<String,RTCPeerConnection>{};
  final _channels=<String,RTCDataChannel>{};
  final _senders=<String,RTCRtpSender>{};
  final _remote=<String,MediaStream>{};
  final _parts=<String,List<String?>>{};
  final _partTimes=<String,DateTime>{};
  MediaStream? _camera;
  String _last='',_source='';
  int _sequence=0;
  bool _host=false;
  Set<String> _viewers={};
  Future<void> _jobs=Future.value();
  String get _id=>widget.control.getString('bridge_id','')!;
  void _emit(Map<String,dynamic> data){if(mounted)widget.control.triggerEvent('event',jsonEncode(data));}
  @override void initState(){super.initState();_configure();}
  @override void didUpdateWidget(covariant StcPeerLinkControl oldWidget){super.didUpdateWidget(oldWidget);_configure();}
  void _configure(){
    final raw=widget.control.getString('command','')!;
    if(raw.isEmpty||raw==_last)return;_last=raw;
    _jobs=_jobs.catchError((Object _){}).then((_)async{
      dynamic cmd;
      try{cmd=jsonDecode(raw);final result=await _command(Map<String,dynamic>.from(cmd));_emit({'kind':'reply','id':cmd['id'],'result':result});}
      catch(error){_emit({'kind':'reply','id':cmd is Map?cmd['id']:null,'error':error is StateError?error.message:'Connection failed. Check the code, camera permission and local network.'});}
    });
  }
  Future<RTCPeerConnection> _newPeer(String id)async{
    if(_peers.containsKey(id))throw StateError('This connection code was already used. Create a new code.');
    if(_peers.length>=8)throw StateError('Eight devices are already paired.');
    final peer=await createPeerConnection({'iceServers':[],'sdpSemantics':'unified-plan'});
    _peers[id]=peer;
    peer.onDataChannel=(channel)=>_attach(id,channel);
    peer.onConnectionState=(state)=>_emit({'kind':'connection','peer':id,'state':state.toString()});
    peer.onTrack=(event)async{
      if(event.track.kind!='video')return;
      final stream=event.streams.isNotEmpty?event.streams.first:await createLocalMediaStream('remote-$id');
      if(event.streams.isEmpty)await stream.addTrack(event.track);
      _remote[id]=stream;await _route();
    };
    return peer;
  }
  void _attach(String id,RTCDataChannel channel){
    _channels[id]=channel;
    channel.onDataChannelState=(state){if(state==RTCDataChannelState.RTCDataChannelOpen)_emit({'kind':'open','peer':id});};
    channel.onMessage=(message){
      if(message.isBinary)return;
      try{
        final frame=jsonDecode(message.text);
        final key='$id:${frame['id']}';final index=frame['part'];final count=frame['count'];final text=frame['text'];
        if(index is! int||count is! int||count<1||count>128||index<0||index>=count||text is! String||text.length>12000)return;
        final now=DateTime.now();
        for(final stale in _partTimes.keys.where((k)=>now.difference(_partTimes[k]!).inSeconds>30).toList()){_parts.remove(stale);_partTimes.remove(stale);}
        if(!_parts.containsKey(key)&&_parts.length>=16)return;
        final chunks=_parts.putIfAbsent(key,()=>List<String?>.filled(count,null));_partTimes[key]=now;
        if(chunks.length!=count)return;chunks[index]=text;
        if(chunks.every((v)=>v!=null)){
          final payload=utf8.decode(base64Decode(chunks.join()));_parts.remove(key);_partTimes.remove(key);
          _emit({'kind':'message','peer':id,'payload':payload});
        }
      }catch(_){}
    };
  }
  Future<void> _gather(RTCPeerConnection peer)async{
    if(peer.iceGatheringState==RTCIceGatheringState.RTCIceGatheringStateComplete)return;
    final done=Completer<void>();
    peer.onIceGatheringState=(s){if(s==RTCIceGatheringState.RTCIceGatheringStateComplete&&!done.isCompleted)done.complete();};
    if(peer.iceGatheringState==RTCIceGatheringState.RTCIceGatheringStateComplete)return;
    await done.future.timeout(const Duration(seconds:12),onTimeout:(){});
  }
  Map<String,dynamic> _decode(String code,String kind){
    if(!code.startsWith('STC1.')||code.length>100000)throw StateError('Paste a complete Stat Tracker connection code.');
    final value=jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(code.substring(5).trim()))));
    if(value is! Map||value['type']!=kind||value['peer'] is! String||!RegExp(r'^[a-f0-9]{32}$').hasMatch(value['peer'])||value['sdp'] is! String||!value['sdp'].startsWith('v=0'))throw StateError('That is not the expected connection code.');
    return Map<String,dynamic>.from(value);
  }
  String _code(String id,RTCSessionDescription sdp)=>'STC1.${base64Url.encode(utf8.encode(jsonEncode({'peer':id,'type':sdp.type,'sdp':sdp.sdp})))}';
  Future<void> _route()async{
    final selected=_source=='self'?_camera:_remote[_source];
    _view(_id).value=selected;
    for(final entry in _senders.entries){
      final forward=_host?(_viewers.contains(entry.key)?selected:null):(_source=='self'?_camera:null);
      final tracks=forward?.getVideoTracks()??[];
      await entry.value.replaceTrack(entry.key==_source||tracks.isEmpty?null:tracks.first);
      await configureVideoSender(entry.value);
    }
  }
  Future<dynamic> _command(Map<String,dynamic> cmd)async{
    final op=cmd['op'];final id=cmd['peer']?.toString()??'';
    if(op=='offer'){
      _host=true;final peer=await _newPeer(id);
      final trans=await peer.addTransceiver(kind:RTCRtpMediaType.RTCRtpMediaTypeVideo,init:RTCRtpTransceiverInit(direction:TransceiverDirection.SendRecv));
      _senders[id]=trans.sender;
      _attach(id,await peer.createDataChannel('match',RTCDataChannelInit()));
      await peer.setLocalDescription(await peer.createOffer());await _gather(peer);
      await _route();return {'code':_code(id,(await peer.getLocalDescription())!)};
    }
    if(op=='answer'){
      _host=false;final data=_decode(cmd['code'],'offer');final name=data['peer'] as String;final peer=await _newPeer(name);
      await peer.setRemoteDescription(RTCSessionDescription(data['sdp'],'offer'));
      final trans=(await peer.getTransceivers()).first;
      await trans.setDirection(TransceiverDirection.SendRecv);_senders[name]=trans.sender;
      await peer.setLocalDescription(await peer.createAnswer());await _gather(peer);
      return {'peer':name,'code':_code(name,(await peer.getLocalDescription())!)};
    }
    if(op=='accept'){
      final data=_decode(cmd['code'],'answer');final peer=_peers[data['peer']];
      if(peer==null)throw StateError('This reply belongs to a different or expired connection.');
      await peer.setRemoteDescription(RTCSessionDescription(data['sdp'],'answer'));return {};
    }
    if(op=='diagnostics'){
      final peer=_peers[id];
      if(peer==null)throw StateError('Device is not connected.');
      final stats=await peer.getStats();
      return {'reports':stats.where((s)=>s.type=='inbound-rtp'||s.type=='outbound-rtp').map((s)=>{'type':s.type,...s.values}).toList()};
    }
    if(op=='send'){
      final channel=_channels[id];
      if(channel==null||channel.state!=RTCDataChannelState.RTCDataChannelOpen)throw StateError('Device disconnected. Reconnect using new codes.');
      final payload=base64Encode(utf8.encode(cmd['payload'] as String));
      if(payload.length>12000*128)throw StateError('Match update is too large.');
      final count=(payload.length/12000).ceil();final message=++_sequence;
      for(var part=0;part<count;part++){
        final end=(part+1)*12000;
        await channel.send(RTCDataChannelMessage(jsonEncode({'id':message,'part':part,'count':count,'text':payload.substring(part*12000,end>payload.length?payload.length:end)})));
      }
      return {};
    }
    if(op=='source'){
      _source=cmd['source']??'';_viewers=Set<String>.from(cmd['viewers']??[]);
      if(_source!='self'&&_camera!=null){for(final track in _camera!.getTracks()){await track.stop();}await _camera!.dispose();_camera=null;}
      await _route();return {};
    }
    if(op=='camera'){
      if(cmd['enabled']==true){
        if(_source!='self')throw StateError('The host has not assigned this device to share video.');
        if(_camera!=null){for(final t in _camera!.getTracks()){await t.stop();}await _camera!.dispose();}
        final video=cameraVideoConstraints(web:kIsWeb,lens:cmd['lens']??'back');
        if((cmd['device_id']??'').isNotEmpty)selectCameraDevice(video,cmd['device_id'],web:kIsWeb);
        _camera=await navigator.mediaDevices.getUserMedia({'audio':false,'video':video});
      }else if(_camera!=null){for(final t in _camera!.getTracks()){await t.stop();}await _camera!.dispose();_camera=null;}
      await _route();return {};
    }
    if(op=='drop'){
      await _channels.remove(id)?.close();await _peers.remove(id)?.close();_senders.remove(id);_remote.remove(id);await _route();return {};
    }
    if(op=='close'){await _close();return {};}
    throw StateError('Unknown connection action.');
  }
  Future<void> _close()async{
    for(final c in _channels.values){await c.close();}_channels.clear();
    for(final p in _peers.values){await p.close();}_peers.clear();_senders.clear();_remote.clear();
    if(_camera!=null){for(final t in _camera!.getTracks()){await t.stop();}await _camera!.dispose();_camera=null;}
    _view(_id).value=null;_parts.clear();_partTimes.clear();
  }
  @override void dispose(){unawaited(_close());super.dispose();}
  @override Widget build(BuildContext context)=>const SizedBox(width:1,height:1);
}

class StcPeerViewControl extends StatefulWidget {
  final Control control;
  const StcPeerViewControl({super.key,required this.control});
  @override State<StcPeerViewControl> createState()=>_ViewState();
}
class _ViewState extends State<StcPeerViewControl> {
  final _renderer=RTCVideoRenderer();ValueNotifier<MediaStream?>? _source;bool _ready=false;
  @override void initState(){super.initState();_source=_view(widget.control.getString('bridge_id','')!);_source!.addListener(_changed);_renderer.initialize().then((_){if(mounted){_ready=true;_changed();}});}
  void _changed(){if(mounted&&_ready){_renderer.srcObject=_source!.value;setState((){});}}
  @override void dispose(){_source?.removeListener(_changed);unawaited(_renderer.dispose());super.dispose();}
  @override Widget build(BuildContext context)=>_ready?RTCVideoView(_renderer,objectFit:RTCVideoViewObjectFit.RTCVideoViewObjectFitContain):const SizedBox();
}
