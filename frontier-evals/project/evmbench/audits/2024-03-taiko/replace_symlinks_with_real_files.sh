#!/bin/bash
# Recursively replace all symlinks in node_modules with real files/directories

set -euo pipefail

find node_modules -type l | while read -r symlink; do
    target=$(readlink "$symlink")
    # If the target is relative, resolve it relative to the symlink's directory
    if [[ "$target" != /* ]]; then
        target="$(cd "$(dirname "$symlink")" && cd "$(dirname "$target")" && pwd)/$(basename "$target")"
    fi
    if [ -e "$target" ]; then
        echo "Replacing symlink: $symlink -> $target"
        rm "$symlink"
        if [ -d "$target" ]; then
            cp -a "$target" "$symlink"
        else
            cp -a "$target" "$symlink"
        fi
    else
        echo "Warning: target $target does not exist for symlink $symlink" >&2
    fi
done

echo "All symlinks in node_modules have been replaced with real files/directories." 