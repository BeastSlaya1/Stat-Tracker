import pathlib
import plistlib
import tempfile
import tomllib
import unittest
from scripts.package_apple_build import validate_app, package

class ApplePreparationTests(unittest.TestCase):
    def info(self):
        with open('pyproject.toml','rb') as f:
            info=tomllib.load(f)['tool']['flet']['ios']['info']
        return dict(info, UIDeviceFamily=[1,2])

    def test_current_permissions_and_orientations_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            app=pathlib.Path(folder)/'Runner.app';app.mkdir()
            (app/'Info.plist').write_bytes(plistlib.dumps(self.info()))
            self.assertEqual(validate_app(app)['UIDeviceFamily'],[1,2])

    def test_missing_ipad_or_local_network_settings_fail(self):
        for key in ('UIDeviceFamily','NSLocalNetworkUsageDescription','UISupportedInterfaceOrientations~ipad'):
            with self.subTest(key=key),tempfile.TemporaryDirectory() as folder:
                app=pathlib.Path(folder);info=self.info();info.pop(key)
                (app/'Info.plist').write_bytes(plistlib.dumps(info))
                with self.assertRaises(ValueError):validate_app(app)

    def test_simulator_packaging_prefers_final_output(self):
        import tarfile
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder)
            for relative in ('build/ios-simulator/Runner.app','build/flutter/build/ios/iphonesimulator/Runner.app'):
                app=root/relative;app.mkdir(parents=True)
                (app/'Info.plist').write_bytes(plistlib.dumps(self.info()))
            output=package('ios-simulator',root)
            with tarfile.open(output) as archive:
                self.assertIn('Runner.app/Info.plist',archive.getnames())
