import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';

import 'camera_preview.dart';

class Extension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) {
    switch (control.type) {
      case "StcCameraPreview":
        return StcCameraPreviewControl(key: key, control: control);
      default:
        return null;
    }
  }
}
