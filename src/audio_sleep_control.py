#!/usr/bin/env python3
"""Audio Sleep Control: a small GNOME app to stop your speaker output from sleeping.

Two switches:
  1. Keep speaker output awake   -> WirePlumber rule (per-user, no password)
  2. Sound chip power saving     -> snd_hda_intel power_save (system, asks for password)
"""
import os
import re
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

__version__ = "1.0.0"
APP_ID = "io.github.tajbinkhan.AudioSleepControl"
WP_DIR = os.path.expanduser("~/.config/wireplumber/wireplumber.conf.d")
WP_RULE = os.path.join(WP_DIR, "51-external-speakers-no-suspend.conf")
KERNEL_PARAM = "/sys/module/snd_hda_intel/parameters/power_save"
MODPROBE_FILE = "/etc/modprobe.d/audio-sleep-control.conf"

STATE_TEXT = {
    "running": ("Playing", "Sound is going to the speakers right now"),
    "idle": ("Awake, silent", "Connected and ready, nothing playing"),
    "suspended": ("Asleep", "No app is using the output, it wakes instantly when sound starts"),
    "creating": ("Starting", ""),
    "error": ("Error", "The sound service reported a problem with this output"),
}


# When running as a snap, the launcher points library/Python paths into the
# snap. Host programs we call (wpctl, pw-cli, systemctl, pkexec) must not
# inherit those, so children get a clean environment.
_SNAP_VARS = (
    "LD_LIBRARY_PATH", "GI_TYPELIB_PATH", "PYTHONHOME", "PYTHONPATH",
    "GDK_PIXBUF_MODULE_FILE", "GDK_PIXBUF_MODULEDIR", "GSK_RENDERER",
)


def child_env():
    env = dict(os.environ)
    if "SNAP" in env:
        for v in _SNAP_VARS:
            env.pop(v, None)
        env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    return env


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5, env=child_env()).stdout
    except Exception:
        return ""


def default_sink():
    """Return (id, node_name, description, state) for the default output, or None."""
    out = run(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"])
    m = re.search(r"^id (\d+),", out, re.M)
    if not m:
        return None
    sink_id = m.group(1)
    name = re.search(r'node\.name = "([^"]*)"', out)
    desc = re.search(r'node\.description = "([^"]*)"', out)
    info = run(["pw-cli", "info", sink_id])
    state = re.search(r'state: "([^"]*)"', info)
    return (
        sink_id,
        name.group(1) if name else "",
        desc.group(1) if desc else "Unknown output",
        state.group(1) if state else "unknown",
    )


def rule_enabled():
    return os.path.exists(WP_RULE)


def rule_text(node_name):
    return f"""monitor.alsa.rules = [
  {{
    matches = [
      {{ node.name = "{node_name}" }}
    ]
    actions = {{
      update-props = {{
        session.suspend-timeout-seconds = 0
        node.pause-on-idle = false
      }}
    }}
  }}
]
"""


def kernel_power_save():
    try:
        with open(KERNEL_PARAM) as f:
            return int(f.read().strip())
    except Exception:
        return None


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Audio Sleep Control")
        self.set_icon_name(APP_ID)
        self.set_default_size(520, 560)
        self._updating = False

        self.toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh")
        refresh.connect("clicked", lambda *_: self.refresh())
        header.pack_end(refresh)
        menu = Gio.Menu()
        menu.append("About Audio Sleep Control", "app.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))
        view.add_top_bar(header)

        page = Adw.PreferencesPage()

        # Status
        status = Adw.PreferencesGroup(title="Status")
        self.output_row = Adw.ActionRow(title="Output")
        self.state_row = Adw.ActionRow(title="Output state")
        self.state_icon = Gtk.Image()
        self.state_row.add_suffix(self.state_icon)
        self.chip_row = Adw.ActionRow(title="Sound chip power saving")
        for r in (self.output_row, self.state_row, self.chip_row):
            r.set_subtitle_selectable(True)
            status.add(r)
        page.add(status)

        # Settings
        settings = Adw.PreferencesGroup(
            title="Settings",
            description="Changes apply right away. Sound may cut out for a second while the sound service restarts.",
        )
        self.keep_awake = Adw.SwitchRow(
            title="Keep speaker output awake",
            subtitle="Stops the sound service putting this output to sleep when idle",
        )
        self.keep_awake.connect("notify::active", self.on_keep_awake)
        settings.add(self.keep_awake)

        self.chip_switch = Adw.SwitchRow(
            title="Turn off sound chip power saving",
            subtitle="Prevents pops and speakers dropping into standby. Asks for your password.",
        )
        self.chip_switch.connect("notify::active", self.on_chip)
        settings.add(self.chip_switch)
        page.add(settings)

        self.toasts.set_child(page)
        view.set_content(self.toasts)
        self.set_content(view)

        self.refresh()
        GLib.timeout_add_seconds(2, self._tick)

    def _tick(self):
        self.refresh()
        return True

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=3))

    def refresh(self):
        sink = default_sink()
        if sink:
            _, _, desc, state = sink
            self.output_row.set_subtitle(desc)
            label, detail = STATE_TEXT.get(state, (state.capitalize(), ""))
            self.state_row.set_subtitle(f"{label}. {detail}" if detail else label)
            icon = {
                "running": "media-playback-start-symbolic",
                "idle": "audio-volume-high-symbolic",
                "suspended": "weather-clear-night-symbolic",
            }.get(state, "dialog-question-symbolic")
            self.state_icon.set_from_icon_name(icon)
        else:
            self.output_row.set_subtitle("No output found")
            self.state_row.set_subtitle("Unknown")

        ps = kernel_power_save()
        if ps is None:
            self.chip_row.set_subtitle("Not available on this system")
            self.chip_switch.set_sensitive(False)
        elif ps == 0:
            self.chip_row.set_subtitle("Off (chip always powered)")
        else:
            self.chip_row.set_subtitle(f"On (powers down after {ps} s of silence)")

        self._updating = True
        self.keep_awake.set_active(rule_enabled())
        if ps is not None:
            self.chip_switch.set_active(ps == 0)
        self._updating = False

    # Switch 1: WirePlumber rule
    def on_keep_awake(self, row, _pspec):
        if self._updating:
            return
        try:
            if row.get_active():
                sink = default_sink()
                if not sink or not sink[1]:
                    raise RuntimeError("Couldn't find your output")
                os.makedirs(WP_DIR, exist_ok=True)
                with open(WP_RULE, "w") as f:
                    f.write(rule_text(sink[1]))
            elif os.path.exists(WP_RULE):
                os.remove(WP_RULE)
        except Exception as e:
            self.toast(f"Failed: {e}")
            self.refresh()
            return
        subprocess.run(["systemctl", "--user", "restart", "wireplumber"], env=child_env())
        self.toast("Output will stay awake" if row.get_active() else "Output can sleep again")
        GLib.timeout_add(1500, lambda: (self.refresh(), False)[1])

    # Switch 2: kernel power_save (needs root via pkexec)
    def on_chip(self, row, _pspec):
        if self._updating:
            return
        if row.get_active():
            script = (
                f"echo 0 > {KERNEL_PARAM} && "
                f"echo 'options snd_hda_intel power_save=0' > {MODPROBE_FILE}"
            )
        else:
            script = f"echo 1 > {KERNEL_PARAM} && rm -f {MODPROBE_FILE}"
        self.chip_switch.set_sensitive(False)
        launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.NONE)
        launcher.set_environ([f"{k}={v}" for k, v in child_env().items()])
        proc = launcher.spawnv(["pkexec", "sh", "-c", script])
        proc.wait_check_async(None, self._chip_done, row.get_active())

    def _chip_done(self, proc, result, turned_off):
        try:
            proc.wait_check_finish(result)
            self.toast("Chip power saving turned off" if turned_off else "Chip power saving turned on")
        except GLib.Error:
            self.toast("Not changed (password cancelled or refused)")
        self.chip_switch.set_sensitive(True)
        self.refresh()


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", self.on_about)
        self.add_action(about)

    def on_about(self, *_):
        Adw.AboutDialog(
            application_name="Audio Sleep Control",
            application_icon=APP_ID,
            developer_name="Tajbin Khan",
            version=__version__,
            website="https://github.com/tajbinkhan/audio-sleep-control",
            issue_url="https://github.com/tajbinkhan/audio-sleep-control/issues",
            license_type=Gtk.License.MIT_X11,
        ).present(self.get_active_window())

    def do_activate(self):
        win = self.get_active_window() or Window(self)
        win.present()


if __name__ == "__main__":
    App().run(None)
