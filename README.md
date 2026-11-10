# Audio Sleep Control

A small GNOME app that stops your speaker output from going to sleep.

Linux puts sound outputs to sleep when nothing is playing. With some speakers
that causes pops, the first second of sound getting cut off, or the speakers
dropping into their own standby. This app shows what your output is doing and
gives you two switches:

| Switch | What it does | Needs password |
|---|---|---|
| **Keep speaker output awake** | Adds a WirePlumber rule (`~/.config/wireplumber/wireplumber.conf.d/51-external-speakers-no-suspend.conf`) so PipeWire never suspends your default output, then restarts WirePlumber | No |
| **Turn off sound chip power saving** | Sets `snd_hda_intel power_save=0` now and in `/etc/modprobe.d/audio-sleep-control.conf` so it stays after a restart | Yes (pkexec) |

Requirements: PipeWire with WirePlumber 0.5+, GTK 4 and libadwaita 1.5+
(Ubuntu 24.04 or newer).

## Install

### .deb (Ubuntu, Debian, Mint, Pop!_OS)

Download the `.deb` from the [latest release](https://github.com/tajbinkhan/audio-sleep-control/releases/latest), then:

```bash
sudo apt install ./audio-sleep-control_*_all.deb
```

### Snap

```bash
sudo snap install audio-sleep-control --classic
```

The snap uses classic confinement because the app changes WirePlumber and
kernel settings, which the snap sandbox doesn't allow.

## Run from source

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
python3 src/audio_sleep_control.py
```

## Build

```bash
packaging/deb/build-deb.sh          # -> dist/audio-sleep-control_<version>_all.deb
snapcraft pack                      # -> audio-sleep-control_<version>_all.snap
```

GitHub Actions builds both on every push and pull request. The packages are
attached to each run as artifacts.

## Releasing

1. Bump `__version__` in `src/audio_sleep_control.py` and add a
   `<release version="X.Y.Z" date="YYYY-MM-DD">` entry at the top of
   `data/io.github.tajbinkhan.AudioSleepControl.metainfo.xml`.
2. Commit, then tag and push:
   ```bash
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```
3. Actions builds the `.deb` and `.snap`, creates a GitHub release with both
   attached, and (once set up, see below) uploads the snap to the Snap Store.

## Publishing to the Snap Store (one-time setup)

1. Create an account at <https://snapcraft.io> and register the name:
   ```bash
   sudo snap install snapcraft --classic
   snapcraft login
   snapcraft register audio-sleep-control
   ```
2. Ask for classic confinement: post in the
   [store-requests forum](https://forum.snapcraft.io/c/store-requests/19)
   explaining why the app needs it (it writes a WirePlumber config in
   `~/.config`, restarts the user's WirePlumber service, and changes
   `snd_hda_intel` power saving through pkexec). The first upload stays in
   manual review until this is approved.
3. Give GitHub Actions upload rights:
   ```bash
   snapcraft export-login --snaps=audio-sleep-control \
     --acls package_access,package_push,package_update,package_release - \
     | gh secret set SNAPCRAFT_STORE_CREDENTIALS
   gh variable set SNAP_PUBLISH --body true
   ```
   Optional: `gh variable set SNAP_CHANNEL --body edge` to release to `edge`
   instead of `stable`.

## License

MIT, see [LICENSE](LICENSE).
