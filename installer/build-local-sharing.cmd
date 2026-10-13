@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 (
  echo Run this from the Visual Studio x64 Native Tools command prompt.
  exit /b 1
)
pushd "%~dp0"
cl /nologo /O2 /EHsc /MT /W4 local-sharing.cpp /Fe:"..\assets\local-sharing.exe" /link fwpuclnt.lib rpcrt4.lib iphlpapi.lib ws2_32.lib
set result=%errorlevel%
if exist local-sharing.obj del local-sharing.obj
popd
exit /b %result%
