import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:stc_camera_preview/src/extension.dart';

class Backend implements FletBackend {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class SessionProbe extends StatefulWidget {
  final VoidCallback opened, closed;
  const SessionProbe({super.key, required this.opened, required this.closed});
  @override
  State<SessionProbe> createState() => ProbeState();
}
class ProbeState extends State<SessionProbe> {
  @override
  void initState() { super.initState(); widget.opened(); }
  @override
  void dispose() { widget.closed(); super.dispose(); }
  @override
  Widget build(BuildContext context) => const SizedBox();
}

void main() {
  testWidgets('camera session survives new control objects and fullscreen parents', (tester) async {
    final backend = Backend();
    final extension = Extension();
    var opened = 0, closed = 0;
    Widget camera(int id) {
      // Flet reconstructs the Control object when its parent tree changes.
      final control = Control(id: id, type: 'StcRtcVideo', properties: {}, backend: backend);
      final widget = extension.createWidget(null, control)!;
      return SessionProbe(key: widget.key, opened: () => opened++, closed: () => closed++);
    }
    await tester.pumpWidget(Directionality(textDirection: TextDirection.ltr, child: Row(children: [camera(7)])));
    for (var i = 0; i < 3; i++) {
      await tester.pumpWidget(Directionality(textDirection: TextDirection.ltr, child: Column(children: [Padding(padding: EdgeInsets.zero, child: camera(7))])));
      await tester.pumpWidget(Directionality(textDirection: TextDirection.ltr, child: Row(children: [camera(7)])));
    }
    expect(opened, 1); expect(closed, 0);
    await tester.pumpWidget(const SizedBox());
    expect(closed, 1);
    await tester.pumpWidget(Directionality(textDirection: TextDirection.ltr, child: camera(8)));
    expect(opened, 2);
    await tester.pumpWidget(const SizedBox());
    expect(closed, 2);
  });
}
