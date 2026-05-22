#!/usr/bin/env python3
"""Diagnosis script: identify root cause of excessive branch conflicts in the mapping engine.

Usage:
    cd /home/knighthana/workspace/modmanager  # 项目根目录
    PYTHONPATH=src python diagnose_conflicts.py
"""

import json
import sys
import os
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from modmgr.rule_aggregator import aggregate
from modmgr.engine import compute_mapping

KMM_RULE_PATH = str(Path(__file__).parent.parent / "description" / "kmm_rule_RWR-khn_CT-castears-z2414_Replace.json.example")
STEAM_WORKSHOP = "/mnt/d/Games/steamapps/workshop/content/270150"
GAME_BASEPATH = "/mnt/d/Games/steamapps/common/RunningWithRifles"

ALL_MOD_IDS = [
    "2606099273", "3425312546", "3426079135", "3427135267",
    "3428584891", "3430161019", "3430976333", "3435124100",
    "3437114999", "3442063538", "3442533598", "3445750210",
    "3470055515",
]

ACTION_ORDERS = {
    "270150:2606099273": 1000,
    "270150:3425312546": 990,
    "270150:3426079135": 980,
    "270150:3427135267": 970,
    "270150:3428584891": 960,
    "270150:3430161019": 950,
    "270150:3430976333": 930,
    "270150:3435124100": 920,
    "270150:3437114999": 910,
    "270150:3442063538": 900,
    "270150:3442533598": 890,
    "270150:3445750210": 880,
    "270150:3470055515": 870,
    "270150:一点不战术地图v1.9 TEMP": 860,
    "270150:warn_vehicles": 850,
    "270150:knighthana_custom_rules": 800,
}

def _maybe_create_temp_mod_dirs(database):
    """Create temp directories for non-numeric mods referenced in the rule
    that don't exist on disk, so the engine can glob their source files.
    Returns list of created paths for cleanup."""
    created = []
    workshop = database["game"][0]["modpath"]

    non_numeric_mods = [
        ("270150:一点不战术地图v1.9 TEMP", "一点不战术地图v1.9 TEMP"),
        ("270150:warn_vehicles", "warn_vehicles"),
    ]

    for mixed_id, dirname in non_numeric_mods:
        dirpath = os.path.join(workshop, dirname)
        if not os.path.isdir(dirpath):
            os.makedirs(dirpath, exist_ok=True)
            created.append(dirpath)

    tempmap_dir = os.path.join(workshop, "一点不战术地图v1.9 TEMP", "maps")
    for sub in ["map10", "map103", "map105_3", "map106"]:
        d = os.path.join(tempmap_dir, sub)
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            created.append(d)
        placeholder = os.path.join(d, ".placeholder")
        if not os.path.exists(placeholder):
            Path(placeholder).touch()
            created.append(placeholder)

    warn_base = os.path.join(workshop, "warn_vehicles", "ct1.9载具圈")
    for sub in ["materials", "particles", "vehicles"]:
        d = os.path.join(warn_base, sub)
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            created.append(d)
        placeholder = os.path.join(d, ".placeholder")
        if not os.path.exists(placeholder):
            Path(placeholder).touch()
            created.append(placeholder)

    return created

def _cleanup(paths):
    for p in paths:
        p = Path(p)
        if p.is_file():
            p.unlink(missing_ok=True)
        elif p.is_dir():
            p.rmdir()


def _mixed_id_nickname_map(aggregated):
    return {
        op["mixed_id"]: op.get("nickname", op["mixed_id"])
        for op in aggregated.get("operation", [])
        if isinstance(op, dict) and "mixed_id" in op
    }

def main():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        user_config_path = f.name

    try:
        aggregated, agg_errors, agg_warnings = aggregate(
            kmm_rule_paths=[KMM_RULE_PATH],
            user_config_path=user_config_path,
            action_orders=ACTION_ORDERS,
        )

        print("=" * 80)
        print("AGGREGATION RESULTS")
        print("=" * 80)
        if agg_errors:
            print(f"ERRORS ({len(agg_errors)}):")
            for e in agg_errors:
                print(f"  {e}")
        if agg_warnings:
            print(f"WARNINGS ({len(agg_warnings)}):")
            for w in agg_warnings:
                print(f"  {w}")

        if aggregated is None:
            print("\nFATAL: Aggregation failed.")
            sys.exit(1)

        n_ops = len(aggregated.get("operation", []))
        print(f"\nAggregation SUCCESS: {n_ops} operations")

        database = {
            "schema_namespace": "KMM_LocalDatabase",
            "schema_version": "knighthana@0.1.0",
            "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "windows"},
            "steamlib": [{"path": "/mnt/d/Games/steamapps/", "game": ["270150"]}],
            "game": [
                {
                    "appid": "270150",
                    "name": "Running With Rifles",
                    "localdate": 0,
                    "basepath": GAME_BASEPATH,
                    "modpath": STEAM_WORKSHOP,
                    "mods_found": ALL_MOD_IDS,
                }
            ],
            "mod": [
                {
                    "mixed_id": "270150:2606099273",
                    "localdate": 0,
                    "path": f"{STEAM_WORKSHOP}/2606099273/",
                }
            ],
        }

        created = _maybe_create_temp_mod_dirs(database)

        result = compute_mapping(aggregated, database)

        print("\n" + "=" * 80)
        print("MAPPING ENGINE RESULTS")
        print("=" * 80)

        if result["errors"]:
            print(f"ERRORS ({len(result['errors'])}):")
            for e in result["errors"][:20]:
                print(f"  {e}")
            if len(result["errors"]) > 20:
                print(f"  ... and {len(result['errors']) - 20} more")
        if result["errors"]:
            print("\nNOTE: Errors exist; final_mapping is empty. Trees data still analyzed below.\n")

        warnings_list = result.get("warnings", [])
        forest = result.get("trees", [])

        warn_summary = defaultdict(int)
        for w in warnings_list:
            prefix = w.split(":", 1)[0] if ":" in w else "OTHER"
            warn_summary[prefix] += 1

        print(f"\nWARNING SUMMARY ({len(warnings_list)} total):")
        for k, v in sorted(warn_summary.items()):
            print(f"  {k}: {v}")

        branching_nodes = [
            f for f in forest
            if f.get("warning") == "W_FOREST_BRANCHING"
            or (len(f.get("changerequest", [])) > 1)
        ]
        nicknames = _mixed_id_nickname_map(aggregated)

        print(f"\nTotal W_FOREST_BRANCHING nodes: {len(branching_nodes)}")

        if not branching_nodes:
            print("No branching conflicts found!")
            return

        dir_conflicts = defaultdict(list)
        for node in branching_nodes:
            target = node["root_path"]
            parent_dir = str(Path(target).parent) + "/"
            dir_conflicts[parent_dir].append(node)

        print(f"\nConflicts by target directory ({len(dir_conflicts)} dirs):")
        print("-" * 80)

        for dir_path in sorted(dir_conflicts.keys()):
            nodes = dir_conflicts[dir_path]
            print(f"\n>>> {dir_path}")
            print(f"    {len(nodes)} conflict(s)")

            pair_counts = defaultdict(int)
            for node in nodes:
                mids = sorted(set(r["mixed_id"] for r in node["changerequest"]))
                for i in range(len(mids)):
                    for j in range(i + 1, len(mids)):
                        pair = tuple(sorted([mids[i], mids[j]]))
                        pair_counts[pair] += 1

            if len(nodes) <= 15:
                for node in nodes:
                    fname = Path(node["root_path"]).name
                    mids = [r["mixed_id"] for r in node["changerequest"]]
                    named = [f"{m} ({nicknames.get(m, '?')})" for m in mids]
                    print(f"    {fname}: {named}")
            else:
                print(f"    (too many files to list individually)")

            if pair_counts:
                print(f"    Mod-pair conflicts:")
                for pair, count in sorted(pair_counts.items(), key=lambda x: -x[1]):
                    a_name = nicknames.get(pair[0], pair[0])
                    b_name = nicknames.get(pair[1], pair[1])
                    print(f"      {a_name} <-> {b_name}: {count} files")

        print("\n" + "=" * 80)
        print("GLOBAL TOP CONFLICT PAIRS")
        print("=" * 80)

        global_pairs = defaultdict(int)
        for node in branching_nodes:
            mids = sorted(set(r["mixed_id"] for r in node["changerequest"]))
            for i in range(len(mids)):
                for j in range(i + 1, len(mids)):
                    pair = tuple(sorted([mids[i], mids[j]]))
                    global_pairs[pair] += 1

        for pair, count in sorted(global_pairs.items(), key=lambda x: -x[1])[:20]:
            a_name = nicknames.get(pair[0], pair[0])
            b_name = nicknames.get(pair[1], pair[1])
            print(f"  {a_name} <-> {b_name}: {count} conflicts")

        unresolved = [w for w in warnings_list if w.startswith("W_FOREST_BRANCHING_UNRESOLVED")]
        if unresolved:
            print(f"\nUNRESOLVED BRANCHING ({len(unresolved)}):")
            for w in unresolved:
                print(f"  {w}")

        no_match = [w for w in warnings_list if w.startswith("W_NO_SOURCE_MATCH")]
        if no_match:
            print(f"\nNO SOURCE MATCH ({len(no_match)}):")
            for w in no_match[:30]:
                print(f"  {w}")
            if len(no_match) > 30:
                print(f"  ... and {len(no_match) - 30} more")

        local_missing = [w for w in warnings_list if w.startswith("W_LOCAL_MOD_MISSING")]
        if local_missing:
            print(f"\nLOCAL MOD MISSING ({len(local_missing)}):")
            for w in local_missing:
                print(f"  {w}")

        if result.get("final_mapping"):
            print(f"\nFinal mapping: {len(result['final_mapping'])} entries")

        # ── ROOT CAUSE ANALYSIS ────────────────────────────────────────────────
        print("\n" + "=" * 80)
        print("ROOT CAUSE ANALYSIS")
        print("=" * 80)

        self_conflict_mods = defaultdict(lambda: {"count": 0, "dirs": set(), "target": ""})
        for node in branching_nodes:
            mids = [r["mixed_id"] for r in node["changerequest"]]
            unique_mids = set(mids)
            if len(unique_mids) == 1:
                mid = mids[0]
                info = self_conflict_mods[mid]
                info["count"] += 1
                info["dirs"].add(str(Path(node["root_path"]).parent) + "/")
                info["target"] = node["root_path"]

        inter_mod_conflicts = [n for n in branching_nodes
                               if len(set(r["mixed_id"] for r in n["changerequest"])) > 1]

        print(f"\nSelf-conflicts (same mod writing to same target via multiple actions): {sum(v['count'] for v in self_conflict_mods.values())}")
        print(f"Cross-mod conflicts (different mods competing for same target): {len(inter_mod_conflicts)}")

        if self_conflict_mods:
            print(f"\nSelf-conflict breakdown by mod:")
            for mid in sorted(self_conflict_mods.keys(), key=lambda k: -self_conflict_mods[k]["count"]):
                info = self_conflict_mods[mid]
                name = nicknames.get(mid, mid)
                print(f"\n  Mod: {name} ({mid})")
                print(f"  Self-conflicting files: {info['count']}")
                print(f"  Affected directories ({len(info['dirs'])}):")
                for d in sorted(info["dirs"]):
                    print(f"    {d}")

                # Check how many unique sources per action entry
                action_entries = aggregated.get("operation", [])
                for op in action_entries:
                    if op.get("mixed_id") == mid:
                        alist = op.get("actionlist", [])
                        print(f"  Action entries in aggregated rule set: {len(alist)}")
                        for i, a in enumerate(alist):
                            src = a.get("from", [])
                            into = a.get("into", [])
                            print(f"    [{i}] from={src} into={into}")
                        break

            print(f"\nROOT CAUSE: All {len(branching_nodes)} branch conflicts are self-conflicts.")
            print("  Multiple action entries in a single mod's actionlist produce duplicate")
            print("  change requests for the same target file. Since action_order is per-mod")
            print("  (not per-action), all entries share the same priority and cannot be resolved.")
            print("  The aggregator's actionlist inherits 'def_destin' across all entries,")
            print("  but does not deduplicate identical target paths from different 'from' globs.")
            print("  THE KMM_RULE AUTHOR SHOULD ensure that action entries within a single mod")
            print("  do not produce overlapping outputs at the same destination paths.")

        if inter_mod_conflicts:
            print(f"\nCross-mod conflicts ({len(inter_mod_conflicts)}):")
            cross_pairs = defaultdict(int)
            for node in inter_mod_conflicts:
                mids = sorted(set(r["mixed_id"] for r in node["changerequest"]))
                for i in range(len(mids)):
                    for j in range(i + 1, len(mids)):
                        cross_pairs[tuple(sorted([mids[i], mids[j]]))] += 1
            for pair, count in sorted(cross_pairs.items(), key=lambda x: -x[1]):
                a_name = nicknames.get(pair[0], pair[0])
                b_name = nicknames.get(pair[1], pair[1])
                print(f"  {a_name} <-> {b_name}: {count} conflicts")

    finally:
        Path(user_config_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
