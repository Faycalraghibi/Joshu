# PowerShell script to fix Joshu configuration
$configPath = "$env:USERPROFILE\.joshu\config.yaml"

if (Test-Path $configPath) {
    # Read the config file
    $configContent = Get-Content $configPath -Raw
    
    # Replace the model line
    $updatedContent = $configContent -replace "model: deepseek/deepseek-chat-v3.1:free", "model: openai/gpt-4o-mini"
    
    # Write back to the file
    $updatedContent | Set-Content $configPath
    
    Write-Host "Successfully updated model from 'deepseek/deepseek-chat-v3.1:free' to 'openai/gpt-4o-mini'"
} else {
    Write-Host "Config file not found at $configPath"
}