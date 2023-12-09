@echo off
rem OEM 850, CR LF
rem setlocal EnableDelayedExpansion
rem Handle UPX
if [%1]==[] (
	set "upx_arg=--noupx"
) else (
	set "upx_arg=--upx-dir %1"
)
rem Run
< NUL call make.bat
call matrix_controller\py\venv\Scripts\activate.bat
echo on
pip install -U pyinstaller
pyinstaller %upx_arg% --onefile --icon ioodymDeni.ico matrix_controller\py\matrix_display.py
@pause