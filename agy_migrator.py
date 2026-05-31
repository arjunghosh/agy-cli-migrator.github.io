#!/usr/bin/env python3
"""
agy-migrator: Unified Capability Porter for the agy CLI.
Ports custom skills, plugins, and MCP servers from Claude environments to Gemini/agy.
"""

import os
import sys
import json
import shutil
import argparse
from datetime import datetime
from pathlib import Path

# Terminal coloring helper
def color_text(text, color_code):
    if sys.stdout.isatty():
        return f"\033[{color_code}m{text}\033[0m"
    return text

def green(t): return color_text(t, "32")
def yellow(t): return color_text(t, "33")
def red(t): return color_text(t, "31")
def cyan(t): return color_text(t, "36")
def bold(t): return color_text(t, "1")

def scan_claude_environment(claude_dir: Path, agents_dir: Path):
    """Scans traditional Claude config directories for skills and MCP servers."""
    skills = set()
    mcps = {}
    
    # 1. Scan Claude CLI skills
    agents_skills = agents_dir / "skills"
    if agents_skills.exists() and agents_skills.is_dir():
        for item in agents_skills.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                skills.add(item.name)
                
    # 2. Scan Claude CLI MCP configurations
    mcp_json = claude_dir / "mcp.json"
    if mcp_json.exists():
        try:
            with open(mcp_json, "r") as f:
                data = json.load(f)
                if "mcpServers" in data:
                    mcps = data["mcpServers"]
        except Exception as e:
            print(red(f"Error loading {mcp_json}: {e}"))
            
    return skills, mcps

def scan_gemini_environment(gemini_dir: Path):
    """Scans Gemini/agy config directories for existing skills and MCP servers."""
    skills = set()
    mcps = {}
    
    # 1. Scan Gemini/agy skills
    gemini_skills = gemini_dir / "skills"
    if gemini_skills.exists() and gemini_skills.is_dir():
        for item in gemini_skills.iterdir():
            if (item.is_dir() or item.is_symlink()) and not item.name.startswith("."):
                skills.add(item.name)
                
    # 2. Scan settings.json for MCP servers
    settings_json = gemini_dir / "settings.json"
    if settings_json.exists():
        try:
            with open(settings_json, "r") as f:
                data = json.load(f)
                if "mcpServers" in data:
                    mcps = data["mcpServers"]
        except Exception as e:
            print(red(f"Error loading {settings_json}: {e}"))
            
    return skills, mcps

def diff_environments(claude_skills, claude_mcps, gemini_skills, gemini_mcps):
    """Identifies capabilities present in Claude but missing in Gemini."""
    skills_to_port = claude_skills - gemini_skills
    
    mcps_to_port = {}
    for name, config in claude_mcps.items():
        if name not in gemini_mcps:
            mcps_to_port[name] = config
            
    return skills_to_port, mcps_to_port

def create_backup(target_file: Path) -> Path:
    """Creates a timestamped backup of the target file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = target_file.parent / f"{target_file.name}.{timestamp}.bak"
    shutil.copy2(target_file, backup_file)
    return backup_file

def port_mcp_servers(settings_file: Path, mcps_to_port, backup=True) -> bool:
    """Merges new MCP servers into settings.json securely."""
    if not settings_file.exists():
        print(red(f"Error: settings.json not found at {settings_file}"))
        return False
        
    try:
        # Create backup first
        if backup:
            backup_path = create_backup(settings_file)
            print(green(f"✓ Backup created successfully at {backup_path.name}"))
            
        with open(settings_file, "r") as f:
            data = json.load(f)
            
        if "mcpServers" not in data:
            data["mcpServers"] = {}
            
        for name, config in mcps_to_port.items():
            data["mcpServers"][name] = config
            print(green(f"✓ Merged MCP server configuration: {name}"))
            
        with open(settings_file, "w") as f:
            json.dump(data, f, indent=2)
            
        return True
    except Exception as e:
        print(red(f"Failed to merge MCP configurations: {e}"))
        return False

def port_skills(skills_to_port, agents_skills_dir: Path, gemini_skills_dir: Path, auto_accept=False) -> int:
    """Creates POSIX symlinks or Windows Directory Junctions for the unique skills."""
    if not gemini_skills_dir.exists():
        gemini_skills_dir.mkdir(parents=True, exist_ok=True)
        
    ported_count = 0
    for skill in sorted(skills_to_port):
        source = agents_skills_dir / skill
        target = gemini_skills_dir / skill
        
        if not source.exists():
            continue
            
        if target.exists() or (sys.platform != "win32" and target.is_symlink()):
            print(yellow(f"⚠ Skill {skill} already exists in target directory. Skipping."))
            continue
            
        if not auto_accept:
            choice = input(f"Port skill {bold(skill)}? [Y/n]: ").strip().lower()
            if choice not in ("", "y", "yes"):
                print(yellow(f"Skipped {skill}."))
                continue
                
        try:
            if sys.platform == "win32":
                # On Windows, try standard os.symlink with target_is_directory=True
                try:
                    os.symlink(source, target, target_is_directory=True)
                    print(green(f"✓ Symlinked skill (Windows Symlink): {skill} -> {source}"))
                except OSError:
                    # Fallback to Windows Directory Junction (mklink /J)
                    # Junctions do not require Administrator privileges
                    # Ensure double quotes for paths to handle spaces
                    ret = os.system(f'mklink /J "{target}" "{source}" >nul 2>&1')
                    if ret == 0:
                        print(green(f"✓ Linked skill (Windows Junction): {skill} -> {source}"))
                    else:
                        # Fallback to copy directory if link fails
                        shutil.copytree(source, target)
                        print(green(f"✓ Ported skill (Windows Copy Fallback): {skill}"))
            else:
                # macOS & Linux (POSIX standard symlink)
                os.symlink(source, target)
                print(green(f"✓ Symlinked skill: {skill} -> {source}"))
            ported_count += 1
        except Exception as e:
            print(red(f"Failed to link skill {skill}: {e}"))
            
    return ported_count

def run_rollback(gemini_dir: Path):
    """Rolls back migrated symlinks/junctions and restores the latest settings backup."""
    gemini_skills = gemini_dir / "skills"
    settings_json = gemini_dir / "settings.json"
    
    print(bold("\n=== Beginning Rollback Run ==="))
    
    # 1. Clean up symlinks / junctions
    if gemini_skills.exists():
        removed_links = 0
        for item in gemini_skills.iterdir():
            is_migrated_link = False
            
            if sys.platform == "win32":
                # On Windows, junctions and symlinks can be removed by rmdir or unlink
                # We check if it points to .agents skills
                try:
                    # Windows directory link detection
                    import stat
                    st = os.stat(item)
                    if stat.S_ISDIR(st.st_mode):
                        # Attempt to check if it's a junction by unlinking
                        # Normal directories raise OSError on unlink
                        os.unlink(item)
                        is_migrated_link = True
                except OSError:
                    pass
            else:
                # POSIX symlink detection
                if item.is_symlink():
                    target = Path(os.readlink(item))
                    if ".agents/skills" in str(target):
                        item.unlink()
                        is_migrated_link = True
                        
            if is_migrated_link:
                print(green(f"✓ Removed ported link: {item.name}"))
                removed_links += 1
                
        if removed_links == 0:
            print(yellow("No ported skills symlinks or junctions found to clean up."))
            
    # 2. Restore settings backup
    backups = sorted(gemini_dir.glob("settings.json.*.bak"))
    if backups:
        latest_backup = backups[-1]
        print(cyan(f"Found latest backup file: {latest_backup.name}"))
        choice = input(f"Restore settings backup {bold(latest_backup.name)}? [Y/n]: ").strip().lower()
        if choice in ("", "y", "yes"):
            shutil.copy2(latest_backup, settings_json)
            print(green(f"✓ Restored {settings_json.name} from backup!"))
        else:
            print(yellow("Rollback of settings.json skipped by user."))
    else:
        print(yellow("No settings.json backup files found to restore."))
        
    print(bold(green("\nRollback process completed successfully!")))

def main():
    parser = argparse.ArgumentParser(
        description="agy-migrator: Surgically port configurations from Claude/Codex into the unified agy CLI environment."
    )
    parser.add_argument("--scan", action="store_true", help="Perform a dry-run environment scanning without modifications.")
    parser.add_argument("--all", action="store_true", help="Automatically port all missing skills and MCPs without prompting.")
    parser.add_argument("--rollback", action="store_true", help="Remove all ported symlinks and restore the latest settings backup.")
    
    args = parser.parse_args()
    
    # Define native paths
    home = Path.home()
    claude_dir = home / ".claude"
    agents_dir = home / ".agents"
    gemini_dir = home / ".gemini"
    
    if args.rollback:
        run_rollback(gemini_dir)
        sys.exit(0)
        
    # Verify environment paths
    if not gemini_dir.exists():
        print(red(f"Error: target agy/gemini configuration folder does not exist at {gemini_dir}"))
        print(yellow("Please ensure the agy CLI is installed and has run at least once before executing."))
        sys.exit(1)
        
    print(bold(cyan("\n=== scanning CLI environments ===")))
    claude_skills, claude_mcps = scan_claude_environment(claude_dir, agents_dir)
    gemini_skills, gemini_mcps = scan_gemini_environment(gemini_dir)
    
    skills_to_port, mcps_to_port = diff_environments(
        claude_skills, claude_mcps, gemini_skills, gemini_mcps
    )
    
    # Present current inventory
    print(bold("\n--- Capability Scan Inventory ---"))
    print(f"Total skills in Claude: {bold(len(claude_skills))} | Present in agy: {bold(len(gemini_skills))}")
    print(f"Total MCPs in Claude:   {bold(len(claude_mcps))} | Present in agy: {bold(len(gemini_mcps))}")
    
    if not skills_to_port and not mcps_to_port:
        print(bold(green("\n✓ All Claude skills and MCP server profiles are already fully ported to your new agy CLI!")))
        sys.exit(0)
        
    # Print what needs mapping
    if skills_to_port:
        print(bold(yellow(f"\nMissing Skills to Port ({len(skills_to_port)}):")))
        for idx, skill in enumerate(sorted(skills_to_port), 1):
            print(f"  {idx:02d}. {skill}")
            
    if mcps_to_port:
        print(bold(yellow(f"\nMissing MCP Servers to Port ({len(mcps_to_port)}):")))
        for idx, mcp in enumerate(sorted(mcps_to_port.keys()), 1):
            print(f"  {idx:02d}. {mcp}")
            
    if args.scan:
        print(bold(cyan("\nDry-run complete. No changes were applied.")))
        sys.exit(0)
        
    # Prompt for port execution
    print(bold(cyan("\n=== Starting Porting Process ===")))
    
    # 1. Port MCP Configurations
    if mcps_to_port:
        port_all_mcps = args.all
        if not port_all_mcps:
            choice = input(f"\nPort all {bold(len(mcps_to_port))} missing MCP servers into settings.json? [Y/n]: ").strip().lower()
            port_all_mcps = choice in ("", "y", "yes")
            
        if port_all_mcps:
            settings_json = gemini_dir / "settings.json"
            port_mcp_servers(settings_json, mcps_to_port)
        else:
            print(yellow("Porting of MCP server configurations skipped."))
            
    # 2. Port Skill symlinks
    if skills_to_port:
        print(bold(cyan("\n--- Porting Skills ---")))
        ported = port_skills(skills_to_port, agents_dir / "skills", gemini_dir / "skills", auto_accept=args.all)
        print(green(f"\n✓ Ported {ported} skills successfully!"))
        
    print(bold(green("\nUnified capability migration run completed successfully!")))
    print(yellow("Please close your current agy CLI shell and launch a fresh one to reload the changes."))

if __name__ == "__main__":
    main()
