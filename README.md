# 🎙 FastWhisper Flow

**พิมพ์ด้วยเสียงภาษาไทย/อังกฤษ บน Mac — ฟรี 100% ทำงานในเครื่อง ไม่ส่งเสียงขึ้นเน็ต**

*Powered by **JTIAPBN.Ai** × **Whispering Weekends***

> กด **Right ⌘** ค้าง → พูด → ปล่อย → ข้อความพิมพ์ให้เองในทุกแอป
> ใช้ได้กับ Notes, LINE, เบราว์เซอร์, VS Code — ทุกที่ที่พิมพ์ได้

ทางเลือกโอเพนซอร์สของ [Wispr Flow](https://wisprflow.ai) ที่ไม่มีค่าบริการรายเดือน ขับเคลื่อนด้วย
[mlx-whisper](https://github.com/ml-explore/mlx-examples) (เร่งความเร็วด้วยชิป Apple Silicon) และโมเดลภาษาไทย
[Thonburian Whisper](https://github.com/biodatlab/thonburian-whisper)

---

## ✨ ความสามารถ

| | |
|---|---|
| 🇹🇭 **ภาษาไทยแม่นยำ** | ใช้โมเดล Thonburian Whisper ที่จูนมาเพื่อภาษาไทยโดยเฉพาะ |
| 🔒 **ส่วนตัว 100%** | ถอดเสียงในเครื่องทั้งหมด ไม่มีข้อมูลออกจาก Mac ของคุณ |
| ⚡ **เร็ว** | ~1 วินาทีต่อประโยค บนชิป M1 ขึ้นไป (ใช้ GPU ผ่าน MLX) |
| 🧹 **ตัดคำฟุ่มเฟือย** | เอ่อ, แบบว่า, อะไรงี้, um, you know… ถูกลบให้อัตโนมัติ |
| 🖥 **ใช้ได้ทุกแอป** | พิมพ์ลงช่องข้อความของแอปไหนก็ได้ที่เคอร์เซอร์อยู่ |
| 💸 **ฟรีตลอดไป** | ไม่มี subscription ไม่มีโควตา |

## 💻 ความต้องการของระบบ

- Mac ชิป **Apple Silicon** (M1 / M2 / M3 / M4)
- macOS 13 ขึ้นไป
- **Python 3.10+** จาก [python.org](https://www.python.org/downloads/) *(จำเป็นทั้งสองวิธีติดตั้ง)*
- อินเทอร์เน็ตครั้งแรก เพื่อดาวน์โหลดโมเดล (~1.5 GB) — หลังจากนั้นออฟไลน์ได้

---

## 📦 วิธีที่ 1: ติดตั้งด้วยตัวติดตั้ง (แนะนำ — ไม่ต้องใช้ Terminal)

1. ดาวน์โหลด **`FastWhisperFlow-Installer.zip`** จาก [**หน้า Releases**](../../releases/latest)
2. แตก zip แล้ว **คลิกขวา** ที่ `Install FastWhisper Flow.app` → **Open** → **Open**
   *(ต้องคลิกขวาครั้งแรก เพราะแอปไม่ได้เซ็นกับ Apple — เป็นปกติของแอปฟรี)*
3. กด **"ติดตั้ง"** แล้วรอโปรเกรส 4 ขั้นตอน (ขั้นดาวน์โหลดโมเดลนานสุด ~5 นาที)
4. เมื่อเสร็จ ระบบจะ**ก๊อปพาธ Python.app ให้ในคลิปบอร์ด** และเปิดหน้า System Settings ให้เอง
   → กด **+** → กด **⌘⇧G** → กด **⌘V** วางพาธ → Enter → เปิดสวิตช์ **ON**
5. เปิดแอปด้วย `FastWhisper Toggle.app` ในโฟลเดอร์ `~/FastWhisperFlow` → รอไอคอน 🎙 ใน menu bar
6. ทดลอง: คลิกช่องข้อความ → กด **Right ⌘** ค้าง → พูด → ปล่อย
   *(ครั้งแรก macOS จะถามสิทธิ์ Microphone และ System Events → กด **Allow** แล้วพูดใหม่อีกรอบ)*

## 🛠 วิธีที่ 2: ติดตั้งจากซอร์สโค้ด (สำหรับนักพัฒนา)

```bash
git clone https://github.com/JTIAPBNAI/fastwhisper.git
cd fastwhisper
./install.sh
```

`install.sh` จะสร้าง virtualenv, ติดตั้ง dependencies, ดาวน์โหลดโมเดล, และสร้าง
`FastWhisper Toggle.app` + launch agent ให้เอง จากนั้นทำตามขั้นตอนให้สิทธิ์ที่พิมพ์บอกตอนจบ
(เหมือนข้อ 4–6 ด้านบน)

รันแบบ manual: `./flow.sh start|stop|restart|status|mic|log`

---

## 🎛 วิธีใช้งาน

| ไอคอน menu bar | สถานะ |
|---|---|
| 🎙 | พร้อมใช้งาน — กด Right ⌘ ค้างเพื่อพูดได้เลย |
| 🔴 | กำลังอัดเสียง (ปล่อยปุ่มเมื่อพูดจบ) |
| ⏳ | กำลังถอดเสียง — **อย่าเพิ่งสลับแอป** ข้อความจะพิมพ์ลงแอปที่เปิดอยู่ |

**เคล็ดลับ:**
- พูดทีละ 1–3 ประโยคจะได้จังหวะลื่นที่สุด (พูดยาวได้ไม่จำกัด แต่รอนานขึ้นตามความยาว)
- ข้อความทุกครั้งถูกเก็บใน**คลิปบอร์ด**ด้วย — ถ้าพิมพ์ไม่ลง กด ⌘V ได้เลย
- เปิด/ปิดแอป: ดับเบิลคลิก `FastWhisper Toggle.app` (มี notification ยืนยัน)
- เปิดอัตโนมัติตอน login: `cp com.fastwhisper.flow.plist ~/Library/LaunchAgents/`

## ⚙️ ปรับแต่ง (แก้ที่หัวไฟล์ `flow.py` แล้ว restart)

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `MODEL` | Thonburian Thai | เปลี่ยนเป็น `mlx-community/whisper-large-v3-turbo` ถ้าเน้นอังกฤษ |
| `LANGUAGE` | `"th"` | `None` = ตรวจภาษาอัตโนมัติ |
| `HOTKEY` | `Key.cmd_r` | ปุ่มกดค้าง เช่น `Key.alt_r` = Right Option |
| `INPUT_DEVICE` | `None` | ล็อกไมค์ตัวใดตัวหนึ่ง เช่น `"MacBook Pro Microphone"` |

เพิ่ม/ลดคำฟุ่มเฟือยที่ถูกตัด: แก้ลิสต์ใน `cleanup.py`

## 🔧 แก้ปัญหา

| อาการ | วิธีแก้ |
|---|---|
| กดปุ่มแล้วไม่มีอะไรเกิดขึ้น | ต้องเป็น **Right ⌘** (ขวาของ spacebar) ไม่ใช่ปุ่มซ้าย และเช็คสิทธิ์ Accessibility ของ Python.app |
| ถอดเสียงได้แต่ไม่พิมพ์ | ข้อความอยู่ในคลิปบอร์ด (⌘V) — เช็คว่าไม่ได้สลับแอประหว่าง ⏳ และให้สิทธิ์ System Events แล้ว |
| ถอดออกมาเป็น "Thank you." | ไมค์ไม่ได้ยินเสียง → เช็คสิทธิ์ Microphone และระดับเสียงที่ System Settings → Sound → Input |
| อยากดู log | `tail -20 /tmp/fastwhisper-flow.log` หรือ `./flow.sh log` |

## 📄 License

MIT — ใช้ แก้ แจกต่อได้อิสระ

โมเดล: [Thonburian Whisper](https://huggingface.co/biodatlab/distill-whisper-th-large-v3) (biodatlab) แปลงเป็น MLX โดย [tawankri](https://huggingface.co/tawankri/distill-thonburian-whisper-large-v3-mlx)

---

<p align="center"><i>Powered by <b>JTIAPBN.Ai</b> — Whispering Weekends 🎙✨</i></p>
