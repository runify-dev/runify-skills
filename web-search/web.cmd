@echo off
setlocal enabledelayedexpansion
rem web.cmd — Windows 统一入口，与 bash 版 web 等价。
rem 用法:  web <command> [args...]
rem   web search --query "claude code"
rem   web                 列出所有命令

set "SELF=%~dp0"
set "SCRIPTS_DIR=%SELF%scripts"
if not exist "%SCRIPTS_DIR%" (
  if exist "%SELF%_common.py" set "SCRIPTS_DIR=%SELF%"
)

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
  echo RESULT_JSON: {"status":"error","stage":"web","error":"未找到 Python^>=3.6（试过 python/python3/py -3）"}
  exit /b 0
)

if "%~1"=="" goto :list
if /i "%~1"=="-h" goto :list
if /i "%~1"=="--help" goto :list
if /i "%~1"=="help" goto :list
if /i "%~1"=="list" goto :list

set "CMD=%~1"
set "TARGET=%SCRIPTS_DIR%\%CMD%.py"
if not exist "%TARGET%" (
  echo RESULT_JSON: {"status":"error","stage":"web","error":"未知命令: %CMD%"}
  goto :list_err
)

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
echo web — 可用命令（用法: web ^<command^> [args...]）
echo.
for %%f in ("%SCRIPTS_DIR%\*.py") do (
  set "base=%%~nf"
  set "first=!base:~0,1!"
  if not "!first!"=="_" echo   web %%~nf
)
echo.
echo 查看某命令的参数：web ^<command^> --help
exit /b 0
