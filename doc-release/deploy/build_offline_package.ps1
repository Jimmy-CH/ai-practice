# DocRelease 离线包构建脚本（开发机 Windows 执行）
# 用法：cd doc-release; .\deploy\build_offline_package.ps1 [-WheelSource platform|wsl]
# 产物：out/docrelease-offline-<日期>.zip
param(
    [ValidateSet("platform", "wsl")][string]$WheelSource = "platform",
    [string]$PythonCmd = "python"   # 仅 platform 模式用：任意本机 Python 的 pip 执行跨平台 download
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot   # doc-release/
$stamp = Get-Date -Format "yyyyMMdd"
$outDir = Join-Path $root "out\docrelease-offline-$stamp"
if (Test-Path $outDir) { $outDir = "$outDir-$(Get-Date -Format 'HHmmss')" }
Write-Host "[build] 输出目录：$outDir"

# 1. 前端构建（含 vue-tsc --noEmit 类型检查）
Push-Location (Join-Path $root "frontend")
try { npm run build } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }

# 2. 目录骨架
foreach ($d in @("backend", "deploy", "wheels")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $outDir $d) | Out-Null
}

# 3. 后端源码（排除运行时产物；robocopy 退出码 >=8 才是失败）
$excludeDirs = @("venv", "__pycache__", ".pytest_cache", ".idea", "archive", "sample_repo")
robocopy (Join-Path $root "backend") (Join-Path $outDir "backend") `
    /E /XD $excludeDirs /XF ".env" "docrelease.db" /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 复制后端源码失败：$LASTEXITCODE" }

# 4. 前端产物 → static/；deploy 脚手架
Copy-Item (Join-Path $root "frontend\dist") (Join-Path $outDir "static") -Recurse
Copy-Item (Join-Path $root "deploy\*") (Join-Path $outDir "deploy\") -Recurse

# 5. 下载 Linux 平台 wheel（Python 3.11 / manylinux）
$req = Join-Path $root "backend\requirements.txt"
if ($WheelSource -eq "wsl") {
    $reqWsl = (wsl wslpath -a ($req -replace '\\', '/')).Trim()
    $whlWsl = (wsl wslpath -a (($outDir + "\wheels") -replace '\\', '/')).Trim()
    wsl bash -c "python3.11 -m pip download -r '$reqWsl' -d '$whlWsl'"
    if ($LASTEXITCODE -ne 0) { throw "WSL wheel 下载失败" }
} else {
    & $PythonCmd -m pip download -r $req -d (Join-Path $outDir "wheels") `
        --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 `
        --python-version 3.11 --implementation cp --only-binary=:all:
    if ($LASTEXITCODE -ne 0) { throw "wheel 下载失败；个别包缺 manylinux wheel 时改用 -WheelSource wsl" }
}

# 6. wheel 平台校验
$bad = Get-ChildItem (Join-Path $outDir "wheels") -Filter "*win_amd64*"
if ($bad) { throw ("wheels 中混入 Windows 平台包：" + ($bad.Name -join ", ")) }
foreach ($must in @("tree_sitter-", "tree_sitter_language_pack-", "pydantic_core-")) {
    if (-not (Get-ChildItem (Join-Path $outDir "wheels") -Filter "$must*")) {
        throw "缺少关键二进制 wheel：$must（改用 -WheelSource wsl 重试）"
    }
}

# 7. MANIFEST.md
$commit = (git -C $root rev-parse HEAD).Trim()
$dirty = (git -C $root status --porcelain) -join "; "
if ($dirty) { Write-Warning "工作区有未提交改动，MANIFEST 记录的 commit 可能与包内容不一致" }
@(
    "# DocRelease 离线包",
    "- 构建时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "- 源码 commit：$commit",
    "- wheel 来源：$WheelSource（目标 Python 3.11 / manylinux）",
    "- 包结构：backend/（后端源码）static/（前端产物）wheels/（离线依赖）deploy/（安装脚手架）",
    "- 部署：解压后在包内 deploy/ 执行 sudo bash install.sh（详见 deploy/README.md）"
) | Set-Content (Join-Path $outDir "MANIFEST.md") -Encoding utf8

# 8. 压缩
$zip = "$outDir.zip"
Compress-Archive -Path $outDir -DestinationPath $zip -Force
Write-Host "[build] 完成：$zip"
Write-Host "[build] wheel 数量：$((Get-ChildItem (Join-Path $outDir 'wheels')).Count)"
