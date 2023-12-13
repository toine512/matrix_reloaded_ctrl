@echo off
rem OEM 850, CR LF

rem Matrix Display Controller: connects the Matrix Reloaded LED panel display to Twitch chat
rem Copyright � 2023  toine512 <os@toine512.fr>
rem 
rem This program is free software: you can redistribute it and/or modify
rem it under the terms of the GNU Affero General Public License as published by
rem the Free Software Foundation, either version 3 of the License, or
rem (at your option) any later version.
rem 
rem This program is distributed in the hope that it will be useful,
rem but WITHOUT ANY WARRANTY; without even the implied warranty of
rem MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
rem GNU Affero General Public License for more details.
rem 
rem You should have received a copy of the GNU Affero General Public License
rem along with this program.  If not, see <https://www.gnu.org/licenses/>.

setlocal enableExtensions
echo on

mkdir matrix_controller\py
copy /y /b run.txt matrix_controller\run.bat
copy /y /b ..\matrix_display.py matrix_controller\py
python -m venv matrix_controller\py\venv
call matrix_controller\py\venv\Scripts\activate.bat
pip install -r ..\requirements.txt

@pause