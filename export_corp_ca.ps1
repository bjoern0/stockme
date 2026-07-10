$patterns = @('netskope', 'corpintra', 'Daimler', 'Mercedes-Benz', 'MB-CA01', 'mic root ca')
$outFile = "$PSScriptRoot\corp_ca_bundle.pem"
if (Test-Path $outFile) { Remove-Item $outFile }

$certs = Get-ChildItem -Path Cert:\LocalMachine\Root, Cert:\CurrentUser\Root
$seen = @{}
foreach ($c in $certs) {
    $match = $false
    foreach ($p in $patterns) {
        if ($c.Subject -like "*$p*") { $match = $true }
    }
    if ($match -and -not $seen.ContainsKey($c.Thumbprint)) {
        $seen[$c.Thumbprint] = $true
        $b64 = [System.Convert]::ToBase64String($c.RawData, [System.Base64FormattingOptions]::InsertLineBreaks)
        Add-Content -Path $outFile -Value "# $($c.Subject)"
        Add-Content -Path $outFile -Value "-----BEGIN CERTIFICATE-----"
        Add-Content -Path $outFile -Value $b64
        Add-Content -Path $outFile -Value "-----END CERTIFICATE-----"
    }
}
Write-Output "Exportiert nach $outFile, $($seen.Count) Zertifikate"
