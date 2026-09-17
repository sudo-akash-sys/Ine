"""Best-effort Windows notifications for ine-agent.

The durable record stays in `.agent/` (STATE/HISTORY/BLOCKERS and the
per-run report, which is written automatically by the supervisor). The
notification is a persistent, always-on-top popup that uses the Ine
round-tile icon, plays a soft chime on arrival, and shows human-usable
prose — no raw file paths, no exit codes, no process ids. It stays open
until the commander clicks its **Dismiss** button, so nothing important
silently disappears.

Invariants:

- `notify()` NEVER raises and NEVER waits: the popup is spawned in a
  detached, hidden PowerShell child that runs its own message loop, so a
  notification can never stop or delay autonomous execution.
- The child is launched through `powershell.exe -EncodedCommand` with
  every payload value base64-injected, so there is no quoting surface and
  no execution-policy dependency. On failure the child simply exits.
- Selection is silent: disabled hosts get a `NullNotifier`.

Live lines and the run report remain the source of truth for anyone that
misses the popup.
"""

import base64
import os
import platform
import shutil
import subprocess

NOTIFY_ENV = "INE_AGENT_NOTIFY"

# PowerShell 5.1 snippet. Title/body/logo/icon/chime/report paths are
# injected as base64 tokens so no text ever needs escaping; the popup is a
# small topmost form with the Ine round-tile icon, a soft chime, prose, an
# optional "open report" link, and a single Dismiss button. It stays until
# dismissed. Everything is wrapped so any failure exits cleanly without a
# window or an exception.
_PS_TEMPLATE = r"""
$ErrorActionPreference = 'SilentlyContinue'
$title  = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('___TITLE___'))
$body   = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('___BODY___'))
$logo   = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('___LOGO___'))
$icon   = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('___ICON___'))
$chime  = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('___CHIME___'))
$report = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('___REPORT___'))
$slot   = ___SLOT___

if (-not ("System.Windows.Forms.Form" -as [type])) {
    try { Add-Type -AssemblyName System.Windows.Forms } catch { return }
    try { Add-Type -AssemblyName System.Drawing } catch { return }
}

try {
    $screen = $null
    try { $screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea } catch {}
    if ($null -eq $screen) { return }

    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'ine-agent'
    $form.FormBorderStyle = 'SizableToolWindow'
    $form.ShowInTaskbar = $false
    $form.TopMost = $true
    $form.MinimizeBox = $false
    $form.MaximizeBox = $false
    $form.StartPosition = 'Manual'
    $form.ClientSize = New-Object System.Drawing.Size(392, 176)
    $form.FormBorderStyle = 'FixedToolWindow'

    $w = $form.ClientSize.Width + 8
    $h = $form.ClientSize.Height + 8
    $x = $screen.Right - $w - 12
    $y = $screen.Bottom - $h - 12 - ($slot * ($h + 8))
    if ($y -lt $screen.Top) { $y = $screen.Top }
    $form.Location = New-Object System.Drawing.Point($x, $y)

    # Ine logo (project asset) for the picture; the round-tile icon.png
    # (falling back to the logo) becomes the window icon.
    $img = $null
    if ($logo -and (Test-Path -LiteralPath $logo)) {
        try { $img = [System.Drawing.Image]::FromFile($logo) } catch { $img = $null }
    }
    $icoImg = $null
    if ($icon -and (Test-Path -LiteralPath $icon)) {
        try {
            $icoImg = [System.Drawing.Image]::FromFile($icon)
            try { $form.Icon = [System.Drawing.Icon]::FromHandle($icoImg.GetHicon()) } catch {}
        } catch { $icoImg = $null }
    }

    $pic = New-Object System.Windows.Forms.PictureBox
    $pic.Location = New-Object System.Drawing.Point(14, 16)
    $pic.Size = New-Object System.Drawing.Size(64, 64)
    $pic.SizeMode = 'Zoom'
    if ($null -ne $img) { $pic.Image = $img }
    else { $pic.BackColor = [System.Drawing.Color]::FromArgb(228, 232, 240) }
    $form.Controls.Add($pic)

    $titleFont = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
    $bodyFont  = New-Object System.Drawing.Font('Segoe UI', 9)
    $linkFont  = New-Object System.Drawing.Font('Segoe UI', 8.5)

    $titleLabel = New-Object System.Windows.Forms.Label
    $titleLabel.Text = $title
    $titleLabel.Font = $titleFont
    $titleLabel.AutoEllipsis = $true
    $titleLabel.Location = New-Object System.Drawing.Point(90, 12)
    $titleLabel.Size = New-Object System.Drawing.Size(288, 24)
    $form.Controls.Add($titleLabel)

    $bodyLabel = New-Object System.Windows.Forms.Label
    $bodyLabel.Text = $body
    $bodyLabel.Font = $bodyFont
    $bodyLabel.AutoSize = $true
    $bodyLabel.MaximumSize = New-Object System.Drawing.Size(288, 96)
    $bodyLabel.Location = New-Object System.Drawing.Point(90, 40)
    $form.Controls.Add($bodyLabel)

    $yText = 40 + [Math]::Max($bodyLabel.PreferredHeight, 30)
    if ($yText -gt 108) { $yText = 108 }

    $dismiss = New-Object System.Windows.Forms.Button
    $dismiss.Text = 'Dismiss'
    $dismiss.Font = $bodyFont
    $dismiss.Width = 84
    $dismiss.Height = 28
    $dismiss.Location = New-Object System.Drawing.Point(($form.ClientSize.Width - 96), 140)
    $dismiss.Anchor = 'Right'
    $dismiss.Add_Click({ $form.Close() })
    $form.Controls.Add($dismiss)

    if ($report) {
        $openLink = New-Object System.Windows.Forms.LinkLabel
        $openLink.Text = 'open run report'
        $openLink.Font = $linkFont
        $openLink.LinkColor = [System.Drawing.Color]::FromArgb(37, 99, 235)
        $openLink.AutoSize = $true
        $openLink.Location = New-Object System.Drawing.Point(90, 146)
        $openLink.Add_Click({ Start-Process -FilePath $report })
        $form.Controls.Add($openLink)
    }

    # Soft chime; async Play() is dispatched by the message loop below.
    if ($chime -and (Test-Path -LiteralPath $chime)) {
        try { $player = New-Object System.Media.SoundPlayer $chime; $player.Play() } catch {}
    }

    [System.Windows.Forms.Application]::Run($form)
    if ($null -ne $img) { try { $img.Dispose() } catch {} }
    if ($null -ne $icoImg) { try { $icoImg.Dispose() } catch {} }
} catch {
    # The popup is advisory garnish; any failure just means no window.
}
"""

# The popup is intentionally persistent (stays until the commander presses
# Dismiss), so the Python side NEVER waits on the child and needs no
# timeout. These constants bound the payload so the form stays small.
_MAX_TITLE = 64
_MAX_BODY = 400


class NullNotifier:
    """No-op notifier used when notifications are disabled or unsupported."""

    def notify(self, title, body, report=None):
        return None


class WindowsPowerShellNotifier:
    """Shows a persistent, always-on-top Ine-branded popup via PowerShell."""

    def __init__(self, powershell="powershell.exe", logo_path=None,
                 icon_path=None, chime_path=None):
        self.powershell = powershell
        self.logo_path = logo_path
        self.icon_path = icon_path
        self.chime_path = chime_path
        self._slot = 0

    def _encoded(self, script):
        # -EncodedCommand wants UTF-16LE base64; this bypasses all quoting
        # and execution-policy concerns for the payload text.
        return base64.b64encode(script.encode("utf-16-le")).decode("ascii")

    @staticmethod
    def _existing(path):
        if path and os.path.isfile(path):
            return path
        return ""

    def notify(self, title, body, report=None):
        title = " ".join((title or "").split())[:_MAX_TITLE]
        body = " ".join((body or "").split())[:_MAX_BODY]
        logo = self._existing(self.logo_path)
        icon = self._existing(self.icon_path) or logo
        chime = self._existing(self.chime_path) or default_chime_path()
        script = _PS_TEMPLATE
        script = script.replace("___TITLE___", _b64(title))
        script = script.replace("___BODY___", _b64(body))
        script = script.replace("___LOGO___", _b64(logo))
        script = script.replace("___ICON___", _b64(icon))
        script = script.replace("___CHIME___", _b64(chime))
        script = script.replace("___REPORT___", _b64(report or ""))
        script = script.replace("___SLOT___", str(self._slot))
        self._slot += 1
        argv = [
            self.powershell,
            "-NoProfile",
            "-NonInteractive",
            "-STA",
            "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden",
            "-EncodedCommand", self._encoded(script),
        ]
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            with open(os.devnull, "w") as devnull:
                # Detached and never awaited: the popup lives until the
                # commander dismisses it, independent of this process.
                subprocess.Popen(argv, stdout=devnull, stderr=devnull,
                                 stdin=devnull, **kwargs)
        except Exception:
            # Notifications are advisory: never let one raise into the
            # supervisor loop.
            pass


def _b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def default_logo_path(root=None):
    """Resolve `assets/logo.png` for `root`, else the repo layout, else None."""
    candidates = []
    if root:
        candidates.append(os.path.join(root, "assets", "logo.png"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.normpath(os.path.join(here, "..", "..", "assets", "logo.png")))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def default_chime_path(root=None):
    """Resolve `assets/chime.wav` for `root`, else the repo layout, else None."""
    candidates = []
    if root:
        candidates.append(os.path.join(root, "assets", "chime.wav"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.normpath(
        os.path.join(here, "..", "..", "assets", "chime.wav")))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def notifications_enabled(flag=None):
    """True when `flag` or the INE_AGENT_NOTIFY env var enables notifications."""
    if flag:
        return True
    raw = os.environ.get(NOTIFY_ENV, "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def create_notifier(flag=None, logo_path=None):
    """Best-effort notifier for the current host.

    Returns a WindowsPowerShellNotifier only when notifications are enabled,
    the host is Windows, and PowerShell is resolvable; otherwise a
    NullNotifier. Selection is silent so disabling is a no-op everywhere.
    The window icon prefers the round-tile `icon.png` beside the logo,
    falling back to the square brand image when absent.
    """
    if not notifications_enabled(flag):
        return NullNotifier()
    if platform.system() != "Windows":
        return NullNotifier()
    if shutil.which("powershell.exe") is None:
        return NullNotifier()
    if logo_path is None:
        logo_path = default_logo_path()
    icon_path = None
    if logo_path:
        candidate = os.path.join(os.path.dirname(logo_path), "icon.png")
        if os.path.isfile(candidate):
            icon_path = candidate
    return WindowsPowerShellNotifier(logo_path=logo_path,
                                     icon_path=icon_path or logo_path)