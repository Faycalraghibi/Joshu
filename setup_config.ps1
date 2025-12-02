# PowerShell script to configure Joshu .env file with a menu interface

# Function to read .env file
function Get-EnvConfig {
    param(
        [string]$Path = ".env"
    )

    # Check if .env file exists in current directory
    if (-not (Test-Path $Path)) {
        Write-Host "Warning: .env file not found at $Path" -ForegroundColor Yellow
        Write-Host "Creating a new .env file with default values..." -ForegroundColor Yellow
        # Create a minimal .env file
        "# Joshu Configuration File" | Out-File $Path -Encoding UTF8
        "OPENROUTER_MODEL=z-ai/glm-4.5-air:free" | Out-File $Path -Encoding UTF8 -Append
        "GLM_Identifier=z-ai/glm-4.5-air:free" | Out-File $Path -Encoding UTF8 -Append
        "DEEPSEEK_Identifier=deepseek/deepseek-chat-v3.1:free" | Out-File $Path -Encoding UTF8 -Append
        "TONGYI_Identifier=alibaba/tongyi-deepresearch-30b-a3b:free" | Out-File $Path -Encoding UTF8 -Append
        "QWEN_Identifier=qwen/qwen3-coder:free" | Out-File $Path -Encoding UTF8 -Append
        "KIMI_DEV_Identifier=moonshotai/kimi-dev-72b:free" | Out-File $Path -Encoding UTF8 -Append
        "AGENTICAT_Identifier=agentica-org/deepcoder-14b-preview:free" | Out-File $Path -Encoding UTF8 -Append
        "GEMMA_Identifier=google/gemma-3-27b-it:free" | Out-File $Path -Encoding UTF8 -Append
        "LLAMA_CPP_MODEL_LLAMA3_8B=/path/to/llama-3-8b.gguf" | Out-File $Path -Encoding UTF8 -Append
        "LLAMA_CPP_MODEL_MISTRAL_7B=/path/to/mistral-7b.gguf" | Out-File $Path -Encoding UTF8 -Append
    }

    $config = @{}
    $content = Get-Content $Path
    foreach ($line in $content) {
        if ($line -match '^\s*([^#][^=]*)\s*=\s*(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            if ($value -match '^["](.*)["]$' -or $value -match "^['](.*)['`]$") {
                $value = $matches[1]
            }
            $config[$key] = $value
        }
    }
    return $config
}

# Function to update .env file
function Set-EnvConfig {
    param(
        [hashtable]$Config,
        [string]$Path = ".env"
    )

    if (-not (Test-Path $Path)) {
        Write-Host "Error: .env file not found at $Path" -ForegroundColor Red
        return
    }

    $content = Get-Content $Path
    $newContent = @()
    $processedKeys = @()

    foreach ($line in $content) {
        if ($line -match '^\s*([^#][^=]*)\s*=\s*(.*)$') {
            $key = $matches[1].Trim()
            if ($Config.ContainsKey($key)) {
                $value = $Config[$key]
                # Add quotes if value contains spaces or special characters
                if ($value -match '\s' -or $value -match '[^a-zA-Z0-9_\-\.:/]') {
                    if ($value -notmatch '^["]' -and $value -notmatch "^['`"]") {
                        $value = "`"$value`""
                    }
                }
                $newContent += "$key=$value"
                $processedKeys += $key
                continue
            }
        }
        $newContent += $line
    }

    # Add any new keys that weren't in the original file
    foreach ($key in $Config.Keys) {
        if ($processedKeys -notcontains $key) {
            $value = $Config[$key]
            # Add quotes if value contains spaces or special characters
            if ($value -match '\s' -or $value -match '[^a-zA-Z0-9_\-\.:/]') {
                if ($value -notmatch '^["]' -and $value -notmatch "^['`"]") {
                    $value = "`"$value`""
                }
            }
            $newContent += "$key=$value"
        }
    }

    $newContent | Set-Content $Path
    Write-Host "Configuration updated successfully!" -ForegroundColor Green
}

# Function to update user config.yaml file
function Set-UserConfig {
    param(
        [string]$ModelIdentifier
    )

    $configPath = "$env:USERPROFILE\.joshu\config.yaml"

    # Ensure the .joshu directory exists
    $joshuDir = "$env:USERPROFILE\.joshu"
    if (-not (Test-Path $joshuDir)) {
        New-Item -ItemType Directory -Path $joshuDir | Out-Null
    }

    if (Test-Path $configPath) {
        # Read the config file
        $configContent = Get-Content $configPath -Raw

        # Check if the file has content
        if ([string]::IsNullOrWhiteSpace($configContent)) {
            # Create default config content
            "model: $ModelIdentifier" | Out-File $configPath -Encoding UTF8
        } else {
            # Replace the model line with the new model
            $updatedContent = $configContent -replace "model: .*", "model: $ModelIdentifier"

            # If no model line was found, add it
            if ($updatedContent -eq $configContent) {
                $updatedContent += "`nmodel: $ModelIdentifier"
            }

            # Write back to the file
            $updatedContent | Set-Content $configPath
        }
    } else {
        # Create the config file with the model
        "model: $ModelIdentifier" | Out-File $configPath -Encoding UTF8
    }

    Write-Host "User config file updated successfully!" -ForegroundColor Green
}

# Function to display menu
function Show-Menu {
    param(
        [hashtable]$Config
    )

    Write-Host "`n=== Joshu Model Selection Menu ===" -ForegroundColor Cyan
    Write-Host "Select a model to set as current:" -ForegroundColor Yellow
    Write-Host "1. DEEPSEEK: $($Config['DEEPSEEK_Identifier'])" -ForegroundColor Gray
    Write-Host "2. TONGYI: $($Config['TONGYI_Identifier'])" -ForegroundColor Gray
    Write-Host "3. QWEN: $($Config['QWEN_Identifier'])" -ForegroundColor Gray
    Write-Host "4. KIMI_DEV: $($Config['KIMI_DEV_Identifier'])" -ForegroundColor Gray
    Write-Host "5. AGENTICAT: $($Config['AGENTICAT_Identifier'])" -ForegroundColor Gray
    Write-Host "6. GEMMA: $($Config['GEMMA_Identifier'])" -ForegroundColor Gray
    Write-Host "7. GLM: $($Config['GLM_Identifier'])" -ForegroundColor Gray
    Write-Host "8. LLAMA_CPP_MODEL_LLAMA3_8B: $($Config['LLAMA_CPP_MODEL_LLAMA3_8B'])" -ForegroundColor Gray
    Write-Host "9. LLAMA_CPP_MODEL_MISTRAL_7B: $($Config['LLAMA_CPP_MODEL_MISTRAL_7B'])" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Current model: $($Config['OPENROUTER_MODEL'])" -ForegroundColor Green
    Write-Host ""
    Write-Host "0. Exit" -ForegroundColor Yellow
    Write-Host "===============================" -ForegroundColor Cyan
}

# Function to get identifier key by option
function Get-IdentifierKey {
    param(
        [int]$Option
    )

    switch ($Option) {
        1 { return "DEEPSEEK_Identifier" }
        2 { return "TONGYI_Identifier" }
        3 { return "QWEN_Identifier" }
        4 { return "KIMI_DEV_Identifier" }
        5 { return "AGENTICAT_Identifier" }
        6 { return "GEMMA_Identifier" }
        7 { return "GLM_Identifier" }
        8 { return "LLAMA_CPP_MODEL_LLAMA3_8B" }
        9 { return "LLAMA_CPP_MODEL_MISTRAL_7B" }
    }
    return $null
}

# Function to get display name by option
function Get-DisplayName {
    param(
        [int]$Option
    )

    switch ($Option) {
        1 { return "DEEPSEEK" }
        2 { return "TONGYI" }
        3 { return "QWEN" }
        4 { return "KIMI_DEV" }
        5 { return "AGENTICAT" }
        6 { return "GEMMA" }
        7 { return "GLM" }
        8 { return "LLAMA_CPP_MODEL_LLAMA3_8B" }
        9 { return "LLAMA_CPP_MODEL_MISTRAL_7B" }
    }
    return $null
}

# Function to get model identifier by option
function Get-ModelIdentifier {
    param(
        [int]$Option,
        [hashtable]$Config
    )

    $identifierKey = Get-IdentifierKey -Option $Option
    if ($identifierKey -and $Config.ContainsKey($identifierKey)) {
        return $Config[$identifierKey]
    }
    return $null
}

# Main script
try {
    Write-Host "Loading Joshu configuration..." -ForegroundColor Cyan

    # Load current configuration
    $config = Get-EnvConfig

    if ($config.Count -eq 0) {
        Write-Host "No configuration found. Creating default configuration..." -ForegroundColor Yellow
        $config = @{
            "OPENROUTER_MODEL" = "z-ai/glm-4.5-air:free"
            "GLM_Identifier" = "z-ai/glm-4.5-air:free"
            "DEEPSEEK_Identifier" = "deepseek/deepseek-chat-v3.1:free"
            "TONGYI_Identifier" = "alibaba/tongyi-deepresearch-30b-a3b:free"
            "QWEN_Identifier" = "qwen/qwen3-coder:free"
            "KIMI_DEV_Identifier" = "moonshotai/kimi-dev-72b:free"
            "AGENTICAT_Identifier" = "agentica-org/deepcoder-14b-preview:free"
            "GEMMA_Identifier" = "google/gemma-3-27b-it:free"
            "LLAMA_CPP_MODEL_LLAMA3_8B" = "/path/to/llama-3-8b.gguf"
            "LLAMA_CPP_MODEL_MISTRAL_7B" = "/path/to/mistral-7b.gguf"
        }
    }

    # Main menu loop
    do {
        Show-Menu -Config $config
        $choice = Read-Host "Select model (0-9)"

        if ($choice -eq "0") {
            Write-Host "Exiting configuration tool." -ForegroundColor Yellow
            break
        }

        if ($choice -ge 1 -and $choice -le 9) {
            $identifierKey = Get-IdentifierKey -Option ([int]$choice)
            $displayName = Get-DisplayName -Option ([int]$choice)
            $modelIdentifier = Get-ModelIdentifier -Option ([int]$choice) -Config $config

            if ($identifierKey -and $config.ContainsKey($identifierKey) -and $modelIdentifier) {
                # Set the selected identifier as the current OPENROUTER_MODEL
                $newConfig = $config.Clone()
                $newConfig["OPENROUTER_MODEL"] = $config[$identifierKey]
                Set-EnvConfig -Config $newConfig

                # Also update the user's config.yaml file
                Set-UserConfig -ModelIdentifier $modelIdentifier

                Write-Host "Set current model to $displayName ($($config[$identifierKey]))" -ForegroundColor Green
                # Reload config to show updated values
                $config = Get-EnvConfig
            }

            Write-Host "Press any key to continue..." -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        } else {
            Write-Host "Invalid option. Please select 0-9." -ForegroundColor Red
        }

    } while ($true)

} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
