@echo off
setlocal enabledelayedexpansion
rem desk.cmd — runctl 薄封装入口（Windows），与 bash 版 desk 等价。
rem 保留 runctl 的退出码（0/1/2/124 有语义），不强制 0。
rem   desk setup                 安装/检查 runctl
rem   desk <runctl 子命令> ...   等价于 README 的 runctl <子命令>

set "SELF=%~dp0"

set "PY="
for %%P in (python python3) do (
  if not defined PY (
    %%P -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,6) else 1)" >nul 2>&1
    if !errorlevel! equ 0 set "PY=%%P"
  )
)
if not defined PY (
  py -3 -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,6) else 1)" >nul 2>&1
  if !errorlevel! equ 0 set "PY=py -3"
)
if not defined PY (
  echo RESULT_JSON: {"status":"error","stage":"desk","error":"未找到 Python^>=3.6（试过 python/python3/py -3）"}
  exit /b 1
)

%PY% "%SELF%desk.py" %*
exit /b %errorlevel%
