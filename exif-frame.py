#!/usr/bin/env python3
"""EXIF Frame Generator — TUI for creating Instagram-style EXIF borders.

Requirements:
    brew install exiftool imagemagick
    pip3 install textual
"""

import subprocess
import sys
import os

try:
    from textual.app import App, ComposeResult
    from textual.widgets import (
        Header, Footer, Input, Checkbox, Button,
        Static, Select, Label,
    )
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.binding import Binding
except ImportError:
    print("┌──────────────────────────────────────────┐")
    print("│  textual is required:                    │")
    print("│  pip3 install textual --break-system-packages │")
    print("└──────────────────────────────────────────┘")
    sys.exit(1)


# ── EXIF field definitions ────────────────────────────────────────
# (key, display_label, exiftool_tag, default_enabled, default_side)
EXIF_FIELDS = [
    ("body",     "Body",          "-Model",        True,  "left"),
    ("lens",     "Lens",          "-LensModel",    True,  "left"),
    ("focal",    "Focal Length",  "-FocalLength",   False, "right"),
    ("shutter",  "Shutter Speed", "-ExposureTime",  True,  "right"),
    ("aperture", "Aperture",      "-FNumber",       True,  "right"),
    ("iso",      "ISO",           "-ISO",           True,  "right"),
]

# ── Default layout settings ──────────────────────────────────────
DEFAULTS = {
    "canvas_size": "5000",
    "border":      "160",
    "text_gap":    "40",
    "font_size":   "90",
    "title_font_size": "120",
    "date_font_size":  "100",
    "wm_font_size":  "100",
    "wm_opacity":    "40",
    "wm_color":      "#dfdfdf",
    "wm_padding":    "30",
    "font_path":   "",
    "text_color":  "#333333",
    "bg_color":    "#ffffff",
    "separator":   "</>",
}

SETTING_LABELS = [
    ("canvas_size",     "Canvas Size (px)"),
    ("border",          "Border (px)"),
    ("text_gap",        "Text Gap (px)"),
    ("font_size",       "EXIF Details Font Size (pt)"),
    ("title_font_size", "Title Font Size (pt)"),
    ("date_font_size",  "Date Font Size (pt)"),
    ("wm_font_size",    "Watermark Size (pt)"),
    ("wm_opacity",      "Watermark Opacity (%)"),
    ("wm_color",        "Watermark Colour"),
    ("wm_padding",      "Watermark Padding (px)"),
    ("font_path",       "Font Path"),
    ("text_color",      "Text Colour"),
    ("bg_color",        "Background Colour"),
    ("separator",       "Separator Char"),
]


# ── Helpers ───────────────────────────────────────────────────────

def read_exif(image_path: str) -> dict:
    """Read EXIF data from an image using exiftool."""
    values = {}
    for key, _, tag, _, _ in EXIF_FIELDS:
        try:
            result = subprocess.run(
                ["exiftool", "-s3", tag, image_path],
                capture_output=True, text=True, timeout=10,
            )
            val = result.stdout.strip()
            values[key] = val if val else ""
        except Exception:
            values[key] = ""

    # Also read date
    try:
        result = subprocess.run(
            ["exiftool", "-s3", "-DateTimeOriginal", image_path],
            capture_output=True, text=True, timeout=10,
        )
        raw_date = result.stdout.strip()
        # Format from "2026:01:15 14:30:00" to "15 January 2026"
        if raw_date:
            from datetime import datetime
            try:
                dt = datetime.strptime(raw_date, "%Y:%m:%d %H:%M:%S")
                values["date"] = dt.strftime("%-d %B %Y")
            except ValueError:
                values["date"] = raw_date
        else:
            values["date"] = ""
    except Exception:
        values["date"] = ""

    return values


def format_value(key: str, value: str) -> str:
    """Format a raw EXIF value for display in the frame."""
    if not value:
        return ""
    if key == "shutter":
        return f"{value}s"
    if key == "aperture":
        return f"ƒ/{value}"
    if key == "iso":
        return f"ISO {value}"
    return value


def generate_frame(image_path: str, exif_values: dict, enabled: dict,
                   sides: dict, formats: dict, settings: dict,
                   title: str = "", date_text: str = "",
                   watermark: str = "", wm_position: str = "southeast",
                   stack_body_lens: bool = False) -> str:
    """Build the framed image with ImageMagick."""

    separator = settings.get("separator", "·")
    sep = f"   {separator}   "

    # Collect left/right text parts
    # When stacking body & lens, they get joined with newline instead of separator
    left_parts, right_parts = [], []
    body_lens_keys = {"body", "lens"}

    # First pass: gather body & lens separately if stacking
    stacked_left = []
    stacked_right = []
    regular_left = []
    regular_right = []

    for key, _, _, _, _ in EXIF_FIELDS:
        if not enabled.get(key):
            continue
        formatted = formats.get(key, exif_values.get(key, ""))
        if not formatted:
            continue
        side = sides.get(key, "left")

        if stack_body_lens and key in body_lens_keys:
            if side == "left":
                stacked_left.append(formatted)
            else:
                stacked_right.append(formatted)
        else:
            if side == "left":
                regular_left.append(formatted)
            else:
                regular_right.append(formatted)

    # Build final text: stacked items joined with newline, then separator to regular items
    left_stacked = "\n".join(stacked_left)
    right_stacked = "\n".join(stacked_right)
    left_regular = sep.join(regular_left)
    right_regular = sep.join(regular_right)

    # Combine stacked and regular parts
    if left_stacked and left_regular:
        left_text = left_stacked + "\n" + left_regular
    else:
        left_text = left_stacked or left_regular

    if right_stacked and right_regular:
        right_text = right_stacked + "\n" + right_regular
    else:
        right_text = right_stacked or right_regular

    # Count text lines for spacing
    bottom_lines = max(
        left_text.count("\n") + 1 if left_text else 0,
        right_text.count("\n") + 1 if right_text else 0,
    )

    # Parse settings
    canvas    = int(settings["canvas_size"])
    border    = int(settings["border"])
    font_size = int(settings["font_size"])
    title_font_size = int(settings.get("title_font_size", font_size))
    date_font_size  = int(settings.get("date_font_size", font_size))
    text_gap  = int(settings["text_gap"])
    font_path = settings["font_path"]
    text_color = settings["text_color"]
    bg_color  = settings["bg_color"]

    # Space needed above and below the photo
    has_top    = bool(title.strip() or date_text.strip())
    has_bottom = bool(left_text or right_text)
    top_space    = (text_gap + max(title_font_size, date_font_size)) if has_top else 0
    bottom_space = (text_gap + int(font_size * bottom_lines * 1.3)) if has_bottom else 0

    photo_max_w = canvas - border * 2
    photo_max_h = canvas - border * 2 - top_space - bottom_space - 40

    # Resize to temp file
    tmp = f"/tmp/exif_frame_{os.getpid()}.png"
    subprocess.run(
        ["magick", image_path, "-resize", f"{photo_max_w}x{photo_max_h}", tmp],
        check=True,
    )

    # Burn watermark onto the photo itself if set
    if watermark.strip():
        wm_size    = int(settings.get("wm_font_size", "40"))
        wm_opacity = int(settings.get("wm_opacity", "40"))
        wm_color   = settings.get("wm_color", "#ffffff")
        wm_padding = int(settings.get("wm_padding", "30"))
        # Convert opacity 0-100 to hex alpha 00-FF
        alpha_hex  = format(int(wm_opacity * 255 / 100), "02x")
        fill_color = f"{wm_color}{alpha_hex}"
        subprocess.run([
            "magick", tmp,
            "-font", font_path,
            "-pointsize", str(wm_size),
            "-fill", fill_color,
            "-gravity", wm_position,
            "-annotate", f"+{wm_padding}+{wm_padding}", watermark.strip(),
            tmp,
        ], check=True)

    # Read actual resized dimensions
    result = subprocess.run(
        ["magick", "identify", "-format", "%w %h", tmp],
        capture_output=True, text=True, check=True,
    )
    actual_w, actual_h = map(int, result.stdout.strip().split())

    # Centre the whole content block (top text + photo + bottom text)
    content_h = top_space + actual_h + bottom_space
    avail_h   = canvas - border * 2
    content_top = border + (avail_h - content_h) // 2

    # Photo starts after the top text area
    photo_top = content_top + top_space
    photo_cy  = photo_top + actual_h // 2
    canvas_cy = canvas // 2
    y_shift   = canvas_cy - photo_cy

    # Handle negative y_shift (photo needs to move down)
    if y_shift >= 0:
        geom = f"+0-{y_shift}"
    else:
        geom = f"+0+{abs(y_shift)}"

    # Align title and date so both bottom edges sit text_gap above the photo
    title_y = photo_top - text_gap - title_font_size
    date_y  = photo_top - text_gap - date_font_size

    # EXIF text Y: just below the photo
    bottom_text_y = photo_top + actual_h + text_gap + font_size

    # Output path — save into a "framed" subfolder next to the original
    img_dir = os.path.dirname(image_path)
    framed_dir = os.path.join(img_dir, "framed")
    os.makedirs(framed_dir, exist_ok=True)
    filename = os.path.basename(image_path)
    output = os.path.join(framed_dir, filename)

    # Build magick command
    cmd = [
        "magick",
        "-size", f"{canvas}x{canvas}", f"xc:{bg_color}",
        tmp,
        "-gravity", "center", "-geometry", geom, "-composite",
        "-font", font_path,
        "-fill", text_color,
    ]

    # Top: title (left) and date (right)
    if title.strip():
        cmd += ["-pointsize", str(title_font_size),
                "-gravity", "northwest", "-annotate", f"+{border}+{title_y}", title.strip()]
    if date_text.strip():
        cmd += ["-pointsize", str(date_font_size),
                "-gravity", "northeast", "-annotate", f"+{border}+{date_y}", date_text.strip()]

    # Bottom: EXIF info
    if left_text:
        cmd += ["-pointsize", str(font_size),
                "-gravity", "northwest", "-annotate", f"+{border}+{bottom_text_y}", left_text]
    if right_text:
        cmd += ["-pointsize", str(font_size),
                "-gravity", "northeast", "-annotate", f"+{border}+{bottom_text_y}", right_text]

    cmd += ["-quality", "95", output]
    subprocess.run(cmd, check=True)

    # Cleanup
    try:
        os.remove(tmp)
    except OSError:
        pass

    return output


# ── TUI ───────────────────────────────────────────────────────────

class ExifFrameApp(App):
    """Full-screen TUI for generating EXIF-framed photos."""

    CSS = """
    Screen {
        background: $surface;
    }

    #scroll {
        height: 1fr;
        padding: 0 1;
    }

    .heading {
        color: $accent;
        text-style: bold;
        padding: 1 0 0 0;
    }

    .divider {
        color: $primary-darken-2;
        padding: 0;
    }

    .field-row {
        height: 3;
        align: left middle;
    }

    .field-row Checkbox {
        width: 24;
    }

    .field-row .val {
        width: 1fr;
        margin: 0 1;
    }

    .field-row .formatted {
        width: 30;
        margin: 0 1;
        color: $text-muted;
    }

    .field-row .side {
        width: 14;
    }

    .setting-row {
        height: 3;
        align: left middle;
    }

    .setting-row .lbl {
        width: 22;
        padding: 1 1 0 0;
        text-align: right;
    }

    .setting-row .inp {
        width: 1fr;
    }

    #bar {
        height: auto;
        dock: bottom;
        padding: 1 1;
        background: $surface;
    }

    #bar Horizontal {
        height: 3;
    }

    #bar Button {
        margin: 0 1;
    }

    #status {
        height: 1;
        padding: 0 1;
    }

    .success { color: $success; }
    .error   { color: $error;   }

    .col-header {
        height: 1;
        padding: 0;
    }

    .col-header .h-field  { width: 24; text-style: bold; color: $text-muted; }
    .col-header .h-raw    { width: 1fr; text-style: bold; color: $text-muted; margin: 0 1; }
    .col-header .h-fmt    { width: 30; text-style: bold; color: $text-muted; margin: 0 1; }
    .col-header .h-side   { width: 14; text-style: bold; color: $text-muted; }

    .file-row {
        height: 3;
        padding: 0 1;
    }

    .file-row .filepath {
        width: 1fr;
        margin: 0 1 0 0;
    }

    .file-row Button {
        min-width: 20;
    }
    """

    BINDINGS = [
        Binding("ctrl+g", "generate", "Generate", show=True),
        Binding("ctrl+l", "load", "Load Image", show=True),
        Binding("ctrl+q", "quit_app", "Quit", show=True),
    ]

    def __init__(self, image_path: str = ""):
        super().__init__()
        self.image_path = os.path.abspath(image_path) if image_path else ""
        self.exif_data = read_exif(self.image_path) if self.image_path else {}

    def compose(self) -> ComposeResult:
        yield Header()

        with VerticalScroll(id="scroll"):
            yield Static(" Image File", classes="heading")
            with Horizontal(classes="file-row"):
                yield Input(value=self.image_path, id="inp_filepath", classes="filepath",
                            placeholder="Drag file here or paste path...")
                yield Button("Load  (Ctrl+L)", variant="primary", id="btn_load")
            yield Static("─" * 80, classes="divider")

            yield Static(" Title, Date & Watermark", classes="heading")
            with Horizontal(classes="setting-row"):
                yield Label("Title (top left):", classes="lbl")
                yield Input(value="", id="inp_title", classes="inp",
                            placeholder="e.g. Windermere Sunset")
            with Horizontal(classes="setting-row"):
                yield Label("Date (top right):", classes="lbl")
                yield Input(value=self.exif_data.get("date", ""), id="inp_date", classes="inp",
                            placeholder="e.g. 15 January 2026")
            with Horizontal(classes="setting-row"):
                yield Label("Watermark (on photo):", classes="lbl")
                yield Input(value="", id="inp_watermark", classes="inp",
                            placeholder="e.g. © Lisa Taylor")
            with Horizontal(classes="setting-row"):
                yield Label("Watermark Position:", classes="lbl")
                yield Select(
                    [("Bottom Right", "southeast"), ("Bottom Left", "southwest"),
                     ("Top Right", "northeast"), ("Top Left", "northwest")],
                    value="southeast",
                    allow_blank=False,
                    id="sel_wm_position",
                    classes="inp",
                )

            yield Static("─" * 80, classes="divider")
            yield Static(" EXIF Fields", classes="heading")

            # Column headers
            with Horizontal(classes="col-header"):
                yield Static("  Field", classes="h-field")
                yield Static("Raw Value", classes="h-raw")
                yield Static("Formatted Preview", classes="h-fmt")
                yield Static("Side", classes="h-side")

            # One row per EXIF field
            for key, label, _, default_on, default_side in EXIF_FIELDS:
                raw = self.exif_data.get(key, "")
                fmt = format_value(key, raw)
                with Horizontal(classes="field-row"):
                    yield Checkbox(label, value=default_on, id=f"chk_{key}")
                    yield Input(value=raw, id=f"val_{key}", classes="val",
                                placeholder="(empty)")
                    yield Static(fmt, id=f"fmt_{key}", classes="formatted")
                    yield Select(
                        [("Left", "left"), ("Right", "right")],
                        value=default_side,
                        allow_blank=False,
                        id=f"side_{key}",
                        classes="side",
                    )

            with Horizontal(classes="field-row"):
                yield Checkbox("Stack Body & Lens (one above the other)", value=False, id="chk_stack_body_lens")

            yield Static("─" * 80, classes="divider")
            yield Static(" Layout & Style", classes="heading")

            for skey, slabel in SETTING_LABELS:
                with Horizontal(classes="setting-row"):
                    yield Label(f"{slabel}:", classes="lbl")
                    yield Input(value=DEFAULTS[skey], id=f"set_{skey}", classes="inp")

        with Vertical(id="bar"):
            yield Static("", id="status")
            with Horizontal():
                yield Button("Generate  (Ctrl+G)", variant="success", id="btn_gen")
                yield Button("Quit  (Ctrl+Q)", variant="error", id="btn_quit")

        yield Footer()

    # ── live preview of formatted value ──
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id and event.input.id.startswith("val_"):
            key = event.input.id[4:]
            fmt_widget = self.query_one(f"#fmt_{key}", Static)
            fmt_widget.update(format_value(key, event.value))

    # ── button handlers ──
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_gen":
            self._generate()
        elif event.button.id == "btn_load":
            self._load_image()
        elif event.button.id == "btn_quit":
            self.exit()

    def action_generate(self) -> None:
        self._generate()

    def action_load(self) -> None:
        self._load_image()

    def action_quit_app(self) -> None:
        self.exit()

    # ── load a new image ──
    def _load_image(self) -> None:
        status = self.query_one("#status", Static)
        filepath = self.query_one("#inp_filepath", Input).value.strip()

        # Handle drag-and-drop paths that may be quoted or escaped
        filepath = filepath.strip("'\"")
        filepath = filepath.replace("\\ ", " ")

        if not filepath:
            status.remove_class("success")
            status.add_class("error")
            status.update("  ✗  No file path entered")
            return

        if not os.path.isfile(filepath):
            status.remove_class("success")
            status.add_class("error")
            status.update(f"  ✗  File not found: {filepath}")
            return

        self.image_path = os.path.abspath(filepath)
        self.exif_data = read_exif(self.image_path)

        # Update all EXIF value fields
        for key, _, _, _, _ in EXIF_FIELDS:
            raw = self.exif_data.get(key, "")
            val_input = self.query_one(f"#val_{key}", Input)
            val_input.value = raw
            fmt_widget = self.query_one(f"#fmt_{key}", Static)
            fmt_widget.update(format_value(key, raw))

        # Update date field
        date_input = self.query_one("#inp_date", Input)
        date_input.value = self.exif_data.get("date", "")

        status.remove_class("error")
        status.add_class("success")
        status.update(f"  ✓  Loaded: {os.path.basename(self.image_path)}")

    # ── gather state and generate ──
    def _generate(self) -> None:
        status = self.query_one("#status", Static)

        filepath = self.query_one("#inp_filepath", Input).value.strip().strip("'\"").replace("\\ ", " ")
        if not filepath or not os.path.isfile(filepath):
            status.remove_class("success")
            status.add_class("error")
            status.update("  ✗  Load an image first")
            return

        self.image_path = os.path.abspath(filepath)

        status.update("  ⏳  Generating...")
        status.remove_class("error")
        status.add_class("success")

        try:
            exif_values = {}
            enabled = {}
            sides = {}
            formats = {}

            for key, _, _, _, _ in EXIF_FIELDS:
                val_input = self.query_one(f"#val_{key}", Input)
                chk = self.query_one(f"#chk_{key}", Checkbox)
                side_sel = self.query_one(f"#side_{key}", Select)

                raw = val_input.value
                exif_values[key] = raw
                enabled[key] = chk.value
                sides[key] = side_sel.value
                formats[key] = format_value(key, raw)

            settings = {}
            for skey, _ in SETTING_LABELS:
                inp = self.query_one(f"#set_{skey}", Input)
                settings[skey] = inp.value

            title = self.query_one("#inp_title", Input).value
            date_text = self.query_one("#inp_date", Input).value
            watermark_text = self.query_one("#inp_watermark", Input).value
            wm_pos = self.query_one("#sel_wm_position", Select).value
            stack = self.query_one("#chk_stack_body_lens", Checkbox).value

            output = generate_frame(
                self.image_path, exif_values, enabled, sides, formats, settings,
                title=title, date_text=date_text, watermark=watermark_text,
                wm_position=wm_pos, stack_body_lens=stack,
            )
            status.update(f"  ✓  Saved: {output}")

        except Exception as e:
            status.remove_class("success")
            status.add_class("error")
            status.update(f"  ✗  Error: {e}")


# ── Entry point ───────────────────────────────────────────────────

def main():
    image_path = ""

    if len(sys.argv) >= 2:
        files = [f for f in sys.argv[1:] if os.path.isfile(f)]
        if len(files) == 1:
            image_path = files[0]
        elif len(files) > 1:
            print("Multiple files found — pick one:")
            for i, f in enumerate(files, 1):
                print(f"  {i}) {os.path.basename(f)}")
            try:
                choice = int(input("\n  → ")) - 1
                image_path = files[choice]
            except (ValueError, IndexError):
                print("Invalid choice.")
                sys.exit(1)

    app = ExifFrameApp(image_path)
    app.title = "EXIF Frame Generator"
    app.run()


if __name__ == "__main__":
    main()
