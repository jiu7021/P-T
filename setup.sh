#!/usr/bin/env bash
# 재현용 환경 구축. macOS Intel(x86_64) 기준.
#
#   bash setup.sh
#
# 왜 venv를 강제하는가:
#   torch 2.2.2(macOS x86_64 마지막 지원 버전)는 NumPy 1.x ABI로 빌드되어
#   시스템에 설치된 NumPy 2.x / pandas 3.x와 공존할 수 없다.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# --- LightGBM OpenMP 패치 (macOS 전용) --------------------------------------
# PyPI의 lib_lightgbm.dylib는 @rpath/libomp.dylib(LLVM OpenMP)를 요구하는데,
# 이는 Homebrew libomp를 전제한다. Homebrew가 없는 환경에서는 dlopen이 실패한다.
# torch 휠에 동봉된 libiomp5.dylib(Intel OpenMP)가 ABI 호환이므로 그것을 쓴다.
# torch와 lightgbm이 서로 다른 OpenMP 런타임을 각각 로드하는 상황을 피할 수 있어
# Homebrew libomp를 별도로 까는 것보다 오히려 안전하다.
LGB_LIB=.venv/lib/python3.12/site-packages/lightgbm/lib/lib_lightgbm.dylib
TORCH_LIB=.venv/lib/python3.12/site-packages/torch/lib
if [ "$(uname)" = "Darwin" ] && [ -f "$LGB_LIB" ]; then
  if ! .venv/bin/python -c "import lightgbm" >/dev/null 2>&1; then
    echo "LightGBM OpenMP 패치 적용"
    ln -sf libiomp5.dylib "$TORCH_LIB/libomp.dylib"
    install_name_tool -add_rpath "@loader_path/../../torch/lib" "$LGB_LIB" 2>/dev/null || true
  fi
fi
# ---------------------------------------------------------------------------

.venv/bin/python - <<'PY'
import numpy, pandas, scipy, pyarrow, sklearn, matplotlib, torch, torchvision, lightgbm
for m in (numpy, pandas, scipy, pyarrow, sklearn, matplotlib, torch, torchvision, lightgbm):
    print(f"{m.__name__:14s}{m.__version__}")
print(f"torch threads : {torch.get_num_threads()}  (CPU 전용)")
PY

echo
echo "완료. 데이터 내려받기: .venv/bin/python src/data/download.py"
