@echo off
rem OEM 850, CR LF
< NUL call make.bat
call matrix_controller\py\venv\Scripts\activate.bat
echo on
pip install -U pyinstaller
pyinstaller --onefile matrix_controller\py\matrix_display.py
@pause