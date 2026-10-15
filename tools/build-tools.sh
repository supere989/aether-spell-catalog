#!/bin/sh
# Build StormLib (pinned) and the read-only MPQ extractor used by webui/asset_io.py. Ubuntu: build-essential cmake zlib1g-dev libbz2-dev.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd); WORK=${WORK:-$HERE/../.build}; TAG=v9.30
mkdir -p "$WORK" && cd "$WORK"
[ -d StormLib ] || git clone --depth 1 --branch "$TAG" https://github.com/ladislav-zezula/StormLib.git
cmake -S StormLib -B StormLib/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF >/dev/null
cmake --build StormLib/build -j"$(nproc)" >/dev/null
c++ -O2 -std=c++17 -I StormLib/src "$HERE/../webui/tools/extract.cpp" StormLib/build/libstorm.a -lz -lbz2 -o "$HERE/../webui/tools/mpqextract"
echo "built $(realpath "$HERE/../webui/tools/mpqextract")"
