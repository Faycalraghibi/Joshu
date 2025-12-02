# PowerShell script to fix Joshu configuration to use GLM model
$configPath = "$env:USERPROFILE\.joshu\config.yaml"

if (Test-Path $configPath) {
    # Read the config file
    $configContent = Get-Content $configPath -Raw

    # Replace the model line with the GLM model
    $updatedContent = $configContent -replace "model: .*", "model: z-ai/glm-4.5-air:free"

    # Write back to the file
    $updatedContent | Set-Content $configPath

    Write-Host "Successfully updated model to 'z-ai/glm-4.5-air:free'"
} else {
    Write-Host "Config file not found at $configPath"
}
