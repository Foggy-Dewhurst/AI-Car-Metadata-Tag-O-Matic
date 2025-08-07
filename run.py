#!/usr/bin/env python3
"""
Simple launcher for Car Identifier GUI v2
"""

import sys
import importlib.util

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        ('PIL', 'Pillow'),
        ('ollama', 'ollama'),
        ('tkinter', 'tkinter')
    ]
    
    missing_packages = []
    
    for package, pip_name in required_packages:
        try:
            importlib.import_module(package)
            print(f"✓ {pip_name} installed")
        except ImportError:
            print(f"✗ {pip_name} not found")
            missing_packages.append(pip_name)
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Please install them with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def main():
    """Main launcher function"""
    print("Car Identifier GUI v2 - Launcher")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        return False
    
    print()
    print("✓ All dependencies met!")
    print("Starting Car Identifier GUI...")
    print()
    
    # Import and run the GUI
    try:
        from car_identifier_gui import main as gui_main
        gui_main()
        return True
    except Exception as e:
        print(f"Error starting GUI: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        print("\nSetup incomplete. Please fix the issues above and try again.")
        sys.exit(1) 