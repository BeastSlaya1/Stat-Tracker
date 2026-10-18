@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 exit /b 1
pushd "%~dp0"
cl /nologo /std:c++20 /EHsc /O2 /MT wifi-point.cpp /Fe:"..\assets\wifi-point.exe" /link windowsapp.lib
set result=%errorlevel%
if exist wifi-point.obj del wifi-point.obj
popd
exit /b %result%
