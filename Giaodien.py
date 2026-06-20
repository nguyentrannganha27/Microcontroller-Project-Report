import serial, tkinter as tk, threading, re, time, math, sys, unicodedata, smtplib, os, subprocess
from tkinter import Frame, Label, Button, Canvas, messagebox, ttk
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from collections import deque
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from serial.tools import list_ports

try:
    import speech_recognition as sr
    VOICE_AVAILABLE = True
except Exception:
    VOICE_AVAILABLE, sr = False, None
    

# ================= CONFIG =================
SERIAL_PORT = None
BAUD_RATE = 9600

def resource_path(relative_path):
    """Return a stable path for files bundled by PyInstaller or placed beside main.py."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# The HEX file is bundled into the EXE as code.hex when using build_app_embed_hex.bat.
# This makes the Flash button use the same HEX file on another laptop.
# HEX_FILE = os.path.abspath(
#     r"D:\Download\DoAn_p12\DoAn_p12\Debug\DoAn_p12.hex"
# )

# If avrdude.exe and avrdude.conf are bundled, the app uses them.
# Otherwise it falls back to avrdude from Windows PATH.
# AVRDUDE_EXE = r"D:\avrdude\avrdude.exe"
# AVRDUDE_CONF = r"D:\avrdude\avrdude.conf"

HEX_FILE = resource_path("DoAn_p12.hex")
AVRDUDE_EXE = resource_path("avrdude.exe")
AVRDUDE_CONF = resource_path("avrdude.conf")


MCU = "m128"
PROGRAMMER = "usbasp"  # Same as ProgISP/USBasp. UART COM is only for data communication.

SENDER_EMAIL = "nguyentrannganha2005@gmail.com"
APP_PASSWORD = "wemjbxfrynlhnrwr"
RECEIVER_EMAIL = "nguyennhatanabc@gmail.com"

# Ngưỡng đồng bộ mặc định ban đầu
TEMP_THRESHOLD = 50
GAS_THRESHOLD = 40

BG_MAIN = "#0b1120"
BG_PANEL = "#111827"
FG_TEXT = "#f8fafc"
FG_SUB = "#94a3b8"

MAIN_HEADING = "#e5e7eb"
DARK_HEADING = "#38bdf8" 

ACCENT_RED = "#ef4444"
ACCENT_GREEN = "#22c55e"
ACCENT_BLUE = "#2563eb"
ACCENT_YELLOW = "#f59e0b"
ACCENT_ORANGE = "#f97316"

# ================= GLOBAL =================
temperature = 0
smoke_val = 0
fan_state = False
fan_angle = 0
fan_mode = "AUTO"
email_sent = False
hardware_alarm_state = False
app_running = True
voice_enabled = False

temp_data = deque([0] * 40, maxlen=40)
smoke_data = deque([0] * 40, maxlen=40)
time_data = deque([""] * 40, maxlen=40)

ser = None  # sẽ mở sau khi người dùng chọn COM trên giao diện

recognizer = None
microphone = None

if VOICE_AVAILABLE:
    try:
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        recognizer.energy_threshold = 120
        recognizer.dynamic_energy_threshold = True
        recognizer.dynamic_energy_adjustment_damping = 0.10
        recognizer.dynamic_energy_ratio = 1.05
        recognizer.pause_threshold = 1.0
        recognizer.phrase_threshold = 0.15
        recognizer.non_speaking_duration = 0.5
    except Exception:
        VOICE_AVAILABLE = False
        recognizer = None
        microphone = None

# ================= ROOT GUI =================
root = tk.Tk()
root.title("SYNERGISTIC SURVEILLANCE APPARATUS")
root.geometry("1280x760")
root.configure(bg=BG_MAIN)


# ================= PROFESSIONAL UI STYLE =================
BORDER = "#334155"
BTN_IDLE = "#172033"
BTN_HOVER = "#25334d"
BTN_TEXT = "#f8fafc"
BTN_DISABLED = "#475569"
BTN_PRESS = "#0f172a"
BTN_FLASH = "#ea580c"
BTN_FLASH_HOVER = "#fb923c"
BTN_PRIMARY = "#1d4ed8"
BTN_PRIMARY_HOVER = "#3b82f6"
BTN_SUCCESS = "#15803d"
BTN_SUCCESS_HOVER = "#22c55e"
BTN_DANGER = "#b91c1c"
BTN_DANGER_HOVER = "#ef4444"

style = ttk.Style()
try:
    style.theme_use("clam")
except Exception:
    pass
style.configure(
    "Pro.TCombobox",
    fieldbackground="#0f172a",
    background="#1f2937",
    foreground=FG_TEXT,
    arrowcolor=ACCENT_BLUE,
    bordercolor=BORDER,
    lightcolor=BORDER,
    darkcolor=BORDER,
    padding=4,
)
style.map(
    "Pro.TCombobox",
    fieldbackground=[("readonly", "#0f172a")],
    foreground=[("readonly", FG_TEXT)],
    selectbackground=[("readonly", "#1e293b")],
    selectforeground=[("readonly", FG_TEXT)],
)

def set_button_state(btn, bg, hover=None, fg="white"):
    btn._normal_bg = bg
    btn._hover_bg = hover or BTN_HOVER
    btn.config(
        bg=bg,
        fg=fg,
        activebackground=btn._hover_bg,
        activeforeground="white",
        highlightbackground=BORDER,
    )

def pro_button(master, text, command=None, bg=None, fg="white", font=None, width=20, height=1, hover=None):
    base = bg or BTN_IDLE
    hover_color = hover or BTN_HOVER
    btn = Button(
        master,
        text=text,
        command=command,
        width=width,
        height=height,
        bg=base,
        fg=fg,
        font=font,
        bd=0,
        relief="flat",
        cursor="hand2",
        activebackground=hover_color,
        activeforeground="white",
        highlightthickness=2,
        highlightbackground=BORDER,
        highlightcolor=hover_color,
        padx=10,
        pady=5,
    )
    btn._normal_bg = base
    btn._hover_bg = hover_color
    btn.bind("<Enter>", lambda e: btn.config(bg=getattr(btn, "_hover_bg", hover_color), highlightbackground=getattr(btn, "_hover_bg", hover_color)) if str(btn["state"]) == "normal" else None)
    btn.bind("<Leave>", lambda e: btn.config(bg=getattr(btn, "_normal_bg", base), highlightbackground=BORDER) if str(btn["state"]) == "normal" else None)
    btn.bind("<ButtonPress-1>", lambda e: btn.config(bg=BTN_PRESS) if str(btn["state"]) == "normal" else None)
    btn.bind("<ButtonRelease-1>", lambda e: btn.config(bg=getattr(btn, "_hover_bg", hover_color)) if str(btn["state"]) == "normal" else None)
    return btn

def on_closing():
    global app_running
    app_running = False
    try:
        if ser and ser.is_open:
            ser.close()
    except Exception:
        pass
    root.destroy()
    sys.exit()

root.protocol("WM_DELETE_WINDOW", on_closing)

# ================= HELPERS (ĐỒNG BỘ CHUỖI LỆNH) =================
def send_command(cmd):
    try:
        if ser and ser.is_open:
            # Tự động chèn ký tự Enter để đồng bộ hóa mạch nạp chuỗi
            if not cmd.endswith("\n"):
                cmd += "\r\n"
            ser.write(cmd.encode())
    except Exception:
        pass

def normalize_text(text):
    text = text.lower().strip().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

def contains_any(text, keys):
    return any(k in text for k in keys)

def extract_number_from_text(text):
    match = re.search(r"\b(\d{1,3})\b", text)
    if match:
        return max(0, min(100, int(match.group(1))))

    words = {
        "khong": 0, "mot": 1, "hai": 2, "ba": 3, "bon": 4, "tu": 4,
        "nam": 5, "lam": 5, "sau": 6, "bay": 7, "tam": 8, "chin": 9,
        "muoi": 10, "hai muoi": 20, "ba muoi": 30, "bon muoi": 40,
        "tu muoi": 40, "nam muoi": 50, "sau muoi": 60,
        "bay muoi": 70, "tam muoi": 80, "chin muoi": 90,
        "mot tram": 100
    }
    for word, value in sorted(words.items(), key=lambda x: len(x[0]), reverse=True):
        if word in text:
            return value
    return None

# ================= BỐ CỤC ĐỒ HỌA PANEL =================
header_frame = Frame(root, bg=BG_MAIN, height=50)
header_frame.pack(fill="x", pady=10)

title_str = "L M 3 5   &   M Q - 2   S Y N E R G I S T I C   S U R V E I L L A N C E"
title_frame = Frame(header_frame, bg=BG_MAIN)
title_frame.pack()
Label(title_frame, text=title_str, font=("Verdana", 22, "bold"), bg=BG_MAIN, fg="#000000").place(x=3, y=4)
Label(title_frame, text=title_str, font=("Verdana", 22, "bold"), bg=BG_MAIN, fg=MAIN_HEADING).pack(padx=10, pady=5)

main_frame = Frame(root, bg=BG_MAIN)
main_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

control_frame = Frame(main_frame, bg=BG_PANEL, bd=1, relief="ridge", highlightbackground="#1e293b", highlightthickness=1)
control_frame.pack(side="left", fill="y", padx=(0, 20), ipadx=20, ipady=10)

right_frame = Frame(main_frame, bg=BG_MAIN)
right_frame.pack(side="right", fill="both", expand=True)

monitor_frame = Frame(right_frame, bg=BG_PANEL, bd=1, relief="ridge", highlightbackground="#1e293b", highlightthickness=1)
monitor_frame.pack(side="top", fill="x", pady=(0, 20))

graph_frame = Frame(right_frame, bg=BG_PANEL, bd=1, relief="ridge", highlightbackground="#1e293b", highlightthickness=1)
graph_frame.pack(side="bottom", fill="both", expand=True)

# ================= COM & PROGRAMMER PANEL =================
def get_available_ports():
    """Return USB serial COM ports that are likely ready for UART data.

    This avoids showing legacy/non-USB ports such as COM1 when the user only
    wants ports created by plugged-in USB-UART modules.
    """
    usb_keywords = (
        "USB", "CH340", "CH341", "CP210", "CP210X", "FTDI",
        "UART", "SERIAL", "CDC", "PROLIFIC", "PL2303", "ARDUINO"
    )
    ready_ports = []
    other_ports = []

    for p in list_ports.comports():
        desc = p.description or "Unknown device"
        hwid = p.hwid or ""
        text = f"{desc} {hwid}".upper()
        label = f"{p.device} - {desc}"

        if any(key in text for key in usb_keywords) or "VID:PID" in text:
            ready_ports.append(label)
        else:
            other_ports.append(label)

    # Prefer USB COM ports. If Windows only reports generic ports, still show them.
    return ready_ports if ready_ports else other_ports

def selected_com_name():
    value = combo_ports.get().strip()
    if not value:
        return None
    return value.split(" - ")[0].strip()

def refresh_ports():
    ports = get_available_ports()
    combo_ports["values"] = ports
    if ports:
        current = combo_ports.get().strip()
        if current in ports:
            combo_ports.set(current)
        else:
            combo_ports.current(0)
        lbl_com_status.config(text=f"{len(ports)} USB COM port(s) ready", fg=ACCENT_GREEN)
    else:
        combo_ports.set("")
        lbl_com_status.config(text="No USB COM port detected", fg=ACCENT_RED)

def connect_selected_port():
    global ser, SERIAL_PORT
    port = selected_com_name()
    if not port:
        messagebox.showwarning("COM", "Please select a COM port first.")
        return
    try:
        if ser and ser.is_open:
            ser.close()
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        SERIAL_PORT = port
        lbl_com_status.config(text=f"Connected to {port} @ {BAUD_RATE}", fg=ACCENT_GREEN)
    except Exception as e:
        ser = None
        lbl_com_status.config(text=f"Failed to open {port}", fg=ACCENT_RED)
        messagebox.showerror("COM Error", str(e))

def flash_hex_file():
    port = selected_com_name()
    if not os.path.exists(HEX_FILE):
        messagebox.showerror("HEX File Error", f"HEX file not found:\n{HEX_FILE}")
        return

    # Đóng UART trước khi nạp để tránh chiếm cổng/thiết bị
    try:
        if ser and ser.is_open:
            ser.close()
    except Exception:
        pass

    # USBasp/ISP flashing: COM port is not used for flashing.
    cmd = [AVRDUDE_EXE]
    if AVRDUDE_CONF:
        cmd += ["-C", AVRDUDE_CONF]
    cmd += ["-c", PROGRAMMER, "-p", MCU, "-B", "10", "-U", f"flash:w:{HEX_FILE}:i"]

    # If your ATmega128 has a UART bootloader, use this style instead:
    # cmd = [AVRDUDE_EXE, "-c", "avr109", "-p", MCU, "-P", port, "-b", "115200", "-U", f"flash:w:{HEX_FILE}:i"]

    lbl_flash_status.config(text="Flashing HEX...", fg=ACCENT_YELLOW)
    btn_flash.config(state="disabled")

    def worker():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            if result.returncode == 0:
                root.after(0, lambda: lbl_flash_status.config(text="Flash completed successfully", fg=ACCENT_GREEN))
                root.after(0, lambda: messagebox.showinfo("AVR", "Code has been flashed successfully to ATmega128."))
            else:
                root.after(0, lambda: lbl_flash_status.config(text="Flash failed", fg=ACCENT_RED))
                root.after(0, lambda: messagebox.showerror("AVRDUDE Error", output[-3000:]))
        except Exception as e:
            root.after(0, lambda: lbl_flash_status.config(text="Flash error", fg=ACCENT_RED))
            root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            root.after(0, lambda: btn_flash.config(state="normal"))

    threading.Thread(target=worker, daemon=True).start()

# ================= THIẾT KẾ CONTROL PANEL =================
Label(control_frame, text="D E V I C E   C O N T R O L", font=("Arial", 16, "bold"), bg=BG_PANEL, fg=MAIN_HEADING).pack(anchor="w", pady=(10, 12))

Label(control_frame, text="UART / PROGRAMMER", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", pady=(4, 6))
combo_ports = ttk.Combobox(control_frame, width=24, state="readonly", style="Pro.TCombobox")
combo_ports.pack(anchor="w", pady=3)
btn_port_row = Frame(control_frame, bg=BG_PANEL)
btn_port_row.pack(anchor="w", pady=3)
pro_button(btn_port_row, text="REFRESH COM", bg=BTN_IDLE, hover=BTN_HOVER, fg=FG_TEXT, font=("Arial", 8, "bold"), command=refresh_ports, width=12).pack(side="left", ipadx=4, ipady=3, padx=(0, 5))
pro_button(btn_port_row, text="CONNECT", bg=BTN_PRIMARY, hover=BTN_PRIMARY_HOVER, fg="white", font=("Arial", 8, "bold"), command=connect_selected_port, width=10).pack(side="left", ipadx=4, ipady=3)
lbl_com_status = Label(control_frame, text="COM scan not started", font=("Arial", 10, "bold"), bg=BG_PANEL, fg=FG_SUB)
lbl_com_status.pack(anchor="w", pady=(2, 8))
btn_flash = pro_button(control_frame, text="FLASH ATMEGA128", width=20, height=1, bg=BTN_FLASH, hover=BTN_FLASH_HOVER, fg="white", font=("Arial", 11, "bold"), command=flash_hex_file)
btn_flash.pack(anchor="w", pady=4)
lbl_flash_status = Label(control_frame, text="Bundled HEX: code.hex", font=("Arial", 10, "bold"), bg=BG_PANEL, fg=FG_SUB, wraplength=220, justify="left")
lbl_flash_status.pack(anchor="w", pady=(2, 12))
refresh_ports()

def auto_refresh_ports():
    if app_running:
        refresh_ports()
        root.after(3000, auto_refresh_ports)

auto_refresh_ports()
Label(control_frame, text="SAFETY INDICATOR", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", pady=(10, 5))

lbl_safe_light_status = Label(control_frame, text="Safe Light: ON", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=ACCENT_GREEN)
lbl_safe_light_status.pack(anchor="w", pady=(0, 2))

lbl_alarm_status = Label(control_frame, text="System: SAFE", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=ACCENT_GREEN)
lbl_alarm_status.pack(anchor="w", pady=(0, 10))

# HÀM ÉP ĐỒNG BỘ CÒI MẠCH C NGAY LẬP TỨC KHI ĐỔI NGƯỠNG
def force_hardware_sync():
    global hardware_alarm_state
    is_danger = temperature >= TEMP_THRESHOLD or smoke_val >= GAS_THRESHOLD
    if is_danger:
        send_command("A")
        hardware_alarm_state = True
    else:
        send_command("a")
        hardware_alarm_state = False

def update_safety_ui():
    is_danger = temperature >= TEMP_THRESHOLD or smoke_val >= GAS_THRESHOLD
    if is_danger:
        lbl_safe_light_status.config(text="Safe Light: OFF", fg=ACCENT_RED)
        lbl_alarm_status.config(text="System: DANGER", fg=ACCENT_RED)
    else:
        lbl_safe_light_status.config(text="Safe Light: ON", fg=ACCENT_GREEN)
        lbl_alarm_status.config(text="System: SAFE", fg=ACCENT_GREEN)

# ================= FAN CONTROL =================
Label(control_frame, text="FAN SYSTEM", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", pady=(15, 8))

def update_fan_ui():
    if fan_mode == "AUTO":
        set_button_state(btn_fan_auto, BTN_SUCCESS, BTN_SUCCESS_HOVER, "white")
        set_button_state(btn_fan_on, BTN_IDLE, BTN_HOVER, FG_TEXT)
        set_button_state(btn_fan_off, BTN_IDLE, BTN_HOVER, FG_TEXT)
    else:
        set_button_state(btn_fan_auto, BTN_IDLE, BTN_HOVER, FG_TEXT)
        if fan_state:
            set_button_state(btn_fan_on, BTN_SUCCESS, BTN_SUCCESS_HOVER, "white")
            set_button_state(btn_fan_off, BTN_IDLE, BTN_HOVER, FG_TEXT)
        else:
            set_button_state(btn_fan_on, BTN_IDLE, BTN_HOVER, FG_TEXT)
            set_button_state(btn_fan_off, BTN_DANGER, BTN_DANGER_HOVER, "white")

def quat_on():
    global fan_state
    if not fan_state:
        send_command("F")
        fan_state = True
        update_fan_ui()

def quat_off():
    global fan_state
    if fan_state:
        send_command("f")
        fan_state = False
        update_fan_ui()

def set_fan_on():
    global fan_mode
    if smoke_val >= GAS_THRESHOLD:
        messagebox.showwarning("SAFETY LOCK", "Gas leakage detected. Fan is forced OFF for safety.")
        return
    fan_mode = "MANUAL_ON"
    quat_on()

def set_fan_off():
    global fan_mode
    fan_mode = "MANUAL_OFF"
    quat_off()

def set_fan_auto():
    global fan_mode
    fan_mode = "AUTO"
    send_command("O")
    update_fan_ui()

btn_fan_auto = pro_button(control_frame, text="FAN AUTO", width=20, height=1, bg=BTN_SUCCESS, hover=BTN_SUCCESS_HOVER, fg="white", font=("Arial", 11, "bold"), command=set_fan_auto)
btn_fan_auto.pack(pady=4)

btn_fan_on = pro_button(control_frame, text="MANUAL ON", width=20, height=1, bg=BTN_IDLE, hover=BTN_HOVER, fg=FG_TEXT, font=("Arial", 11, "bold"), command=set_fan_on)
btn_fan_on.pack(pady=4)

btn_fan_off = pro_button(control_frame, text="MANUAL OFF", width=20, height=1, bg=BTN_IDLE, hover=BTN_HOVER, fg=FG_TEXT, font=("Arial", 11, "bold"), command=set_fan_off)
btn_fan_off.pack(pady=(4, 10))

# ================= VOICE MODULE =================
def safe_voice_status_update(msg, color):
    if voice_enabled:
        lbl_voice_status.config(text=msg, fg=color)

Label(control_frame, text="VOICE CONTROL", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", pady=(15, 8))
lbl_voice_status = Label(control_frame, text="Voice: OFF", font=("Arial", 11, "bold"), bg=BG_PANEL, fg=FG_SUB)
lbl_voice_status.pack(anchor="w", pady=2)

def toggle_voice_control():
    global voice_enabled
    if not VOICE_AVAILABLE:
        messagebox.showerror("Voice Error", "Speech recognition environment is not installed.")
        return
    
    voice_enabled = not voice_enabled
    if voice_enabled:
        btn_voice.config(text="VOICE ON"); set_button_state(btn_voice, BTN_SUCCESS, BTN_SUCCESS_HOVER, "white")
        lbl_voice_status.config(text="Voice: Listening...", fg=ACCENT_GREEN)
    else:
        btn_voice.config(text="VOICE OFF"); set_button_state(btn_voice, BTN_IDLE, BTN_HOVER, FG_TEXT)
        lbl_voice_status.config(text="Voice: OFF", fg=FG_SUB)

btn_voice = pro_button(control_frame, text="VOICE OFF", width=20, height=1, bg=BTN_IDLE, hover=BTN_HOVER, fg=FG_TEXT, font=("Arial", 11, "bold"), command=toggle_voice_control)
btn_voice.pack(pady=(4, 10))

def set_temp_threshold_by_voice(value):
    global TEMP_THRESHOLD
    TEMP_THRESHOLD = value
    entry_temp.delete(0, tk.END)
    entry_temp.insert(0, str(value))
    send_command(f"T{value}") # Đồng bộ cứng xuống EEPROM mạch C
    update_safety_ui()
    force_hardware_sync()
    safe_voice_status_update(f"Voice: Temp = {value}°C", ACCENT_GREEN)

def set_gas_threshold_by_voice(value):
    global GAS_THRESHOLD
    GAS_THRESHOLD = value
    entry_gas.delete(0, tk.END)
    entry_gas.insert(0, str(value))
    send_command(f"S{value}") # Đồng bộ cứng xuống EEPROM mạch C
    update_safety_ui()
    force_hardware_sync()
    safe_voice_status_update(f"Voice: Gas = {value}%", ACCENT_GREEN)

def handle_voice_command(text):
    if not voice_enabled: return False 
    raw = text.lower().strip()
    clean = normalize_text(raw)
    
    temp_keys = ["nhiet do", "nhiet", "temperature", "temp", "dat nhiet do", "cai nhiet do", "nguong nhiet do"]
    gas_keys = ["gas", "khoi", "khi gas", "khi", "do am", "am", "humidity", "nguong gas", "dat gas", "cai gas"]
    off_keys = ["tat quat", "tat", "dung quat", "dung", "ngung quat", "ngung", "fan off", "off", "stop fan", "turn off"]
    on_keys = ["bat quat", "bat", "mo quat", "mo", "quat chay", "chay", "fan on", "on", "start fan", "turn on"]
    auto_keys = ["tu dong", "che do tu dong", "auto", "fan auto", "quat auto", "che do auto"]

    if contains_any(clean, temp_keys):
        value = extract_number_from_text(clean)
        if value is not None:
            root.after(0, lambda v=value: set_temp_threshold_by_voice(v))
        else:
            root.after(0, lambda: safe_voice_status_update("Voice: Number not detected", ACCENT_YELLOW))
        return True
    if contains_any(clean, gas_keys):
        value = extract_number_from_text(clean)
        if value is not None:
            root.after(0, lambda v=value: set_gas_threshold_by_voice(v))
        else:
            root.after(0, lambda: safe_voice_status_update("Voice: Number not detected", ACCENT_YELLOW))
        return True
    if contains_any(clean, off_keys):
        root.after(0, set_fan_off)
        root.after(0, lambda: safe_voice_status_update("Voice: Fan OFF", ACCENT_GREEN))
        return True
    if contains_any(clean, on_keys):
        root.after(0, set_fan_on)
        root.after(0, lambda: safe_voice_status_update("Voice: Fan ON", ACCENT_GREEN))
        return True
    if contains_any(clean, auto_keys):
        root.after(0, set_fan_auto)
        root.after(0, lambda: safe_voice_status_update("Voice: Fan Auto", ACCENT_GREEN))
        return True
    return False

def voice_listener():
    global voice_enabled
    if not VOICE_AVAILABLE or recognizer is None or microphone is None: return
    try:
        with microphone as source:
            root.after(0, lambda: safe_voice_status_update("Voice: Calibrating...", ACCENT_YELLOW))
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
        while app_running:
            if not voice_enabled:
                time.sleep(0.1)
                continue
            try:
                root.after(0, lambda: safe_voice_status_update("Voice: Listening...", ACCENT_BLUE))
                with microphone as source:
                    audio = recognizer.listen(source, timeout=6, phrase_time_limit=6)
                if not voice_enabled: continue
                results = []
                try:
                    result_vi = recognizer.recognize_google(audio, language="vi-VN", show_all=True)
                    if isinstance(result_vi, str): results.append(result_vi)
                    elif isinstance(result_vi, dict):
                        for item in result_vi.get("alternative", []):
                            if item.get("transcript", ""): results.append(item.get("transcript", ""))
                except Exception: pass
                
                command_found = False
                for text in results:
                    if handle_voice_command(text):
                        command_found = True
                        break
                if not command_found and voice_enabled:
                    root.after(0, lambda: safe_voice_status_update("Voice: Command not recognized", FG_SUB))
            except sr.WaitTimeoutError:
                root.after(0, lambda: safe_voice_status_update("Voice: Waiting...", FG_SUB))
            except Exception: pass
            time.sleep(0.05)
    except Exception: pass

# ================= EMAIL & THRESHOLD MANAGEMENT =================
Label(control_frame, text="SYSTEM ALERT", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", pady=(15, 8))
lbl_email_status = Label(control_frame, text="Email: Standby", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=ACCENT_GREEN)
lbl_email_status.pack(anchor="w", pady=(2, 10))

# Move threshold section slightly upward and give the input rows more vertical room
Label(control_frame, text="THRESHOLD SETTINGS", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", pady=(8, 6))

def apply_temp():
    global TEMP_THRESHOLD
    try:
        val = int(entry_temp.get())
        TEMP_THRESHOLD = val
        send_command(f"T{val}") # Bắn lệnh nạp EEPROM phần cứng
        update_safety_ui()
        force_hardware_sync()
        messagebox.showinfo("Success", f"Temperature threshold updated: {val}°C")
    except ValueError:
        messagebox.showerror("Input Error", "Please enter a valid number.")

def apply_gas():
    global GAS_THRESHOLD
    try:
        val = int(entry_gas.get())
        GAS_THRESHOLD = val
        send_command(f"S{val}") # Bắn lệnh nạp EEPROM phần cứng
        update_safety_ui()
        force_hardware_sync()
        messagebox.showinfo("Success", f"Gas threshold updated: {val}%")
    except ValueError:
        messagebox.showerror("Input Error", "Please enter a valid number.")

# Threshold input rows - fixed layout so Gas value is never hidden
THRESHOLD_ROW_W = 260
LABEL_W = 82
ENTRY_W = 74
APPLY_W = 78
ROW_H = 38

frame_temp = Frame(control_frame, bg=BG_PANEL, width=THRESHOLD_ROW_W, height=ROW_H)
frame_temp.pack(anchor="w", pady=(2, 3))
frame_temp.pack_propagate(False)
Label(frame_temp, text="Temp (°C):", font=("Arial", 11, "bold"), bg=BG_PANEL, fg=FG_TEXT, width=9, anchor="w").place(x=0, y=4, width=LABEL_W, height=28)
entry_temp = tk.Entry(frame_temp, width=6, bg="#0f172a", fg=FG_TEXT, insertbackground="white", bd=0, highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT_BLUE, font=("Arial", 14, "bold"), justify="center")
entry_temp.insert(0, str(TEMP_THRESHOLD))
entry_temp.place(x=LABEL_W + 4, y=0, width=ENTRY_W, height=36)
pro_button(frame_temp, text="APPLY", bg=BTN_PRIMARY, hover=BTN_PRIMARY_HOVER, fg="white", font=("Arial", 8, "bold"), command=apply_temp, width=7).place(x=LABEL_W + ENTRY_W + 14, y=0, width=APPLY_W, height=36)

frame_gas = Frame(control_frame, bg=BG_PANEL, width=THRESHOLD_ROW_W, height=ROW_H)
frame_gas.pack(anchor="w", pady=(2, 0))
frame_gas.pack_propagate(False)
Label(frame_gas, text="Gas (%):", font=("Arial", 11, "bold"), bg=BG_PANEL, fg=FG_TEXT, width=9, anchor="w").place(x=0, y=4, width=LABEL_W, height=28)
entry_gas = tk.Entry(frame_gas, width=6, bg="#0f172a", fg=FG_TEXT, insertbackground="white", bd=0, highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT_BLUE, font=("Arial", 14, "bold"), justify="center")
entry_gas.insert(0, str(GAS_THRESHOLD))
entry_gas.place(x=LABEL_W + 4, y=0, width=ENTRY_W, height=36)
pro_button(frame_gas, text="APPLY", bg=BTN_PRIMARY, hover=BTN_PRIMARY_HOVER, fg="white", font=("Arial", 8, "bold"), command=apply_gas, width=7).place(x=LABEL_W + ENTRY_W + 14, y=0, width=APPLY_W, height=36)

# ================= DIALS MONITORING =================
Label(monitor_frame, text="MONITORING DIALS", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", padx=10, pady=5)
dials_frame = Frame(monitor_frame, bg=BG_PANEL)
dials_frame.pack(fill="both", expand=True)

canvas_temp = Canvas(dials_frame, width=320, height=240, bg=BG_PANEL, highlightthickness=0)
canvas_smoke = Canvas(dials_frame, width=320, height=240, bg=BG_PANEL, highlightthickness=0)
canvas_fan = Canvas(dials_frame, width=320, height=240, bg=BG_PANEL, highlightthickness=0)
canvas_temp.pack(side="left", expand=True)
canvas_smoke.pack(side="left", expand=True)
canvas_fan.pack(side="left", expand=True)

def draw_dial(canvas, x, y, radius, value_str, sub_str, color, angle=0):
    try:
        canvas.delete("all")
        canvas.create_oval(x - radius - 6, y - radius - 6, x + radius + 6, y + radius + 6, outline="#0f172a", width=8)
        canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="#334155", width=5)
        for i in range(0, 360, 8):
            rad = math.radians(i + angle)
            x1 = x + (radius - 20) * math.cos(rad)
            y1 = y + (radius - 20) * math.sin(rad)
            x2 = x + (radius + 4) * math.cos(rad)
            y2 = y + (radius + 4) * math.sin(rad)
            canvas.create_line(x1, y1, x2, y2, fill=color, width=3)

        # Value layer: draw it last with a dark backing so TEMP/GAS numbers never disappear.
        canvas.create_rectangle(x - 78, y - 43, x + 78, y + 14, fill=BG_PANEL, outline="")
        canvas.create_text(x + 2, y - 14, text=value_str, fill="#020617", font=("Arial", 36, "bold"))
        canvas.create_text(x, y - 16, text=value_str, fill="white", font=("Arial", 36, "bold"))
        canvas.create_text(x, y + 36, text=sub_str, fill=FG_SUB, font=("Arial", 12, "bold"))
    except Exception:
        pass

def draw_fan_dial(canvas, x, y, radius, is_on, sub_str, angle=0):
    try:
        canvas.delete("all")
        frame_color = ACCENT_GREEN if is_on else "#64748b"
        blade_color = "#94a3b8" if is_on else "#475569"
        blade_shadow = "#1e293b"
        hub_color = "#e5e7eb" if is_on else "#94a3b8"

        # outer body and safety grille
        canvas.create_oval(x - radius - 8, y - radius - 8, x + radius + 8, y + radius + 8, outline="#020617", width=8)
        canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="#334155", width=5)
        canvas.create_oval(x - radius + 18, y - radius + 18, x + radius - 18, y + radius - 18, outline="#1e293b", width=2)
        canvas.create_oval(x - radius + 40, y - radius + 40, x + radius - 40, y + radius - 40, outline="#1e293b", width=2)
        for i in range(0, 360, 30):
            rad = math.radians(i)
            canvas.create_line(x, y, x + (radius - 8) * math.cos(rad), y + (radius - 8) * math.sin(rad), fill="#1e293b", width=1)

        # subtle motion trails when running
        if is_on:
            for offset in (18, 36):
                for i in range(3):
                    theta = math.radians(angle + i * 120 - offset)
                    x1 = x + 35 * math.cos(theta - 0.28)
                    y1 = y + 35 * math.sin(theta - 0.28)
                    x2 = x + 82 * math.cos(theta)
                    y2 = y + 82 * math.sin(theta)
                    x3 = x + 35 * math.cos(theta + 0.28)
                    y3 = y + 35 * math.sin(theta + 0.28)
                    canvas.create_polygon(x1, y1, x2, y2, x3, y3, fill="#1f2937", outline="", smooth=True)

        # three curved blades
        for i in range(3):
            theta = math.radians(angle + i * 120)
            pts_shadow = []
            pts = []
            for r, a in [(24, -0.25), (82, -0.45), (94, 0.06), (34, 0.32)]:
                pts_shadow.extend([x + 3 + r * math.cos(theta + a), y + 3 + r * math.sin(theta + a)])
                pts.extend([x + r * math.cos(theta + a), y + r * math.sin(theta + a)])
            canvas.create_polygon(*pts_shadow, fill=blade_shadow, outline="", smooth=True)
            canvas.create_polygon(*pts, fill=blade_color, outline=frame_color, width=1, smooth=True)

        # hub and status text
        canvas.create_oval(x - 23, y - 23, x + 23, y + 23, fill="#0f172a", outline=frame_color, width=3)
        canvas.create_oval(x - 11, y - 11, x + 11, y + 11, fill=hub_color, outline="")
        canvas.create_text(x, y + 105, text="ON" if is_on else "OFF", fill=frame_color, font=("Arial", 26, "bold"))
        canvas.create_text(x, y + 132, text=sub_str, fill=FG_SUB, font=("Arial", 11, "bold"))
    except Exception:
        pass

def animate_dials():
    global fan_angle
    if not app_running: return
    try:
        update_safety_ui()
        temp_color = ACCENT_RED if temperature >= TEMP_THRESHOLD else ACCENT_GREEN
        smoke_color = ACCENT_RED if smoke_val >= GAS_THRESHOLD else ACCENT_ORANGE
        fan_color = ACCENT_RED if fan_state else "#64748b"

        draw_dial(canvas_temp, 160, 120, 105, f"{temperature}°C", "LM35 TEMP", temp_color)
        draw_dial(canvas_smoke, 160, 120, 105, f"{smoke_val}%", "GAS & SMOKE", smoke_color)
        if fan_state: fan_angle = (fan_angle + 18) % 360
        draw_fan_dial(canvas_fan, 160, 120, 105, fan_state, "AUTO MODE" if fan_mode == "AUTO" else "MANUAL MODE", fan_angle)
        root.after(40, animate_dials)
    except Exception: pass

# ================= REAL-TIME PLOT GRAPH =================
Label(graph_frame, text="REAL-TIME TELEMETRY", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", padx=10, pady=5)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6), dpi=100)
fig.patch.set_facecolor(BG_PANEL)
fig.subplots_adjust(left=0.05, right=0.98, top=0.9, bottom=0.15, wspace=0.15)
canvas_graph = FigureCanvasTkAgg(fig, master=graph_frame)
canvas_graph.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

def style_axis(ax):
    ax.set_facecolor(BG_MAIN)
    ax.grid(True, color="#334155", linestyle="-", linewidth=0.5)
    ax.tick_params(axis="y", colors=FG_SUB)
    for spine in ax.spines.values(): spine.set_color("#333")

def update_graph(frame):
    if not app_running: return
    try:
        ax1.clear(); ax2.clear()
        y_temp, y_smoke, times = list(temp_data), list(smoke_data), list(time_data)
        if len(y_temp) == 0: return
        x = list(range(len(y_temp)))
        step = max(1, len(x) // 6)

        style_axis(ax1)
        ax1.plot(x, y_temp, color=ACCENT_RED, linewidth=3)
        ax1.fill_between(x, y_temp, 0, color=ACCENT_RED, alpha=0.3)
        ax1.axhline(TEMP_THRESHOLD, color=ACCENT_YELLOW, linestyle="--", linewidth=2)
        ax1.set_title("TEMPERATURE (°C)", color=FG_SUB, fontsize=10, fontweight="bold")
        ax1.set_ylim(0, 100); ax1.set_xlim(0, max(1, len(x) - 1))
        ax1.set_xticks(x[::step]); ax1.set_xticklabels(times[::step], color=FG_SUB, fontsize=8)

        style_axis(ax2)
        ax2.plot(x, y_smoke, color=ACCENT_ORANGE, linewidth=3)
        ax2.fill_between(x, y_smoke, 0, color=ACCENT_ORANGE, alpha=0.3)
        ax2.axhline(GAS_THRESHOLD, color=ACCENT_YELLOW, linestyle="--", linewidth=2)
        ax2.set_title("COMBUSTIBLE GAS (%)", color=FG_SUB, fontsize=10, fontweight="bold")
        ax2.set_ylim(0, 100); ax2.set_xlim(0, max(1, len(x) - 1))
        ax2.set_xticks(x[::step]); ax2.set_xticklabels(times[::step], color=FG_SUB, fontsize=8)
    except Exception: pass

ani = FuncAnimation(fig, update_graph, interval=1000, cache_frame_data=False)

# ================= EMAIL THREAD =================
def reset_email_ui():
    if app_running: lbl_email_status.config(text="Email: Standby", fg=ACCENT_GREEN)

def allow_resend_email():
    global email_sent
    email_sent = False

def send_emergency_email(current_temp, current_gas):
    try:
        root.after(0, lambda: lbl_email_status.config(text="Sending email...", fg=ACCENT_YELLOW))
        msg = MIMEText(f"EMERGENCY ALERT: Dangerous condition detected!\n\nCurrent temperature: {current_temp}°C\nGas/smoke level: {current_gas}%\n\nPlease inspect the system immediately.", 'plain', 'utf-8')
        msg["Subject"] = f"EMERGENCY ALERT: Temp {current_temp}°C - Gas {current_gas}%"
        sender_name = str(Header("Temperature and Gas Monitoring System", 'utf-8'))
        msg["From"] = formataddr((sender_name, SENDER_EMAIL))
        msg["To"] = RECEIVER_EMAIL
        
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
        server.quit()
        
        root.after(0, lambda: lbl_email_status.config(text="Email sent", fg=ACCENT_RED))
        root.after(5000, reset_email_ui)
        root.after(60000, allow_resend_email)
    except Exception:
        root.after(0, lambda: lbl_email_status.config(text="Email error", fg=FG_SUB))

# ================= UART MASTER BACKEND THREAD =================
def read_uart():
    global temperature, smoke_val, email_sent
    global hardware_alarm_state, fan_mode

    while app_running:
        try:
            # GIẢI QUYẾT TRIỆT ĐỂ LỖI RESET CHIP: Liên tục nhồi lệnh nếu đang ở Manual Mode
            if fan_mode == "MANUAL_ON":
                send_command("F")
            elif fan_mode == "MANUAL_OFF":
                send_command("f")

            if ser and ser.is_open and ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    match_temp = re.search(r"Nhiet do hien tai:\s*(\d+)", line)
                    match_smoke = re.search(r"KHOI:\s*(\d+)", line)

                    if match_temp:
                        temperature = int(match_temp.group(1))
                        temp_data.append(temperature)
                        time_data.append(time.strftime("%H:%M:%S"))
                    if match_smoke:
                        smoke_val = min(int(match_smoke.group(1)), 100)
                        smoke_data.append(smoke_val)

                    # LOGIC QUYẾT ĐỊNH ĐỒNG BỘ CỦA MASTER PYTHON
                    is_temp_danger = temperature >= TEMP_THRESHOLD
                    is_gas_danger = smoke_val >= GAS_THRESHOLD
                    is_danger = is_temp_danger or is_gas_danger

                    if is_danger and not hardware_alarm_state:
                        send_command("A") # Ép vi điều khiển hú còi
                        hardware_alarm_state = True
                        if is_temp_danger:
                            fan_mode = "AUTO"
                            root.after(0, update_fan_ui)
                        root.after(0, update_safety_ui)
                    elif not is_danger and hardware_alarm_state:
                        send_command("a") # Ép vi điều khiển tắt còi
                        hardware_alarm_state = False
                        root.after(0, update_safety_ui)

                    # Điều khiển quạt khi ở chế độ tự động
                    if fan_mode == "AUTO":
                        if is_gas_danger:
                            if fan_state: root.after(0, quat_off)
                        else:
                            if is_temp_danger and not fan_state: root.after(0, quat_on)
                            elif not is_temp_danger and fan_state: root.after(0, quat_off)

                    # Gửi Email cảnh báo sự cố khẩn cấp
                    if is_danger and not email_sent:
                        email_sent = True 
                        threading.Thread(target=send_emergency_email, args=(temperature, smoke_val), daemon=True).start()
                    elif not is_danger and email_sent:
                        email_sent = False
                        root.after(0, reset_email_ui)
        except Exception: pass
        time.sleep(0.1)

# ================= RUN SYSTEMS =================
threading.Thread(target=read_uart, daemon=True).start()
threading.Thread(target=voice_listener, daemon=True).start()
animate_dials()
root.mainloop()