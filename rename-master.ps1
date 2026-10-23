# Rename a master entry in a plugin's TES4 header (works for FO3/FNV/FO4 plugins; header is not compressed).
#   powershell -File .\rename-master.ps1 -Plugin <path.esm> -From FalloutNV.esm -To Fallout3.esm [-Out <path>]
# Used because the lab feeds Fallout3.esm to xConvert under the name FalloutNV.esm.
param(
  [Parameter(Mandatory)][string]$Plugin,
  [Parameter(Mandatory)][string]$From,
  [Parameter(Mandatory)][string]$To,
  [string]$Out = $Plugin
)
$ErrorActionPreference = 'Stop'
$enc = [Text.Encoding]::GetEncoding(28591)
$b = [IO.File]::ReadAllBytes((Resolve-Path $Plugin))
if ($enc.GetString($b, 0, 4) -ne 'TES4') { throw "$Plugin is not a plugin (no TES4 header)" }
$hdrSize = [BitConverter]::ToUInt32($b, 4)
$pos = 24; $end = 24 + $hdrSize
while ($pos -lt $end) {
  $sig = $enc.GetString($b, $pos, 4); $sz = [BitConverter]::ToUInt16($b, $pos + 4)
  if ($sig -eq 'MAST' -and $enc.GetString($b, $pos + 6, $sz).TrimEnd([char]0) -ieq $From) {
    $new = $enc.GetBytes("$To`0")
    $outBytes = New-Object Collections.Generic.List[byte]
    $outBytes.AddRange([byte[]]$b[0..($pos + 3)])
    $outBytes.AddRange([BitConverter]::GetBytes([uint16]$new.Length))
    $outBytes.AddRange($new)
    $outBytes.AddRange([byte[]]$b[($pos + 6 + $sz)..($b.Length - 1)])
    $arr = $outBytes.ToArray()
    [BitConverter]::GetBytes([uint32]($hdrSize + $new.Length - $sz)).CopyTo($arr, 4)
    [IO.File]::WriteAllBytes($Out, $arr)
    $m = [regex]::Matches($enc.GetString($arr, 0, [Math]::Min(4096, $arr.Length)), 'MAST..([^\x00]+)\x00') | ForEach-Object { $_.Groups[1].Value }
    "$([IO.Path]::GetFileName($Out)): masters = $($m -join ', ')"
    return
  }
  $pos += 6 + $sz
}
throw "Master $From not found in $Plugin"
