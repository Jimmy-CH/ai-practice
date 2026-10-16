# DocRelease 部署包构建脚本（开发机 Windows 执行）
# 用法：cd doc-release; .\deploy\build_package.ps1
# 产物：out/docrelease-package-<日期>.zip（依赖由部署机在线安装，不含 wheels）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot   # doc-release/
$stamp = Get-Date -Format "yyyyMMdd"
$outDir = Join-Path $root "out\docrelease-package-$stamp"
if (Test-Path $outDir) { $outDir = "$outDir-$(Get-Date -Format 'HHmmss')" }
Write-Host "[build] 输出目录：$outDir"

# 1. 前端构建（含 vue-tsc --noEmit 类型检查；PS 5.1 下 npm 的 stderr 在重定向下
#    会包装成 ErrorRecord 误杀构建，经 cmd 合并流后以 $LASTEXITCODE 判定成败）
Push-Location (Join-Path $root "frontend")
try { cmd /c "npm run build 2>&1" } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }

# 2. 目录骨架
foreach ($d in @("backend", "deploy")) {
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

# 5. MANIFEST.md
$commit = (git -C $root rev-parse HEAD).Trim()
$dirty = (git -C $root status --porcelain) -join "; "
if ($dirty) { Write-Warning "工作区有未提交改动，MANIFEST 记录的 commit 可能与包内容不一致" }
@(
    "# DocRelease 部署包",
    "- 构建时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "- 源码 commit：$commit",
    "- 包结构：backend/（后端源码）static/（前端产物）deploy/（安装脚手架）",
    "- 部署：解压后在包内 deploy/ 执行 sudo bash install.sh（系统级）或 bash install.sh（用户级，无需 root），详见 deploy/README.md"
) | Set-Content (Join-Path $outDir "MANIFEST.md") -Encoding utf8

# 6. 压缩
$zip = "$outDir.zip"
Compress-Archive -Path $outDir -DestinationPath $zip -Force
Write-Host "[build] 完成：$zip"
