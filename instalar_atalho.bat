@echo off
rem Cria o atalho "OdontoDesk (Python)" na Area de Trabalho e no Menu Iniciar.
cd /d "%~dp0"
set PYW=
for /f "delims=" %%i in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW (
  for /f "delims=" %%i in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW=%%i"
)
if not exist "%PYW%" (
  echo Nao encontrei o Python. Instale em python.org marcando "Add python.exe to PATH".
  pause
  exit /b 1
)
python -m pip install -q -r requirements.txt
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$w = New-Object -ComObject WScript.Shell;" ^
  "foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {" ^
  "  $l = $w.CreateShortcut((Join-Path $d 'OdontoDesk (Python).lnk'));" ^
  "  $l.TargetPath = '%PYW%'; $l.Arguments = '\"%~dp0desktop.py\"'; $l.WorkingDirectory = '%~dp0';" ^
  "  $l.IconLocation = '%~dp0odontodesk\static\icone.ico'; $l.Description = 'OdontoDesk em Python'; $l.Save() }"
echo.
echo Pronto! Use o icone "OdontoDesk (Python)" na Area de Trabalho ou no Menu Iniciar.
pause
