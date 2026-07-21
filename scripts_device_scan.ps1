# Per-device scan of d:\Uni-Lab-OS\unilabos\devices (community + core)
# Extract: name/manufacturer/tags/conn/framework/probe_cmd/actions/verdict -> CSV

$ErrorActionPreference = 'SilentlyContinue'
$dev = "d:\Uni-Lab-OS\unilabos\devices"
$com = Join-Path $dev "community"
$out = "d:\Uni-Lab\Uni-Lab-OS\device_scan_report_v2.csv"

$rows = New-Object System.Collections.Generic.List[object]

function Classify($t) {
    $conn = "UNKNOWN"; $framework = ""
    # 第一层: 直接通信信号
    if ($t -match '(?i)(MessageBasedDriver|pyvisa|::INSTR|from lantz|import lantz)') { $conn = "VISA_SCPI"; $framework = "lantz/VISA" }
    elseif ($t -match '(?i)(import serial|serial\.Serial|pyserial|baudrate|RS-?232|RS-?485)') { $conn = "SERIAL"; $framework = "pyserial" }
    elseif ($t -match '(?i)(pymodbus|minimalmodbus|modbus_tk|import modbus)') { $conn = "MODBUS"; $framework = "modbus" }
    elseif ($t -match '(?i)(socket\.socket|TCPIP|from_hostname|TcpInstrument|import socket)') { $conn = "TCP"; $framework = "socket" }
    else {
        # 第二层: 上游框架根模块推断 (读 import 根)
        $roots = @{}
        foreach ($m in [regex]::Matches($t, '(?m)^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)')) { $roots[$m.Groups[1].Value] = $true }
        $has = { param($k) $roots.ContainsKey($k) }
        if ((& $has 'instruments') -or (& $has 'qcodes') -or (& $has 'pymeasure') -or (& $has 'labtoolkit') -or (& $has 'oscope_scpi') -or (& $has 'RsInstrument') -or (& $has 'msox3000') -or (& $has 'tinyscpi') -or (& $has 'curvequery') -or (& $has 'labdrivers')) { $conn = "VISA_SCPI"; $framework = "scpi-framework" }
        elseif ((& $has 'pyModbusTCP') -or (& $has 'snap7')) { $conn = "MODBUS"; $framework = "modbus-tcp" }
        elseif ((& $has 'epics') -or (& $has 'epicsscan') -or (& $has 'vxi11') -or (& $has 'twisted') -or (& $has 'telnetlib') -or (& $has 'nanonisTCP') -or (& $has 'pylontech')) { $conn = "TCP"; $framework = "network-framework" }
        elseif ((& $has 'seabreeze') -or (& $has 'wasatch') -or (& $has 'genicam') -or (& $has 'harvesters') -or (& $has 'cv2') -or (& $has 'PySpin') -or (& $has 'pyueye')) { $conn = "USB_SDK"; $framework = "camera/spectro-sdk" }
        elseif ((& $has 'usb') -or (& $has 'pyusb') -or (& $has 'ctypes') -or (& $has 'ftd2xx') -or (& $has 'pyftdi') -or (& $has 'usbtmc')) { $conn = "USB_SDK"; $framework = "usb/dll" }
        elseif ((& $has 'nidaqmx') -or (& $has 'gpiozero') -or (& $has 'RPi')) { $conn = "DAQ_GPIO"; $framework = "daq/gpio" }
        elseif ((& $has 'pylabrobot') -or (& $has 'xarm') -or (& $has 'mecademicpy') -or (& $has 'rtde') -or (& $has 'unitree') -or (& $has 'robotiq') -or (& $has 'rclpy')) { $conn = "ROBOT"; $framework = "robot/ros-sdk" }
        elseif ((& $has 'requests') -or (& $has 'tornado') -or (& $has 'paramiko') -or (& $has 'pylogix') -or (& $has 'ophyd') -or (& $has 'pcdsdevices') -or (& $has 'qslib')) { $conn = "TCP"; $framework = "network/rest" }
        elseif ((& $has 'pywinauto') -or (& $has 'clr') -or (& $has 'win32com')) { $conn = "SW_AUTO"; $framework = "windows-sw-automation" }
    }

    $probe = ''
    if ($t -match '\*IDN\?') { $probe = '*IDN?' }
    elseif ($t -match '(?i)(?:query|ask|write)\(\s*[''"]([^''"]*\?[^''"]*)[''"]') { $probe = $Matches[1] }
    elseif ($t -match '(?i)(?:query|ask)\(\s*[''"]([^''"]{1,24})[''"]') { $probe = $Matches[1] }

    return @{ conn = $conn; framework = $framework; probe = $probe }
}

function Verdict($conn, $probe) {
    if ($conn -eq "SERIAL" -and $probe -ne "") { return "T1_serial_probe_ready" }
    if ($conn -eq "SERIAL") { return "T1b_serial_probe_tbd" }
    if ($conn -eq "VISA_SCPI") { return "T2_visa_needs_rs232_idn" }
    if ($conn -eq "MODBUS") { return "T2m_modbus_probeable" }
    if ($conn -eq "TCP") { return "T3_network_needs_ext" }
    if ($conn -eq "USB_SDK") { return "T3u_usb_sdk_not_serial" }
    if ($conn -eq "DAQ_GPIO") { return "T3d_daq_gpio_local" }
    if ($conn -eq "ROBOT") { return "T3r_robot_sdk" }
    if ($conn -eq "SW_AUTO") { return "T3s_sw_automation" }
    return "T4_manual_review"
}

# ---- community ----
foreach ($d in (Get-ChildItem -LiteralPath $com -Directory)) {
    $drv = Join-Path $d.FullName "driver.py"
    if (-not (Test-Path $drv)) { continue }
    $t = Get-Content -LiteralPath $drv -Raw -Encoding UTF8
    $ry = Join-Path $d.FullName "registry.yaml"
    $reg = ""; if (Test-Path $ry) { $reg = Get-Content -LiteralPath $ry -Raw -Encoding UTF8 }

    $name = $d.Name; $manu = ""; $tags = ""; $nActions = 0
    if ($reg) {
        # 只吃同行空格(不能用 \s*, 因 .NET \s 含换行会误捕下一行的 type: string)
        # 去掉外层引号; 若为空(如 name: '')则回退文件夹名
        if ($reg -match '(?m)^[^\S\r\n]*name:[^\S\r\n]*(\S.*)$') { $cand = $Matches[1].Trim().Trim("'`""); if ($cand -ne '') { $name = $cand } }
        if ($reg -match '(?m)^[^\S\r\n]*manufacturer:[^\S\r\n]*(\S.*)$') { $manu = $Matches[1].Trim().Trim("'`"") }
        $nActions = ([regex]::Matches($reg, '(?m)^\s{6}auto-[\w-]+:')).Count
    }
    $c = Classify $t
    $rows.Add([pscustomobject]@{
        source="community"; folder=$d.Name; name=$name; manufacturer=$manu;
        conn=$c.conn; framework=$c.framework; probe_cmd=$c.probe; actions=$nActions; verdict=(Verdict $c.conn $c.probe)
    })
}

# ---- core ----
$coreFiles = Get-ChildItem -LiteralPath $dev -Recurse -Filter *.py -File |
    Where-Object { $_.FullName -notmatch '__pycache__' -and $_.FullName -notmatch '\\community\\' -and $_.Name -ne '__init__.py' }
foreach ($f in $coreFiles) {
    $t = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8
    if ($null -eq $t) { continue }
    if ($t -notmatch '(?m)^\s*class\s') { continue }
    $c = Classify $t
    $rel = $f.FullName.Substring($dev.Length + 1) -replace '\\','/'
    $rows.Add([pscustomobject]@{
        source="core"; folder=$rel; name=$f.BaseName; manufacturer="";
        conn=$c.conn; framework=$c.framework; probe_cmd=$c.probe; actions=0; verdict=(Verdict $c.conn $c.probe)
    })
}

$rows | Export-Csv -LiteralPath $out -NoTypeInformation -Encoding UTF8
"total_rows: " + $rows.Count
""
"== by verdict =="
$rows | Group-Object verdict | Sort-Object Count -Descending | ForEach-Object { "{0,6}  {1}" -f $_.Count, $_.Name }
""
"== by conn =="
$rows | Group-Object conn | Sort-Object Count -Descending | ForEach-Object { "{0,6}  {1}" -f $_.Count, $_.Name }
""
"== by source =="
$rows | Group-Object source | ForEach-Object { "{0,6}  {1}" -f $_.Count, $_.Name }
"csv: $out"
