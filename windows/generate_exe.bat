@echo off
rem OEM 850, CR LF

rem Matrix Display Controller: connects the Matrix Reloaded LED panel display to Twitch chat
rem Copyright ¸ 2023  toine512 <os@toine512.fr>
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
pyinstaller %upx_arg% --onefile --icon ..\ioodymDeni.ico --distpath exe\dist --specpath exe --workpath exe\build matrix_controller\py\matrix_display.py

@pause