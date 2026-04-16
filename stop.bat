@echo off
chcp 65001 >nul
echo Stopping AI Test Case Generator services...
taskkill //F //IM python.exe >nul 2>&1
taskkill //F //IM streamlit.exe >nul 2>&1
echo Done.
