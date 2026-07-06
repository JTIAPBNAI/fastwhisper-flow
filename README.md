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
git clone https://github.com/JTIAPBNAI/fastwhisper-flow.git
cd fastwhisper-flow
./install.sh
```

`install.sh` จะสร้าง virtualenv, ติดตั้ง dependencies, ดาวน์โหลดโมเดล, และสร้าง
`FastWhisper Toggle.app` ให้เอง จากนั้นทำตามขั้นตอนให้สิทธิ์ที่พิมพ์บอกตอนจบ
(เหมือนข้อ 4–6 ด้านบน)

รันแบบ manual: `./flow.sh start|stop|restart|status|mic|log`
เริ่มแอปหลังติดตั้งด้วย `FastWhisper Toggle.app` เท่านั้น แอปจะไม่เริ่มเองทันทีหลังติดตั้งหรือหลัง login

---

## 🎛 วิธีใช้งาน

| ไอคอน menu bar | สถานะ |
|---|---|
| 🎙 | พร้อมใช้งาน — กด Right ⌘ ค้างเพื่อพูดได้เลย |
| 🔴 | กำลังอัดเสียง — โหมดไทย (ปล่อยปุ่มเมื่อพูดจบ) |
| 🔵 | กำลังอัดเสียง — โหมด English/auto-detect (Right ⌘ + Option) |
| 🟢 | กำลังอัดเสียงจากระบบ (Right ⌘ + Shift) |
| ⏳ | กำลังถอดเสียง — **อย่าเพิ่งสลับแอป** ข้อความจะพิมพ์ลงแอปที่เปิดอยู่ |

**เคล็ดลับ:**
- พูดทีละ 1–3 ประโยคจะได้จังหวะลื่นที่สุด (พูดยาวได้ไม่จำกัด แต่รอนานขึ้นตามความยาว)
- จะพูด**อังกฤษล้วนหรือปนอังกฤษเยอะ ๆ**: กด **Right ⌘ + Option** ค้าง — ใช้โมเดล multilingual ตรวจภาษาอัตโนมัติ (โหมดปกติยังล็อกไทยเพื่อความแม่นยำสูงสุด)
- ข้อความทุกครั้งถูกเก็บใน**คลิปบอร์ด**ด้วย — ถ้าพิมพ์ไม่ลง กด ⌘V ได้เลย
- เปิด/ปิดแอป: ดับเบิลคลิก `FastWhisper Toggle.app` (มี notification ยืนยัน)
- ดูสถานะใน menu bar ได้ทันที: Hotkey, Microphone, Accessibility, Input, Model
- แก้ปัญหาเบื้องต้นจาก menu bar ได้: `Restart Listener`, `Test Mic`, `Open Log`
- อัปเดตจาก menu bar ได้: `Check Update` จะดาวน์โหลด release ล่าสุด แล้วอัปเดตเฉพาะไฟล์แอปโดยไม่ลง `.venv` หรือโมเดลใหม่
- รีเซ็ตสิทธิ์เพื่อทดสอบติดตั้งใหม่: `./reset-permissions.sh`

## ⚙️ ปรับแต่ง (แก้ที่หัวไฟล์ `flow.py` แล้ว restart)

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `MODEL` | Thonburian Thai | เปลี่ยนเป็น `mlx-community/whisper-large-v3-turbo` ถ้าเน้นอังกฤษ |
| `LANGUAGE` | `"th"` | `None` = ตรวจภาษาอัตโนมัติ |
| `HOTKEY` | `Key.cmd_r` | ปุ่มกดค้าง เช่น `Key.alt_r` = Right Option |
| `INPUT_DEVICE` | `None` | ล็อกไมค์ตัวใดตัวหนึ่ง เช่น `"MacBook Pro Microphone"` |
| `LOOPBACK_DEVICE` | `"BlackHole 2ch"` | อุปกรณ์สำหรับจับเสียงจากระบบ (Right ⌘ + Shift) |
| `LOOPBACK_MODEL` | `whisper-large-v3-turbo` | โมเดล multilingual สำหรับเสียงระบบ (โมเดลไทยจะเดาเป็นไทยหมด) |
| `LOOPBACK_LANGUAGE` | `None` | ตรวจภาษาอัตโนมัติในโหมดเสียงระบบ — ใส่ `"en"`/`"th"` เพื่อล็อก |

เพิ่ม/ลดคำฟุ่มเฟือยที่ถูกตัด: แก้ลิสต์ใน `cleanup.py`

## 🛠 สำหรับผู้พัฒนา — ออก release ใหม่

1. แก้โค้ด → commit → push `main`
2. รัน `./build-installer.sh` — อัปเดต payload ใน `Installer File/FastWhisperFlow-Installer.zip` ให้เป็นโค้ดล่าสุด + re-sign อัตโนมัติ
3. `gh release create vX.Y.Z "Installer File/FastWhisperFlow-Installer.zip" --title "..." --notes "..."`

> ⚠️ **ห้ามลบ** `Installer File/FastWhisperFlow-Installer.zip` — ตัว `Install FastWhisper Flow.app` (ไอคอน + สคริปต์ติดตั้ง) มีอยู่แค่ใน zip นี้และไม่ได้อยู่ใน git (ถูก ignore) สคริปต์ build ต้องใช้เป็นแม่แบบ

## 🔊 ถอดเสียงจากระบบ (Right ⌘ + Shift)

กด **Right ⌘ + Shift** ค้าง = ถอดเสียงที่ Mac กำลังเล่นอยู่ (วิดีโอ YouTube, คอล, พอดแคสต์ ฯลฯ) แทนไมค์
โหมดนี้ใช้โมเดล multilingual (`whisper-large-v3-turbo`) และ**ตรวจภาษาอัตโนมัติ** — เนื้อหาอังกฤษได้อังกฤษ ไทยได้ไทย

### ขั้นที่ 1 — ติดตั้ง BlackHole (ครั้งเดียว)

```bash
brew install blackhole-2ch
```

หรือดาวน์โหลดจาก [existential.audio/blackhole](https://existential.audio/blackhole/) — เป็น audio driver จึงต้องใส่รหัสผ่านเครื่อง

### ขั้นที่ 2 — สร้าง Multi-Output Device (ครั้งเดียว)

BlackHole เป็น "ลำโพงเสมือน" — ถ้าส่งเสียงเข้า BlackHole ตรง ๆ จะจับเสียงได้แต่**หูจะไม่ได้ยิน**
จึงต้องสร้างอุปกรณ์ที่ส่งเสียงออก 2 ทางพร้อมกัน (ลำโพงจริง + BlackHole):

1. เปิดแอป **Audio MIDI Setup** (กด ⌘Space พิมพ์ "Audio MIDI")
2. กดปุ่ม **+** มุมล่างซ้าย → เลือก **Create Multi-Output Device**
3. ในรายการด้านขวา ติ๊ก **Use** ให้ 2 ตัว:
   - ✅ ลำโพงที่ใช้จริง (เช่น MacBook Pro Speakers หรือจอ/หูฟัง)
   - ✅ **BlackHole 2ch**
4. (แนะนำ) ติ๊ก **Drift Correction** ให้ BlackHole 2ch เพื่อกันเสียงเพี้ยน

### ขั้นที่ 3 — ตั้งเป็น Sound Output

**System Settings → Sound → Output** → เลือก **Multi-Output Device**
(หรือคลิกไอคอนลำโพงบน menu bar) — ยังได้ยินเสียงตามปกติ แต่เสียงจะไหลเข้า BlackHole ด้วย

จากนั้นทดลอง: เปิดวิดีโอ → กด **Right ⌘ + Shift** ค้าง → ปล่อย → ข้อความพิมพ์ให้เหมือนโหมดไมค์

### ข้อควรรู้ / แก้ปัญหา

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| ปุ่มปรับเสียงบนคีย์บอร์ดใช้ไม่ได้ | ข้อจำกัดของ Multi-Output Device — ปรับเสียงในตัวแอป หรือใน Audio MIDI Setup แทน |
| เห็น ⚠️ ที่ menu bar หลังปล่อยปุ่ม | ไม่มีเสียงเข้า BlackHole — เช็คว่า Sound Output เป็น Multi-Output Device อยู่ (ขั้นที่ 3) |
| ได้ข้อความมั่ว ๆ ซ้ำ ๆ เช่น "nenenene" | อัดได้แต่ความเงียบ — สาเหตุเดียวกับข้อบน |
| ไม่ได้ติดตั้ง BlackHole | โหมดไมค์ (Right ⌘) ยังใช้ได้ปกติ — โหมดระบบจะขึ้น ⚠️ เฉย ๆ |
| อยากกลับไปใช้ลำโพงตรง ๆ | เปลี่ยน Sound Output กลับเป็นลำโพงเดิม (โหมดระบบจะใช้ไม่ได้จนกว่าจะสลับกลับ) |

> เคล็ดลับ: ติดตั้ง `brew install switchaudio-osx` แล้วสลับ output จาก terminal ได้เลย:
> `SwitchAudioSource -t output -s "Multi-Output Device"` ↔ `SwitchAudioSource -t output -s "MacBook Pro Speakers"`

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
