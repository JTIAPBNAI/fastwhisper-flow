set payload to «event sysoexec» "applet=$(ps -p $PPID -o comm=); payload=$(cd \"$(dirname \"$applet\")/../Resources/payload\" && pwd -P); printf %s \"$payload/\""
set installDir to («event sysoexec» "printf %s $HOME") & "/FastWhisperFlow"
set tq to quoted form of installDir
set appVersion to "__APP_VERSION__"

«event sysodlog» "ติดตั้ง FastWhisper Flow v" & appVersion & " — พิมพ์ด้วยเสียงภาษาไทย ฟรี ทำงานในเครื่อง 100%" & return & return & "จะติดตั้งลงที่: " & installDir & return & "ใช้เวลา 5-10 นาที (ดาวน์โหลดโมเดล ~1.5GB)" given «class btns»:{"ยกเลิก", "ติดตั้ง"}, «class dflt»:"ติดตั้ง", «class appr»:"FastWhisper Flow"
if «class bhit» of result is not "ติดตั้ง" then return

set progress total steps to 4
set progress description to "กำลังติดตั้ง FastWhisper Flow v" & appVersion & "…"
try
	set progress completed steps to 0
	set progress additional description to "ขั้นที่ 1/4: คัดลอกไฟล์โปรแกรม…"
	«event sysoexec» "mkdir -p " & tq & " && cp " & quoted form of payload & "* " & tq & "/ && cd " & tq & " && chmod +x install.sh flow.sh reset-permissions.sh"
	
	set progress completed steps to 1
	set progress additional description to "ขั้นที่ 2/4: ติดตั้งไลบรารี Python… (~1-2 นาที)"
	«event sysoexec» "cd " & tq & " && ./install.sh deps > /tmp/fastwhisper-install.log 2>&1"
	
	set progress completed steps to 2
	set progress additional description to "ขั้นที่ 3/4: ดาวน์โหลดโมเดลภาษาไทย ~1.5GB… (นานสุดในทุกขั้น)"
	«event sysoexec» "cd " & tq & " && ./install.sh model >> /tmp/fastwhisper-install.log 2>&1"
	
	set progress completed steps to 3
	set progress additional description to "ขั้นที่ 4/4: สร้างแอปเปิด-ปิดและตั้งค่า…"
	«event sysoexec» "cd " & tq & " && ./install.sh apps >> /tmp/fastwhisper-install.log 2>&1"
	set progress completed steps to 4
	
	set pyapp to «event sysoexec» "cd " & tq & " && .venv/bin/python -c \"import sys,os;p=os.path.join(sys.base_prefix,chr(82)+chr(101)+chr(115)+chr(111)+chr(117)+chr(114)+chr(99)+chr(101)+chr(115),chr(80)+chr(121)+chr(116)+chr(104)+chr(111)+chr(110)+chr(46)+chr(97)+chr(112)+chr(112));print(p if os.path.exists(p) else sys.base_prefix)\""
	«event sysodlog» "✅ ติดตั้ง FastWhisper Flow v" & appVersion & " เสร็จแล้ว!" & return & return & "เหลือขั้นตอนที่ macOS บังคับให้ทำเอง 1 ครั้ง:" & return & return & "1. System Settings → Privacy & Security → Accessibility → กด + → กด ⌘⇧G → วางพาธนี้:" & return & pyapp & return & return & "2. เปิดแอปด้วย FastWhisper Toggle.app ในโฟลเดอร์ที่จะเปิดให้" & return & "3. กด Right ⌘ ค้างแล้วพูด — กด Allow เมื่อถูกถามสิทธิ์" given «class btns»:{"คัดลอกพาธ + เปิดโฟลเดอร์"}, «class dflt»:1, «class appr»:"FastWhisper Flow"
	«event JonspClp» pyapp
	«event sysoexec» "open " & tq & " && open \"x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility\""
on error errMsg
	«event sysodlog» "❌ ติดตั้งไม่สำเร็จ: " & errMsg & return & return & "ดูรายละเอียดใน /tmp/fastwhisper-install.log" given «class btns»:{"ปิด"}, «class appr»:"FastWhisper Flow"
end try
