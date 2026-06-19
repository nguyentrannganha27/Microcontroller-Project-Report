import serial, tkinter as tk, threading, re, time, math, sys, unicodedata, smtplib
from tkinter import Frame, Label, Button, Canvas, messagebox
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from collections import deque
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

try:
    import speech_recognition as sr
    VOICE_AVAILABLE = True
except Exception:
    VOICE_AVAILABLE, sr = False, None

# ================= CONFIG =================
SERIAL_PORT = "COM3"
BAUD_RATE = 9600

SENDER_EMAIL = "nguyentrannganha2005@gmail.com"
APP_PASSWORD = "wemjbxfrynlhnrwr"
RECEIVER_EMAIL = "nguyennhatanabc@gmail.com"

# Ngưỡng đồng bộ mặc định ban đầu
TEMP_THRESHOLD = 50
GAS_THRESHOLD = 40

BG_MAIN = "#111111"
BG_PANEL = "#1a1a1a"
FG_TEXT = "#ffffff"
FG_SUB = "#888888"

MAIN_HEADING = "#D4D4D4"
DARK_HEADING = "#788796" 

ACCENT_RED = "#e50000"
ACCENT_GREEN = "#00e572"
ACCENT_BLUE = "#00a2ff"
ACCENT_YELLOW = "#facc15"
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

ser = None
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
except Exception:
    ser = None

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

control_frame = Frame(main_frame, bg=BG_PANEL, bd=1, relief="ridge", highlightbackground="#333", highlightthickness=1)
control_frame.pack(side="left", fill="y", padx=(0, 20), ipadx=20, ipady=10)

right_frame = Frame(main_frame, bg=BG_MAIN)
right_frame.pack(side="right", fill="both", expand=True)

monitor_frame = Frame(right_frame, bg=BG_PANEL, bd=1, relief="ridge", highlightbackground="#333", highlightthickness=1)
monitor_frame.pack(side="top", fill="x", pady=(0, 20))

graph_frame = Frame(right_frame, bg=BG_PANEL, bd=1, relief="ridge", highlightbackground="#333", highlightthickness=1)
graph_frame.pack(side="bottom", fill="both", expand=True)

# ================= THIẾT KẾ CONTROL PANEL =================
Label(control_frame, text="D E V I C E   C O N T R O L", font=("Arial", 16, "bold"), bg=BG_PANEL, fg=MAIN_HEADING).pack(anchor="w", pady=(10, 20))
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
        btn_fan_auto.config(bg=ACCENT_GREEN, fg="white")
        btn_fan_on.config(bg="#333", fg=FG_TEXT)
        btn_fan_off.config(bg="#333", fg=FG_TEXT)
    else:
        btn_fan_auto.config(bg="#333", fg=FG_TEXT)
        btn_fan_on.config(bg=ACCENT_RED if fan_state else "#333", fg="white" if fan_state else FG_TEXT)
        btn_fan_off.config(bg="#333" if fan_state else ACCENT_RED, fg=FG_TEXT if fan_state else "white")

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
        messagebox.showwarning("KHÓA AN TOÀN", "Đang rò rỉ khí Gas! Cưỡng chế ngắt quạt chống nổ!")
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

btn_fan_auto = Button(control_frame, text="FAN AUTO", width=20, height=1, bg=ACCENT_GREEN, fg="white", font=("Arial", 11, "bold"), bd=0, command=set_fan_auto)
btn_fan_auto.pack(pady=4)

btn_fan_on = Button(control_frame, text="MANUAL ON", width=20, height=1, bg="#333", fg=FG_TEXT, font=("Arial", 11, "bold"), bd=0, command=set_fan_on)
btn_fan_on.pack(pady=4)

btn_fan_off = Button(control_frame, text="MANUAL OFF", width=20, height=1, bg="#333", fg=FG_TEXT, font=("Arial", 11, "bold"), bd=0, command=set_fan_off)
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
        messagebox.showerror("Voice Error", "Chưa cài môi trường nhận diện giọng nói.")
        return
    
    voice_enabled = not voice_enabled
    if voice_enabled:
        btn_voice.config(text="VOICE ON", bg=ACCENT_GREEN, fg="white")
        lbl_voice_status.config(text="Voice: Đang nghe...", fg=ACCENT_GREEN)
    else:
        btn_voice.config(text="VOICE OFF", bg="#333", fg=FG_TEXT)
        lbl_voice_status.config(text="Voice: OFF", fg=FG_SUB)

btn_voice = Button(control_frame, text="VOICE OFF", width=20, height=1, bg="#333", fg=FG_TEXT, font=("Arial", 11, "bold"), bd=0, command=toggle_voice_control)
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
            root.after(0, lambda: safe_voice_status_update("Voice: Chưa nghe số", ACCENT_YELLOW))
        return True
    if contains_any(clean, gas_keys):
        value = extract_number_from_text(clean)
        if value is not None:
            root.after(0, lambda v=value: set_gas_threshold_by_voice(v))
        else:
            root.after(0, lambda: safe_voice_status_update("Voice: Chưa nghe số", ACCENT_YELLOW))
        return True
    if contains_any(clean, off_keys):
        root.after(0, set_fan_off)
        root.after(0, lambda: safe_voice_status_update("Voice: Tắt quạt", ACCENT_GREEN))
        return True
    if contains_any(clean, on_keys):
        root.after(0, set_fan_on)
        root.after(0, lambda: safe_voice_status_update("Voice: Bật quạt", ACCENT_GREEN))
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
            root.after(0, lambda: safe_voice_status_update("Voice: Cân chỉnh...", ACCENT_YELLOW))
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
        while app_running:
            if not voice_enabled:
                time.sleep(0.1)
                continue
            try:
                root.after(0, lambda: safe_voice_status_update("Voice: Đang nghe...", ACCENT_BLUE))
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
                    root.after(0, lambda: safe_voice_status_update("Voice: Không rõ lệnh", FG_SUB))
            except sr.WaitTimeoutError:
                root.after(0, lambda: safe_voice_status_update("Voice: Chờ lệnh...", FG_SUB))
            except Exception: pass
            time.sleep(0.05)
    except Exception: pass

# ================= EMAIL & THRESHOLD MANAGEMENT =================
Label(control_frame, text="SYSTEM ALERT", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", pady=(15, 8))
lbl_email_status = Label(control_frame, text="📧 Email: Standby", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=ACCENT_GREEN)
lbl_email_status.pack(anchor="w", pady=(2, 10))

Label(control_frame, text="THRESHOLD SETTINGS", font=("Arial", 12, "bold"), bg=BG_PANEL, fg=DARK_HEADING).pack(anchor="w", pady=(15, 8))

def apply_temp():
    global TEMP_THRESHOLD
    try:
        val = int(entry_temp.get())
        TEMP_THRESHOLD = val
        send_command(f"T{val}") # Bắn lệnh nạp EEPROM phần cứng
        update_safety_ui()
        force_hardware_sync()
        messagebox.showinfo("Thành công", f"Đã cập nhật ngưỡng Nhiệt độ: {val}°C")
    except ValueError:
        messagebox.showerror("Lỗi Nhập Liệu", "Vui lòng nhập số hợp lệ!")

def apply_gas():
    global GAS_THRESHOLD
    try:
        val = int(entry_gas.get())
        GAS_THRESHOLD = val
        send_command(f"S{val}") # Bắn lệnh nạp EEPROM phần cứng
        update_safety_ui()
        force_hardware_sync()
        messagebox.showinfo("Thành công", f"Đã cập nhật ngưỡng Khí Gas: {val}%")
    except ValueError:
        messagebox.showerror("Lỗi Nhập Liệu", "Vui lòng nhập số hợp lệ!")

# Layout ô Temp + nút Apply rời
frame_temp = Frame(control_frame, bg=BG_PANEL)
frame_temp.pack(fill="x", pady=4)
Label(frame_temp, text="Temp (°C):", font=("Arial", 11, "bold"), bg=BG_PANEL, fg=FG_TEXT, width=9, anchor="w").pack(side="left")
entry_temp = tk.Entry(frame_temp, width=5, bg="#333", fg=FG_TEXT, insertbackground="white", bd=0, font=("Arial", 14, "bold"), justify="center")
entry_temp.insert(0, str(TEMP_THRESHOLD))
entry_temp.pack(side="left", ipady=3, padx=(0, 5))
Button(frame_temp, text="APPLY", bg=ACCENT_BLUE, fg="white", font=("Arial", 8, "bold"), bd=0, command=apply_temp).pack(side="left", ipady=4, ipadx=4)

# Layout ô Gas + nút Apply rời
frame_gas = Frame(control_frame, bg=BG_PANEL)
frame_gas.pack(fill="x", pady=4)
Label(frame_gas, text="Gas (%):", font=("Arial", 11, "bold"), bg=BG_PANEL, fg=FG_TEXT, width=9, anchor="w").pack(side="left")
entry_gas = tk.Entry(frame_gas, width=5, bg="#333", fg=FG_TEXT, insertbackground="white", bd=0, font=("Arial", 14, "bold"), justify="center")
entry_gas.insert(0, str(GAS_THRESHOLD))
entry_gas.pack(side="left", ipady=3, padx=(0, 5))
Button(frame_gas, text="APPLY", bg=ACCENT_BLUE, fg="white", font=("Arial", 8, "bold"), bd=0, command=apply_gas).pack(side="left", ipady=4, ipadx=4)

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
        canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="#333333", width=5)
        for i in range(0, 360, 8):
            rad = math.radians(i + angle)
            x1 = x + (radius - 20) * math.cos(rad)
            y1 = y + (radius - 20) * math.sin(rad)
            x2 = x + (radius + 4) * math.cos(rad)
            y2 = y + (radius + 4) * math.sin(rad)
            canvas.create_line(x1, y1, x2, y2, fill=color, width=3)
        canvas.create_text(x, y - 15, text=value_str, fill="white", font=("Arial", 36, "bold"))
        canvas.create_text(x, y + 35, text=sub_str, fill=FG_SUB, font=("Arial", 12, "bold"))
    except Exception: pass

def animate_dials():
    global fan_angle
    if not app_running: return
    try:
        update_safety_ui()
        temp_color = ACCENT_RED if temperature >= TEMP_THRESHOLD else ACCENT_GREEN
        smoke_color = ACCENT_RED if smoke_val >= GAS_THRESHOLD else ACCENT_ORANGE
        fan_color = ACCENT_RED if fan_state else "#555555"

        draw_dial(canvas_temp, 160, 120, 105, f"{temperature}°C", "LM35 TEMP", temp_color)
        draw_dial(canvas_smoke, 160, 120, 105, f"{smoke_val}%", "GAS & SMOKE", smoke_color)
        if fan_state: fan_angle = (fan_angle + 12) % 360
        draw_dial(canvas_fan, 160, 120, 105, "ON" if fan_state else "OFF", "AUTO MODE" if fan_mode == "AUTO" else "MANUAL MODE", fan_color, fan_angle)
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
    ax.grid(True, color="#333", linestyle="-", linewidth=0.5)
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
    if app_running: lbl_email_status.config(text="📧 Email: Standby", fg=ACCENT_GREEN)

def allow_resend_email():
    global email_sent
    email_sent = False

def send_emergency_email(current_temp, current_gas):
    try:
        root.after(0, lambda: lbl_email_status.config(text="⏳ Đang gửi mail...", fg=ACCENT_YELLOW))
        msg = MIMEText(f"🚨 CẢNH BÁO: Hệ thống phát hiện nguy hiểm!\n\nNhiệt độ hiện tại: {current_temp}°C\nNồng độ Khí/Khói: {current_gas}%\n\nVui lòng kiểm tra khẩn cấp!", 'plain', 'utf-8')
        msg["Subject"] = f"🚨 KHẨN CẤP: Temp {current_temp}°C - Gas {current_gas}%"
        sender_name = str(Header("Hệ thống giám sát nhiệt độ và khí gas", 'utf-8'))
        msg["From"] = formataddr((sender_name, SENDER_EMAIL))
        msg["To"] = RECEIVER_EMAIL
        
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
        server.quit()
        
        root.after(0, lambda: lbl_email_status.config(text="📧 ĐÃ GỬI MAIL!", fg=ACCENT_RED))
        root.after(5000, reset_email_ui)
        root.after(60000, allow_resend_email)
    except Exception:
        root.after(0, lambda: lbl_email_status.config(text="❌ Lỗi gửi mail", fg=FG_SUB))

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