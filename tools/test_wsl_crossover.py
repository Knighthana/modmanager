#!/usr/bin/env python3
"""WSL Cross-Platform Steam Discovery Test

Tests Steam library discovery from WSL environment to Windows Steam installations.
Outputs detailed results to log file for analysis.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from modmanager.steam_scanner import SteamScanner


def log_result(message: str, log_file: Path, level: str = "INFO"):
    """Log message to console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {level:8} {message}"
    print(log_line)
    with open(log_file, "a") as f:
        f.write(log_line + "\n")


def test_wsl_steam_discovery(output_log: str = "wsl_steam_scan.log"):
    """Test Steam discovery from WSL environment."""
    log_path = Path(output_log)
    
    # Clear previous log
    log_path.write_text("")
    
    log_result("=" * 80, log_path)
    log_result("WSL Steam Library Discovery Test", log_path)
    log_result("=" * 80, log_path)
    log_result(f"Test started at {datetime.now()}", log_path)
    log_result(f"Running on: {sys.platform}", log_path)
    log_result("", log_path)
    
    try:
        # Initialize scanner
        log_result("Initializing SteamScanner...", log_path)
        scanner = SteamScanner(working_pathstyle="linux")
        
        # Discover Steam libraries
        log_result("Discovering Steam libraries...", log_path)
        libraries = scanner.discover_steam_libraries()
        
        if not libraries:
            log_result("❌ No Steam libraries found", log_path, "WARNING")
            log_result("", log_path)
            log_result("Checked paths:", log_path)
            paths = [
                Path.home() / ".steam" / "root" / "steamapps",
                Path.home() / ".local" / "share" / "Steam" / "steamapps",
                Path("C:/Program Files (x86)/Steam/steamapps"),
                Path("C:/Program Files/Steam/steamapps"),
                Path("/mnt/c/Program Files (x86)/Steam/steamapps"),
                Path("/mnt/c/Program Files/Steam/steamapps"),
            ]
            for p in paths:
                exists = "✓" if p.exists() else "✗"
                log_result(f"  {exists} {p}", log_path)
            return
        
        log_result(f"✅ Found {len(libraries)} Steam library/libraries:", log_path)
        log_result("", log_path)
        
        # Process each library
        total_games = 0
        total_mods = 0
        
        for i, lib in enumerate(libraries, 1):
            log_result(f"Library {i}: {lib.path}", log_path)
            log_result(f"  libraryfolders.vdf present: {lib.contains_libraryfolders_vdf}", log_path)
            
            try:
                # Discover games in library
                games = scanner.discover_games_in_library(lib.path)
                
                if games:
                    log_result(f"  Found {len(games)} game(s):", log_path)
                    total_games += len(games)
                    
                    for appid, game_info in sorted(games.items()):
                        log_result(f"    - [{appid}] {game_info.name}", log_path)
                        log_result(f"        Base: {game_info.basepath}", log_path)
                        log_result(f"        Mods: {game_info.modpath}", log_path)
                        
                        # Discover mods for this game
                        mods = scanner.discover_mods_for_game(appid, game_info.modpath)
                        if mods:
                            log_result(f"        Found {len(mods)} mod(s): {', '.join(mods[:5])}", log_path)
                            if len(mods) > 5:
                                log_result(f"        ... and {len(mods) - 5} more", log_path)
                            total_mods += len(mods)
                else:
                    log_result(f"  No games found in this library", log_path)
            
            except Exception as e:
                log_result(f"  ⚠ Error scanning library: {e}", log_path, "ERROR")
            
            log_result("", log_path)
        
        # Summary
        log_result("=" * 80, log_path)
        log_result("SCAN SUMMARY", log_path)
        log_result("=" * 80, log_path)
        log_result(f"Libraries found:  {len(libraries)}", log_path)
        log_result(f"Games discovered: {total_games}", log_path)
        log_result(f"Mods discovered:  {total_mods}", log_path)
        log_result(f"Test completed at {datetime.now()}", log_path)
        
    except Exception as e:
        log_result(f"❌ Fatal error: {e}", log_path, "ERROR")
        import traceback
        log_result(traceback.format_exc(), log_path, "ERROR")


if __name__ == "__main__":
    test_wsl_steam_discovery()
    print(f"\n✅ Results saved to: wsl_steam_scan.log")
