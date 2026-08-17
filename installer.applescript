set payload to «event sysoexec» "applet=$(ps -p $PPID -o comm=); payload=$(cd \"$(dirname \"$applet\")/../Resources/payload\" && pwd -P); printf %s \"$payload/\""
set installDir to («event sysoexec» "printf %s $HOME") & "/FastWhisperFlow"
set tq to quoted form of installDir
set appVersion to "__APP_VERSION__"

«event sysodlog» "ติดตั้ง FastWhisper Flow v" & appVersion & " — พิมพ์ด้วยเสียงภาษาไทย ฟรี ทำงานในเครื่อง 100%" & return & return & "จะติดตั้งลงที่: " & installDir & return & "ใช้เวลา 5-10 นาที (ติดตั้ง Python 3.13 อัตโนมัติถ้าจำเป็น และดาวน์โหลดโมเดล ~1.5GB)" given «class btns»:{"ยกเลิก", "ติดตั้ง"}, «class dflt»:"ติดตั้ง", «class appr»:"FastWhisper Flow"
if «class bhit» of result is not "ติดตั้ง" then return

set progress total steps to 4
set progress description to "กำลังติดตั้ง FastWhisper Flow v" & appVersion & "…"
try
	set progress completed steps to 0
	set progress additional description to "ขั้นที่ 1/4: คัดลอกไฟล์โปรแกรม…"
	«event sysoexec» "mkdir -p " & tq & " && cp " & quoted form of payload & "* " & tq & "/ && cd " & tq & " && chmod +x install.sh flow.sh reset-permissions.sh"
	
	set progress completed steps to 1
	set progress additional description to "ขั้นที่ 2/4: ตรวจสอบ Python 3.13 และติดตั้งไลบรารี… (~1-3 นาที)"
	«event sysoexec» "cd " & tq & " && ./install.sh deps > /tmp/fastwhisper-install.log 2>&1"
	
	set progress completed steps to 2
	set progress additional description to "ขั้นที่ 3/4: ดาวน์โหลดโมเดลภาษาไทย ~1.5GB… (นานสุดในทุกขั้น)"
	«event sysoexec» "cd " & tq & " && ./install.sh model >> /tmp/fastwhisper-install.log 2>&1"
	
	set progress completed steps to 3
	set progress additional description to "ขั้นที่ 4/4: สร้างแอปเปิด-ปิดและตั้งค่า…"
	«event sysoexec» "cd " & tq & " && ./install.sh apps >> /tmp/fastwhisper-install.log 2>&1"
	set progress completed steps to 4
	
	set pyapp to «event sysoexec» "cd " & tq & " && .venv/bin/python -c \"import sys,os;p=os.path.join(sys.base_prefix,chr(82)+chr(101)+chr(115)+chr(111)+chr(117)+chr(114)+chr(99)+chr(101)+chr(115),chr(80)+chr(121)+chr(116)+chr(104)+chr(111)+chr(110)+chr(46)+chr(97)+chr(112)+chr(112));print(p if os.path.exists(p) else sys.base_prefix)\""
	«event sysodlog» "✅ ติดตั้ง FastWhisper Flow v" & appVersion & " พร้อม Python 3.13 และไลบรารีทั้งหมดแล้ว!" & return & return & "กดปุ่มด้านล่างเพื่อเปิด FastWhisper Toggle.app ระบบจะลงทะเบียน Python.app และเปิดหน้า Accessibility ให้" & return & return & "เมื่อ macOS ถาม ให้เปิดสิทธิ์ Python.app (FastWhisper Toggle.app ไม่จำเป็นต้องอยู่ในรายการ Accessibility)" & return & return & "หาก Python.app ไม่ขึ้นอัตโนมัติ: กด + → ⌘⇧G → วางพาธที่คัดลอกไว้:" & return & pyapp given «class btns»:{"เปิดแอป + ตั้งค่าสิทธิ์"}, «class dflt»:1, «class appr»:"FastWhisper Flow"
	«event JonspClp» pyapp
	«event sysoexec» "open " & quoted form of (installDir & "/FastWhisper Toggle.app") & " && sleep 2 && open \"x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility\" && open " & tq
on error errMsg
	«event sysodlog» "❌ ติดตั้งไม่สำเร็จ: " & errMsg & return & return & "ดูรายละเอียดใน /tmp/fastwhisper-install.log" given «class btns»:{"ปิด"}, «class appr»:"FastWhisper Flow"
end try
