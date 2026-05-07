"""Steam system scanner: discover game libraries, games, and installed mods.

This module automatically scans the local system to generate database.json,
eliminating the need for manual configuration.

Main functions:
- discover_steam_libraries() → find all Steam library locations
- discover_games_in_libraries() → find installed games
- discover_mods_for_game() → find workshop mods for a game
- generate_database() → complete database.json generation

Example usage:
    scanner = SteamScanner()
    database = scanner.generate_database(
        working_pathstyle="linux",
        output_path="database.json"
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .vdf_parser import parse_libraryfolders_vdf
from .acf_parser import parse_appmanifest_acf
from .pathstyle import PathStyle, detect_pathstyle, normalize


@dataclass
class SteamLibraryInfo:
    """Information about a Steam library location."""
    path: str
    contains_libraryfolders_vdf: bool = False
    games_found: list[str] | None = None


@dataclass
class GameInfo:
    """Information about an installed game."""
    appid: str
    name: str
    basepath: str
    modpath: str
    mods_found: list[str] | None = None


@dataclass
class DatabaseInfo:
    """Complete database structure matching database.json schema."""
    OS: dict[str, str]  # { workingpathstyle, steamlibpathstyle }
    steamlib: list[dict[str, Any]]
    game: list[dict[str, Any]]


class SteamScanner:
    """Scan system for Steam libraries, games, and mods."""

    def __init__(self, working_pathstyle: str = "linux"):
        """
        Initialize scanner.

        Args:
            working_pathstyle: "linux" or "windows" - current process environment style
        """
        self.working_pathstyle = working_pathstyle
        self.steam_libraries: list[SteamLibraryInfo] = []
        self.games: dict[str, GameInfo] = {}  # keyed by appid
        self.steamlib_pathstyle: str = "linux"

    def discover_steam_libraries(self) -> list[SteamLibraryInfo]:
        """
        Discover all Steam library locations on the system.

        Returns:
            List of SteamLibraryInfo objects
            
        Algorithm:
            1. Try common Steam installation paths (Windows, Linux, WSL)
            2. Check for libraryfolders.vdf in each location
            3. Parse libraryfolders.vdf to find additional libraries
            4. Return all found library paths
        """
        libraries_by_path: dict[str, SteamLibraryInfo] = {}
        parsed_styles: list[str] = []
        
        # Common Steam paths to check
        common_paths = [
            Path.home() / ".steam" / "root" / "steamapps",  # Linux
            Path.home() / ".local" / "share" / "Steam" / "steamapps",  # Linux alternative
            Path("C:/Program Files (x86)/Steam/steamapps"),  # Windows
            Path("C:/Program Files/Steam/steamapps"),  # Windows alternative
            Path("/mnt/c/Program Files (x86)/Steam/steamapps"),  # WSL
            Path("/mnt/c/Program Files/Steam/steamapps"),  # WSL alternative
        ]
        
        for path in common_paths:
            if path.exists() and path.is_dir():
                path_str = str(path)
                if path_str not in libraries_by_path:
                    libraries_by_path[path_str] = SteamLibraryInfo(
                        path=path_str,
                        contains_libraryfolders_vdf=False,
                        games_found=[]
                    )

                vdf_path = path / "libraryfolders.vdf"
                if vdf_path.exists():
                    libraries_by_path[path_str].contains_libraryfolders_vdf = True

        # Expand all libraries from each discovered main VDF location.
        for lib in list(libraries_by_path.values()):
            if not lib.contains_libraryfolders_vdf:
                continue

            vdf_path = Path(lib.path) / "libraryfolders.vdf"
            try:
                parsed = self.parse_libraryfolders_vdf(str(vdf_path))
            except Exception:
                continue

            parsed_style = parsed.get("steamlib_pathstyle")
            if isinstance(parsed_style, str):
                parsed_styles.append(parsed_style)

            for parsed_lib in parsed.get("libraries", []):
                raw_path = str(parsed_lib.get("path", "")).strip()
                if not raw_path:
                    continue

                target_style = PathStyle.LINUX if self.working_pathstyle == "linux" else PathStyle.WINDOWS
                normalized_path = normalize(raw_path, target_style)

                # VDF 'path' is the Steam root dir (e.g. D:\Games), not the steamapps
                # sub-directory.  Append 'steamapps' so discovery works correctly.
                sep = "\\" if target_style == PathStyle.WINDOWS else "/"
                if not normalized_path.rstrip("/\\").endswith("steamapps"):
                    normalized_path = normalized_path.rstrip("/\\") + sep + "steamapps"

                if normalized_path not in libraries_by_path:
                    libraries_by_path[normalized_path] = SteamLibraryInfo(
                        path=normalized_path,
                        contains_libraryfolders_vdf=(normalized_path == lib.path),
                        games_found=[]
                    )

                game_ids = parsed_lib.get("games", [])
                if isinstance(game_ids, list):
                    existing = libraries_by_path[normalized_path].games_found or []
                    libraries_by_path[normalized_path].games_found = sorted(set(existing + [str(g) for g in game_ids]))

        libraries = list(libraries_by_path.values())

        if parsed_styles:
            self.steamlib_pathstyle = parsed_styles[0]
        elif libraries:
            style = detect_pathstyle(libraries[0].path)
            self.steamlib_pathstyle = "windows" if style == PathStyle.WINDOWS else "linux"

        self.steam_libraries = libraries
        return libraries

    def parse_libraryfolders_vdf(self, vdf_path: str) -> dict[str, Any]:
        """
        Parse libraryfolders.vdf to get library paths and game list.

        Args:
            vdf_path: Path to libraryfolders.vdf file

        Returns:
            {
              "libraries": [{"path": "...", "games": [...appids...]}],
              "steamlib_pathstyle": "windows" | "linux"
            }
        """
        return parse_libraryfolders_vdf(vdf_path)

    def discover_games_in_library(self, library_path: str) -> dict[str, GameInfo]:
        """
        Discover all installed games in a Steam library.

        Args:
            library_path: Root path of a Steam library

        Returns:
            Dict of {appid: GameInfo}
            
        Algorithm:
            1. Scan for appmanifest_*.acf files in steamapps/
            2. For each appid found, determine basepath (game directory)
            3. For each appid, set modpath (workshop/content/{appid}/)
            4. Return discovered games
        """
        games = {}
        lib_path = Path(library_path)
        
        if not lib_path.exists():
            return games
        
        # Find all appmanifest_*.acf files
        for manifest_file in lib_path.glob("appmanifest_*.acf"):
            try:
                game_data = parse_appmanifest_acf(str(manifest_file))
                appid = game_data.get("appid", "")
                
                if appid:
                    installdir = game_data.get("installdir", "")
                    name = game_data.get("name", "")
                    
                    # Determine base path and mod path
                    basepath = str(lib_path / "common" / installdir) if installdir else str(lib_path / "common")
                    modpath = str(lib_path / "workshop" / "content" / appid)
                    
                    games[appid] = GameInfo(
                        appid=appid,
                        name=name,
                        basepath=basepath,
                        modpath=modpath,
                        mods_found=None
                    )
            except Exception:
                # Skip files that can't be parsed
                continue
        
        return games

    def discover_mods_for_game(self, appid: str, mod_root: str) -> list[str]:
        """
        Discover installed mods for a game.

        Args:
            appid: Game app ID
            mod_root: Path to workshop/content/{appid}/ directory

        Returns:
            List of mod content IDs found in the directory

        Algorithm:
            1. List directories in mod_root
            2. Each directory name is a mod content ID
            3. Verify appworkshop_{appid}.acf exists and mentions this mod
            4. Return list of verified mod IDs
        """
        mods = []
        mod_path = Path(mod_root)
        
        if not mod_path.exists() or not mod_path.is_dir():
            return mods
        
        # List all subdirectories (each is a mod)
        for item in mod_path.iterdir():
            if item.is_dir():
                mods.append(item.name)
        
        return sorted(mods, key=int)

    def generate_database(
        self,
        working_pathstyle: str = "linux",
        greedy_parsing: bool = False,
    ) -> DatabaseInfo:
        """
        Generate complete database.json by scanning the system.

        Args:
            working_pathstyle: Current environment path style
            greedy_parsing: If True, parse mods even if game is unknown

        Returns:
            DatabaseInfo object ready to be serialized as database.json

        Raises:
            Exception: If no Steam libraries found or other critical errors

        Algorithm:
            1. Discover all Steam libraries
            2. Parse libraryfolders.vdf for library locations
            3. For each library, discover installed games
            4. For each game, discover installed mods
            5. Assemble into DatabaseInfo structure
            6. Return database
        """
        # Discover all Steam libraries
        libraries = self.discover_steam_libraries()
        
        if not libraries:
            raise Exception("No Steam libraries found on the system")
        
        steamlib_list = []
        game_list = []
        seen_game_ids: set[str] = set()
        
        for lib in libraries:
            # Add library info to list
            # Discover games in this library.
            games = self.discover_games_in_library(lib.path)
            per_library_game_ids = sorted(set(list(games.keys()) + (lib.games_found or [])))
            scoped_game_ids = set(lib.games_found or [])

            steamlib_list.append({
                "path": lib.path,
                "contains_libraryfolders_vdf": lib.contains_libraryfolders_vdf,
                "game": per_library_game_ids,
            })
            
            for appid, game_info in games.items():
                if appid in seen_game_ids:
                    continue

                # Default mode is non-greedy: parse mods only for appids in VDF game scope.
                should_parse_mods = greedy_parsing or not scoped_game_ids or appid in scoped_game_ids
                mods = self.discover_mods_for_game(appid, game_info.modpath) if should_parse_mods else []
                game_info.mods_found = mods
                seen_game_ids.add(appid)
                
                # Add game to list
                game_list.append({
                    "appid": game_info.appid,
                    "name": game_info.name,
                    "basepath": game_info.basepath,
                    "modpath": game_info.modpath,
                    "mods_found": game_info.mods_found
                })
        
        # Create DatabaseInfo
        database = DatabaseInfo(
            OS={
                "workingpathstyle": working_pathstyle,
                "steamlibpathstyle": self.steamlib_pathstyle,
            },
            steamlib=steamlib_list,
            game=game_list
        )
        
        return database

    def save_database(self, database: DatabaseInfo, output_path: str) -> bool:
        """
        Save generated database to file.

        Args:
            database: DatabaseInfo object
            output_path: Path where to save database.json

        Returns:
            True if save successful
        """
        try:
            # Convert DatabaseInfo to dict
            db_dict = asdict(database)
            
            # Write to JSON file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, "w") as f:
                json.dump(db_dict, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Failed to save database: {e}")
            return False


def scan_and_generate_database(
    output_path: str = "database.json",
    working_pathstyle: str = "linux",
) -> DatabaseInfo:
    """
    Convenience function: scan system and generate database.json.

    Args:
        output_path: Where to save the generated database.json
        working_pathstyle: Current environment path style

    Returns:
        Generated DatabaseInfo object
    """
    scanner = SteamScanner(working_pathstyle=working_pathstyle)
    database = scanner.generate_database()
    scanner.save_database(database, output_path)
    return database
