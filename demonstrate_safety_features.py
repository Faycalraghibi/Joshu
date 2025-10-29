#!/usr/bin/env python3
"""
Demonstration script for Joshu Safety Features
"""

from joshu.core.safety import assess_command_safety
from joshu.tools.system_info import get_system_info


def demonstrate_safety_features():
    """Demonstrate the various safety features."""
    
    system_info = get_system_info()
    is_windows = "Windows" in system_info
    
    print("=== Joshu Safety Features Demonstration ===\n")
    print(f"Detected System: {system_info}\n")
    
    # Test cases with different danger levels
    if is_windows:
        test_cases = [
            # Safe commands
            ("dir", "Safe command - directory listing"),
            ("cd", "Safe command - change directory"),
            ("echo 'Hello World'", "Safe command - print text"),
            
            # Medium danger - sudo commands (not applicable on Windows)
            ("takeown /f file.txt", "Medium danger - take ownership"),
            
            # Medium danger - basic destructive commands
            ("del temp.txt", "Medium danger - file deletion"),
            
            # High danger - recursive operations
            ("rd /s /q C:/temp", "High danger - recursive directory deletion"),
            
            # Critical danger - system destruction
            ("del /s /q C:/", "Critical danger - drive deletion"),
            ("format C:", "Critical danger - drive formatting"),
            
            # Sandbox mode examples
            ("dir", "Safe command in sandbox mode"),
            ("del temp.txt", "Destructive command in sandbox mode"),
        ]
    else:
        test_cases = [
            # Safe commands
            ("ls -la", "Safe command - directory listing"),
            ("pwd", "Safe command - print working directory"),
            ("echo 'Hello World'", "Safe command - print text"),
            
            # Medium danger - sudo commands
            ("sudo ls -la", "Medium danger - sudo usage"),
            
            # Medium danger - basic destructive commands
            ("rm temp.txt", "Medium danger - file deletion"),
            
            # High danger - recursive operations
            ("rm -r /home/user/documents", "High danger - recursive deletion in home directory"),
            
            # Critical danger - system destruction
            ("rm -rf /", "Critical danger - root directory deletion"),
            ("rm -rf /home", "High danger - home directory deletion"),
            
            # Sandbox mode examples
            ("ls -la", "Safe command in sandbox mode"),
            ("rm temp.txt", "Destructive command in sandbox mode"),
        ]
    
    for i, (command, description) in enumerate(test_cases, 1):
        print(f"{i}. {description}")
        print(f"   Command: {command}")
        
        # Test normal mode
        if i <= len(test_cases) - 2:  # First set of tests in normal mode
            report = assess_command_safety(command)
            print(f"   Safety Status: {'SAFE' if report.safe else 'UNSAFE'}")
            print(f"   Danger Level: {report.danger_level}")
            if report.reasons:
                print("   Reasons:")
                for reason in report.reasons:
                    print(f"     - {reason}")
            if report.suggested_alternative:
                print(f"   Suggested Alternative: {report.suggested_alternative}")
        
        # Test sandbox mode for the last two examples
        else:
            report = assess_command_safety(command, sandbox_mode=True)
            print(f"   Safety Status (Sandbox): {'SAFE' if report.safe else 'UNSAFE'}")
            print(f"   Danger Level: {report.danger_level}")
            if report.reasons:
                print("   Reasons:")
                for reason in report.reasons:
                    print(f"     - {reason}")
            if report.suggested_alternative:
                print(f"   Suggested Alternative: {report.suggested_alternative}")
        
        print()


if __name__ == "__main__":
    demonstrate_safety_features()