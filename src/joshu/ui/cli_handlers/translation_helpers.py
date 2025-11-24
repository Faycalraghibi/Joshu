"""Translation and safety checking helpers."""

from typing import Optional
from rich.console import Console
import typer

from joshu.core.translate import Translation
from joshu.core.safety import SafetyReport
from joshu.tools.shell import run_command, run_command_with_auto_fix
from joshu.core.context_provider import ContextProvider

console = Console()


def check_conversational_response(translation: Translation) -> bool:
    """Check if a translation is a conversational response that shouldn't be executed."""
    needs_execution = getattr(translation, 'needs_execution', True)
    
    # Check explanation and command format directly as backup
    explanation_lower = translation.explanation.lower()
    command_normalized = translation.command.replace('\\\"', '"').replace("\\'", "'")
    
    conversational_keywords = [
        "conversational response", "direct response", "direct answer",
        "to user's query", "to user's question", "user's query", "user's question",
        "answering", "providing answer", "providing response"
    ]
    
    is_conversational_explanation = any(keyword in explanation_lower for keyword in conversational_keywords)
    is_conversational_command = (
        '"""' in command_normalized or
        (command_normalized.startswith('echo "') and len(translation.command) > 100)
    )

    
    # Override needs_execution if we detect conversational response
    if is_conversational_explanation or is_conversational_command:
        needs_execution = False
    
    return not needs_execution


def display_safety_report(report: SafetyReport) -> None:
    """Display a safety report with appropriate styling."""
    if not report.safe:
        if report.danger_level == "CRITICAL":
            console.print("[bold red]⚠️  DANGER: This command could cause serious damage[/bold red]")
        elif report.danger_level == "HIGH":
            console.print("[bold yellow]⚠️  WARNING: This command is potentially dangerous[/bold yellow]")
        elif report.danger_level == "MEDIUM":
            console.print("[yellow]⚠️  CAUTION: This command requires careful consideration[/yellow]")
        else:
            console.print("[yellow]⚠️  Command flagged for review[/yellow]")
        
        for r in report.reasons:
            console.print(f" - {r}")
        if report.suggested_alternative:
            console.print(
                f"[yellow]Suggested safer alternative:[/yellow] {report.suggested_alternative}"
            )


def handle_translation_execution(
    translation: Translation,
    user_input: str,
    sandbox: bool,
    auto_execute: bool,
    context_provider: Optional[ContextProvider] = None,
    skip_safety_check: bool = False,
    model: str = "meta-llama/llama-3.1-8b-instruct:free"
) -> int:
    """
    Handle translation execution with safety checks, confirmation, and auto-fix retry.
    
    Returns:
        Exit code (0 for success, non-zero for failure/cancellation)
    """
    from joshu.core.safety import assess_command_safety
    from joshu.core.config import get_config_manager
    
    # Safety check FIRST - never bypass safety even for conversational responses
    if not skip_safety_check:
        report = assess_command_safety(translation.command, sandbox)
        if not report.safe:
            display_safety_report(report)
            return 3
    
    # Check if conversational response (after safety check)
    if check_conversational_response(translation):
        # Execute conversational response directly without asking
        code, out, err = run_command(translation.command)
        if code == 0:
            if out:
                console.print(out)
        else:
            if err:
                console.print(f"[red]{err}[/red]")
        return 0
    
    # Check if this is a code generation request
    if "code command" in translation.explanation.lower() or "code' command" in translation.explanation.lower():
        console.print("[yellow]💡 Tip: For code generation requests, use the 'code' command:[/yellow]")
        console.print(f"[yellow]   joshu code \"{user_input}\"[/yellow]")
        console.print("[yellow]This will generate the code directly instead of trying to translate to a shell command.[/yellow]")
        return 0
    
    # Auto-execute or ask for confirmation
    if auto_execute:
        console.print("[dim]Auto-executing command (auto_execute enabled in config)[/dim]")
        proceed = True
    else:
        proceed = typer.confirm("Execute this command?", default=False)
        if not proceed:
            console.print("[dim]Cancelled.[/dim]\\n")
            if context_provider:
                context_provider.update_context_from_response(
                    user_input,
                    "Command cancelled by user"
                )
            return 0
    
    # Get config for auto-fix
    config_manager = get_config_manager()
    config_dict = config_manager.config.to_dict()
    
    # Execute command with auto-fix support
    code, out, err, fixed_cmd = run_command_with_auto_fix(
        translation.command,
        config_dict,
        context_provider,
        timeout=60,
        model=model
    )
    
    # Display fix notification if auto-fix was applied
    if fixed_cmd:
        console.print(f"[yellow]✨ Original command failed. Auto-fixed to:[/yellow]")
        console.print(f"[cyan]{fixed_cmd}[/cyan]")
    
    # Handle results
    if code == 0:
        if out:
            console.print(out)
        console.print("[green]Done.[/green]")
        
        if context_provider:
            result_msg = f"Executed: {fixed_cmd if fixed_cmd else translation.command}\\nOutput: {out[:100]}..."
            if fixed_cmd:
                result_msg = f"Auto-fixed and executed: {translation.command} → {fixed_cmd}\\nOutput: {out[:100]}..."
            context_provider.update_context_from_response(user_input, result_msg)
        return 0
    else:
        if err:
            console.print(f"[red]{err}[/red]")
        
        if context_provider:
            fail_msg = f"Failed to execute: {translation.command}\\nError: {err[:100]}..."
            if fixed_cmd:
                fail_msg = f"Auto-fix attempted but still failed: {translation.command} → {fixed_cmd}\\nError: {err[:100]}..."
            context_provider.update_context_from_response(user_input, fail_msg)
        return code

