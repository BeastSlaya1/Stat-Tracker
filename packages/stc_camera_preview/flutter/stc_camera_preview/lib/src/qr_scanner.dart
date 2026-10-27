import 'dart:async';
import 'dart:convert';
import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class StcQrScannerControl extends StatefulWidget {
  final Control control;
  const StcQrScannerControl({super.key, required this.control});
  @override
  State<StcQrScannerControl> createState() => _StcQrScannerState();
}

class _StcQrScannerState extends State<StcQrScannerControl> {
  late final MobileScannerController _controller;
  bool _sent = false;

  @override
  void initState() {
    super.initState();
    if (kIsWeb) {
      MobileScannerPlatform.instance
          .setWebBarcodeReader(WebBarcodeReader.barcodeDetector);
    }
    _controller = MobileScannerController(
      formats: const [BarcodeFormat.qrCode],
      detectionSpeed: DetectionSpeed.noDuplicates,
      autoStart: true,
    );
  }

  void _onDetect(BarcodeCapture capture) {
    if (_sent) return;
    final value = capture.barcodes
        .map((barcode) => barcode.rawValue)
        .whereType<String>()
        .firstWhere((text) => text.startsWith('STC1.') || text.startsWith('STCQ1.'), orElse: () => '');
    if (value.isEmpty) return;
    _sent = true;
    widget.control.triggerEvent('event', jsonEncode({'code': value}));
    unawaited(_controller.stop());
  }

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: MobileScanner(
          controller: _controller,
          onDetect: _onDetect,
          errorBuilder: (context, error) => ColoredBox(
            color: const Color(0xFF0B1220),
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Text(
                  'Camera unavailable. Allow camera access and try again. (${error.errorCode.name})',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white),
                ),
              ),
            ),
          ),
        ),
      );

  @override
  void dispose() {
    unawaited(_controller.dispose());
    super.dispose();
  }
}
