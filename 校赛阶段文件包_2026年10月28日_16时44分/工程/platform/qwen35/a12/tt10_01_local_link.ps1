$ErrorActionPreference = 'Stop'
$direct = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq '192.168.2.1' } | ForEach-Object {
    [pscustomobject]@{ InterfaceAlias = $_.InterfaceAlias; InterfaceIndex = $_.InterfaceIndex; Address = $_.IPAddress; PrefixLength = $_.PrefixLength; State = $_.AddressState.ToString() }
})
$neighbor = @(Get-NetNeighbor -AddressFamily IPv4 -IPAddress '192.168.2.2' -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{ InterfaceAlias = $_.InterfaceAlias; InterfaceIndex = $_.InterfaceIndex; Address = $_.IPAddress; MAC = $_.LinkLayerAddress; State = $_.State.ToString() }
})
$route = @(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '192.168.2.0/24' -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{ InterfaceAlias = $_.InterfaceAlias; InterfaceIndex = $_.InterfaceIndex; Prefix = $_.DestinationPrefix; NextHop = $_.NextHop; Metric = $_.RouteMetric }
})
$serial = @(Get-CimInstance Win32_SerialPort | ForEach-Object { [pscustomobject]@{ Port = $_.DeviceID; Name = $_.Name; PNPDeviceID = $_.PNPDeviceID } })
[pscustomobject]@{
    Scope = 'LOCAL_READ_ONLY_NO_NETWORK_OR_BOARD_MUTATION'
    ObservedUTC = [DateTime]::UtcNow.ToString('o')
    DirectAddress = $direct
    TargetNeighbor = $neighbor
    DirectRoute = $route
    SerialDevices = $serial
} | ConvertTo-Json -Depth 4
