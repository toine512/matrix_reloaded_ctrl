@rem OEM 850, CR LF
@setlocal enableExtensions
mkdir matrix_controller\py
copy /y /b run.txt matrix_controller\run.bat
copy /y /b ..\matrix_display.py matrix_controller\py
python -m venv matrix_controller\py\venv
call matrix_controller\py\venv\Scripts\activate.bat
pip install -r ..\requirements.txt
@pause