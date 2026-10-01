import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:image/image.dart' as img;
import 'camera_lifecycle_test.dart' as fixtures;

class FrameControl extends fixtures.TestControl {
  final frames = <String>[];
  FrameControl():super(broadcast:true);
  @override
  void triggerEvent(String name,[dynamic data]) {
    super.triggerEvent(name,data);
    if(name=='frame')frames.add(data.toString());
  }
}
void main(){
  fixtures.androidTest('Android raw camera frame becomes a rotated JPEG event', (tester) async {
    final camera=fixtures.FakeCamera();CameraPlatform.instance=camera;
    final control=FrameControl();
    await tester.pumpWidget(fixtures.screen(control));await fixtures.flush(tester);
    // The camera package has its own Android rotation; our widget adds none.
    expect(find.byType(RotatedBox), findsOneWidget);
    await tester.runAsync(() async {
      camera.streams.values.single.add(CameraImageData(
        format:const CameraImageFormat(ImageFormatGroup.yuv420,raw:35),width:8,height:4,
        planes:[
          CameraImagePlane(bytes:Uint8List.fromList(List.filled(32,100)),bytesPerRow:8,bytesPerPixel:1),
          CameraImagePlane(bytes:Uint8List.fromList(List.filled(8,128)),bytesPerRow:4,bytesPerPixel:1),
          CameraImagePlane(bytes:Uint8List.fromList(List.filled(8,128)),bytesPerRow:4,bytesPerPixel:1),
        ]));
    });
    for(var i=0;i<100 && control.frames.isEmpty;i++){
      await tester.pump();
      await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds:20)));
    }
    await tester.pump();
    expect(control.errors,isEmpty);expect(control.frames,hasLength(1));
    final jpeg=img.decodeJpg(base64Decode(control.frames.single));
    expect(jpeg,isNotNull);expect(jpeg!.width,4);expect(jpeg.height,8);
    await tester.pumpWidget(const SizedBox());await fixtures.flush(tester);
  });
}
