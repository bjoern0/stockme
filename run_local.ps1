# Lokaler Testlauf. Setzt automatisch die Corporate-CA-Bundle-Umgebungsvariablen,
# falls combined_ca_bundle.pem existiert (siehe README "SSL in Firmennetzwerken").
$bundle = Join-Path $PSScriptRoot "combined_ca_bundle.pem"
if (Test-Path $bundle) {
    $env:CURL_CA_BUNDLE = $bundle
    $env:REQUESTS_CA_BUNDLE = $bundle
    $env:SSL_CERT_FILE = $bundle
    Write-Output "Nutze Corporate-CA-Bundle: $bundle"
}
& "$PSScriptRoot\.venv\Scripts\python.exe" -m src.main
