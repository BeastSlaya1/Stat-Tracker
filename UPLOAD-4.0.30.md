# Updated Stat Tracker v4.0.30

This revision stays v4.0.30 as requested. Android uses build number 33 so it can update the earlier v4.0.30 installation. Update every participating device.

## Included changes
- Basketball TXT export matches the supplied example: match details, ordered counts, SCC sequences, events and one embedded match-data block. Older exports still import. The on-screen statistics retain their rate calculations.
- Guests scan the same Wi-Fi/hotspot and press Connect to this match. The host receives an automatic approval prompt. Once approved, the guest opens the match and starts receiving the camera connection automatically; no second Connect action is required.
- The host selects Attack, Defense, Cards, Opposition or All when approving a device, with an expandable list of individual stat checkboxes. Assign controls in the connected-device list changes this later. Conversions and incompletes follow their parent stat. All devices receive the whole match, regardless of which stats they may enter. Camera, possession and timer control remain with the host.
- Permissions are enforced by the host. If permissions change while inputs are waiting to sync, those inputs remain queued; the host must restore the required stat permission to accept them.
- Portrait clipping fixes, section-specific incompletes and Defense spelling from the earlier v4.0.30 are retained.

## Sharing
1. Connect all devices to the same trusted Wi-Fi/hotspot. Internet is optional after signing into the app beforehand.
2. Host opens a match and chooses Shared match > Host this match. Turn on its camera to share video.
3. Guest chooses Shared match > Scan for shared matches > Connect to this match.
4. Host selects the device's section/stats and presses Approve connection. Guest connects automatically.

Manual connection remains available for unusual networks or older hosts. Hidden sessions remain undiscoverable and use manual details plus approval. Use installed apps for LAN sharing; browser hosting/joining is not supported. Networks with client isolation or blocked private-network firewall access can prevent discovery and connections.

## GitHub upload
Upload the source ZIP contents including .github. Run Deploy web build. Replace the Windows and Android assets in release v4.0.30 with these updated files. No server migration or account-server deployment is required. Microsoft sign-in was cancelled and is not included.

## Validation
Regression tests cover the export layout, old/new imports, scan/connect/approve flow, assigned stats and modifiers, shared events, and per-device video signaling. Camera transmission between physical devices still needs checking on your network. iOS remains source preparation only.
