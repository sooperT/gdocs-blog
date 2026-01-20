#!/usr/bin/env python3
"""
Validate that generated files match their generators.

This script checks that HTML files can be regenerated from their source
generators without changes. Prevents drift between generators and outputs.

Usage:
    python3 validate_generators.py
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return success status"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out: {cmd}"


def compare_files(file1, file2):
    """Compare two files, return True if identical"""
    try:
        with open(file1, 'r', encoding='utf-8') as f1:
            content1 = f1.read()
        with open(file2, 'r', encoding='utf-8') as f2:
            content2 = f2.read()
        return content1 == content2
    except Exception as e:
        print(f"Error comparing files: {e}")
        return False


def validate_generator(generator_script, output_file, description):
    """
    Validate that running a generator produces the same output as committed file.

    Args:
        generator_script: Path to generator script
        output_file: Path to generated HTML file
        description: Human-readable description

    Returns:
        (success: bool, message: str)
    """
    print(f"\nValidating: {description}")
    print(f"  Generator: {generator_script}")
    print(f"  Output: {output_file}")

    # Check if files exist
    if not os.path.exists(generator_script):
        return False, f"Generator script not found: {generator_script}"

    if not os.path.exists(output_file):
        return False, f"Output file not found: {output_file}"

    # Create temp directory for comparison
    with tempfile.TemporaryDirectory() as tmpdir:
        # Backup current output file
        backup_path = os.path.join(tmpdir, os.path.basename(output_file))
        shutil.copy2(output_file, backup_path)

        # Run generator
        print(f"  Running: python3 {generator_script}")
        success, stdout, stderr = run_command(f"python3 {generator_script}", description)

        if not success:
            # Restore backup
            shutil.copy2(backup_path, output_file)
            return False, f"Generator failed to run:\n{stderr}"

        # Compare generated file with backup
        if compare_files(output_file, backup_path):
            print(f"  ✓ Output matches generator")
            return True, "Files match - generator is in sync"
        else:
            # Restore backup
            shutil.copy2(backup_path, output_file)
            return False, "Output differs from generator - GENERATOR OUT OF SYNC!"


def main():
    print("="*60)
    print("VALIDATING GENERATOR SCRIPTS")
    print("="*60)

    # Define generator validations
    validations = [
        {
            'generator': 'generate_homepage.py',
            'output': 'index.html',
            'description': 'Homepage'
        },
        {
            'generator': 'generate_archive.py',
            'output': 'words/index.html',
            'description': 'Archive Page'
        }
    ]

    failed_validations = []

    for validation in validations:
        success, message = validate_generator(
            validation['generator'],
            validation['output'],
            validation['description']
        )

        if not success:
            failed_validations.append({
                'description': validation['description'],
                'message': message
            })
            print(f"  ✗ FAILED: {message}")

    print("\n" + "="*60)

    if failed_validations:
        print("❌ VALIDATION FAILED")
        print("="*60)
        print("\nThe following generators are out of sync:\n")
        for failure in failed_validations:
            print(f"  • {failure['description']}")
            print(f"    {failure['message']}\n")

        print("ACTION REQUIRED:")
        print("1. Check what changed in the generator scripts")
        print("2. Regenerate the affected files")
        print("3. Review changes in git diff before committing")
        print("4. Only commit if changes are intentional")

        return 1
    else:
        print("✅ ALL VALIDATIONS PASSED")
        print("="*60)
        print("\nAll generated files match their generators.")
        print("Safe to commit!")

        return 0


if __name__ == '__main__':
    sys.exit(main())
