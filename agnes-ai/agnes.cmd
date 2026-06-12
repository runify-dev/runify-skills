@echo off
setlocal enabledelayedexpansion
rem agnes.cmd — Windows 统一入口，与 bash 版 agnes 等价。
rem 用法:  agnes <command> [args...]
rem   agnes text_to_image --prompt "一只猫"
rem   agnes                 列出所有命令

rem 1) 定位脚本目录
set "SELF=%~dp0"
set "SCRIPTS_DIR=%SELF%scripts"
if not exist "%SCRIPTS_DIR%" (
  if exist "%SELF%_common.py" set "SCRIPTS_DIR=%SELF%"
)

rem 2) 选一个可用且 >=3.6 的 Python（依次尝试 python / py -3 / python3）
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
  echo RESULT_JSON: {"status":"error","stage":"agnes","error":"未找到 Python^>=3.6（试过 python/python3/py -3）"}
  exit /b 0
)

rem 3) 无参数 → 列命令
if "%~1"=="" goto :list
if /i "%~1"=="-h" goto :list
if /i "%~1"=="--help" goto :list
if /i "%~1"=="help" goto :list
if /i "%~1"=="list" goto :list

set "CMD=%~1"
set "TARGET=%SCRIPTS_DIR%\%CMD%.py"
if not exist "%TARGET%" (
  echo RESULT_JSON: {"status":"error","stage":"agnes","error":"未知命令: %CMD%"}
  goto :list_err
)

rem 4) 剥掉首个子命令，把剩余参数原样透传（保留引号，支持带空格的 --prompt "..."）
set "REST=%*"
call set "REST=%%REST:*%1=%%"
%PY% "%TARGET%"%REST%
set "RC=%errorlevel%"
if not "%RC%"=="0" echo RESULT_JSON: {"status":"error","stage":"%CMD%","error":"命令异常退出（exit %RC%），详见 stderr"}
exit /b 0

:list
call :print_list
exit /b 0

:list_err
call :print_list 1>&2
exit /b 0

:print_list
echo agnes — 可用命令（用法: agnes ^<command^> [args...]）
echo.
for %%f in ("%SCRIPTS_DIR%\*.py") do (
  set "base=%%~nf"
  set "first=!base:~0,1!"
  if not "!first!"=="_" echo   agnes %%~nf
)
echo.
echo 查看某命令的参数：agnes ^<command^> --help
exit /b 0
