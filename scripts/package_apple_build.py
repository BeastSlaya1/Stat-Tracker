"""Validate an Apple build and preserve its bundle symlinks in a tar archive."""
import pathlib
import plistlib
import sys
import tarfile


def validate_app(app):
    with (app / 'Info.plist').open('rb') as source:
        info = plistlib.load(source)
    for key in ('NSCameraUsageDescription', 'NSLocalNetworkUsageDescription'):
        if not info.get(key):
            raise ValueError(f'Missing Apple permission: {key}')
    if not {1, 2}.issubset(set(info.get('UIDeviceFamily', []))):
        raise ValueError('Build must support both iPhone and iPad')
    for key in ('UISupportedInterfaceOrientations', 'UISupportedInterfaceOrientations~ipad'):
        modes = info.get(key, [])
        if 'UIInterfaceOrientationPortrait' not in modes or 'UIInterfaceOrientationLandscapeLeft' not in modes:
            raise ValueError(f'Missing portrait/landscape support: {key}')
    ats = info.get('NSAppTransportSecurity', {})
    if ats.get('NSAllowsArbitraryLoads'):
        raise ValueError('Do not globally disable transport security')
    if not ats.get('NSAllowsLocalNetworking'):
        raise ValueError('Local-network transport declaration is missing')
    exceptions = ats.get('NSExceptionDomains', {})
    for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16'):
        if not exceptions.get(network, {}).get('NSExceptionAllowsInsecureHTTPLoads'):
            raise ValueError(f'Missing local transport exception: {network}')
    return info


def package(target, root=pathlib.Path('.')):
    if target == 'ipa':
        candidates = sorted((root / 'build').rglob('*.xcarchive'))
        if len(candidates) != 1:
            raise ValueError('Expected exactly one unsigned device archive')
        artifact = candidates[0]
        apps = list((artifact / 'Products/Applications').glob('*.app'))
    elif target == 'ios-simulator':
        apps = sorted((root / 'build/ios-simulator').glob('*.app'))
        if not apps:
            apps = sorted((root / 'build').glob('**/iphonesimulator/*.app'))
        artifact = apps[0] if len(apps) == 1 else None
    else:
        raise ValueError('Unsupported Apple target')
    if len(apps) != 1 or artifact is None:
        raise ValueError('Expected exactly one Apple app bundle')
    validate_app(apps[0])
    output = root / f'Stat-Tracker-Apple-{target}.tar.gz'
    with tarfile.open(output, 'w:gz', dereference=False) as archive:
        archive.add(artifact, arcname=artifact.name)
    print(f'Validated and packaged {output.name}')
    return output


if __name__ == '__main__':
    package(sys.argv[1])
