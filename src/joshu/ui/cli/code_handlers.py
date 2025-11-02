"""Code editor command handlers."""

import os
import re
from pathlib import Path
from typing import Optional
from rich.console import Console
import typer

from joshu.tools.code_editor import CodeEditor

console = Console()


def handle_code_command(
    prompt: str,
    file: Optional[str],
    language: Optional[str],
    dry_run: bool
) -> None:
    """Handle the code command - route to appropriate handler."""
    editor = CodeEditor()
    prompt_lower = prompt.lower()
    
    if file:
        # File-specific operations
        if "edit" in prompt_lower or "modify" in prompt_lower or "update" in prompt_lower:
            _handle_file_edit(editor, prompt, file, language, dry_run)
        elif "create" in prompt_lower or "generate" in prompt_lower or "write" in prompt_lower:
            _handle_file_create(editor, prompt, file, language, dry_run)
        else:
            # Default to editing if file is specified
            _handle_file_edit(editor, prompt, file, language, dry_run)
    else:
        # General code operations
        if "explain" in prompt_lower or "what does this code do" in prompt_lower:
            _handle_code_explanation(editor, prompt, dry_run)
        elif ("debug" in prompt_lower or "fix" in prompt_lower) and "error" in prompt_lower:
            _handle_code_debugging(editor, prompt, dry_run)
        elif "refactor" in prompt_lower or "optimize" in prompt_lower or "improve" in prompt_lower:
            _handle_code_refactoring(editor, prompt, dry_run)
        else:
            # Default to code generation
            _handle_code_generation(editor, prompt, language, dry_run)


def _handle_file_edit(editor: CodeEditor, prompt: str, file_path: str, language: Optional[str], dry_run: bool) -> None:
    """Handle file editing operations."""
    console.print(f"[bold]Editing file:[/bold] {file_path}")
    
    try:
        if not os.path.exists(file_path):
            console.print(f"[red]File {file_path} does not exist.[/red]")
            console.print(f"[yellow]Use file creation instead: joshu code 'create ...' --file {file_path}[/yellow]")
            return
        
        if not dry_run:
            console.print(f"[yellow]⚠️  This will modify {file_path}[/yellow]")
            if not typer.confirm("Proceed with editing?", default=False):
                console.print("[dim]Edit cancelled.[/dim]")
                return
        
        result = editor.edit_file(file_path, prompt)
        
        if dry_run:
            console.print(f"[bold]Proposed edit:[/bold] {prompt}")
            console.print("[dim]Note: Use without --dry-run to see actual changes.[/dim]")
        else:
            if result.get("success", False):
                console.print(f"[green]✓ {result.get('message', 'File edited successfully')}[/green]")
                if result.get("backup_path"):
                    console.print(f"[dim]Backup created: {result['backup_path']}[/dim]")
            else:
                console.print(f"[red]✗ {result.get('message', 'Failed to edit file')}[/red]")
                if result.get("backup_path"):
                    console.print(f"[dim]Backup available: {result['backup_path']}[/dim]")
                
    except Exception as e:
        console.print(f"[red]Error editing file: {e}[/red]")


def _handle_file_create(editor: CodeEditor, prompt: str, file_path: str, language: Optional[str], dry_run: bool) -> None:
    """Handle file creation operations."""
    console.print(f"[bold]Creating file:[/bold] {file_path}")
    
    try:
        if not language:
            path = Path(file_path)
            language = editor.get_language_from_extension(path.suffix)
        
        generated_code = editor.generate_code(prompt, language)
        
        if dry_run:
            console.print(f"[bold]Proposed content:[/bold]")
            console.print(generated_code)
        else:
            if editor.write_file(file_path, generated_code):
                console.print("[green]File created successfully.[/green]")
            else:
                console.print("[red]Failed to create file.[/red]")
                
    except Exception as e:
        console.print(f"[red]Error creating file: {e}[/red]")


def _handle_code_explanation(editor: CodeEditor, prompt: str, dry_run: bool) -> None:
    """Handle code explanation operations."""
    console.print("[bold]Code Explanation:[/bold]\n")
    
    code_to_explain = ""
    
    if os.path.exists(prompt.strip()):
        try:
            code_to_explain, _ = editor.read_file(prompt.strip())
            console.print(f"[dim]Explaining code from file: {prompt}[/dim]\n")
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            return
    elif ":" in prompt:
        parts = prompt.split(":", 1)
        if len(parts) > 1:
            code_to_explain = parts[1].strip()
    else:
        words = prompt.split()
        for word in words:
            if os.path.exists(word):
                try:
                    code_to_explain, _ = editor.read_file(word)
                    break
                except:
                    pass
        
        if not code_to_explain:
            code_to_explain = prompt.replace("explain", "", 1).replace("this", "", 1).replace("code", "", 1).strip()
    
    if not code_to_explain or len(code_to_explain.strip()) < 10:
        console.print("[yellow]Please provide the code to explain.[/yellow]")
        console.print("[dim]You can:[/dim]")
        console.print("[dim]  1. Provide code directly: 'explain this code: def foo(): pass'[/dim]")
        console.print("[dim]  2. Provide a file path: 'explain this code: src/main.py'[/dim]")
        
        user_code = typer.prompt("\nEnter code or file path", default="")
        if user_code:
            if os.path.exists(user_code):
                try:
                    code_to_explain, _ = editor.read_file(user_code)
                except Exception as e:
                    console.print(f"[red]Error reading file: {e}[/red]")
                    return
            else:
                code_to_explain = user_code
    
    if not code_to_explain:
        console.print("[red]No code provided.[/red]")
        return
    
    detail_level = typer.prompt("Detail level (low/medium/high)", default="medium")
    
    console.print("[dim]Generating explanation...[/dim]\n")
    explanation = editor._core.explain_code(code_to_explain, detail_level)
    
    console.print("[bold]Explanation:[/bold]\n")
    console.print(explanation)


def _handle_code_debugging(editor: CodeEditor, prompt: str, dry_run: bool) -> None:
    """Handle code debugging operations."""
    console.print("[bold]Code Debugging:[/bold]\n")
    
    code_to_debug = ""
    error_message = ""
    prompt_lower = prompt.lower()
    
    words = prompt.split()
    for word in words:
        if os.path.exists(word):
            try:
                code_to_debug, _ = editor.read_file(word)
                console.print(f"[dim]Reading code from file: {word}[/dim]\n")
                break
            except Exception as e:
                console.print(f"[yellow]Could not read file {word}: {e}[/yellow]")
    
    if not code_to_debug:
        if "error:" in prompt_lower or "exception:" in prompt_lower:
            separator = "error:" if "error:" in prompt_lower else "exception:"
            parts = prompt.split(separator, 1)
            if len(parts) > 1:
                remainder = parts[1].strip()
                if "in" in remainder:
                    error_parts = remainder.split("in", 1)
                    error_message = error_parts[0].strip()
                    code_to_debug = error_parts[1].strip()
                else:
                    error_message = remainder
        elif ":" in prompt:
            parts = prompt.split(":", 1)
            if len(parts) > 1:
                code_to_debug = parts[1].strip()
    
    if not error_message:
        error_message = typer.prompt("Enter the error message (or press Enter to skip)", default="")
    
    if not code_to_debug or len(code_to_debug.strip()) < 10:
        console.print("[yellow]Code not found in prompt.[/yellow]")
        code_input = typer.prompt("Enter code or file path to debug", default="")
        if code_input:
            if os.path.exists(code_input):
                try:
                    code_to_debug, _ = editor.read_file(code_input)
                except Exception as e:
                    console.print(f"[red]Error reading file: {e}[/red]")
                    return
            else:
                code_to_debug = code_input
    
    if not code_to_debug:
        console.print("[red]No code provided for debugging.[/red]")
        return
    
    console.print("[dim]Analyzing code...[/dim]\n")
    debug_report = editor._core.debug_code(code_to_debug, error_message)
    
    console.print(f"[bold]Error Type:[/bold] {debug_report.error_type}")
    console.print(f"[bold]Error Message:[/bold] {debug_report.error_message}\n")
    
    if debug_report.suggestions:
        console.print("[bold]Suggestions:[/bold]")
        for i, suggestion in enumerate(debug_report.suggestions, 1):
            console.print(f"  {i}. {suggestion}")
    
    if debug_report.code_snippets:
        console.print("\n[bold]Suggested Code Fixes:[/bold]")
        for i, snippet in enumerate(debug_report.code_snippets, 1):
            console.print(f"\n[bold]Fix {i}:[/bold]")
            console.print(f"[code]{snippet}[/code]")


def _handle_code_refactoring(editor: CodeEditor, prompt: str, dry_run: bool) -> None:
    """Handle code refactoring operations."""
    console.print("[bold]Code Refactoring:[/bold]\n")
    
    refactoring_goal = ""
    code_to_refactor = ""
    language = "python"
    prompt_lower = prompt.lower()
    
    action_words = ["refactor", "optimize", "improve", "simplify"]
    for word in action_words:
        if word in prompt_lower:
            parts = prompt.split(word, 1)
            if len(parts) > 1:
                remainder = parts[1].strip()
                if " to " in remainder.lower() or " for " in remainder.lower():
                    goal_match = re.search(r'^(.*?)(?:\s+to\s+|\s+for\s+)(.+)$', remainder, re.IGNORECASE)
                    if goal_match:
                        refactoring_goal = goal_match.group(2).strip()
                        potential_code = goal_match.group(1).strip()
                        if len(potential_code) > 20:
                            code_to_refactor = potential_code
                    else:
                        refactoring_goal = remainder
                else:
                    refactoring_goal = remainder
                break
    
    words = prompt.split()
    for word in words:
        if os.path.exists(word):
            try:
                code_to_refactor, detected_language = editor.read_file(word)
                language = detected_language
                console.print(f"[dim]Reading code from file: {word}[/dim]\n")
                break
            except Exception as e:
                console.print(f"[yellow]Could not read file {word}: {e}[/yellow]")
    
    if not code_to_refactor:
        if "code:" in prompt:
            parts = prompt.split("code:", 1)
            if len(parts) > 1:
                code_to_refactor = parts[1].strip()
        elif len(prompt) > 100:
            code_pattern = r'(def\s+\w+|function\s+\w+|class\s+\w+)[\s\S]*$'
            match = re.search(code_pattern, prompt, re.IGNORECASE)
            if match:
                code_to_refactor = match.group(0)
    
    if not refactoring_goal:
        refactoring_goal = typer.prompt("What should be improved? (e.g., 'performance', 'readability', 'simplify')", default="improve code quality")
    
    if not code_to_refactor or len(code_to_refactor.strip()) < 10:
        console.print("[yellow]Code not found in prompt.[/yellow]")
        code_input = typer.prompt("Enter code or file path to refactor", default="")
        if code_input:
            if os.path.exists(code_input):
                try:
                    code_to_refactor, detected_language = editor.read_file(code_input)
                    language = detected_language
                except Exception as e:
                    console.print(f"[red]Error reading file: {e}[/red]")
                    return
            else:
                code_to_refactor = code_input
    
    if not code_to_refactor:
        console.print("[red]No code provided for refactoring.[/red]")
        return
    
    if not language or language == "text":
        path = Path(code_to_refactor) if os.path.exists(code_to_refactor) else None
        if path:
            language = editor.get_language_from_extension(path.suffix)
        else:
            language = "python"
    
    console.print(f"[dim]Refactoring code ({refactoring_goal})...[/dim]\n")
    refactored_code = editor._core.refactor_code(code_to_refactor, refactoring_goal, {"language": language})
    
    console.print("[bold]Refactored code:[/bold]\n")
    console.print(refactored_code)
    
    if not dry_run and typer.confirm("\nSave refactored code to a file?"):
        default_filename = f"refactored_code.{_get_extension_for_language(language)}"
        filename = typer.prompt("Enter filename", default=default_filename)
        
        if editor.write_file(filename, refactored_code):
            console.print(f"[green]Refactored code saved to {filename}[/green]")
        else:
            console.print("[red]Failed to save refactored code.[/red]")


def _handle_code_generation(editor: CodeEditor, prompt: str, language: Optional[str], dry_run: bool) -> None:
    """Handle code generation operations."""
    console.print("[bold]Code Generation:[/bold]\n")
    
    if not language:
        prompt_lower = prompt.lower()
        if "python" in prompt_lower:
            language = "python"
        elif "javascript" in prompt_lower or "js" in prompt_lower:
            language = "javascript"
        elif "typescript" in prompt_lower or "ts" in prompt_lower:
            language = "typescript"
        elif "bash" in prompt_lower or "shell" in prompt_lower:
            language = "bash"
        else:
            language = typer.prompt("Programming language", default="python")
    
    console.print(f"[dim]Generating {language} code...[/dim]\n")
    generated_code = editor._core.generate_code(prompt, language)
    
    console.print(f"[bold]Generated {language} code:[/bold]\n")
    console.print(generated_code)
    
    if not dry_run and typer.confirm("\nSave this code to a file?"):
        default_filename = f"generated_code.{_get_extension_for_language(language)}"
        filename = typer.prompt("Enter filename", default=default_filename)
        
        if editor.write_file(filename, generated_code):
            console.print(f"[green]Code saved to {filename}[/green]")
        else:
            console.print("[red]Failed to save code.[/red]")


def _get_extension_for_language(language: str) -> str:
    """Get file extension for a programming language."""
    extensions = {
        "python": "py",
        "javascript": "js",
        "typescript": "ts",
        "bash": "sh",
        "yaml": "yaml",
        "json": "json",
        "plain": "txt",
        "html": "html",
        "css": "css"
    }
    return extensions.get(language.lower(), "txt")

