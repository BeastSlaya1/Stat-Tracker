import base64
import json
import threading
import types
import unittest
import urllib.request
from unittest.mock import Mock
import main


class PairedVideoTests(unittest.TestCase):
    def test_single_small_frame_crosses_bridge_and_paired_http_without_buffer_delay(self):
        sender = main.StatTrackerApp.__new__(main.StatTrackerApp)
        sender.pair_status = "idle"
        sender.camera_mode_streaming = True
        sender._latest_jpeg_frame = None
        sender._native_frame_count = 0
        sender.camera_error = None
        sender._new_frame_cond = threading.Condition()
        server = main._ThreadingMJPEGServer(("127.0.0.1", 0), main._MJPEGRequestHandler)
        server.app_ref = sender
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        url = "http://127.0.0.1:" + str(server.server_port)
        receiver = main.StatTrackerApp.__new__(main.StatTrackerApp)
        receiver._camera_capture_stop = threading.Event()
        receiver._new_frame_cond = threading.Condition()
        receiver.camera_error = None
        receiver._full_refresh = Mock()
        receiver.camera_image = types.SimpleNamespace(src="", update=lambda: receiver._camera_capture_stop.set())
        try:
            with urllib.request.urlopen(url + "/pair/request?code=42", timeout=2) as response:
                self.assertEqual(json.load(response)["status"], "pending")
            self.assertEqual(sender.pair_pending_code, 42)
            sender.pair_status = "approved"
            # A deliberately tiny marker-delimited frame verifies transport,
            # not image decoding. No second frame is sent to fill the buffer.
            frame = b"\xff\xd8" + b"small-frame" * 20 + b"\xff\xd9"
            sender._on_stc_preview_frame(types.SimpleNamespace(data=base64.b64encode(frame).decode()))
            client = threading.Thread(target=receiver._mjpeg_url_pull_loop, args=(url + "/video",), daemon=True)
            client.start()
            self.assertTrue(receiver._camera_capture_stop.wait(2), "First frame was held waiting for a larger buffer")
            self.assertEqual(receiver._latest_jpeg_frame, frame)
            self.assertEqual(receiver.camera_image.src, "data:image/jpeg;base64," + base64.b64encode(frame).decode())
            client.join(2)
        finally:
            receiver._camera_capture_stop.set()
            sender.camera_mode_streaming = False
            with sender._new_frame_cond:
                sender._new_frame_cond.notify_all()
            server.shutdown()
            server.server_close()
            worker.join(2)
